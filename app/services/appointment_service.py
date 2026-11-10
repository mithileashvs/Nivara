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
from app.models.appointments import Appointment, AppointmentHistory, ReschedulingRequest
from app.models.enums import (
    ACTIVE_APPOINTMENT_STATUSES,
    AppointmentStatus as S,
    AuditAction,
    AuditActorRole,
    AuditEntityType,
    AuditSeverity,
    NotificationType,
    ReschedulingStatus,
    SlotStatus,
    SystemActor,
    UserRole,
    WaitlistOfferStatus,
)
from app.schemas.appointments import AppointmentCreate
from app.services.audit_service import AuditService
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
        self.audit = AuditService(db, settings)

    @property
    def coll(self) -> Any:
        return self.db[C.APPOINTMENTS]

    # ------------------------------------------------------------------ helpers

    async def _history(
        self,
        appt_id: str,
        prev: str | None,
        new: str,
        actor: Actor | None,
        reason: str | None,
        previous_date: str | None = None,
        previous_time: str | None = None,
        new_date: str | None = None,
        new_time: str | None = None,
        metadata: dict[str, Any] | None = None,
        db: Any | None = None,
    ) -> None:
        target_db = db or self.db
        try:
            await target_db[C.APPOINTMENT_HISTORY].insert_one(
                AppointmentHistory(
                    appointment_id=appt_id,
                    previous_status=prev,
                    new_status=new,
                    changed_by=actor.user_id if actor else None,
                    changed_by_role=actor.role if actor else SystemActor.SYSTEM.value,
                    reason=reason,
                    previous_date=previous_date,
                    previous_time=previous_time,
                    new_date=new_date,
                    new_time=new_time,
                    metadata=metadata,
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
        waitlist_offer_id = before.get("waitlist_offer_id")
        exclude_pid: Any = None
        if appt_id:
            appt = await self._transition(
                appt_id, [S.REQUESTED.value], S.CANCELLED,
                "Request expired: the doctor did not respond in time", extra_filter={"slot_id": slot["_id"]},
            )
            if appt:
                await self._history(appt_id, S.REQUESTED.value, S.CANCELLED.value, None, "Request expired (slot hold timed out)")
                await self.audit.log_event(
                    action=AuditAction.APPOINTMENT_EXPIRED,
                    entity_type=AuditEntityType.APPOINTMENT,
                    entity_id=appt_id,
                    actor_id=None,
                    actor_role=AuditActorRole.SYSTEM,
                    hospital_id=appt.get("hospital_id"),
                    description=f"Appointment request expired (hold timed out) for {_when(appt)}",
                    metadata={"appointment_id": appt_id, "slot_id": slot["_id"], "department_id": appt.get("department_id")},
                )
                await self.notifications.notify(
                    user_id=appt["patient_user_id"], type=NotificationType.APPOINTMENT_CANCELLED,
                    title="Appointment request expired",
                    message=f"Your request with Dr. {appt['doctor_name']} for {_when(appt)} expired because it was not confirmed in time. You can request another slot.",
                    appointment_id=appt_id,
                )
        elif waitlist_offer_id:
            expired_offer = await self.db[C.WAITLIST_OFFERS].find_one_and_update(
                {"_id": waitlist_offer_id, "status": WaitlistOfferStatus.PENDING.value},
                {"$set": {"status": WaitlistOfferStatus.EXPIRED.value, "responded_at": now, "updated_at": now}},
            )
            if expired_offer:
                exclude_pid = expired_offer.get("patient_id")
                patient_doc = await self.db[C.PATIENTS].find_one({"_id": exclude_pid}) if exclude_pid else None
                if patient_doc:
                    await self.notifications.notify(
                        user_id=patient_doc["user_id"],
                        type=NotificationType.WAITLIST_EXPIRED.value,
                        title="Slot offer expired",
                        message="Your time-limited slot offer has expired and has been offered to the next waitlisted patient.",
                        category="WAITLIST",
                        action_url="/waitlist",
                    )
                await self.audit.log_event(
                    action=AuditAction.WAITLIST_OFFER_EXPIRED,
                    entity_type=AuditEntityType.WAITLIST_OFFER,
                    entity_id=expired_offer["_id"],
                    actor_id=None,
                    actor_role=AuditActorRole.SYSTEM,
                    hospital_id=before.get("hospital_id"),
                    description="Waitlist slot offer expired and released",
                    metadata={"slot_id": slot["_id"], "waitlist_entry_id": expired_offer.get("waitlist_entry_id")},
                )
        if slot["start_at"] > now:
            await self.recovery.on_slot_released(slot["_id"], exclude_patient_id=exclude_pid)
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
        await self.audit.log_event(
            action=AuditAction.APPOINTMENT_REQUESTED,
            entity_type=AuditEntityType.APPOINTMENT,
            entity_id=appt_id,
            actor_id=actor.user_id,
            actor_role=actor.role,
            hospital_id=slot["hospital_id"],
            description=f"Appointment requested for {_when(doc)}",
            metadata={
                "appointment_date": doc["appointment_date"],
                "start_time": doc["start_time"],
                "doctor_id": doctor["_id"],
                "department_id": slot["department_id"],
                "slot_id": slot["_id"],
                "consultation_type": ctype,
            },
        )
        # Notify doctor of incoming request
        await self.notifications.notify(
            user_id=doctor["user_id"],
            type=NotificationType.APPOINTMENT_REQUESTED.value,
            title="New appointment request",
            message=f"{actor.name} requested an appointment on {_when(doc)}. Please accept or reject it.",
            appointment_id=appt_id,
            action_url=f"/doctor/appointments/{appt_id}",
        )
        # Notify patient that request was submitted
        await self.notifications.notify(
            user_id=actor.user_id,
            type=NotificationType.APPOINTMENT_REQUESTED.value,
            title="Appointment request submitted",
            message=f"Your request with Dr. {doctor['name']} for {_when(doc)} has been submitted. You will be notified once they decide.",
            appointment_id=appt_id,
            action_url=f"/appointments/{appt_id}",
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
        await self.audit.log_event(
            action=AuditAction.APPOINTMENT_CONFIRMED,
            entity_type=AuditEntityType.APPOINTMENT,
            entity_id=appt["_id"],
            actor_id=actor.user_id,
            actor_role=actor.role,
            hospital_id=appt["hospital_id"],
            description=f"Appointment confirmed for {_when(appt)}",
            metadata={"previous_status": S.REQUESTED.value, "new_status": S.CONFIRMED.value, "doctor_id": appt["doctor_id"]},
        )
        await self.notifications.notify(
            user_id=appt["patient_user_id"],
            type=NotificationType.APPOINTMENT_ACCEPTED.value,
            title="Appointment confirmed",
            message=f"Dr. {appt['doctor_name']} confirmed your appointment on {_when(appt)}.",
            appointment_id=appt["_id"],
            action_url=f"/appointments/{appt['_id']}",
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
        await self.audit.log_event(
            action=AuditAction.APPOINTMENT_REJECTED,
            entity_type=AuditEntityType.APPOINTMENT,
            entity_id=appt["_id"],
            actor_id=actor.user_id,
            actor_role=actor.role,
            hospital_id=appt["hospital_id"],
            description=f"Appointment request declined for {_when(appt)}",
            metadata={"previous_status": S.REQUESTED.value, "new_status": S.REJECTED.value, "doctor_id": appt["doctor_id"]},
        )
        await self.notifications.notify(
            user_id=appt["patient_user_id"],
            type=NotificationType.APPOINTMENT_REJECTED.value,
            title="Appointment request declined",
            message=f"Dr. {appt['doctor_name']} could not accept your request for {_when(appt)}." + (f" Reason: {reason}" if reason else ""),
            appointment_id=appt["_id"],
            action_url=f"/appointments/{appt['_id']}",
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
        audit_act = AuditAction.APPOINTMENT_COMPLETED if to == S.COMPLETED else AuditAction.APPOINTMENT_NO_SHOW
        await self.audit.log_event(
            action=audit_act,
            entity_type=AuditEntityType.APPOINTMENT,
            entity_id=appt["_id"],
            actor_id=actor.user_id,
            actor_role=actor.role,
            hospital_id=appt["hospital_id"],
            description=f"Appointment marked {to.value} for {_when(appt)}",
            metadata={"previous_status": S.CONFIRMED.value, "new_status": to.value, "doctor_id": appt["doctor_id"]},
        )
        return updated  # the slot stays BOOKED: the time was used

    async def complete(self, actor: Actor, appointment_id: str, reason: str | None) -> dict:
        return await self._finish(actor, appointment_id, S.COMPLETED, "complete", reason)

    async def no_show(self, actor: Actor, appointment_id: str, reason: str | None) -> dict:
        return await self._finish(actor, appointment_id, S.NO_SHOW, "mark as no-show", reason)

    # ------------------------------------------------------------------ cancel

    async def cancel(self, actor: Actor, appointment_id: str, reason: str | None) -> dict:
        appt = await self.get_for_actor(actor, appointment_id)
        if appt["status"] not in (S.REQUESTED.value, S.CONFIRMED.value, S.RESCHEDULE_REQUESTED.value):
            raise self._bad_transition(appt["status"], "cancel")
        now = utcnow()
        if appt["start_at"] <= now:
            raise ConflictError("The appointment has already started; it can no longer be cancelled.", code="appointment_started")
        if not reason or not reason.strip():
            raise BadRequestError("Cancellation reason is mandatory.", code="cancellation_reason_required")
        clean_reason = reason.strip()

        async with self.db.transaction() as tx_db:
            # 1. Optimistic locking on the appointment's exact status
            updated = await tx_db[C.APPOINTMENTS].find_one_and_update(
                {"_id": appt["_id"], "status": appt["status"]},
                {"$set": {
                    "status": S.CANCELLED.value,
                    "is_active": False,
                    "status_reason": clean_reason,
                    "updated_at": now,
                }}
            )
            if updated is None:
                raise ConflictError("This appointment was changed by someone else. Please refresh.", code="appointment_changed")

            # 2. Check for pending rescheduling request and cancel it
            pending_resched = await tx_db[C.RESCHEDULING_REQUESTS].find_one(
                {"appointment_id": appt["_id"], "status": ReschedulingStatus.REQUESTED.value}
            )
            if pending_resched:
                # Release the held requested slot
                await tx_db[C.APPOINTMENT_SLOTS].find_one_and_update(
                    {"_id": pending_resched["requested_slot_id"], "appointment_id": appt["_id"], "status": SlotStatus.HELD.value},
                    {"$set": {"status": SlotStatus.AVAILABLE.value, "appointment_id": None, "held_until": None, "updated_at": now}}
                )
                # Update rescheduling request status
                await tx_db[C.RESCHEDULING_REQUESTS].find_one_and_update(
                    {"_id": pending_resched["_id"]},
                    {"$set": {
                        "status": ReschedulingStatus.CANCELLED.value,
                        "doctor_response": "Cancelled due to appointment cancellation",
                        "resolved_at": now,
                        "updated_at": now,
                    }}
                )
                await self._history(
                    appt["_id"],
                    S.RESCHEDULE_REQUESTED.value,
                    ReschedulingStatus.CANCELLED.value,
                    actor,
                    "Rescheduling request cancelled due to appointment cancellation",
                    metadata={"event": "RESCHEDULE_CANCELLED", "request_id": pending_resched["_id"]},
                    db=tx_db,
                )

            # 3. Release main occupied slot
            await tx_db[C.APPOINTMENT_SLOTS].find_one_and_update(
                {"_id": appt["slot_id"], "appointment_id": appt["_id"]},
                {"$set": {"status": SlotStatus.AVAILABLE.value, "appointment_id": None, "held_until": None, "updated_at": now}}
            )

            # 4. Write appointment history
            await self._history(
                appt["_id"],
                appt["status"],
                S.CANCELLED.value,
                actor,
                clean_reason,
                metadata={"event": "APPOINTMENT_CANCELLED", "cancellation_reason": clean_reason},
                db=tx_db,
            )

            # 4b. Centralized audit log inside TX
            await AuditService(tx_db, self.settings).log_event(
                action=AuditAction.APPOINTMENT_CANCELLED,
                entity_type=AuditEntityType.APPOINTMENT,
                entity_id=appt["_id"],
                actor_id=actor.user_id,
                actor_role=actor.role,
                hospital_id=appt["hospital_id"],
                description=f"Appointment on {_when(appt)} cancelled by {actor.role}",
                metadata={
                    "previous_status": appt["status"],
                    "new_status": S.CANCELLED.value,
                    "cancelled_pending_reschedule": bool(pending_resched),
                },
            )

            # 5. Notifications
            if actor.is_patient:
                doctor_title = (
                    "Appointment cancelled while reschedule pending"
                    if pending_resched
                    else "Appointment cancelled by patient"
                )
                doctor_msg = (
                    f"{appt['patient_name']} cancelled the appointment on {_when(appt)} while a rescheduling request was pending. Reason: {clean_reason}"
                    if pending_resched
                    else f"{appt['patient_name']} cancelled the appointment on {_when(appt)}. Reason: {clean_reason}"
                )
                await NotificationService(tx_db).notify(
                    user_id=appt["doctor_user_id"],
                    type=NotificationType.APPOINTMENT_CANCELLED.value,
                    title=doctor_title,
                    message=doctor_msg,
                    appointment_id=appt["_id"],
                    action_url=f"/doctor/appointments/{appt['_id']}",
                )
                await NotificationService(tx_db).notify(
                    user_id=appt["patient_user_id"],
                    type=NotificationType.APPOINTMENT_CANCELLED.value,
                    title="Appointment cancellation confirmed",
                    message=f"Your appointment with Dr. {appt['doctor_name']} on {_when(appt)} has been cancelled.",
                    appointment_id=appt["_id"],
                    action_url=f"/appointments/{appt['_id']}",
                )
            else:
                await NotificationService(tx_db).notify(
                    user_id=appt["patient_user_id"],
                    type=NotificationType.APPOINTMENT_CANCELLED.value,
                    title="Appointment cancelled by doctor",
                    message=f"Dr. {appt['doctor_name']} cancelled the appointment on {_when(appt)}. Reason: {clean_reason}",
                    appointment_id=appt["_id"],
                    action_url=f"/appointments/{appt['_id']}",
                )

        # 6. Post-transaction recovery
        if appt["start_at"] > now:
            await self.recovery.on_slot_released(appt["slot_id"], exclude_patient_id=appt["patient_id"] if actor.is_patient else None)
        return updated

    # ------------------------------------------------------------------ reschedule

    async def request_reschedule(self, actor: Actor, appointment_id: str, new_slot_id: str, reason: str | None) -> dict:
        """Patient requests to move a CONFIRMED appointment to a new slot of the same doctor.

        The original appointment remains valid and its slot occupied until approved.
        The new slot is held temporarily awaiting doctor decision.
        """
        if not actor.is_patient:
            raise ForbiddenError("Only the appointment owner can request rescheduling", code="forbidden_role")
        if not reason or not reason.strip():
            raise BadRequestError("A reason for rescheduling is mandatory.", code="reschedule_reason_required")
        clean_reason = reason.strip()

        appt = await self.get_for_actor(actor, appointment_id)
        if appt["status"] != S.CONFIRMED.value:
            raise self._bad_transition(appt["status"], "reschedule")

        now = utcnow()
        if appt["start_at"] <= now:
            raise ConflictError("The appointment has already started.", code="appointment_started")
        if oid(new_slot_id) == appt["slot_id"]:
            raise BadRequestError("The new slot is the same as the current slot", code="same_slot")

        # Prevent multiple active rescheduling requests for the same appointment
        existing_req = await self.db[C.RESCHEDULING_REQUESTS].find_one(
            {"appointment_id": appt["_id"], "status": ReschedulingStatus.REQUESTED.value}
        )
        if existing_req:
            raise ConflictError("A rescheduling request is already pending for this appointment.", code="reschedule_already_pending")

        new_slot, doctor = await self._prepare_slot(new_slot_id, appt["consultation_type"], now, expected_doctor_id=appt["doctor_id"])
        await self._check_patient_capacity(appt["patient_id"], new_slot, exclude_id=appt["_id"], count_pending=False)

        hold_until = min(now + timedelta(minutes=self.settings.request_hold_minutes), new_slot["start_at"])

        async with self.db.transaction() as tx_db:
            # 1. Claim new slot as HELD
            earliest = now + timedelta(minutes=self.settings.min_booking_lead_minutes)
            claimed = await tx_db[C.APPOINTMENT_SLOTS].find_one_and_update(
                {"_id": new_slot["_id"], "status": SlotStatus.AVAILABLE.value, "start_at": {"$gte": earliest}},
                {"$set": {
                    "status": SlotStatus.HELD.value,
                    "appointment_id": appt["_id"],
                    "held_until": hold_until,
                    "block_source": None,
                    "blocked_by_availability_id": None,
                    "updated_at": now,
                }}
            )
            if claimed is None:
                raise ConflictError("The requested slot is no longer available. Please choose another slot.", code="slot_unavailable")

            # 2. Update appointment status to RESCHEDULE_REQUESTED
            updated = await tx_db[C.APPOINTMENTS].find_one_and_update(
                {"_id": appt["_id"], "status": S.CONFIRMED.value},
                {"$set": {
                    "status": S.RESCHEDULE_REQUESTED.value,
                    "status_reason": clean_reason,
                    "updated_at": now,
                }}
            )
            if updated is None:
                # Release the held slot
                await tx_db[C.APPOINTMENT_SLOTS].find_one_and_update(
                    {"_id": new_slot["_id"], "appointment_id": appt["_id"]},
                    {"$set": {"status": SlotStatus.AVAILABLE.value, "appointment_id": None, "held_until": None, "updated_at": now}}
                )
                raise ConflictError("This appointment was changed by someone else. Please refresh.", code="appointment_changed")

            # 3. Create ReschedulingRequest record
            req_id = str(uuid4())
            req_doc = ReschedulingRequest(
                id=req_id,
                appointment_id=appt["_id"],
                patient_id=actor.profile_id,
                patient_user_id=actor.user_id,
                patient_name=actor.name,
                doctor_id=doctor["_id"],
                doctor_user_id=doctor["user_id"],
                doctor_name=doctor["name"],
                hospital_id=new_slot["hospital_id"],
                department_id=new_slot["department_id"],
                old_slot_id=appt["slot_id"],
                requested_slot_id=new_slot["_id"],
                old_appointment_date=appt["appointment_date"],
                old_start_time=appt["start_time"],
                old_end_time=appt["end_time"],
                requested_appointment_date=new_slot["date"],
                requested_start_time=new_slot["start_time"],
                requested_end_time=new_slot["end_time"],
                reason=clean_reason,
                status=ReschedulingStatus.REQUESTED.value,
                doctor_response=None,
                created_at=now,
                updated_at=now,
                resolved_at=None,
            ).to_mongo()
            try:
                await tx_db[C.RESCHEDULING_REQUESTS].insert_one(req_doc)
            except DuplicateKeyError:
                raise ConflictError(
                    "A rescheduling request is already pending for this appointment.",
                    code="reschedule_already_pending",
                ) from None

            # 4. Record in appointment history
            hist_note = f"Reschedule requested from {_when(appt)} to {new_slot['date']} at {new_slot['start_time']}: {clean_reason}"
            await self._history(
                appt["_id"],
                S.CONFIRMED.value,
                S.RESCHEDULE_REQUESTED.value,
                actor,
                hist_note,
                previous_date=appt["appointment_date"],
                previous_time=appt["start_time"],
                new_date=new_slot["date"],
                new_time=new_slot["start_time"],
                metadata={"event": "RESCHEDULE_REQUESTED", "request_id": req_id},
                db=tx_db,
            )

            # 4b. Centralized audit log inside TX
            await AuditService(tx_db, self.settings).log_event(
                action=AuditAction.APPOINTMENT_RESCHEDULE_REQUESTED,
                entity_type=AuditEntityType.APPOINTMENT,
                entity_id=appt["_id"],
                actor_id=actor.user_id,
                actor_role=actor.role,
                hospital_id=new_slot["hospital_id"],
                description=f"Rescheduling requested from {_when(appt)} to {new_slot['date']} at {new_slot['start_time']}",
                metadata={
                    "reschedule_request_id": req_id,
                    "old_date": appt["appointment_date"],
                    "old_start_time": appt["start_time"],
                    "new_date": new_slot["date"],
                    "new_start_time": new_slot["start_time"],
                },
            )

            # 5. Notifications
            # Doctor
            await NotificationService(tx_db).notify(
                user_id=doctor["user_id"],
                type=NotificationType.RESCHEDULE_REQUESTED.value,
                title="Rescheduling request received",
                message=f"{actor.name} requested to move their appointment from {_when(appt)} to {new_slot['date']} at {new_slot['start_time']}. Reason: {clean_reason}",
                appointment_id=appt["_id"],
                action_url=f"/doctor/appointments/{appt['_id']}",
                data={"rescheduling_request_id": req_id},
            )
            # Patient
            await NotificationService(tx_db).notify(
                user_id=actor.user_id,
                type=NotificationType.RESCHEDULE_REQUESTED.value,
                title="Rescheduling request submitted",
                message=f"Your request to reschedule with Dr. {doctor['name']} to {new_slot['date']} at {new_slot['start_time']} has been submitted for approval.",
                appointment_id=appt["_id"],
                action_url=f"/appointments/{appt['_id']}",
                data={"rescheduling_request_id": req_id},
            )

        return updated

    async def approve_reschedule(self, actor: Actor, request_id: str, reason: str | None) -> dict:
        """Doctor approves a patient's rescheduling request.

        Atomically verifies requested slot, reassigns slot, releases old slot,
        updates appointment references and history, and notifies the patient.
        """
        if not actor.is_doctor:
            raise ForbiddenError("Only doctors can approve rescheduling requests", code="forbidden_role")

        req = await self.db[C.RESCHEDULING_REQUESTS].find_one({"_id": oid(request_id), "doctor_id": actor.profile_id})
        if req is None:
            raise NotFoundError("Rescheduling request not found", code="reschedule_request_not_found")
        if req["status"] != ReschedulingStatus.REQUESTED.value:
            raise ConflictError(f"This rescheduling request has already been {req['status'].lower()}.", code="request_already_resolved")

        appt = await self.get_for_actor(actor, req["appointment_id"])
        if appt["status"] != S.RESCHEDULE_REQUESTED.value:
            raise self._bad_transition(appt["status"], "approve reschedule")

        now = utcnow()
        async with self.db.transaction() as tx_db:
            # 1. Verify and promote the requested slot to BOOKED
            promoted = await tx_db[C.APPOINTMENT_SLOTS].find_one_and_update(
                {"_id": req["requested_slot_id"], "appointment_id": appt["_id"], "status": SlotStatus.HELD.value},
                {"$set": {"status": SlotStatus.BOOKED.value, "held_until": None, "updated_at": now}}
            )
            if promoted is None:
                # If hold expired, try direct booking if still available
                earliest = now + timedelta(minutes=self.settings.min_booking_lead_minutes)
                promoted = await tx_db[C.APPOINTMENT_SLOTS].find_one_and_update(
                    {"_id": req["requested_slot_id"], "status": SlotStatus.AVAILABLE.value, "start_at": {"$gte": earliest}},
                    {"$set": {"status": SlotStatus.BOOKED.value, "appointment_id": appt["_id"], "held_until": None, "updated_at": now}}
                )
            if promoted is None:
                raise ConflictError("The requested slot is no longer available.", code="slot_unavailable")

            # 2. Release original slot
            old_slot_id = appt["slot_id"]
            await tx_db[C.APPOINTMENT_SLOTS].find_one_and_update(
                {"_id": old_slot_id, "appointment_id": appt["_id"]},
                {"$set": {"status": SlotStatus.AVAILABLE.value, "appointment_id": None, "held_until": None, "updated_at": now}}
            )

            # 2b. Guard against patient overlapping active appointments before updating
            overlap_count = await tx_db[C.APPOINTMENTS].count_documents(
                {
                    "patient_id": appt["patient_id"],
                    "is_active": True,
                    "start_at": {"$lt": promoted["end_at"]},
                    "end_at": {"$gt": promoted["start_at"]},
                    "_id": {"$ne": appt["_id"]},
                }
            )
            if overlap_count:
                raise ConflictError(
                    "You already have an appointment that overlaps this time.",
                    code="patient_time_conflict",
                )

            # 3. Update appointment with new slot and restore CONFIRMED status
            try:
                updated = await tx_db[C.APPOINTMENTS].find_one_and_update(
                    {"_id": appt["_id"], "status": S.RESCHEDULE_REQUESTED.value},
                    {"$set": {
                        "slot_id": promoted["_id"],
                        "hospital_id": promoted["hospital_id"],
                        "department_id": promoted["department_id"],
                        "appointment_date": promoted["date"],
                        "start_time": promoted["start_time"],
                        "end_time": promoted["end_time"],
                        "start_at": promoted["start_at"],
                        "end_at": promoted["end_at"],
                        "status": S.CONFIRMED.value,
                        "is_active": True,
                        "status_reason": reason,
                        "reminder_sent": False,
                        "updated_at": now,
                    }}
                )
            except DuplicateKeyError:
                raise ConflictError(
                    "You already have an appointment that overlaps this time.",
                    code="patient_time_conflict",
                ) from None
            if updated is None:
                raise ConflictError("This appointment was changed by someone else. Please refresh.", code="appointment_changed")

            # 4. Update request status
            await tx_db[C.RESCHEDULING_REQUESTS].find_one_and_update(
                {"_id": req["_id"], "status": ReschedulingStatus.REQUESTED.value},
                {"$set": {
                    "status": ReschedulingStatus.APPROVED.value,
                    "doctor_response": reason,
                    "resolved_at": now,
                    "updated_at": now,
                }}
            )

            # 5. Record appointment history
            hist_note = f"Reschedule approved from {_when(appt)} to {_when(updated)}" + (f". Note: {reason}" if reason else "")
            await self._history(
                appt["_id"],
                S.RESCHEDULE_REQUESTED.value,
                S.CONFIRMED.value,
                actor,
                hist_note,
                previous_date=appt["appointment_date"],
                previous_time=appt["start_time"],
                new_date=updated["appointment_date"],
                new_time=updated["start_time"],
                metadata={"event": "RESCHEDULE_APPROVED", "request_id": req["_id"]},
                db=tx_db,
            )
            await AuditService(tx_db, self.settings).log_event(
                action=AuditAction.APPOINTMENT_RESCHEDULE_APPROVED,
                entity_type=AuditEntityType.APPOINTMENT,
                entity_id=appt["_id"],
                actor_id=actor.user_id,
                actor_role=actor.role,
                hospital_id=updated["hospital_id"],
                description=f"Rescheduling approved from {_when(appt)} to {_when(updated)}",
                metadata={"reschedule_request_id": req["_id"]},
            )

            # 6. Notify patient
            await NotificationService(tx_db).notify(
                user_id=appt["patient_user_id"],
                type=NotificationType.RESCHEDULE_APPROVED.value,
                title="Reschedule approved",
                message=f"Dr. {appt['doctor_name']} approved your rescheduling request. Your appointment is confirmed for {_when(updated)}.",
                appointment_id=appt["_id"],
                action_url=f"/appointments/{appt['_id']}",
                data={"rescheduling_request_id": req["_id"]},
            )

        # 7. Post-transaction: recover old slot via waitlist
        if appt["start_at"] > now:
            await self.recovery.on_slot_released(old_slot_id, exclude_patient_id=appt["patient_id"])
        await self.waitlist.mark_fulfilled(appt["patient_id"], promoted["_id"], appt["_id"])

        return updated

    async def reject_reschedule(self, actor: Actor, request_id: str, reason: str | None) -> dict:
        """Doctor rejects a patient's rescheduling request.

        The original appointment remains CONFIRMED in its original slot.
        The temporary reservation on the requested slot is released.
        Request updated to REJECTED, logged to history, and patient notified.
        """
        if not actor.is_doctor:
            raise ForbiddenError("Only doctors can reject rescheduling requests", code="forbidden_role")

        req = await self.db[C.RESCHEDULING_REQUESTS].find_one({"_id": oid(request_id), "doctor_id": actor.profile_id})
        if req is None:
            raise NotFoundError("Rescheduling request not found", code="reschedule_request_not_found")
        if req["status"] != ReschedulingStatus.REQUESTED.value:
            raise ConflictError(f"This rescheduling request has already been {req['status'].lower()}.", code="request_already_resolved")

        appt = await self.get_for_actor(actor, req["appointment_id"])
        now = utcnow()

        async with self.db.transaction() as tx_db:
            # 1. Release temporary held requested slot
            await tx_db[C.APPOINTMENT_SLOTS].find_one_and_update(
                {"_id": req["requested_slot_id"], "appointment_id": appt["_id"], "status": SlotStatus.HELD.value},
                {"$set": {"status": SlotStatus.AVAILABLE.value, "appointment_id": None, "held_until": None, "updated_at": now}}
            )

            # 2. Revert appointment status back to CONFIRMED
            updated = await tx_db[C.APPOINTMENTS].find_one_and_update(
                {"_id": appt["_id"], "status": S.RESCHEDULE_REQUESTED.value},
                {"$set": {
                    "status": S.CONFIRMED.value,
                    "updated_at": now,
                }}
            )
            if updated is None and appt["status"] == S.CONFIRMED.value:
                updated = appt
            elif updated is None:
                raise ConflictError("This appointment was changed by someone else. Please refresh.", code="appointment_changed")

            # 3. Update request status to REJECTED
            await tx_db[C.RESCHEDULING_REQUESTS].find_one_and_update(
                {"_id": req["_id"], "status": ReschedulingStatus.REQUESTED.value},
                {"$set": {
                    "status": ReschedulingStatus.REJECTED.value,
                    "doctor_response": reason,
                    "resolved_at": now,
                    "updated_at": now,
                }}
            )

            # 4. Insert history
            hist_note = f"Reschedule declined by Dr. {appt['doctor_name']}; original appointment retained for {_when(appt)}." + (f" Reason: {reason}" if reason else "")
            await self._history(
                appt["_id"],
                S.RESCHEDULE_REQUESTED.value,
                S.CONFIRMED.value,
                actor,
                hist_note,
                previous_date=req.get("requested_appointment_date"),
                previous_time=req.get("requested_start_time"),
                new_date=appt["appointment_date"],
                new_time=appt["start_time"],
                metadata={"event": "RESCHEDULE_REJECTED", "request_id": req["_id"]},
                db=tx_db,
            )
            await AuditService(tx_db, self.settings).log_event(
                action=AuditAction.APPOINTMENT_RESCHEDULE_REJECTED,
                entity_type=AuditEntityType.APPOINTMENT,
                entity_id=appt["_id"],
                actor_id=actor.user_id,
                actor_role=actor.role,
                hospital_id=appt["hospital_id"],
                description=f"Rescheduling request declined; original appointment kept on {_when(appt)}",
                metadata={"reschedule_request_id": req["_id"]},
            )

            # 5. Notify patient
            await NotificationService(tx_db).notify(
                user_id=appt["patient_user_id"],
                type=NotificationType.RESCHEDULE_REJECTED.value,
                title="Reschedule request declined",
                message=f"Dr. {appt['doctor_name']} declined your rescheduling request. Your original appointment on {_when(appt)} remains confirmed." + (f" Reason: {reason}" if reason else ""),
                appointment_id=appt["_id"],
                action_url=f"/appointments/{appt['_id']}",
                data={"rescheduling_request_id": req["_id"]},
            )

        return updated

    async def reschedule(self, actor: Actor, appointment_id: str, new_slot_id: str, reason: str | None) -> dict:
        """Move an appointment to another slot of the SAME doctor.

        * Patient: initiates a rescheduling request awaiting doctor approval (CONFIRMED -> RESCHEDULE_REQUESTED).
        * Doctor: directly moves a CONFIRMED appointment and keeps it CONFIRMED.
        """
        if actor.is_patient:
            return await self.request_reschedule(actor, appointment_id, new_slot_id, reason)

        # Doctor direct rescheduling
        appt = await self.get_for_actor(actor, appointment_id)
        if appt["status"] != S.CONFIRMED.value:
            raise self._bad_transition(appt["status"], "reschedule")
        now = utcnow()
        if appt["start_at"] <= now:
            raise ConflictError("The appointment has already started.", code="appointment_started")
        if oid(new_slot_id) == appt["slot_id"]:
            raise BadRequestError("The new slot is the same as the current slot", code="same_slot")

        new_slot, _doctor = await self._prepare_slot(new_slot_id, appt["consultation_type"], now, expected_doctor_id=appt["doctor_id"])
        await self._check_patient_capacity(appt["patient_id"], new_slot, exclude_id=appt["_id"], count_pending=False)

        async with self.db.transaction() as tx_db:
            # Claim new slot as BOOKED
            earliest = now + timedelta(minutes=self.settings.min_booking_lead_minutes)
            claimed = await tx_db[C.APPOINTMENT_SLOTS].find_one_and_update(
                {"_id": new_slot["_id"], "status": SlotStatus.AVAILABLE.value, "start_at": {"$gte": earliest}},
                {"$set": {"status": SlotStatus.BOOKED.value, "appointment_id": appt["_id"], "held_until": None, "updated_at": now}}
            )
            if claimed is None:
                raise ConflictError("This slot is no longer available. Please choose another slot.", code="slot_unavailable")

            old_slot_id = appt["slot_id"]
            # Release old slot
            await tx_db[C.APPOINTMENT_SLOTS].find_one_and_update(
                {"_id": old_slot_id, "appointment_id": appt["_id"]},
                {"$set": {"status": SlotStatus.AVAILABLE.value, "appointment_id": None, "held_until": None, "updated_at": now}}
            )

            try:
                updated = await tx_db[C.APPOINTMENTS].find_one_and_update(
                    {"_id": appt["_id"], "slot_id": appt["slot_id"], "status": S.CONFIRMED.value},
                    {"$set": {
                        "slot_id": new_slot["_id"],
                        "hospital_id": new_slot["hospital_id"],
                        "department_id": new_slot["department_id"],
                        "appointment_date": new_slot["date"],
                        "start_time": new_slot["start_time"],
                        "end_time": new_slot["end_time"],
                        "start_at": new_slot["start_at"],
                        "end_at": new_slot["end_at"],
                        "status": S.CONFIRMED.value,
                        "is_active": True,
                        "status_reason": reason,
                        "reminder_sent": False,
                        "updated_at": now,
                    }},
                )
            except DuplicateKeyError:
                raise ConflictError(
                    "You already have an appointment that overlaps this time.",
                    code="patient_time_conflict",
                ) from None
            if updated is None:
                raise ConflictError("This appointment was changed by someone else. Please refresh.", code="appointment_changed")

            note = f"Rescheduled from {_when(appt)} to {_when(updated)}" + (f": {reason}" if reason else "")
            await self._history(
                appt["_id"],
                appt["status"],
                S.CONFIRMED.value,
                actor,
                note,
                previous_date=appt["appointment_date"],
                previous_time=appt["start_time"],
                new_date=updated["appointment_date"],
                new_time=updated["start_time"],
                metadata={"event": "DOCTOR_RESCHEDULED"},
                db=tx_db,
            )
            await AuditService(tx_db, self.settings).log_event(
                action=AuditAction.APPOINTMENT_DIRECT_RESCHEDULED,
                entity_type=AuditEntityType.APPOINTMENT,
                entity_id=appt["_id"],
                actor_id=actor.user_id,
                actor_role=actor.role,
                hospital_id=updated["hospital_id"],
                description=f"Doctor rescheduled appointment from {_when(appt)} to {_when(updated)}",
                metadata={"old_date": appt["appointment_date"], "new_date": updated["appointment_date"]},
            )

            await NotificationService(tx_db).notify(
                user_id=appt["patient_user_id"],
                type=NotificationType.APPOINTMENT_RESCHEDULED.value,
                title="Appointment rescheduled",
                message=f"Dr. {appt['doctor_name']} moved your appointment from {_when(appt)} to {_when(updated)}." + (f" Reason: {reason}" if reason else ""),
                appointment_id=appt["_id"],
            )

        if appt["start_at"] > now:
            await self.recovery.on_slot_released(old_slot_id, exclude_patient_id=appt["patient_id"])
        await self.waitlist.mark_fulfilled(appt["patient_id"], new_slot["_id"], appt["_id"])
        return updated

    async def list_reschedule_requests_for_doctor(
        self, actor: Actor, params: PageParams, status: str | None = None
    ) -> tuple[list[dict], int]:
        if not actor.is_doctor:
            raise ForbiddenError("Only doctors can access their reschedule requests", code="forbidden_role")
        query: dict[str, Any] = {"doctor_id": actor.profile_id}
        if status:
            query["status"] = status
        items, total = await paginate(self.db[C.RESCHEDULING_REQUESTS], query, params, sort=[("created_at", -1), ("_id", -1)])
        hospital_ids = {i["hospital_id"] for i in items if i.get("hospital_id")}
        department_ids = {i["department_id"] for i in items if i.get("department_id")}
        hospitals = {h["_id"]: h["name"] for h in await self.db[C.HOSPITALS].find(
            {"_id": {"$in": list(hospital_ids)}}, {"name": 1}
        ).to_list(length=None)} if hospital_ids else {}
        departments = {d["_id"]: d["name"] for d in await self.db[C.DEPARTMENTS].find(
            {"_id": {"$in": list(department_ids)}}, {"name": 1}
        ).to_list(length=None)} if department_ids else {}
        for item in items:
            item["hospital_name"] = hospitals.get(item.get("hospital_id"))
            item["department_name"] = departments.get(item.get("department_id"))
        return items, total

    async def list_reschedule_requests_for_appointment(
        self, actor: Actor, appointment_id: str
    ) -> list[dict]:
        appt = await self.get_for_actor(actor, appointment_id)
        items = await self.db[C.RESCHEDULING_REQUESTS].find(
            {"appointment_id": appt["_id"]}
        ).sort([("created_at", -1), ("_id", -1)]).to_list(length=100)
        hospital_ids = {i["hospital_id"] for i in items if i.get("hospital_id")}
        department_ids = {i["department_id"] for i in items if i.get("department_id")}
        hospitals = {h["_id"]: h["name"] for h in await self.db[C.HOSPITALS].find(
            {"_id": {"$in": list(hospital_ids)}}, {"name": 1}
        ).to_list(length=None)} if hospital_ids else {}
        departments = {d["_id"]: d["name"] for d in await self.db[C.DEPARTMENTS].find(
            {"_id": {"$in": list(department_ids)}}, {"name": 1}
        ).to_list(length=None)} if department_ids else {}
        for item in items:
            item["hospital_name"] = hospitals.get(item.get("hospital_id"))
            item["department_name"] = departments.get(item.get("department_id"))
        return items

    async def get_reschedule_request(self, actor: Actor, request_id: str) -> dict:
        req = await self.db[C.RESCHEDULING_REQUESTS].find_one({"_id": oid(request_id)})
        if req is None:
            raise NotFoundError("Rescheduling request not found", code="reschedule_request_not_found")
        if actor.is_patient and req["patient_id"] != actor.profile_id:
            raise NotFoundError("Rescheduling request not found", code="reschedule_request_not_found")
        if actor.is_doctor and req["doctor_id"] != actor.profile_id:
            raise NotFoundError("Rescheduling request not found", code="reschedule_request_not_found")
        return req

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
