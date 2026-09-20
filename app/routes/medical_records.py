from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DB, CurrentUser, DoctorCtx, SettingsDep
from app.core.errors import ForbiddenError
from app.database.collections import C
from app.models.enums import UserRole
from app.routes.docs import errs
from app.schemas.clinical import DocumentCreate, MedicalRecordCreate, MedicalRecordOut, MedicalRecordUpdate
from app.schemas.common import Page, make_page
from app.services.medical_record_service import MedicalRecordService
from app.utils.object_id import ObjectIdPath, ObjectIdStr
from app.utils.pagination import PageParams, page_params
from app.utils.serialization import to_api

router = APIRouter(prefix="/medical-records", tags=["Medical Records"])


async def _profile(user: dict, db: Any) -> tuple[str, Any]:
    """Patients and doctors only — admins have NO access to medical records."""
    if user["role"] == UserRole.PATIENT:
        p = await db[C.PATIENTS].find_one({"user_id": user["_id"]})
    elif user["role"] == UserRole.DOCTOR:
        p = await db[C.DOCTORS].find_one({"user_id": user["_id"]})
    else:
        raise ForbiddenError("Administrators cannot access medical records", code="forbidden_role")
    if p is None:
        raise ForbiddenError("Profile not found", code="profile_missing")
    return user["role"], p["_id"]


def _out(doc: dict) -> dict:
    data = to_api(doc)
    data["documents"] = [{**d, "id": d["id"]} for d in data.get("documents", [])]
    return data


@router.post("", response_model=MedicalRecordOut, status_code=201, summary="Add consultation notes",
             description="The treating doctor records their own notes for a confirmed/completed appointment (one record per appointment). SmartCare never generates clinical content. **Auth:** DOCTOR.",
             responses=errs(401, 403, 404, 409, 422))
async def create_record(payload: MedicalRecordCreate, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    return _out(await MedicalRecordService(db, settings).create(ctx.doctor["_id"], payload))


@router.get("", response_model=Page[MedicalRecordOut], summary="List my medical records",
            description="Patients: their own records. Doctors: records they authored (optionally filtered by patient). Admins: 403. **Auth:** PATIENT or DOCTOR.",
            responses=errs(401, 403, 422))
async def list_records(user: CurrentUser, db: DB, settings: SettingsDep, params: Annotated[PageParams, Depends(page_params)],
                       patient_id: ObjectIdStr | None = None, appointment_id: ObjectIdStr | None = None) -> Any:
    role, pid = await _profile(user, db)
    items, total = await MedicalRecordService(db, settings).list(role, pid, params, patient_id=patient_id, appointment_id=appointment_id)
    return make_page([_out(i) for i in items], total, params.page, params.page_size)


@router.get("/{record_id}", response_model=MedicalRecordOut, summary="Get a medical record",
            description="Only the record's patient or authoring doctor; everyone else gets 404. **Auth:** PATIENT or DOCTOR.", responses=errs(401, 403, 404, 422))
async def get_record(record_id: ObjectIdPath, user: CurrentUser, db: DB, settings: SettingsDep) -> Any:
    role, pid = await _profile(user, db)
    return _out(await MedicalRecordService(db, settings).get(role, pid, record_id))


@router.patch("/{record_id}", response_model=MedicalRecordOut, summary="Edit consultation notes",
              description="Authoring doctor only. **Auth:** DOCTOR.", responses=errs(401, 403, 404, 422))
async def update_record(record_id: ObjectIdPath, payload: MedicalRecordUpdate, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    return _out(await MedicalRecordService(db, settings).update_notes(ctx.doctor["_id"], record_id, payload.notes))


@router.post("/{record_id}/documents", response_model=MedicalRecordOut, status_code=201, summary="Attach document metadata",
             description="Registers a reference (https URL) to a file already stored in external object storage. No file bytes are stored in MongoDB. **Auth:** PATIENT (own record) or authoring DOCTOR.",
             responses=errs(400, 401, 403, 404, 422))
async def add_document(record_id: ObjectIdPath, payload: DocumentCreate, user: CurrentUser, db: DB, settings: SettingsDep) -> Any:
    role, pid = await _profile(user, db)
    return _out(await MedicalRecordService(db, settings).add_document(role, pid, user["_id"], record_id, payload))


@router.delete("/{record_id}/documents/{document_id}", response_model=MedicalRecordOut, summary="Remove a document reference",
               description="Only the user who attached it. **Auth:** PATIENT or DOCTOR.", responses=errs(401, 403, 404, 422))
async def remove_document(record_id: ObjectIdPath, document_id: ObjectIdPath, user: CurrentUser, db: DB, settings: SettingsDep) -> Any:
    role, pid = await _profile(user, db)
    return _out(await MedicalRecordService(db, settings).remove_document(user["_id"], role, pid, record_id, document_id))
