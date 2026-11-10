from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Request,
    Response,
    UploadFile,
)

from app.core.audit_context import extract_client_ip
from app.core.dependencies import (
    DB,
    AdminUser,
    CurrentUser,
    DoctorCtx,
    PatientCtx,
    SettingsDep,
)
from app.core.errors import ForbiddenError
from app.database.collections import C
from app.models.enums import UserRole
from app.routes.docs import errs
from app.schemas.clinical import (
    DocumentCreate,
    DocumentOut,
    DocumentShareCreate,
    DocumentShareOut,
    MedicalAuditOut,
    MedicalDocumentOut,
    MedicalRecordCreate,
    MedicalRecordOut,
    MedicalRecordUpdate,
    MedicalStatsOut,
    MedicalTimelineItem,
)
from app.schemas.common import Page, make_page
from app.services.medical_record_service import MedicalRecordService
from app.utils.object_id import ObjectIdPath, ObjectIdStr
from app.utils.pagination import PageParams, page_params
from app.utils.serialization import to_api

router = APIRouter(prefix="/medical-records", tags=["Medical Records"])


def _out(doc: dict) -> dict:
    data = to_api(doc)
    data["documents"] = [{**d, "id": d["id"]} for d in data.get("documents", [])]
    return data


def _doc_out(doc: dict) -> dict:
    data = to_api(doc)
    if "shares" in data and isinstance(data["shares"], list):
        data["shares"] = [to_api(s) for s in data["shares"]]
    return data


# ---------------------------------------------------------------------------
# Phase 4: Secure Medical Document Upload & Management (Patient)
# ---------------------------------------------------------------------------

@router.post("/documents/upload", response_model=MedicalDocumentOut, status_code=201, summary="Upload a medical document",
             description="Uploads and securely stores a private medical document (PDF, JPEG, PNG, WebP, TIFF). **Auth:** PATIENT.",
             responses=errs(400, 401, 403, 422))
async def upload_document(
    ctx: PatientCtx,
    request: Request,
    db: DB,
    settings: SettingsDep,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=255),
    category: str = Form(..., description="LAB_REPORT, PRESCRIPTION, IMAGING, DISCHARGE_SUMMARY, CONSULTATION_REPORT, OTHER"),
    description: str | None = Form(None),
    appointment_id: str | None = Form(None),
) -> Any:
    content = await file.read()
    client_ip = extract_client_ip(request, settings)
    doc = await MedicalRecordService(db, settings).upload_document(
        patient=ctx.patient,
        title=title,
        category=category,
        description=description,
        appointment_id=appointment_id,
        filename=file.filename or "medical_document.bin",
        content=content,
        client_ip=client_ip,
    )
    return _doc_out(doc)


@router.get("/documents", response_model=Page[MedicalDocumentOut], summary="List my medical documents",
            description="Patients list their own uploaded medical documents with category filters and title search. **Auth:** PATIENT.",
            responses=errs(401, 403, 422))
async def list_patient_documents(
    ctx: PatientCtx,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search by document title or description"),
) -> Any:
    items, total = await MedicalRecordService(db, settings).list_patient_documents(
        patient_id=ctx.patient["_id"],
        category=category,
        search=search,
        params=params,
    )
    return make_page([_doc_out(i) for i in items], total, params.page, params.page_size)


@router.get("/documents/{document_id}", response_model=MedicalDocumentOut, summary="Get document metadata",
            description="Patient inspects metadata and share history for a specific document. **Auth:** PATIENT.",
            responses=errs(401, 403, 404, 422))
async def get_patient_document(
    document_id: str,
    ctx: PatientCtx,
    db: DB,
    settings: SettingsDep,
) -> Any:
    doc = await MedicalRecordService(db, settings).get_patient_document(ctx.patient["_id"], document_id)
    return _doc_out(doc)


@router.get("/documents/{document_id}/download", summary="Download medical document",
            description="Streams the private medical document file. Requires ownership or active doctor consent. Access is audited. **Auth:** PATIENT or DOCTOR.",
            responses=errs(401, 403, 404, 422))
async def download_document(
    document_id: str,
    user: CurrentUser,
    request: Request,
    db: DB,
    settings: SettingsDep,
) -> Any:
    client_ip = extract_client_ip(request, settings)
    content, mime_type, filename = await MedicalRecordService(db, settings).download_document(
        user=user,
        document_id=document_id,
        client_ip=client_ip,
    )
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": mime_type,
        "Cache-Control": "private, no-cache, no-store, must-revalidate",
        "X-Content-Type-Options": "nosniff",
    }
    return Response(content=content, media_type=mime_type, headers=headers)


@router.delete("/documents/{document_id}", summary="Delete medical document",
               description="Patient deletes their own document. Revokes all active doctor shares and deletes the stored file. **Auth:** PATIENT.",
               responses=errs(401, 403, 404, 422))
async def delete_patient_document(
    document_id: str,
    ctx: PatientCtx,
    request: Request,
    db: DB,
    settings: SettingsDep,
) -> Any:
    client_ip = extract_client_ip(request, settings)
    return await MedicalRecordService(db, settings).delete_patient_document(
        patient_id=ctx.patient["_id"],
        user_id=ctx.user["_id"],
        document_id=document_id,
        client_ip=client_ip,
    )


# ---------------------------------------------------------------------------
# Phase 4: Patient-Controlled Sharing & Consent
# ---------------------------------------------------------------------------

@router.post("/documents/{document_id}/share", response_model=DocumentShareOut, status_code=201, summary="Share document with a doctor",
             description="Patient grants explicit consent for a doctor to access a document. **Auth:** PATIENT.",
             responses=errs(400, 401, 403, 404, 422))
async def share_document(
    document_id: str,
    payload: DocumentShareCreate,
    ctx: PatientCtx,
    request: Request,
    db: DB,
    settings: SettingsDep,
) -> Any:
    client_ip = extract_client_ip(request, settings)
    share = await MedicalRecordService(db, settings).share_document_with_doctor(
        patient=ctx.patient,
        document_id=document_id,
        doctor_id=payload.doctor_id,
        appointment_id=payload.appointment_id,
        notes=payload.notes,
        client_ip=client_ip,
    )
    return to_api(share)


@router.delete("/documents/{document_id}/share/{doctor_id}", response_model=DocumentShareOut, summary="Revoke doctor's access to document",
               description="Patient revokes consent for a doctor. Future access by that doctor is immediately blocked. **Auth:** PATIENT.",
               responses=errs(401, 403, 404, 422))
async def revoke_share(
    document_id: str,
    doctor_id: str,
    ctx: PatientCtx,
    request: Request,
    db: DB,
    settings: SettingsDep,
) -> Any:
    client_ip = extract_client_ip(request, settings)
    share = await MedicalRecordService(db, settings).revoke_document_share(
        patient=ctx.patient,
        document_id=document_id,
        doctor_id=doctor_id,
        client_ip=client_ip,
    )
    return to_api(share)


@router.get("/documents/{document_id}/shares", response_model=list[DocumentShareOut], summary="List consent history for a document",
            description="Patient inspects active and historical shares for a specific document. **Auth:** PATIENT.",
            responses=errs(401, 403, 404, 422))
async def list_document_shares(
    document_id: str,
    ctx: PatientCtx,
    db: DB,
    settings: SettingsDep,
) -> Any:
    shares = await MedicalRecordService(db, settings).list_document_shares(ctx.patient["_id"], document_id)
    return [to_api(s) for s in shares]


# ---------------------------------------------------------------------------
# Phase 4: Doctor Access to Shared Documents
# ---------------------------------------------------------------------------

@router.get("/shared", response_model=Page[MedicalDocumentOut], summary="List documents shared with me",
            description="Doctors view documents that patients have actively shared with them. **Auth:** DOCTOR.",
            responses=errs(401, 403, 422))
async def list_shared_documents(
    ctx: DoctorCtx,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
    category: str | None = Query(None, description="Filter by document category"),
    patient_id: str | None = Query(None, description="Filter by patient ID"),
) -> Any:
    items, total = await MedicalRecordService(db, settings).list_shared_with_doctor(
        doctor_id=ctx.doctor["_id"],
        category=category,
        patient_id=patient_id,
        params=params,
    )
    return make_page([_doc_out(i) for i in items], total, params.page, params.page_size)


@router.get("/shared/{document_id}", response_model=MedicalDocumentOut, summary="Get shared document metadata",
            description="Doctor inspects metadata for a shared document. Requires valid consent. **Auth:** DOCTOR.",
            responses=errs(401, 403, 404, 422))
async def get_shared_document(
    document_id: str,
    ctx: DoctorCtx,
    request: Request,
    db: DB,
    settings: SettingsDep,
) -> Any:
    client_ip = extract_client_ip(request, settings)
    doc = await MedicalRecordService(db, settings).get_shared_document_for_doctor(
        doctor=ctx.doctor,
        document_id=document_id,
        client_ip=client_ip,
    )
    return _doc_out(doc)


# ---------------------------------------------------------------------------
# Phase 4: Medical Timeline & Audit Log
# ---------------------------------------------------------------------------

@router.get("/timeline", response_model=Page[MedicalTimelineItem], summary="Get chronological medical timeline",
            description="Aggregates appointments, documents, and consultation notes chronologically. **Auth:** PATIENT or DOCTOR.",
            responses=errs(401, 403, 422))
async def get_timeline(
    user: CurrentUser,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
    patient_id: str | None = Query(None, description="Patient ID (required if DOCTOR)"),
) -> Any:
    service = MedicalRecordService(db, settings)
    if user["role"] == UserRole.PATIENT.value:
        patient = await db[C.PATIENTS].find_one({"user_id": user["_id"]})
        if not patient:
            raise ForbiddenError("Patient profile not found", code="profile_missing")
        target_pid = patient["_id"]
        profile_id = patient["_id"]
    elif user["role"] == UserRole.DOCTOR.value:
        doctor = await db[C.DOCTORS].find_one({"user_id": user["_id"]})
        if not doctor:
            raise ForbiddenError("Doctor profile not found", code="profile_missing")
        if not patient_id:
            raise ForbiddenError("patient_id query parameter is required for doctor timeline requests", code="missing_patient_id")
        target_pid = patient_id
        profile_id = doctor["_id"]
    else:
        raise ForbiddenError("Administrators cannot access patient medical timelines", code="forbidden_role")

    items, total = await service.get_medical_timeline(
        role=user["role"],
        profile_id=profile_id,
        patient_id=target_pid,
        params=params,
    )
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.get("/patients/{patient_id}/timeline", response_model=Page[MedicalTimelineItem], summary="Get patient timeline (Doctor)",
            description="Doctor views a treated patient's medical timeline. Requires treating relationship or active consent. **Auth:** DOCTOR.",
            responses=errs(401, 403, 422))
async def get_patient_timeline_doctor(
    patient_id: str,
    ctx: DoctorCtx,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
) -> Any:
    items, total = await MedicalRecordService(db, settings).get_medical_timeline(
        role=UserRole.DOCTOR.value,
        profile_id=ctx.doctor["_id"],
        patient_id=patient_id,
        params=params,
    )
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.get("/audits", response_model=Page[MedicalAuditOut], summary="View medical record access audit log",
            description="Patients view access logs on their own records; Admins view compliance access logs. Doctors: 403. **Auth:** PATIENT or ADMIN.",
            responses=errs(401, 403, 422))
async def get_audit_trail(
    user: CurrentUser,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
    patient_id: str | None = Query(None, description="Patient filter (ADMIN only)"),
) -> Any:
    service = MedicalRecordService(db, settings)
    if user["role"] == UserRole.PATIENT.value:
        patient = await db[C.PATIENTS].find_one({"user_id": user["_id"]})
        if not patient:
            raise ForbiddenError("Patient profile not found", code="profile_missing")
        profile_id = patient["_id"]
    elif user["role"] == UserRole.ADMIN.value:
        profile_id = user["_id"]
    else:
        raise ForbiddenError("Doctors do not have permission to view medical audit trails", code="forbidden_role")

    items, total = await service.get_audit_history(
        role=user["role"],
        profile_id=profile_id,
        user_id=user["_id"],
        patient_id=patient_id,
        params=params,
    )
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


# ---------------------------------------------------------------------------
# Phase 4: Administrative Operational Statistics
# ---------------------------------------------------------------------------

@router.get("/admin/stats", response_model=MedicalStatsOut, summary="Medical records operational statistics",
            description="Aggregated document volumes, categories, and sharing metrics. Does NOT expose document contents or downloads. **Auth:** ADMIN.",
            responses=errs(401, 403))
async def get_admin_medical_stats(
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
) -> Any:
    stats = await MedicalRecordService(db, settings).get_admin_operational_stats()
    return to_api(stats)


# ---------------------------------------------------------------------------
# Consultation Notes & Legacy Reference Routes (Preserved for compatibility)
# ---------------------------------------------------------------------------

async def _profile(user: dict, db: Any) -> tuple[str, Any]:
    """Patients and doctors only — admins have NO access to consultation notes."""
    if user["role"] == UserRole.PATIENT:
        p = await db[C.PATIENTS].find_one({"user_id": user["_id"]})
    elif user["role"] == UserRole.DOCTOR:
        p = await db[C.DOCTORS].find_one({"user_id": user["_id"]})
    else:
        raise ForbiddenError("Administrators cannot access consultation notes", code="forbidden_role")
    if p is None:
        raise ForbiddenError("Profile not found", code="profile_missing")
    return user["role"], p["_id"]


@router.post("", response_model=MedicalRecordOut, status_code=201, summary="Add consultation notes",
             description="The treating doctor records their own notes for a confirmed/completed appointment (one record per appointment). **Auth:** DOCTOR.",
             responses=errs(401, 403, 404, 409, 422))
async def create_record(payload: MedicalRecordCreate, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    return _out(await MedicalRecordService(db, settings).create(ctx.doctor["_id"], payload))


@router.get("", response_model=Page[MedicalRecordOut], summary="List consultation notes",
            description="Patients: their own notes. Doctors: notes they authored. **Auth:** PATIENT or DOCTOR.",
            responses=errs(401, 403, 422))
async def list_records(
    user: CurrentUser,
    db: DB,
    settings: SettingsDep,
    params: Annotated[PageParams, Depends(page_params)],
    patient_id: ObjectIdStr | None = None,
    appointment_id: ObjectIdStr | None = None,
) -> Any:
    role, pid = await _profile(user, db)
    items, total = await MedicalRecordService(db, settings).list(role, pid, params, patient_id=patient_id, appointment_id=appointment_id)
    return make_page([_out(i) for i in items], total, params.page, params.page_size)


@router.get("/{record_id}", response_model=MedicalRecordOut, summary="Get consultation notes",
            description="Only the record's patient or authoring doctor. **Auth:** PATIENT or DOCTOR.",
            responses=errs(401, 403, 404, 422))
async def get_record(record_id: ObjectIdPath, user: CurrentUser, db: DB, settings: SettingsDep) -> Any:
    role, pid = await _profile(user, db)
    return _out(await MedicalRecordService(db, settings).get(role, pid, record_id))


@router.patch("/{record_id}", response_model=MedicalRecordOut, summary="Edit consultation notes",
              description="Authoring doctor only. **Auth:** DOCTOR.",
              responses=errs(401, 403, 404, 422))
async def update_record(record_id: ObjectIdPath, payload: MedicalRecordUpdate, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    return _out(await MedicalRecordService(db, settings).update_notes(ctx.doctor["_id"], record_id, payload.notes))


@router.post("/{record_id}/documents", response_model=MedicalRecordOut, status_code=201, summary="Attach document reference to consultation note",
             description="Registers a legacy reference to a file in external storage. **Auth:** PATIENT or authoring DOCTOR.",
             responses=errs(400, 401, 403, 404, 422))
async def add_document(record_id: ObjectIdPath, payload: DocumentCreate, user: CurrentUser, db: DB, settings: SettingsDep) -> Any:
    role, pid = await _profile(user, db)
    return _out(await MedicalRecordService(db, settings).add_document(role, pid, user["_id"], record_id, payload))


@router.delete("/{record_id}/documents/{document_id}", response_model=MedicalRecordOut, summary="Remove a document reference from consultation note",
               description="Only the user who attached it. **Auth:** PATIENT or DOCTOR.",
               responses=errs(401, 403, 404, 422))
async def remove_document(record_id: ObjectIdPath, document_id: ObjectIdPath, user: CurrentUser, db: DB, settings: SettingsDep) -> Any:
    role, pid = await _profile(user, db)
    return _out(await MedicalRecordService(db, settings).remove_document(user["_id"], role, pid, record_id, document_id))
