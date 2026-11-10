from typing import Any

from fastapi import APIRouter

from app.core.dependencies import DB, DoctorCtx, ParticipantActor, SettingsDep
from app.routes.docs import errs
from app.schemas.appointments import AppointmentDecision, AppointmentOut, ReschedulingRequestOut
from app.services.appointment_service import AppointmentService
from app.utils.object_id import ObjectIdPath
from app.utils.serialization import to_api

router = APIRouter(prefix="/reschedule-requests", tags=["Reschedule Requests"])


def _svc(db: Any, settings: Any) -> AppointmentService:
    return AppointmentService(db, settings)


@router.post("/{request_id}/approve", response_model=AppointmentOut, summary="Doctor approves a rescheduling request",
             description=("Doctor approves a patient's rescheduling request. The requested slot is booked, the previous slot is freed, "
                          "the appointment schedule is updated, and the patient is notified. **Auth:** DOCTOR."),
             responses=errs(400, 401, 403, 404, 409, 422))
async def approve_reschedule(request_id: ObjectIdPath, payload: AppointmentDecision, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    return to_api(await _svc(db, settings).approve_reschedule(ctx.actor, request_id, payload.reason))


@router.post("/{request_id}/reject", response_model=AppointmentOut, summary="Doctor rejects a rescheduling request",
             description=("Doctor declines a patient's rescheduling request. The original appointment and its slot remain confirmed, "
                          "the temporary hold on the requested slot is released, and the patient is notified. **Auth:** DOCTOR."),
             responses=errs(400, 401, 403, 404, 409, 422))
async def reject_reschedule(request_id: ObjectIdPath, payload: AppointmentDecision, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    return to_api(await _svc(db, settings).reject_reschedule(ctx.actor, request_id, payload.reason))


@router.get("/{request_id}", response_model=ReschedulingRequestOut, summary="Get rescheduling request details",
            description="Get details of a specific rescheduling request. **Auth:** PATIENT or DOCTOR.",
            responses=errs(401, 403, 404, 422))
async def get_reschedule_request(request_id: ObjectIdPath, actor: ParticipantActor, db: DB, settings: SettingsDep) -> Any:
    return to_api(await _svc(db, settings).get_reschedule_request(actor, request_id))
