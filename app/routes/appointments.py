from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.dependencies import DB, DoctorCtx, ParticipantActor, PatientCtx, SettingsDep
from app.models.enums import AppointmentStatus
from app.routes.docs import errs
from app.schemas.appointments import (
    AppointmentCreate, AppointmentDecision, AppointmentHistoryOut, AppointmentOut, AppointmentReject, AppointmentReschedule,
)
from app.schemas.common import Page, make_page
from app.services.appointment_service import AppointmentService
from app.utils.object_id import ObjectIdPath
from app.utils.pagination import PageParams, page_params
from app.utils.serialization import to_api

router = APIRouter(prefix="/appointments", tags=["Appointments"])


def _svc(db: Any, settings: Any) -> AppointmentService:
    return AppointmentService(db, settings)


@router.post("", response_model=AppointmentOut, status_code=201, summary="Request an appointment",
             description=("Creates a `REQUESTED` appointment and atomically HOLDS the slot for the doctor's decision (patients can never confirm). "
                          "Returns **409** if the slot was taken by someone else, is blocked/booked, or the hospital, department or doctor has closed "
                          "intake (error `code` says which). Stale requests expire automatically. **Auth:** PATIENT."),
             responses=errs(400, 401, 403, 404, 409, 422))
async def request_appointment(payload: AppointmentCreate, ctx: PatientCtx, db: DB, settings: SettingsDep) -> Any:
    return to_api(await _svc(db, settings).request(ctx.actor, payload))


@router.get("", response_model=Page[AppointmentOut], summary="List my appointments",
            description="Patients see their own; doctors see appointments addressed to them. Admins have no access. **Auth:** PATIENT or DOCTOR.",
            responses=errs(401, 403, 422))
async def list_appointments(actor: ParticipantActor, db: DB, settings: SettingsDep, params: Annotated[PageParams, Depends(page_params)],
                            status: AppointmentStatus | None = None, date_from: date | None = None, date_to: date | None = None) -> Any:
    items, total = await _svc(db, settings).list_for_actor(actor, params, status=status.value if status else None, date_from=date_from, date_to=date_to)
    return make_page([to_api(i) for i in items], total, params.page, params.page_size)


@router.get("/{appointment_id}", response_model=AppointmentOut, summary="Get an appointment",
            description="Only the appointment's patient or doctor. Others get 404. **Auth:** PATIENT or DOCTOR.", responses=errs(401, 403, 404, 422))
async def get_appointment(appointment_id: ObjectIdPath, actor: ParticipantActor, db: DB, settings: SettingsDep) -> Any:
    return to_api(await _svc(db, settings).get_for_actor(actor, appointment_id))


@router.get("/{appointment_id}/history", response_model=list[AppointmentHistoryOut], summary="Appointment status history",
            description="Every status change with who made it and why. **Auth:** PATIENT or DOCTOR of the appointment.", responses=errs(401, 403, 404, 422))
async def appointment_history(appointment_id: ObjectIdPath, actor: ParticipantActor, db: DB, settings: SettingsDep) -> Any:
    return [to_api(h) for h in await _svc(db, settings).history(actor, appointment_id)]


@router.post("/{appointment_id}/accept", response_model=AppointmentOut, summary="Doctor accepts a request",
             description="`REQUESTED` → `CONFIRMED`. Only the appointment's doctor; admins and patients get 403. Fails with 409 if the request expired. **Auth:** DOCTOR.",
             responses=errs(401, 403, 404, 409, 422))
async def accept(appointment_id: ObjectIdPath, payload: AppointmentDecision, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    return to_api(await _svc(db, settings).accept(ctx.actor, appointment_id, payload.reason))


@router.post("/{appointment_id}/reject", response_model=AppointmentOut, summary="Doctor rejects a request",
             description="`REQUESTED` → `REJECTED`; the slot returns to AVAILABLE and may be offered to the waitlist. **Auth:** DOCTOR.",
             responses=errs(401, 403, 404, 409, 422))
async def reject(appointment_id: ObjectIdPath, payload: AppointmentReject, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    return to_api(await _svc(db, settings).reject(ctx.actor, appointment_id, payload.reason))


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut, summary="Cancel an appointment",
             description=("`REQUESTED`/`CONFIRMED` → `CANCELLED` by the patient or the doctor, before it starts. The slot becomes AVAILABLE again and "
                          "cancelled-slot recovery notifies eligible waitlisted patients. **Auth:** PATIENT or DOCTOR of the appointment."),
             responses=errs(401, 403, 404, 409, 422))
async def cancel(appointment_id: ObjectIdPath, payload: AppointmentDecision, actor: ParticipantActor, db: DB, settings: SettingsDep) -> Any:
    return to_api(await _svc(db, settings).cancel(actor, appointment_id, payload.reason))


@router.post("/{appointment_id}/complete", response_model=AppointmentOut, summary="Mark a consultation completed",
             description="`CONFIRMED` → `COMPLETED`, only once the appointment has started. **Auth:** DOCTOR.", responses=errs(401, 403, 404, 409, 422))
async def complete(appointment_id: ObjectIdPath, payload: AppointmentDecision, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    return to_api(await _svc(db, settings).complete(ctx.actor, appointment_id, payload.reason))


@router.post("/{appointment_id}/no-show", response_model=AppointmentOut, summary="Mark a patient no-show",
             description="`CONFIRMED` → `NO_SHOW`, only once the appointment has started. **Auth:** DOCTOR.", responses=errs(401, 403, 404, 409, 422))
async def no_show(appointment_id: ObjectIdPath, payload: AppointmentDecision, ctx: DoctorCtx, db: DB, settings: SettingsDep) -> Any:
    return to_api(await _svc(db, settings).no_show(ctx.actor, appointment_id, payload.reason))


@router.post("/{appointment_id}/reschedule", response_model=AppointmentOut, summary="Reschedule to another slot of the same doctor",
             description=("**Patient:** the new slot is held and the appointment returns to `REQUESTED` — the doctor must approve the new time. "
                          "**Doctor:** a `CONFIRMED` appointment moves directly and stays `CONFIRMED`. The old slot is freed atomically. "
                          "**Auth:** PATIENT or DOCTOR of the appointment."),
             responses=errs(400, 401, 403, 404, 409, 422))
async def reschedule(appointment_id: ObjectIdPath, payload: AppointmentReschedule, actor: ParticipantActor, db: DB, settings: SettingsDep) -> Any:
    return to_api(await _svc(db, settings).reschedule(actor, appointment_id, payload.new_slot_id, payload.reason))
