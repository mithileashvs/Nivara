"""Appointment lifecycle engine.

    REQUESTED --doctor accepts--> CONFIRMED --> COMPLETED | NO_SHOW
        |  \\--doctor rejects--> REJECTED
        \\--patient/doctor cancels, or hold expires--> CANCELLED  (CONFIRMED can also be cancelled)

Patients only ever *request*. Only the appointment's doctor can confirm/reject; admins have no role.

Consistency rules (see slot_service for the slot-side atomic transitions):
* The APPOINTMENT document is the arbiter of its own status: every transition is a conditional
  update on the expected current status, so two racing decisions cannot both win.
* The SLOT document is the arbiter of ownership: a slot is only released/promoted when it is still
  owned by that appointment id, so a slot that has moved on is never disturbed.
* Whoever moves an appointment to a terminal state is responsible for releasing its slot.
"""
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from uuid import uuid4

from app.core.config import Settings
from app.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.database.collections import C
from app.database.session import DuplicateKeyError
from app.models.appointments import Appointment, AppointmentHistory
from app.models.enums import (
    ACTIVE_APPOINTMENT_STATUSES, AppointmentStatus as S, NotificationType, SlotStatus, SystemActor, UserRole,
)
from app.schemas.appointments import AppointmentCreate
from app.services.notification_service import NotificationService
from app.services.slot_recovery_service import SlotRecoveryService
from app.services.slot_rules import slot_block_reason
from app.services.slot_service import SlotService, reason_to_error
from app.services.waitlist_service import WaitlistService
from app.utils.object_id import oid
from app.utils.pagination import PageParams, paginate
from app.utils.time_utils import date_to_str, utcnow

logger = logging.getLogger("nivara.appointments")

MAX_ACTIVE_LOOKAHEAD = 500


@dataclass(frozen=True)
class Actor:
    """The authenticated caller acting on an appointment (patient or doctor)."""

    user_id: str
    role: str
    profile_id: str  # patient_id or doctor_id
    name: str

    @property
    def is_patient(self) -> bool:
        return self.role == UserRole.PATIENT

    @property
    def is_doctor(self) -> bool:
        return self.role == UserRole.DOCTOR


def _when(a: dict) -> str:
    return f"{a['appointment_date']} at {a['start_time']}"


class AppointmentService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.slots = SlotService(db, settings)
        self.notifications = NotificationService(db)
        self.recovery = SlotRecoveryService(db, settings)
        self.waitlist = WaitlistService(db, settings)

    @property
    def coll(self) -> Any:
        return self.db[C.APPOINTMENTS]

    # ------------------------------------------------------------------ helpers

    async def _history(
        self, appt_id: str, prev: str | None, new: str, actor: Actor | None, reason: str | None
    ) -> None:
        try:
            await self.db[C.APPOINTMENT_HISTORY].insert_one(
                AppointmentHistory(
                    appointment_id=appt_id,
                    previous_status=prev,
                    new_status=new,
                    changed_by=actor.user_id if actor else None,
                    changed_by_role=actor.role if actor else SystemActor.SYSTEM.value,
                    reason=reason,
                ).to_mongo()
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to write appointment history for %s", appt_id)

    async def _transition(
        self,
        appt_id: str,
        from_statuses: list[str],
        to: S,
        reason: str | None,
        extra_filter: dict[str, Any] | None = None,
    ) -> dict | None:
        return await self.coll.find_one_and_update(
            {"_id": appt_id, "status": {"$in": from_statuses}, **(extra_filter or {})},
            {"$set": {"status": to.value, "is_active": to in ACTIVE_APPOINTMENT_STATUSES, "status_reason": reason, "updated_at": utcnow()}},
        )

    async def get_for_actor(self, actor: Actor, appointment_id: str) -> dict:
        field = "patient_id" if actor.is_patient else "doctor_id"
        appt = await self.coll.find_one({"_id": oid(appointment_id), field: actor.profile_id})
        if appt is None:  # 404 (not 403) so other people's appointment ids are not revealed
            raise NotFoundError("Appointment not found", code="appointment_not_found")
        return appt

    @staticmethod
    def _bad_transition(current: str, action: str) -> ConflictError:
        return ConflictError(
            f"Cannot {action} an appointment that is {current}.", code="invalid_status_transition", details={"current_status": current}
        )

    async def _release_and_recover(self, appt: dict, *, exclude_patient: bool = True) -> None:
        released = await self.slots.release(appt["slot_id"], appt["_id"])
        if released is not None and released["start_at"] > utcnow():
            await self.recovery.on_slot_released(
                appt["slot_id"], exclude_patient_id=appt["patient_id"] if exclude_patient else None
            )

    # ------------------------------------------------------------------ hold expiry

    async def expire_stale_hold(self, slot: dict) -> bool:
        """Formally expire a request whose hold ran out. The slot is released FIRST (its own atomic
        condition ``held_until < now`` is mutually exclusive with a doctor's accept, which requires
        ``held_until >= now``), then the appointment is cancelled by the system."""
        now = utcnow()
        before = await self.slots.release_expired_hold(slot, now)
        if before is None:
            return False
        appt_id = before.get("appointment_id")
        if appt_id:
            appt = await self._transition(
                appt_id, [S.REQUESTED.value], S.CANCELLED,
                "Request expired: the doctor did not respond in time", extra_filter={"slot_id": slot["_id"]},
            )
            if appt:
                await self._history(appt_id, S.REQUESTED.value, S.CANCELLED.value, None, "Request expired (slot hold timed out)")
                await self.notifications.notify(
                    user_id=appt["patient_user_id"], type=NotificationType.APPOINTMENT_CANCELLED,
                    title="Appointment request expired",
                    message=f"Your request with Dr. {appt['doctor_name']} for {_when(appt)} expired because it was not confirmed in time. You can request another slot.",
                    appointment_id=appt_id,
                )
        if slot["start_at"] > now:
            await self.recovery.on_slot_released(slot["_id"], exclude_patient_id=None)
        return True

    # ------------------------------------------------------------------ validation shared by request/reschedule

    async def _prepare_slot(self, slot_id: str, consultation_type: str, now, expected_doctor_id: str | None = None):
        slot = await self.slots.get(oid(slot_id))
        if expected_doctor_id is not None and slot["doctor_id"] != expected_doctor_id:
            raise BadRequestError("Rescheduling must stay with the same doctor; request a new appointment instead", code="different_doctor")
        if slot["status"] == SlotStatus.HELD and slot.get("held_until") and slot["held_until"] < now:
            await self.expire_stale_hold(slot)  # lazily free stale holds so the slot can be re-claimed
            slot = await self.slots.get(slot["_id"])
        doctor = await self.db[C.DOCTORS].find_one({"_id": slot["doctor_id"]})
        hospital = await self.db[C.HOSPITALS].find_one({"_id": slot["hospital_id"]})
        department = await self.db[C.DEPARTMENTS].find_one({"_id": slot["department_id"]})
        reason = slot_block_reason(slot, doctor, hospital, department, now=now, min_lead_minutes=self.settings.min_booking_lead_minutes)
        if reason:
            raise reason_to_error(reason)
        if consultation_type not in doctor.get("consultation_types", []):
            raise BadRequestError(f"This doctor does not offer {consultation_type} consultations", code="consultation_type_not_offered")
        if slot["start_at"] > now + timedelta(days=self.settings.max_scheduling_horizon_days):
            raise BadRequestError("This slot is too far in the future to book", code="date_too_far")
        return slot, doctor

    async def _check_patient_capacity(self, patient_id: str, slot: dict, exclude_id: str | None = None, count_pending: bool = True) -> None:
        exclude = {"_id": {"$ne": exclude_id}} if exclude_id else {}
        if count_pending:
            pending = await self.coll.count_documents({"patient_id": patient_id, "status": S.REQUESTED.value, **exclude})
            if pending >= self.settings.max_pending_requests_per_patient:
                raise ConflictError(
                    f"You already have {pending} pending requests. Wait for a decision or cancel one first.", code="too_many_pending_requests"
                )
        overlap = await self.coll.count_documents(
            {"patient_id": patient_id, "is_active": True, "start_at": {"$lt": slot["end_at"]}, "end_at": {"$gt": slot["start_at"]}, **exclude}
        )
        if overlap:
            raise ConflictError("You already have an appointment that overlaps this time.", code="patient_time_conflict")

    # ------------------------------------------------------------------ patient: request

    async def request(self, actor: Actor, payload: AppointmentCreate) -> dict:
        now = utcnow()
        ctype = payload.consultation_type.value
        slot, doctor = await self._prepare_slot(payload.slot_id, ctype, now)
        await self._check_patient_capacity(actor.profile_id, slot)

        appt_id = str(uuid4())
        hold_until = min(now + timedelta(minutes=self.settings.request_hold_minutes), slot["start_at"])
        # >>> The concurrency-critical step: one atomic conditional update. Losers get 409. <<<
        await self.slots.claim(slot["_id"], appt_id, target=SlotStatus.HELD, hold_until=hold_until, now=now)

        doc = Appointment(
            id=appt_id, patient_id=actor.profile_id, patient_user_id=actor.user_id, patient_name=actor.name,
            doctor_id=doctor["_id"], doctor_user_id=doctor["user_id"], doctor_name=doctor["name"],
            hospital_id=slot["hospital_id"], department_id=slot["department_id"], slot_id=slot["_id"],
            appointment_date=slot["date"], start_time=slot["start_time"], end_time=slot["end_time"],
            start_at=slot["start_at"], end_at=slot["end_at"], consultation_type=ctype, reason=payload.reason,
        ).to_mongo()
        try:
            await self.coll.insert_one(doc)
        except DuplicateKeyError:  # second line of defence (partial unique indexes)
            await self.slots.release(slot["_id"], appt_id)
            raise ConflictError("This slot or time is already taken by another active appointment.", code="slot_unavailable") from None
        except Exception:
            await self.slots.release(slot["_id"], appt_id)
            raise

        await self._history(appt_id, None, S.REQUESTED.value, actor, payload.reason)
        await self.notifications.notify(
            user_id=doctor["user_id"], type=NotificationType.APPOINTMENT_REQUESTED, title="New appointment request",
            message=f"{actor.name} requested an appointment on {_when(doc)}. Please accept or reject it.", appointment_id=appt_id,
        )
        await self.waitlist.mark_fulfilled(actor.profile_id, slot["_id"], appt_id)
        return doc

    # ------------------------------------------------------------------ doctor: decisions

    async def accept(self, actor: Actor, appointment_id: str, reason: str | None) -> dict:
        appt = await self.get_for_actor(actor, appointment_id)
        if appt["status"] != S.REQUESTED:
            raise self._bad_transition(appt["status"], "accept")
        now = utcnow()
        if not await self.slots.promote_to_booked(appt["slot_id"], appt["_id"], now):
            slot = await self.db[C.APPOINTMENT_SLOTS].find_one({"_id": appt["slot_id"]})
            if slot and slot["status"] == SlotStatus.HELD and slot.get("appointment_id") == appt["_id"]:
                await self.expire_stale_hold(slot)
                raise ConflictError("This request has expired and can no longer be accepted.", code="request_expired")
            raise ConflictError("This request can no longer be accepted.", code="appointment_not_pending")
        updated = await self._transition(appt["_id"], [S.REQUESTED.value], S.CONFIRMED, reason, extra_filter={"slot_id": appt["slot_id"]})
        if updated is None:  # changed concurrently; the actor that changed it releases the slot
            raise ConflictError("This appointment was changed by someone else. Please refresh.", code="appointment_changed")
        await self._history(appt["_id"], S.REQUESTED.value, S.CONFIRMED.value, actor, reason)
        await self.notifications.notify(
            user_id=appt["patient_user_id"], type=NotificationType.APPOINTMENT_ACCEPTED, title="Appointment confirmed",
            message=f"Dr. {appt['doctor_name']} confirmed your appointment on {_when(appt)}.", appointment_id=appt["_id"],
        )
        return updated

    async def reject(self, actor: Actor, appointment_id: str, reason: str | None) -> dict:
        appt = await self.get_for_actor(actor, appointment_id)
        if appt["status"] != S.REQUESTED:
            raise self._bad_transition(appt["status"], "reject")
        updated = await self._transition(appt["_id"], [S.REQUESTED.value], S.REJECTED, reason)
        if updated is None:
            raise ConflictError("This appointment was changed by someone else. Please refresh.", code="appointment_changed")
        await self._release_and_recover(appt)
        await self._history(appt["_id"], S.REQUESTED.value, S.REJECTED.value, actor, reason)
        await self.notifications.notify(
            user_id=appt["patient_user_id"], type=NotificationType.APPOINTMENT_REJECTED, title="Appointment request declined",
            message=f"Dr. {appt['doctor_name']} could not accept your request for {_when(appt)}." + (f" Reason: {reason}" if reason else ""),
            appointment_id=appt["_id"],
        )
        return updated

    async def _finish(self, actor: Actor, appointment_id: str, to: S, action: str, reason: str | None) -> dict:
        appt = await self.get_for_actor(actor, appointment_id)
        if appt["status"] != S.CONFIRMED:
            raise self._bad_transition(appt["status"], action)
        if utcnow() < appt["start_at"]:
            raise ConflictError(f"Cannot mark {to.value} before the appointment start time.", code="appointment_not_started")
        updated = await self._transition(appt["_id"], [S.CONFIRMED.value], to, reason)
        if updated is None:
            raise ConflictError("This appointment was changed by someone else. Please refresh.", code="appointment_changed")
        await self._history(appt["_id"], S.CONFIRMED.value, to.value, actor, reason)
        return updated  # the slot stays BOOKED: the time was used

    async def complete(self, actor: Actor, appointment_id: str, reason: str | None) -> dict:
        return await self._finish(actor, appointment_id, S.COMPLETED, "complete", reason)

    async def no_show(self, actor: Actor, appointment_id: str, reason: str | None) -> dict:
        return await self._finish(actor, appointment_id, S.NO_SHOW, "mark as no-show", reason)

    # ------------------------------------------------------------------ cancel

    async def cancel(self, actor: Actor, appointment_id: str, reason: str | None) -> dict:
        appt = await self.get_for_actor(actor, appointment_id)
        if appt["status"] not in (S.REQUESTED, S.CONFIRMED):
            raise self._bad_transition(appt["status"], "cancel")
        if appt["start_at"] <= utcnow():
            raise ConflictError("The appointment has already started; it can no longer be cancelled.", code="appointment_started")
        # Atomic, optimistic-concurrency guard: the write is conditioned on the EXACT status just
        # read, not the full set of cancellable statuses. If a concurrent transition (e.g. the
        # doctor accepting) changes the status between our read and this write, the filter no
        # longer matches and we lose the race cleanly (409) instead of overwriting it.
        updated = await self._transition(appt["_id"], [appt["status"]], S.CANCELLED, reason)
        if updated is None:
            raise ConflictError("This appointment was changed by someone else. Please refresh.", code="appointment_changed")
        # Slot becomes AVAILABLE again -> cancelled-slot recovery offers it to the smart waitlist.
        await self._release_and_recover(appt)
        await self._history(appt["_id"], appt["status"], S.CANCELLED.value, actor, reason)
        other_user, who = (appt["doctor_user_id"], appt["patient_name"]) if actor.is_patient else (appt["patient_user_id"], f"Dr. {appt['doctor_name']}")
        await self.notifications.notify(
            user_id=other_user, type=NotificationType.APPOINTMENT_CANCELLED, title="Appointment cancelled",
            message=f"{who} cancelled the appointment on {_when(appt)}." + (f" Reason: {reason}" if reason else ""), appointment_id=appt["_id"],
        )
        return updated

    # ------------------------------------------------------------------ reschedule

    async def reschedule(self, actor: Actor, appointment_id: str, new_slot_id: str, reason: str | None) -> dict:
        """Move an appointment to another slot of the SAME doctor.

        * Patient: back to REQUESTED — the doctor must approve the new time (patients never self-confirm).
        * Doctor: only CONFIRMED appointments; stays CONFIRMED (the doctor is the decision-maker).
        """
        appt = await self.get_for_actor(actor, appointment_id)
        allowed_from = [S.REQUESTED.value, S.CONFIRMED.value] if actor.is_patient else [S.CONFIRMED.value]
        if appt["status"] not in allowed_from:
            raise self._bad_transition(appt["status"], "reschedule")
        now = utcnow()
        if appt["start_at"] <= now:
            raise ConflictError("The appointment has already started.", code="appointment_started")
        if oid(new_slot_id) == appt["slot_id"]:
            raise BadRequestError("The new slot is the same as the current slot", code="same_slot")

        new_slot, _doctor = await self._prepare_slot(new_slot_id, appt["consultation_type"], now, expected_doctor_id=appt["doctor_id"])
        await self._check_patient_capacity(appt["patient_id"], new_slot, exclude_id=appt["_id"], count_pending=False)

        new_status = S.REQUESTED if actor.is_patient else S.CONFIRMED
        if actor.is_patient:
            hold_until = min(now + timedelta(minutes=self.settings.request_hold_minutes), new_slot["start_at"])
            await self.slots.claim(new_slot["_id"], appt["_id"], target=SlotStatus.HELD, hold_until=hold_until, now=now)
        else:
            await self.slots.claim(new_slot["_id"], appt["_id"], target=SlotStatus.BOOKED, hold_until=None, now=now)

        try:
            updated = await self.coll.find_one_and_update(
                {"_id": appt["_id"], "slot_id": appt["slot_id"], "status": {"$in": allowed_from}},
                {"$set": {
                    "slot_id": new_slot["_id"], "hospital_id": new_slot["hospital_id"], "department_id": new_slot["department_id"],
                    "appointment_date": new_slot["date"], "start_time": new_slot["start_time"], "end_time": new_slot["end_time"],
                    "start_at": new_slot["start_at"], "end_at": new_slot["end_at"], "status": new_status.value, "is_active": True,
                    "status_reason": reason, "reminder_sent": False, "updated_at": now,
                }},
            )
        except DuplicateKeyError:
            updated = None
        if updated is None:
            await self.slots.release(new_slot["_id"], appt["_id"])  # undo our claim
            raise ConflictError("This appointment was changed by someone else. Please refresh.", code="appointment_changed")

        await self._release_and_recover(appt)  # free the old slot (and offer it to the waitlist)
        note = f"Rescheduled from {_when(appt)} to {_when(updated)}" + (f": {reason}" if reason else "")
        await self._history(appt["_id"], appt["status"], new_status.value, actor, note)
        await self.waitlist.mark_fulfilled(appt["patient_id"], new_slot["_id"], appt["_id"])
        target_user = appt["doctor_user_id"] if actor.is_patient else appt["patient_user_id"]
        who = appt["patient_name"] if actor.is_patient else f"Dr. {appt['doctor_name']}"
        await self.notifications.notify(
            user_id=target_user, type=NotificationType.APPOINTMENT_RESCHEDULED, title="Appointment rescheduled",
            message=f"{who} moved the appointment from {_when(appt)} to {_when(updated)}."
            + (" Please review and accept or reject the new time." if actor.is_patient else ""),
            appointment_id=appt["_id"],
        )
        return updated

    # ------------------------------------------------------------------ queries

    async def list_for_actor(
        self, actor: Actor, params: PageParams, *, status: str | None, date_from: date | None, date_to: date | None
    ) -> tuple[list[dict], int]:
        query: dict[str, Any] = {("patient_id" if actor.is_patient else "doctor_id"): actor.profile_id}
        if status:
            query["status"] = status
        if date_from or date_to:
            query["appointment_date"] = {}
            if date_from:
                query["appointment_date"]["$gte"] = date_to_str(date_from)
            if date_to:
                query["appointment_date"]["$lte"] = date_to_str(date_to)
        return await paginate(self.coll, query, params, sort=[("start_at", -1), ("_id", -1)])

    async def history(self, actor: Actor, appointment_id: str) -> list[dict]:
        appt = await self.get_for_actor(actor, appointment_id)
        return await self.db[C.APPOINTMENT_HISTORY].find({"appointment_id": appt["_id"]}).sort([("created_at", 1), ("_id", 1)]).to_list(length=500)

    # ------------------------------------------------------------------ admin: read-only monitoring

    async def list_for_admin(
        self,
        admin: dict,
        params: PageParams,
        *,
        status: str | None,
        doctor_id: str | None,
        patient_id: str | None,
        hospital_id: str | None,
        department_id: str | None,
        appointment_date: date | None,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[list[dict], int]:
        """Platform-monitoring listing. Admins never approve/reject — see `app.routes.admin`.

        A hospital-scoped admin (``managed_hospital_ids`` is not None) is restricted to their own
        hospitals: an explicit ``hospital_id`` outside that scope is rejected, and with no filter
        the query is narrowed to the scoped hospitals automatically.
        """
        query: dict[str, Any] = {}
        if status:
            query["status"] = status
        if doctor_id:
            query["doctor_id"] = oid(doctor_id)
        if patient_id:
            query["patient_id"] = oid(patient_id)
        if department_id:
            query["department_id"] = oid(department_id)

        scope = admin.get("managed_hospital_ids")
        if hospital_id:
            hid = oid(hospital_id)
            if scope is not None and hid not in scope:
                raise ForbiddenError("You are not authorised to view appointments for this hospital", code="hospital_scope_forbidden")
            query["hospital_id"] = hid
        elif scope is not None:
            query["hospital_id"] = {"$in": scope}

        if appointment_date:
            query["appointment_date"] = date_to_str(appointment_date)
        elif date_from or date_to:
            query["appointment_date"] = {}
            if date_from:
                query["appointment_date"]["$gte"] = date_to_str(date_from)
            if date_to:
                query["appointment_date"]["$lte"] = date_to_str(date_to)

        items, total = await paginate(self.coll, query, params, sort=[("start_at", -1), ("_id", -1)])

        hospital_ids = {i["hospital_id"] for i in items}
        department_ids = {i["department_id"] for i in items}
        hospitals = {h["_id"]: h["name"] for h in await self.db[C.HOSPITALS].find(
            {"_id": {"$in": list(hospital_ids)}}, {"name": 1}
        ).to_list(length=None)} if hospital_ids else {}
        departments = {d["_id"]: d["name"] for d in await self.db[C.DEPARTMENTS].find(
            {"_id": {"$in": list(department_ids)}}, {"name": 1}
        ).to_list(length=None)} if department_ids else {}
        for i in items:
            i["hospital_name"] = hospitals.get(i["hospital_id"])
            i["department_name"] = departments.get(i["department_id"])
        return items, total
