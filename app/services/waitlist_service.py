"""Intelligent Waitlist and Automatic Slot Reallocation Service.

Uses SQLAlchemy 2.0 async operations and PostgreSQL for:
1. Patient waitlist entries with live dynamic queue position calculation.
2. Slot recovery and automatic time-limited offer generation.
3. Concurrency-safe offer acceptance (creating an appointment awaiting doctor approval),
   offer decline, and automatic queue progression.
4. Background offer expiration with automatic reallocation to the next eligible patient.
5. Doctor and Admin waitlist monitoring statistics.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
import logging
import re
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    and_,
    asc,
    desc,
    false,
    func,
    insert,
    or_,
    select,
    update,
    delete,
)
from sqlalchemy.exc import IntegrityError

from app.core.config import MatchingConfig, Settings
from app.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.database.collections import C
from app.database.session import DuplicateKeyError, _normalize_row
from app.database.tables import (
    appointment_history_table as ht,
    appointment_slots_table as st,
    appointments_table as at,
    departments_table as dept_t,
    doctors_table as dt,
    hospitals_table as ht_hosp,
    patients_table as pt,
    users_table as ut,
    waitlist_entries_table as wt,
    waitlist_offers_table as ot,
)
from app.models.enums import (
    ACTIVE_APPOINTMENT_STATUSES,
    AppointmentStatus as S,
    AuditAction,
    AuditActorRole,
    AuditEntityType,
    ConsultationType,
    NotificationType,
    SlotStatus,
    WaitlistOfferStatus,
    WaitlistStatus,
)
from app.schemas.engagement import WaitlistCreate
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.utils.pagination import PageParams
from app.utils.text import normalize
from app.utils.time_utils import as_utc, date_to_str, time_to_str, today_local, utcnow

logger = logging.getLogger("nivara.waitlist")

_HEX24_RE = re.compile(r"^[0-9a-fA-F]{24}$")


def _parse_uuid(value: Any, *, allow_hex_miss: bool = False) -> str | None:
    if value is None:
        raise BadRequestError("Invalid identifier", code="invalid_id")
    s = str(value).strip()
    if not s:
        raise BadRequestError("Invalid identifier", code="invalid_id")
    try:
        return str(UUID(s))
    except (ValueError, AttributeError, TypeError):
        if allow_hex_miss and _HEX24_RE.fullmatch(s):
            return None
        raise BadRequestError("Invalid identifier", code="invalid_id") from None


def evaluate_entry(
    entry: dict, slot: dict, doctor: dict, existing_start_at: datetime | None, cfg: MatchingConfig, now: datetime
) -> dict[str, Any] | None:
    """Return ``{"score", "factors"}`` if the entry is eligible for the slot, else None."""
    w = cfg.waitlist_weights
    score, factors = 0.0, []

    def hit(key: str, label: str) -> None:
        nonlocal score
        score += w.get(key, 0.0)
        factors.append(label)

    if entry.get("doctor_id"):
        if str(entry["doctor_id"]) != str(slot["doctor_id"]):
            return None
        hit("doctor", "Preferred doctor")
    if entry.get("hospital_id"):
        if str(entry["hospital_id"]) != str(slot["hospital_id"]):
            return None
        hit("hospital", "Preferred hospital")
    if entry.get("department_id"):
        if str(entry["department_id"]) != str(slot["department_id"]):
            return None
        hit("department", "Preferred department")
    if entry.get("specialty_normalized"):
        if entry["specialty_normalized"] != doctor.get("specialty_normalized"):
            return None
        hit("specialty", "Specialty match")
    if not (entry["date_from"] <= slot["date"] <= entry["date_to"]):
        return None
    if entry.get("time_from") or entry.get("time_to"):
        if entry.get("time_from") and slot["start_time"] < entry["time_from"]:
            return None
        if entry.get("time_to") and slot["start_time"] >= entry["time_to"]:
            return None
        hit("time_window", "Within preferred time range")
    if entry.get("consultation_type"):
        if entry["consultation_type"] not in doctor.get("consultation_types", []):
            return None
        hit("consultation_type", "Consultation type offered")
    if entry.get("existing_appointment_id"):
        if existing_start_at is None or as_utc(slot["start_at"]) >= as_utc(existing_start_at):
            return None
        hit("earlier_than_existing", "Earlier than current appointment")
    waited = max(0, (as_utc(now) - as_utc(entry["created_at"])).days)
    if waited:
        cap = cfg.waiting_time_cap_days
        score += w.get("waiting_time", 0.0) * min(waited, cap) / cap
        factors.append(f"Waiting {waited} day(s)")
    return {"score": round(score, 2), "factors": factors}


class WaitlistService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.notifications = NotificationService(db)
        self.audit = AuditService(db, settings)

    # ------------------------------------------------------------------ SQLAlchemy connection helpers

    @asynccontextmanager
    async def _get_conn(self, for_write: bool = False):
        if getattr(self.db, "_conn", None) is not None:
            yield self.db._conn
        else:
            async with self.db.connect() as conn:
                yield conn
                if for_write:
                    await conn.commit()

    async def _fetch_one(self, stmt: Any, table_name: str) -> dict[str, Any] | None:
        async with self._get_conn() as conn:
            res = await conn.execute(stmt)
            row = res.mappings().first()
            if row is None:
                return None
            return _normalize_row(dict(row), table_name)

    async def _fetch_all(self, stmt: Any, table_name: str) -> list[dict[str, Any]]:
        async with self._get_conn() as conn:
            res = await conn.execute(stmt)
            return [_normalize_row(dict(r), table_name) for r in res.mappings().all()]

    async def _count(self, stmt: Any) -> int:
        async with self._get_conn() as conn:
            res = await conn.execute(stmt)
            return res.scalar_one() or 0

    async def _update_returning(self, stmt: Any, table_name: str) -> dict[str, Any] | None:
        async with self._get_conn(for_write=True) as conn:
            try:
                res = await conn.execute(stmt)
                row = res.mappings().first()
                if row is None:
                    return None
                return _normalize_row(dict(row), table_name)
            except IntegrityError as exc:
                raise DuplicateKeyError(str(exc)) from exc

    async def _execute_write(self, stmt: Any) -> int:
        async with self._get_conn(for_write=True) as conn:
            try:
                res = await conn.execute(stmt)
                return res.rowcount if res.rowcount is not None and res.rowcount >= 0 else 0
            except IntegrityError as exc:
                raise DuplicateKeyError(str(exc)) from exc

    # ------------------------------------------------------------------ dynamic queue position

    async def compute_queue_position(self, entry: dict) -> tuple[int, int]:
        """Compute fair and transparent queue position based on request creation timestamp.
        Returns (position, patients_ahead)."""
        if entry.get("status") != WaitlistStatus.ACTIVE.value:
            return (0, 0)

        clauses = [
            wt.c.status == WaitlistStatus.ACTIVE.value,
            wt.c.created_at < entry["created_at"],
        ]

        if entry.get("doctor_id"):
            clauses.append(wt.c.doctor_id == str(entry["doctor_id"]))
        elif entry.get("department_id"):
            clauses.append(wt.c.department_id == str(entry["department_id"]))
        elif entry.get("hospital_id"):
            clauses.append(wt.c.hospital_id == str(entry["hospital_id"]))
        elif entry.get("specialty_normalized"):
            clauses.append(wt.c.specialty_normalized == entry["specialty_normalized"])

        stmt = select(func.count()).select_from(wt).where(and_(*clauses))
        ahead = await self._count(stmt)
        return (ahead + 1, ahead)

    # ------------------------------------------------------------------ patient: waitlist entries

    async def create(self, patient: dict, payload: WaitlistCreate) -> dict:
        today = today_local(self.settings.app_timezone)
        if payload.date_to < today:
            raise BadRequestError("date_to is in the past", code="date_in_past")

        now = utcnow()

        # 1. Compatibility & Active status checks
        doctor_uuid = _parse_uuid(payload.doctor_id, allow_hex_miss=True) if payload.doctor_id else None
        hospital_uuid = _parse_uuid(payload.hospital_id, allow_hex_miss=True) if payload.hospital_id else None
        department_uuid = _parse_uuid(payload.department_id, allow_hex_miss=True) if payload.department_id else None
        existing_uuid = _parse_uuid(payload.existing_appointment_id, allow_hex_miss=True) if payload.existing_appointment_id else None

        if payload.doctor_id:
            if doctor_uuid is None:
                raise NotFoundError("Doctor not found or currently inactive", code="doctor_not_found")
            d_stmt = select(dt).where(and_(dt.c.id == doctor_uuid, dt.c.profile_status == "ACTIVE"))
            doctor = await self._fetch_one(d_stmt, C.DOCTORS)
            if not doctor:
                raise NotFoundError("Doctor not found or currently inactive", code="doctor_not_found")
            if payload.hospital_id and (hospital_uuid is None or hospital_uuid not in [str(h) for h in doctor.get("hospital_ids", [])]):
                raise BadRequestError("Selected doctor does not practice at the selected hospital", code="incompatible_hospital")
            if payload.department_id and (department_uuid is None or department_uuid not in [str(d) for d in doctor.get("department_ids", [])]):
                raise BadRequestError("Selected doctor does not belong to the selected department", code="incompatible_department")

        if payload.hospital_id:
            if hospital_uuid is None:
                raise NotFoundError("Hospital not found", code="hospital_not_found")
            h_stmt = select(ht_hosp.c.id).where(ht_hosp.c.id == hospital_uuid)
            if not await self._fetch_one(h_stmt, C.HOSPITALS):
                raise NotFoundError("Hospital not found", code="hospital_not_found")

        if payload.department_id:
            if department_uuid is None:
                raise NotFoundError("Department not found", code="department_not_found")
            dept_stmt = select(dept_t.c.id).where(dept_t.c.id == department_uuid)
            if not await self._fetch_one(dept_stmt, C.DEPARTMENTS):
                raise NotFoundError("Department not found", code="department_not_found")

        existing_id = None
        if payload.existing_appointment_id:
            if existing_uuid is None:
                raise BadRequestError("existing_appointment_id must be one of your active appointments", code="invalid_existing_appointment")
            appt_stmt = select(at).where(
                and_(
                    at.c.id == existing_uuid,
                    at.c.patient_id == patient["_id"],
                    at.c.status.in_([s.value for s in ACTIVE_APPOINTMENT_STATUSES]),
                )
            )
            existing = await self._fetch_one(appt_stmt, C.APPOINTMENTS)
            if existing is None:
                raise BadRequestError("existing_appointment_id must be one of your active appointments", code="invalid_existing_appointment")
            existing_id = str(existing["_id"])

        # 2. Check for duplicate active entry with identical criteria
        dup_clauses = [
            wt.c.patient_id == patient["_id"],
            wt.c.status == WaitlistStatus.ACTIVE.value,
            wt.c.date_from == date_to_str(payload.date_from),
            wt.c.date_to == date_to_str(payload.date_to),
        ]
        if payload.doctor_id:
            dup_clauses.append(wt.c.doctor_id == str(payload.doctor_id))
        else:
            dup_clauses.append(wt.c.doctor_id.is_(None))
        if payload.department_id:
            dup_clauses.append(wt.c.department_id == str(payload.department_id))
        else:
            dup_clauses.append(wt.c.department_id.is_(None))
        if payload.hospital_id:
            dup_clauses.append(wt.c.hospital_id == str(payload.hospital_id))
        else:
            dup_clauses.append(wt.c.hospital_id.is_(None))

        dup_check = await self._fetch_one(select(wt.c.id).where(and_(*dup_clauses)).limit(1), C.WAITLIST_ENTRIES)
        if dup_check:
            raise ConflictError("You already have an active waitlist entry matching these criteria.", code="duplicate_waitlist_entry")

        active_count = await self._count(
            select(func.count()).select_from(wt).where(
                and_(wt.c.patient_id == patient["_id"], wt.c.status == WaitlistStatus.ACTIVE.value)
            )
        )
        if active_count >= self.settings.waitlist_max_active_entries_per_patient:
            raise ConflictError("Too many active waitlist entries. Cancel one first.", code="waitlist_limit_reached")

        entry_id = str(uuid4())
        ins_stmt = insert(wt).values(
            id=entry_id,
            patient_id=patient["_id"],
            patient_user_id=patient["user_id"],
            doctor_id=str(payload.doctor_id) if payload.doctor_id else None,
            department_id=str(payload.department_id) if payload.department_id else None,
            hospital_id=str(payload.hospital_id) if payload.hospital_id else None,
            specialty=payload.specialty,
            specialty_normalized=normalize(payload.specialty) if payload.specialty else None,
            date_from=date_to_str(payload.date_from),
            date_to=date_to_str(payload.date_to),
            time_from=time_to_str(payload.time_from) if payload.time_from else None,
            time_to=time_to_str(payload.time_to) if payload.time_to else None,
            consultation_type=payload.consultation_type.value if payload.consultation_type else None,
            existing_appointment_id=existing_id,
            status=WaitlistStatus.ACTIVE.value,
            notified_slot_ids=[],
            fulfilled_appointment_id=None,
            created_at=now,
            updated_at=now,
        )
        await self._execute_write(ins_stmt)

        doc = await self.get(entry_id)
        pos, ahead = await self.compute_queue_position(doc)
        doc["queue_position"] = pos
        doc["patients_ahead"] = ahead

        # Notify patient of confirmation
        await self.notifications.notify(
            user_id=patient["user_id"],
            type=NotificationType.WAITLIST_SLOT_AVAILABLE.value,
            title="Waitlist registration confirmed",
            message=f"You have joined the waitlist for {doc.get('specialty') or 'your requested consultation'}. Your current queue position is #{pos}.",
            category="WAITLIST",
            action_url="/waitlist",
        )
        await self.audit.log_event(
            action=AuditAction.WAITLIST_JOINED,
            entity_type=AuditEntityType.WAITLIST_ENTRY,
            entity_id=entry_id,
            actor_id=patient["user_id"],
            actor_role=AuditActorRole.PATIENT,
            hospital_id=str(payload.hospital_id) if payload.hospital_id else None,
            description=f"Patient joined waitlist ({doc.get('date_from')} to {doc.get('date_to')})",
            metadata={"queue_position": pos, "specialty": doc.get("specialty")},
        )

        return doc

    async def get(self, entry_id: str) -> dict:
        entry_uuid = _parse_uuid(entry_id, allow_hex_miss=True)
        if entry_uuid is None:
            raise NotFoundError("Waitlist entry not found", code="waitlist_not_found")
        stmt = select(wt).where(wt.c.id == entry_uuid)
        doc = await self._fetch_one(stmt, C.WAITLIST_ENTRIES)
        if doc is None:
            raise NotFoundError("Waitlist entry not found", code="waitlist_not_found")
        return doc

    async def list_mine(
        self,
        patient_id: str,
        params: PageParams,
        status: WaitlistStatus | None,
        *,
        exclude_active: bool = False,
    ) -> tuple[list[dict], int]:
        clauses = [wt.c.patient_id == str(patient_id)]
        if status:
            clauses.append(wt.c.status == status.value)
        elif exclude_active:
            clauses.append(wt.c.status != WaitlistStatus.ACTIVE.value)

        total = await self._count(select(func.count()).select_from(wt).where(and_(*clauses)))
        stmt = (
            select(wt)
            .where(and_(*clauses))
            .order_by(desc(wt.c.created_at))
            .offset(params.offset)
            .limit(params.page_size)
        )
        items = await self._fetch_all(stmt, C.WAITLIST_ENTRIES)

        enriched: list[dict] = []
        for item in items:
            row = dict(item)
            if row.get("status") == WaitlistStatus.ACTIVE.value:
                pos, ahead = await self.compute_queue_position(row)
                row["queue_position"] = pos
                row["patients_ahead"] = ahead
            enriched.append(row)

        return enriched, total

    async def get_mine(self, patient_id: str, entry_id: str) -> dict:
        entry_uuid = _parse_uuid(entry_id, allow_hex_miss=True)
        if entry_uuid is None:
            raise NotFoundError("Waitlist entry not found", code="waitlist_not_found")
        stmt = select(wt).where(and_(wt.c.id == entry_uuid, wt.c.patient_id == str(patient_id)))
        doc = await self._fetch_one(stmt, C.WAITLIST_ENTRIES)
        if doc is None:
            raise NotFoundError("Waitlist entry not found", code="waitlist_not_found")
        res = dict(doc)
        if res.get("status") == WaitlistStatus.ACTIVE.value:
            pos, ahead = await self.compute_queue_position(res)
            res["queue_position"] = pos
            res["patients_ahead"] = ahead
        return res

    async def cancel(self, patient_id: str, entry_id: str) -> dict:
        entry_uuid = _parse_uuid(entry_id, allow_hex_miss=True)
        if entry_uuid is None:
            raise NotFoundError("Waitlist entry not found", code="waitlist_not_found")
        now = utcnow()
        stmt = (
            update(wt)
            .where(and_(wt.c.id == entry_uuid, wt.c.patient_id == str(patient_id), wt.c.status == WaitlistStatus.ACTIVE.value))
            .values(status=WaitlistStatus.CANCELLED.value, updated_at=now)
            .returning(wt)
        )
        doc = await self._update_returning(stmt, C.WAITLIST_ENTRIES)
        if doc is None:
            await self.get_mine(patient_id, entry_uuid)  # raises 404 if not found
            raise ConflictError("Only ACTIVE waitlist entries can be cancelled", code="waitlist_not_active")

        # Also cancel any pending offer for this entry and release its held slot
        off_stmt = (
            update(ot)
            .where(and_(ot.c.waitlist_entry_id == entry_uuid, ot.c.status == WaitlistOfferStatus.PENDING.value))
            .values(status=WaitlistOfferStatus.CANCELLED.value, updated_at=now)
            .returning(ot)
        )
        pending_offer = await self._update_returning(off_stmt, C.WAITLIST_OFFERS)
        if pending_offer:
            # Release slot safely
            slot_stmt = (
                update(st)
                .where(and_(st.c.id == pending_offer["slot_id"], st.c.status == SlotStatus.HELD.value))
                .values(status=SlotStatus.AVAILABLE.value, appointment_id=None, held_until=None, waitlist_offer_id=None, updated_at=now)
            )
            await self._execute_write(slot_stmt)
            # Progression: re-run slot recovery for next waitlist patient
            from app.services.slot_recovery_service import SlotRecoveryService
            await SlotRecoveryService(self.db, self.settings).on_slot_released(pending_offer["slot_id"], exclude_patient_id=patient_id)

        # Notify patient
        await self.notifications.notify(
            user_id=doc["patient_user_id"],
            type=NotificationType.WAITLIST_EXPIRED.value,
            title="Waitlist request cancelled",
            message="Your waitlist entry has been cancelled.",
            category="WAITLIST",
            action_url="/waitlist",
        )
        await self.audit.log_event(
            action=AuditAction.WAITLIST_CANCELLED,
            entity_type=AuditEntityType.WAITLIST_ENTRY,
            entity_id=entry_uuid,
            actor_id=doc["patient_user_id"],
            actor_role=AuditActorRole.PATIENT,
            hospital_id=doc.get("hospital_id"),
            description="Patient cancelled waitlist entry",
            metadata={"cancelled_pending_offer": bool(pending_offer)},
        )

        return doc

    async def mark_fulfilled(self, patient_id: str, slot_id: str, appointment_id: str) -> int:
        now = utcnow()
        stmt = (
            update(wt)
            .where(
                and_(
                    wt.c.patient_id == str(patient_id),
                    wt.c.status == WaitlistStatus.ACTIVE.value,
                )
            )
            .values(status=WaitlistStatus.FULFILLED.value, fulfilled_appointment_id=str(appointment_id), updated_at=now)
        )
        return await self._execute_write(stmt)

    async def expire_old(self) -> int:
        now = utcnow()
        today = date_to_str(today_local(self.settings.app_timezone))
        find_stmt = select(wt).where(and_(wt.c.status == WaitlistStatus.ACTIVE.value, wt.c.date_to < today))
        entries = await self._fetch_all(find_stmt, C.WAITLIST_ENTRIES)

        upd_stmt = (
            update(wt)
            .where(and_(wt.c.status == WaitlistStatus.ACTIVE.value, wt.c.date_to < today))
            .values(status=WaitlistStatus.EXPIRED.value, updated_at=now)
        )
        count = await self._execute_write(upd_stmt)
        for entry in entries:
            await self.notifications.notify(
                user_id=entry["patient_user_id"],
                type=NotificationType.WAITLIST_EXPIRED.value,
                title="Waitlist request expired",
                message=f"Your waitlist request for dates up to {entry['date_to']} has expired.",
                category="WAITLIST",
                action_url="/waitlist",
            )
            await self.audit.log_event(
                action=AuditAction.WAITLIST_EXPIRED,
                entity_type=AuditEntityType.WAITLIST_ENTRY,
                entity_id=entry["_id"],
                actor_id=None,
                actor_role=AuditActorRole.SYSTEM,
                hospital_id=entry.get("hospital_id"),
                description=f"Waitlist entry expired past date_to {entry['date_to']}",
            )
        return count

    # ------------------------------------------------------------------ slot offers & queue progression

    async def find_eligible(self, slot: dict, doctor: dict, exclude_patient_id: str | None = None) -> list[dict[str, Any]]:
        now = utcnow()
        clauses = [
            wt.c.status == WaitlistStatus.ACTIVE.value,
            wt.c.date_from <= slot["date"],
            wt.c.date_to >= slot["date"],
            or_(wt.c.doctor_id.is_(None), wt.c.doctor_id == str(slot["doctor_id"])),
            or_(wt.c.hospital_id.is_(None), wt.c.hospital_id == str(slot["hospital_id"])),
            or_(wt.c.department_id.is_(None), wt.c.department_id == str(slot["department_id"])),
        ]
        if doctor.get("specialty_normalized"):
            clauses.append(or_(wt.c.specialty_normalized.is_(None), wt.c.specialty_normalized == doctor["specialty_normalized"]))
        if exclude_patient_id:
            clauses.append(wt.c.patient_id != str(exclude_patient_id))

        stmt = select(wt).where(and_(*clauses)).order_by(asc(wt.c.created_at)).limit(500)
        candidates = await self._fetch_all(stmt, C.WAITLIST_ENTRIES)

        # Exclude candidates already notified for this slot
        slot_id_str = str(slot["_id"])
        candidates = [c for c in candidates if slot_id_str not in (c.get("notified_slot_ids") or [])]

        existing_ids = [c["existing_appointment_id"] for c in candidates if c.get("existing_appointment_id")]
        existing_start: dict[str, datetime] = {}
        if existing_ids:
            appt_stmt = select(at.c.id, at.c.start_at).where(and_(at.c.id.in_(existing_ids), at.c.is_active.is_(True)))
            async with self._get_conn() as conn:
                res = await conn.execute(appt_stmt)
                for r in res:
                    existing_start[str(r.id)] = r.start_at

        best: dict[str, dict[str, Any]] = {}
        for entry in candidates:
            result = evaluate_entry(
                entry, slot, doctor, existing_start.get(str(entry.get("existing_appointment_id"))), self.settings.matching_config, now
            )
            if result is None:
                continue
            row = {"entry": entry, **result}
            current = best.get(str(entry["patient_id"]))
            if (
                current is None
                or row["score"] > current["score"]
                or (row["score"] == current["score"] and as_utc(entry["created_at"]) < as_utc(current["entry"]["created_at"]))
            ):
                best[str(entry["patient_id"])] = row

        return sorted(best.values(), key=lambda r: (-r["score"], as_utc(r["entry"]["created_at"])))

    async def process_slot_for_waitlist(self, slot: dict, doctor: dict, exclude_patient_id: Any = None) -> dict[str, Any] | None:
        """Called whenever an appointment slot becomes AVAILABLE.
        Identifies the highest priority matching waitlist entry, reserves the slot as HELD,
        creates a time-limited WaitlistOffer, and alerts the patient.
        """
        now = utcnow()
        slot_id = str(slot["_id"])

        # 1. Ensure no active pending offer exists for this slot
        existing_pending = await self._fetch_one(
            select(ot).where(and_(ot.c.slot_id == slot_id, ot.c.status == WaitlistOfferStatus.PENDING.value)),
            C.WAITLIST_OFFERS,
        )
        if existing_pending:
            logger.info("Slot %s already has an active pending offer %s", slot_id, existing_pending["_id"])
            return existing_pending

        # 2. Find eligible active waitlist entries
        ranked = await self.find_eligible(slot, doctor, exclude_patient_id)
        if not ranked:
            return None

        # Filter out candidates who already have an active pending offer on another slot
        candidate = None
        for row in ranked:
            p_id = row["entry"]["patient_id"]
            active_offer = await self._fetch_one(
                select(ot.c.id).where(and_(ot.c.patient_id == str(p_id), ot.c.status == WaitlistOfferStatus.PENDING.value)),
                C.WAITLIST_OFFERS,
            )
            if not active_offer:
                candidate = row
                break

        if candidate is None:
            return None

        entry = candidate["entry"]
        offer_id = str(uuid4())
        expiry_minutes = self.settings.waitlist_offer_expiry_minutes
        expires_at = now + timedelta(minutes=expiry_minutes)
        now_utc = as_utc(now)
        expires_at_utc = as_utc(expires_at)

        # Perform reservation, offer creation, FK linkage, and notified_slot_ids update atomically
        # so circular FKs (waitlist_offers.slot_id <-> appointment_slots.waitlist_offer_id) stay valid.
        created_offer: dict[str, Any] | None = None
        try:
            async with self.db.transaction() as tx:
                tx_svc = WaitlistService(tx, self.settings)

                # 3. Concurrency-safe slot lock: transition AVAILABLE -> HELD before creating offer row
                slot_claim_stmt = (
                    update(st)
                    .where(and_(st.c.id == slot_id, st.c.status == SlotStatus.AVAILABLE.value))
                    .values(
                        status=SlotStatus.HELD.value,
                        held_until=expires_at,
                        waitlist_offer_id=None,
                        updated_at=now_utc,
                    )
                    .returning(st)
                )
                claimed_slot = await tx_svc._update_returning(slot_claim_stmt, C.APPOINTMENT_SLOTS)
                if not claimed_slot:
                    logger.info("Slot %s was claimed concurrently; aborting waitlist offer", slot_id)
                    return None

                # 4. Insert the WaitlistOffer record (slot_id FK exists)
                offer_ins_stmt = insert(ot).values(
                    id=offer_id,
                    waitlist_entry_id=entry["_id"],
                    patient_id=entry["patient_id"],
                    doctor_id=str(slot["doctor_id"]),
                    slot_id=slot_id,
                    status=WaitlistOfferStatus.PENDING.value,
                    expires_at=expires_at_utc,
                    responded_at=None,
                    reason=None,
                    appointment_id=None,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
                await tx_svc._execute_write(offer_ins_stmt)

                # 5. Link waitlist_offer_id onto the claimed HELD slot (offer_id FK now exists)
                await tx_svc._execute_write(
                    update(st)
                    .where(and_(st.c.id == slot_id, st.c.status == SlotStatus.HELD.value))
                    .values(waitlist_offer_id=offer_id, updated_at=now_utc)
                )

                # 6. Mark notified on the waitlist entry
                current_notified = list(entry.get("notified_slot_ids") or [])
                if slot_id not in current_notified:
                    current_notified.append(slot_id)
                notif_upd = (
                    update(wt)
                    .where(wt.c.id == entry["_id"])
                    .values(notified_slot_ids=current_notified, updated_at=now_utc)
                )
                await tx_svc._execute_write(notif_upd)
                created_offer = await tx_svc._fetch_one(select(ot).where(ot.c.id == offer_id), C.WAITLIST_OFFERS)
        except DuplicateKeyError:
            logger.info("Concurrent waitlist offer already registered for slot %s; aborting", slot_id)
            return None

        # 7. Real-time notification and audit trail outside transaction
        await self.notifications.notify(
            user_id=entry["patient_user_id"],
            type=NotificationType.WAITLIST_OFFER_AVAILABLE.value,
            title="Time-limited appointment slot offer",
            message=(
                f"A matching slot with Dr. {doctor['name']} on {slot['date']} at {slot['start_time']} "
                f"is temporarily reserved for you for {expiry_minutes} minutes. Accept the offer now to book."
            ),
            category="WAITLIST",
            action_url="/waitlist?tab=offers",
            data={
                "offer_id": offer_id,
                "slot_id": slot_id,
                "doctor_id": str(slot["doctor_id"]),
                "doctor_name": doctor["name"],
                "appointment_date": slot["date"],
                "start_time": slot["start_time"],
                "expires_at": expires_at_utc.isoformat(),
            },
        )

        logger.info("Generated waitlist offer %s for patient %s on slot %s", offer_id, entry["patient_id"], slot_id)
        await self.audit.log_event(
            action=AuditAction.WAITLIST_OFFER_CREATED,
            entity_type=AuditEntityType.WAITLIST_OFFER,
            entity_id=offer_id,
            actor_id=None,
            actor_role=AuditActorRole.SYSTEM,
            hospital_id=str(slot["hospital_id"]),
            description=f"Waitlist offer generated for slot on {slot['date']} at {slot['start_time']}",
            metadata={"slot_id": slot_id, "waitlist_entry_id": entry["_id"], "doctor_id": str(slot["doctor_id"])},
        )
        return created_offer

    async def accept_offer(self, patient: dict, offer_id: str, reason: str | None = None) -> dict:
        """Patient accepts a pending waitlist offer.
        Converts the held slot into a formal appointment request (REQUESTED status),
        preserving doctor approval, fulfills the waitlist entry, and marks the offer ACCEPTED.
        """
        now = utcnow()
        now_utc = as_utc(now)
        offer_uuid = _parse_uuid(offer_id, allow_hex_miss=True)
        if offer_uuid is None:
            raise NotFoundError("Waitlist offer not found", code="offer_not_found")
        offer_stmt = select(ot).where(and_(ot.c.id == offer_uuid, ot.c.patient_id == patient["_id"]))
        offer = await self._fetch_one(offer_stmt, C.WAITLIST_OFFERS)
        if not offer:
            raise NotFoundError("Waitlist offer not found", code="offer_not_found")

        if offer["status"] != WaitlistOfferStatus.PENDING.value:
            raise ConflictError(f"Offer is no longer pending (current status: {offer['status']})", code="offer_not_pending")

        if now_utc > as_utc(offer["expires_at"]):
            await self._expire_single_offer(offer, now)
            raise ConflictError("This slot offer has expired. The slot has been reallocated.", code="offer_expired")

        slot_stmt = select(st).where(st.c.id == offer["slot_id"])
        slot = await self._fetch_one(slot_stmt, C.APPOINTMENT_SLOTS)
        if not slot or slot["status"] != SlotStatus.HELD.value:
            raise ConflictError("The reserved slot is no longer available.", code="slot_unavailable")

        doc_stmt = select(dt).where(dt.c.id == offer["doctor_id"])
        doctor = await self._fetch_one(doc_stmt, C.DOCTORS)
        if not doctor or doctor.get("profile_status") != "ACTIVE":
            raise ConflictError("The doctor is no longer available for booking.", code="doctor_unavailable")

        # Resolve canonical patient name and consultation type
        patient_user = await self._fetch_one(select(ut.c.name).where(ut.c.id == patient["user_id"]), C.USERS)
        patient_name = (patient_user or {}).get("name") or patient.get("name") or "Patient"

        entry = await self._fetch_one(select(wt).where(wt.c.id == offer["waitlist_entry_id"]), C.WAITLIST_ENTRIES)
        valid_ctypes = {ct.value for ct in ConsultationType}
        doc_ctypes = [str(ct) for ct in (doctor.get("consultation_types") or []) if str(ct) in valid_ctypes]
        entry_ctype = entry.get("consultation_type") if entry else None
        if entry_ctype in valid_ctypes and (not doc_ctypes or entry_ctype in doc_ctypes):
            chosen_ctype = entry_ctype
        elif doc_ctypes:
            chosen_ctype = doc_ctypes[0]
        else:
            chosen_ctype = ConsultationType.FIRST_VISIT.value

        # Atomic PostgreSQL transaction
        async with self.db.transaction() as tx:
            tx_service = WaitlistService(tx, self.settings)

            # 0. Prevent double-booking a patient into overlapping active appointments
            overlap_stmt = (
                select(at.c.id)
                .where(
                    and_(
                        at.c.patient_id == patient["_id"],
                        at.c.is_active.is_(True),
                        at.c.start_at < slot["end_at"],
                        at.c.end_at > slot["start_at"],
                    )
                )
                .limit(1)
            )
            if await tx_service._fetch_one(overlap_stmt, C.APPOINTMENTS):
                raise ConflictError(
                    "You already have an appointment that overlaps this time.",
                    code="patient_time_conflict",
                )

            # 1. Atomic transition of offer from PENDING to ACCEPTED
            acc_stmt = (
                update(ot)
                .where(
                    and_(
                        ot.c.id == offer["_id"],
                        ot.c.status == WaitlistOfferStatus.PENDING.value,
                        ot.c.expires_at > now_utc,
                    )
                )
                .values(
                    status=WaitlistOfferStatus.ACCEPTED.value,
                    responded_at=now_utc,
                    reason=reason,
                    updated_at=now_utc,
                )
                .returning(ot)
            )
            accepted_offer = await tx_service._update_returning(acc_stmt, C.WAITLIST_OFFERS)
            if not accepted_offer:
                raise ConflictError("Offer has already been processed or expired.", code="offer_concurrency_conflict")

            # 2. Create formal appointment in REQUESTED status (preserving doctor approval)
            appt_id = str(uuid4())
            hold_until = min(now + timedelta(minutes=self.settings.request_hold_minutes), slot["start_at"])

            slot_upd_stmt = (
                update(st)
                .where(st.c.id == slot["_id"])
                .values(appointment_id=appt_id, held_until=hold_until, waitlist_offer_id=offer["_id"], updated_at=now_utc)
            )
            await tx_service._execute_write(slot_upd_stmt)

            appt_ins_stmt = insert(at).values(
                id=appt_id,
                patient_id=patient["_id"],
                patient_user_id=patient["user_id"],
                patient_name=patient_name,
                doctor_id=doctor["_id"],
                doctor_user_id=doctor["user_id"],
                doctor_name=doctor["name"],
                hospital_id=slot["hospital_id"],
                department_id=slot["department_id"],
                slot_id=slot["_id"],
                appointment_date=slot["date"],
                start_time=slot["start_time"],
                end_time=slot["end_time"],
                start_at=slot["start_at"],
                end_at=slot["end_at"],
                consultation_type=chosen_ctype,
                reason=reason or "Booked from waitlist slot offer",
                status=S.REQUESTED.value,
                is_active=True,
                status_reason=None,
                reminder_sent=False,
                created_at=now_utc,
                updated_at=now_utc,
            )
            try:
                await tx_service._execute_write(appt_ins_stmt)
            except DuplicateKeyError:
                raise ConflictError(
                    "You already have an appointment that overlaps this time.",
                    code="patient_time_conflict",
                ) from None

            # Link appointment_id to offer
            link_offer_stmt = (
                update(ot)
                .where(ot.c.id == offer["_id"])
                .values(appointment_id=appt_id, updated_at=now_utc)
            )
            await tx_service._execute_write(link_offer_stmt)

            # Fulfill the waitlist entry
            ful_entry_stmt = (
                update(wt)
                .where(wt.c.id == offer["waitlist_entry_id"])
                .values(status=WaitlistStatus.FULFILLED.value, fulfilled_appointment_id=appt_id, updated_at=now_utc)
            )
            await tx_service._execute_write(ful_entry_stmt)

            # Record appointment history
            hist_stmt = insert(ht).values(
                id=str(uuid4()),
                appointment_id=appt_id,
                previous_status=None,
                new_status=S.REQUESTED.value,
                changed_by=patient["user_id"],
                changed_by_role="PATIENT",
                reason=reason or "Requested via accepted waitlist offer",
                previous_date=None,
                previous_time=None,
                new_date=slot["date"],
                new_time=slot["start_time"],
                metadata={"event": "WAITLIST_OFFER_ACCEPTED", "offer_id": str(offer["_id"])},
                created_at=now_utc,
                updated_at=now_utc,
            )
            await tx_service._execute_write(hist_stmt)
            await AuditService(tx, self.settings).log_event(
                action=AuditAction.WAITLIST_OFFER_ACCEPTED,
                entity_type=AuditEntityType.WAITLIST_OFFER,
                entity_id=offer["_id"],
                actor_id=patient["user_id"],
                actor_role=AuditActorRole.PATIENT,
                hospital_id=slot["hospital_id"],
                description=f"Waitlist offer accepted; appointment request created for {slot['date']} at {slot['start_time']}",
                metadata={"appointment_id": appt_id, "slot_id": slot["_id"], "waitlist_entry_id": offer["waitlist_entry_id"]},
            )

        # Notify doctor and patient
        await self.notifications.notify(
            user_id=doctor["user_id"],
            type=NotificationType.APPOINTMENT_REQUESTED.value,
            title="Waitlist appointment request",
            message=f"{patient_name} accepted a waitlist slot offer for {slot['date']} at {slot['start_time']}. Please review and confirm.",
            appointment_id=appt_id,
            action_url=f"/doctor/appointments/{appt_id}",
        )
        await self.notifications.notify(
            user_id=patient["user_id"],
            type=NotificationType.WAITLIST_OFFER_ACCEPTED.value,
            title="Offer accepted — appointment requested",
            message=f"You accepted the slot offer for Dr. {doctor['name']} on {slot['date']} at {slot['start_time']}. Your appointment request is awaiting doctor confirmation.",
            appointment_id=appt_id,
            action_url=f"/appointments/{appt_id}",
        )

        appointment_doc = await self._fetch_one(select(at).where(at.c.id == appt_id), C.APPOINTMENTS)
        return {
            "offer": accepted_offer,
            "appointment": appointment_doc,
        }

    async def decline_offer(self, patient: dict, offer_id: str, reason: str | None = None) -> dict:
        """Patient declines a pending slot offer.
        Releases the HELD slot back to AVAILABLE and immediately triggers queue progression
        so the next eligible patient receives an offer.
        """
        now = utcnow()
        offer_uuid = _parse_uuid(offer_id, allow_hex_miss=True)
        if offer_uuid is None:
            raise NotFoundError("Waitlist offer not found", code="offer_not_found")
        offer = await self._fetch_one(
            select(ot).where(and_(ot.c.id == offer_uuid, ot.c.patient_id == patient["_id"])),
            C.WAITLIST_OFFERS,
        )
        if not offer:
            raise NotFoundError("Waitlist offer not found", code="offer_not_found")

        if offer["status"] != WaitlistOfferStatus.PENDING.value:
            raise ConflictError(f"Offer is no longer pending (current status: {offer['status']})", code="offer_not_pending")

        # Atomic conditional update to DECLINED
        now_utc = as_utc(now)
        dec_stmt = (
            update(ot)
            .where(and_(ot.c.id == offer["_id"], ot.c.status == WaitlistOfferStatus.PENDING.value))
            .values(status=WaitlistOfferStatus.DECLINED.value, responded_at=now_utc, reason=reason, updated_at=now_utc)
            .returning(ot)
        )
        declined_offer = await self._update_returning(dec_stmt, C.WAITLIST_OFFERS)
        if not declined_offer:
            raise ConflictError("Offer has already been processed or expired.", code="offer_concurrency_conflict")

        # Release the held slot back to AVAILABLE
        slot_rel_stmt = (
            update(st)
            .where(and_(st.c.id == offer["slot_id"], st.c.status == SlotStatus.HELD.value))
            .values(status=SlotStatus.AVAILABLE.value, appointment_id=None, held_until=None, waitlist_offer_id=None, updated_at=now_utc)
            .returning(st)
        )
        released_slot = await self._update_returning(slot_rel_stmt, C.APPOINTMENT_SLOTS)

        # Notify patient
        await self.notifications.notify(
            user_id=patient["user_id"],
            type=NotificationType.WAITLIST_OFFER_DECLINED.value,
            title="Slot offer declined",
            message="You declined the slot offer. You remain on the waitlist for future openings.",
            category="WAITLIST",
            action_url="/waitlist",
        )

        # Immediate Queue Progression: Offer the freed slot to the next eligible patient
        await self.audit.log_event(
            action=AuditAction.WAITLIST_OFFER_DECLINED,
            entity_type=AuditEntityType.WAITLIST_OFFER,
            entity_id=offer["_id"],
            actor_id=patient["user_id"],
            actor_role=AuditActorRole.PATIENT,
            hospital_id=released_slot.get("hospital_id") if released_slot else None,
            description="Patient declined waitlist slot offer",
            metadata={"slot_id": offer["slot_id"], "waitlist_entry_id": offer["waitlist_entry_id"]},
        )
        if released_slot:
            from app.services.slot_recovery_service import SlotRecoveryService
            await SlotRecoveryService(self.db, self.settings).on_slot_released(offer["slot_id"], exclude_patient_id=patient["_id"])

        return declined_offer

    async def _expire_single_offer(self, offer: dict, now: datetime) -> bool:
        """Expire a single pending offer atomically, release the held slot, notify the patient,
        and trigger queue progression for the freed slot."""
        now_utc = as_utc(now)
        exp_stmt = (
            update(ot)
            .where(and_(ot.c.id == offer["_id"], ot.c.status == WaitlistOfferStatus.PENDING.value))
            .values(status=WaitlistOfferStatus.EXPIRED.value, responded_at=now_utc, updated_at=now_utc)
            .returning(ot)
        )
        expired = await self._update_returning(exp_stmt, C.WAITLIST_OFFERS)
        if not expired:
            return False

        # Release slot only if still held
        slot_rel_stmt = (
            update(st)
            .where(and_(st.c.id == offer["slot_id"], st.c.status == SlotStatus.HELD.value))
            .values(status=SlotStatus.AVAILABLE.value, appointment_id=None, held_until=None, waitlist_offer_id=None, updated_at=now_utc)
            .returning(st)
        )
        released_slot = await self._update_returning(slot_rel_stmt, C.APPOINTMENT_SLOTS)

        # Notify patient
        patient = await self._fetch_one(select(pt).where(pt.c.id == offer["patient_id"]), C.PATIENTS)
        if patient:
            await self.notifications.notify(
                user_id=patient["user_id"],
                type=NotificationType.WAITLIST_EXPIRED.value,
                title="Slot offer expired",
                message="Your time-limited slot offer has expired and has been offered to the next waitlisted patient.",
                category="WAITLIST",
                action_url="/waitlist",
            )

        # Queue Progression: offer freed slot to next waitlist patient
        await self.audit.log_event(
            action=AuditAction.WAITLIST_OFFER_EXPIRED,
            entity_type=AuditEntityType.WAITLIST_OFFER,
            entity_id=offer["_id"],
            actor_id=None,
            actor_role=AuditActorRole.SYSTEM,
            hospital_id=released_slot.get("hospital_id") if released_slot else None,
            description="Waitlist slot offer expired and released",
            metadata={"slot_id": offer["slot_id"], "waitlist_entry_id": offer["waitlist_entry_id"]},
        )
        if released_slot:
            from app.services.slot_recovery_service import SlotRecoveryService
            await SlotRecoveryService(self.db, self.settings).on_slot_released(offer["slot_id"], exclude_patient_id=offer["patient_id"])
        return True

    async def expire_pending_offers(self) -> int:
        """Periodic background task that finds and expires stale pending offers."""
        now = utcnow()
        now_utc = as_utc(now)
        stmt = (
            select(ot)
            .where(and_(ot.c.status == WaitlistOfferStatus.PENDING.value, ot.c.expires_at <= now_utc))
            .limit(100)
        )
        stale_offers = await self._fetch_all(stmt, C.WAITLIST_OFFERS)
        count = 0
        for offer in stale_offers:
            try:
                if await self._expire_single_offer(offer, now):
                    count += 1
            except Exception:  # noqa: BLE001
                logger.exception("Failed to expire waitlist offer %s", offer.get("_id"))
        return count

    # ------------------------------------------------------------------ listing & stats

    async def list_offers_for_patient(self, patient_id: str, status: WaitlistOfferStatus | None = None) -> list[dict]:
        """Fetch all slot offers for a patient enriched with doctor, hospital, and slot details."""
        clauses = [ot.c.patient_id == str(patient_id)]
        if status:
            clauses.append(ot.c.status == status.value)

        stmt = (
            select(
                ot,
                dt.c.name.label("doctor_name"),
                dt.c.specialty.label("specialty"),
                st.c.date.label("appointment_date"),
                st.c.start_time.label("start_time"),
                st.c.end_time.label("end_time"),
                st.c.hospital_id.label("hospital_id"),
                st.c.department_id.label("department_id"),
                ht_hosp.c.name.label("hospital_name"),
                dept_t.c.name.label("department_name"),
            )
            .select_from(
                ot
                .join(dt, ot.c.doctor_id == dt.c.id, isouter=True)
                .join(st, ot.c.slot_id == st.c.id, isouter=True)
                .join(ht_hosp, st.c.hospital_id == ht_hosp.c.id, isouter=True)
                .join(dept_t, st.c.department_id == dept_t.c.id, isouter=True)
            )
            .where(and_(*clauses))
            .order_by(desc(ot.c.created_at))
            .limit(100)
        )
        return await self._fetch_all(stmt, C.WAITLIST_OFFERS)

    async def get_doctor_waitlist_stats(self, doctor_id: str) -> dict[str, int]:
        """Statistics for the authenticated doctor's waitlist."""
        d_id = str(doctor_id)
        today_str = date_to_str(today_local(self.settings.app_timezone))

        active_entries = await self._count(
            select(func.count()).select_from(wt).where(and_(wt.c.doctor_id == d_id, wt.c.status == WaitlistStatus.ACTIVE.value))
        )
        pending_offers = await self._count(
            select(func.count()).select_from(ot).where(and_(ot.c.doctor_id == d_id, ot.c.status == WaitlistOfferStatus.PENDING.value))
        )
        fulfilled_entries = await self._count(
            select(func.count()).select_from(wt).where(and_(wt.c.doctor_id == d_id, wt.c.status == WaitlistStatus.FULFILLED.value))
        )
        upcoming = await self._count(
            select(func.count()).select_from(at).where(
                and_(at.c.doctor_id == d_id, at.c.status == S.CONFIRMED.value, at.c.appointment_date >= today_str)
            )
        )
        return {
            "active_waitlist_patients": active_entries,
            "pending_offers": pending_offers,
            "fulfilled_entries": fulfilled_entries,
            "upcoming_waitlist_appointments": upcoming,
        }

    async def list_for_doctor(self, doctor_id: str, params: PageParams) -> tuple[list[dict], int]:
        """List active waitlist entries for a specific doctor."""
        d_id = str(doctor_id)
        clauses = [wt.c.doctor_id == d_id, wt.c.status == WaitlistStatus.ACTIVE.value]

        total = await self._count(select(func.count()).select_from(wt).where(and_(*clauses)))
        stmt = (
            select(wt)
            .where(and_(*clauses))
            .order_by(asc(wt.c.created_at))
            .offset(params.offset)
            .limit(params.page_size)
        )
        items = await self._fetch_all(stmt, C.WAITLIST_ENTRIES)
        enriched: list[dict] = []
        for item in items:
            row = dict(item)
            pos, ahead = await self.compute_queue_position(row)
            row["queue_position"] = pos
            row["patients_ahead"] = ahead
            enriched.append(row)
        return enriched, total

    async def get_admin_waitlist_stats(self, hospital_scope: list[str] | None = None) -> dict[str, Any]:
        """Platform-wide or hospital-scoped waitlist analytics for administrators."""
        if hospital_scope is not None:
            allowed = [str(h) for h in hospital_scope]
            if not allowed:
                return {
                    "total_active_entries": 0,
                    "pending_offers": 0,
                    "fulfilled_entries": 0,
                    "expired_offers": 0,
                    "hospital_breakdown": {},
                    "department_breakdown": {},
                    "doctor_breakdown": {},
                }
            clauses = [wt.c.hospital_id.in_(allowed)]
            pending_stmt = (
                select(func.count())
                .select_from(ot.join(st, ot.c.slot_id == st.c.id))
                .where(and_(ot.c.status == WaitlistOfferStatus.PENDING.value, st.c.hospital_id.in_(allowed)))
            )
            expired_stmt = (
                select(func.count())
                .select_from(ot.join(st, ot.c.slot_id == st.c.id))
                .where(and_(ot.c.status == WaitlistOfferStatus.EXPIRED.value, st.c.hospital_id.in_(allowed)))
            )
        else:
            clauses = []
            pending_stmt = (
                select(func.count())
                .select_from(ot)
                .where(ot.c.status == WaitlistOfferStatus.PENDING.value)
            )
            expired_stmt = (
                select(func.count())
                .select_from(ot)
                .where(ot.c.status == WaitlistOfferStatus.EXPIRED.value)
            )

        total_active = await self._count(
            select(func.count()).select_from(wt).where(and_(wt.c.status == WaitlistStatus.ACTIVE.value, *clauses))
        )
        fulfilled_entries = await self._count(
            select(func.count()).select_from(wt).where(and_(wt.c.status == WaitlistStatus.FULFILLED.value, *clauses))
        )
        pending_offers = await self._count(pending_stmt)
        expired_offers = await self._count(expired_stmt)

        # Breakdowns using PostgreSQL GROUP BY
        hosp_breakdown: dict[str, int] = {}
        dept_breakdown: dict[str, int] = {}
        doctor_breakdown: dict[str, int] = {}

        h_stmt = (
            select(wt.c.hospital_id, func.count().label("n"))
            .where(and_(wt.c.status == WaitlistStatus.ACTIVE.value, wt.c.hospital_id.isnot(None), *clauses))
            .group_by(wt.c.hospital_id)
        )
        async with self._get_conn() as conn:
            res = await conn.execute(h_stmt)
            for r in res:
                hosp_breakdown[str(r.hospital_id)] = r.n

        d_stmt = (
            select(wt.c.department_id, func.count().label("n"))
            .where(and_(wt.c.status == WaitlistStatus.ACTIVE.value, wt.c.department_id.isnot(None), *clauses))
            .group_by(wt.c.department_id)
        )
        async with self._get_conn() as conn:
            res = await conn.execute(d_stmt)
            for r in res:
                dept_breakdown[str(r.department_id)] = r.n

        doc_stmt = (
            select(wt.c.doctor_id, func.count().label("n"))
            .where(and_(wt.c.status == WaitlistStatus.ACTIVE.value, wt.c.doctor_id.isnot(None), *clauses))
            .group_by(wt.c.doctor_id)
        )
        async with self._get_conn() as conn:
            res = await conn.execute(doc_stmt)
            for r in res:
                doctor_breakdown[str(r.doctor_id)] = r.n

        return {
            "total_active_entries": total_active,
            "pending_offers": pending_offers,
            "fulfilled_entries": fulfilled_entries,
            "expired_offers": expired_offers,
            "hospital_breakdown": hosp_breakdown,
            "department_breakdown": dept_breakdown,
            "doctor_breakdown": doctor_breakdown,
        }

    async def list_for_admin(
        self,
        params: PageParams,
        hospital_id: str | None = None,
        department_id: str | None = None,
        doctor_id: str | None = None,
        status: WaitlistStatus | None = None,
        hospital_scope: list[str] | None = None,
    ) -> tuple[list[dict], int]:
        """Admin monitoring of waitlist entries with filters and strict hospital scoping."""
        clauses = []
        norm_hid = _parse_uuid(hospital_id, allow_hex_miss=True) if hospital_id else None
        if hospital_scope is not None:
            allowed = [str(h) for h in hospital_scope]
            if hospital_id:
                if norm_hid is None or norm_hid not in allowed:
                    raise ForbiddenError(
                        "You are not authorised to view waitlist entries for this hospital",
                        code="hospital_scope_forbidden",
                    )
                clauses.append(wt.c.hospital_id == norm_hid)
            elif not allowed:
                return [], 0
            else:
                clauses.append(wt.c.hospital_id.in_(allowed))
        elif hospital_id:
            if norm_hid is None:
                return [], 0
            clauses.append(wt.c.hospital_id == norm_hid)

        if department_id:
            dept_uuid = _parse_uuid(department_id, allow_hex_miss=True)
            if dept_uuid is None:
                return [], 0
            clauses.append(wt.c.department_id == dept_uuid)
        if doctor_id:
            doc_uuid = _parse_uuid(doctor_id, allow_hex_miss=True)
            if doc_uuid is None:
                return [], 0
            clauses.append(wt.c.doctor_id == doc_uuid)
        if status:
            clauses.append(wt.c.status == status.value)

        where_clause = and_(*clauses) if clauses else True
        total = await self._count(select(func.count()).select_from(wt).where(where_clause))
        stmt = (
            select(wt)
            .where(where_clause)
            .order_by(desc(wt.c.created_at))
            .offset(params.offset)
            .limit(params.page_size)
        )
        items = await self._fetch_all(stmt, C.WAITLIST_ENTRIES)
        enriched: list[dict] = []
        for item in items:
            row = dict(item)
            if row.get("status") == WaitlistStatus.ACTIVE.value:
                pos, ahead = await self.compute_queue_position(row)
                row["queue_position"] = pos
                row["patients_ahead"] = ahead
            enriched.append(row)
        return enriched, total
