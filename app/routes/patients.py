from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.dependencies import DB, AdminUser, DoctorCtx, PatientCtx
from app.routes.docs import errs
from app.schemas.common import Page, make_page
from app.schemas.users import PatientOut, PatientSummaryForAdminOut, PatientSummaryForDoctorOut, PatientUpdate
from app.services.patient_service import PatientService, merge_patient
from app.utils.object_id import ObjectIdPath
from app.utils.pagination import PageParams, page_params
from app.utils.serialization import to_api

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("/me", response_model=PatientOut, summary="Get my patient profile",
            description="**Auth:** PATIENT.", responses=errs(401, 403))
async def get_me(ctx: PatientCtx) -> Any:
    return to_api(merge_patient(ctx.patient, ctx.user))


@router.patch("/me", response_model=PatientOut, summary="Update my patient profile",
              description="Update name, phone, date of birth, gender and basic contact information. **Auth:** PATIENT.",
              responses=errs(401, 403, 422))
async def update_me(payload: PatientUpdate, ctx: PatientCtx, db: DB) -> Any:
    return to_api(await PatientService(db).update_me(ctx.user, ctx.patient, payload))


@router.get("", response_model=Page[PatientSummaryForAdminOut], summary="List patients (identity only)",
            description="Platform administration view: id, name and sign-up date only — no contact or health-related details. **Auth:** ADMIN.",
            responses=errs(401, 403))
async def list_patients(_admin: AdminUser, db: DB, params: Annotated[PageParams, Depends(page_params)]) -> Any:
    items, total = await PatientService(db).list_for_admin(params)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.get("/{patient_id}", response_model=PatientSummaryForDoctorOut, summary="Get a patient I have an appointment with",
            description="A doctor can view minimal details only of patients who have an appointment with them; anyone else gets 404. **Auth:** DOCTOR.",
            responses=errs(401, 403, 404, 422))
async def get_patient(patient_id: ObjectIdPath, ctx: DoctorCtx, db: DB) -> Any:
    return to_api(await PatientService(db).get_for_doctor(ctx.doctor["_id"], patient_id))
