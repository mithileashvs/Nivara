"""Platform & Scoped Administration Service (Phase 6 Enhanced)."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import and_, desc, false, func, or_, select

from app.core.config import Settings
from app.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.database.collections import C
from app.database.session import DuplicateKeyError, _normalize_row
from app.database.tables import (
    appointments_table as at,
    audit_logs_table as al_t,
    departments_table as dept_t,
    doctors_table as dt,
    hospitals_table as ht,
    patients_table as pt,
    users_table as ut,
)
from app.models.enums import (
    AuditAction,
    AuditActorRole,
    AuditEntityType,
    AuditSeverity,
    IntakeStatus,
    NotificationType,
    ProfileStatus,
    UserRole,
)
from app.models.users import User
from app.schemas.admin import AdminUserCreate
from app.services.audit_service import AuditService, _valid_uuid_str
from app.services.notification_service import NotificationService
from app.utils.object_id import oid, oids
from app.utils.pagination import PageParams
from app.utils.text import normalize
from app.utils.time_utils import utcnow


def require_platform_admin(user: dict) -> None:
    if user.get("managed_hospital_ids") is not None:
        raise ForbiddenError("This action requires a platform-wide administrator", code="platform_admin_required")


class AdminService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.audit = AuditService(db, settings)

    def _is_postgresql(self) -> bool:
        engine = getattr(self.db, "engine", None)
        return getattr(getattr(engine, "dialect", None), "name", "") == "postgresql"

    async def _validate_hospitals(self, hospital_ids: list[str] | None):
        if hospital_ids is None:
            return None
        ids = oids(hospital_ids)
        if await self.db[C.HOSPITALS].count_documents({"_id": {"$in": ids}}) != len(set(ids)):
            raise BadRequestError("One or more hospitals do not exist", code="invalid_hospital")
        return list(dict.fromkeys(ids))

    async def create_admin(self, payload: AdminUserCreate, *, actor: dict | None = None) -> dict:
        user = User(
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            role=UserRole.ADMIN,
            password_hash=hash_password(payload.password, self.settings.bcrypt_rounds),
            managed_hospital_ids=await self._validate_hospitals(payload.managed_hospital_ids),
        ).to_mongo()
        try:
            await self.db[C.USERS].insert_one(user)
        except DuplicateKeyError:
            raise ConflictError("An account with this email already exists", code="email_taken") from None
        await self.audit.log_event(
            action=AuditAction.ADMIN_CREATED,
            entity_type=AuditEntityType.USER,
            entity_id=user["_id"],
            actor_id=actor["_id"] if actor else None,
            actor_role=str(actor["role"]) if actor else AuditActorRole.ADMIN,
            severity=AuditSeverity.WARNING,
            description=f"Created administrator account for {user['email']}",
            metadata={
                "target_email": user["email"],
                "managed_hospital_ids": user.get("managed_hospital_ids"),
                "is_platform_admin": user.get("managed_hospital_ids") is None,
            },
        )
        return user

    async def list_users(
        self,
        params: PageParams,
        role: UserRole | None,
        is_active: bool | None,
        q: str | None = None,
    ) -> tuple[list[dict], int]:
        clauses: list[Any] = []
        if role:
            clauses.append(ut.c.role == role.value)
        if is_active is not None:
            clauses.append(ut.c.is_active.is_(is_active))
        if q and q.strip():
            term = f"%{q.strip()}%"
            clauses.append(or_(ut.c.name.ilike(term), ut.c.email.ilike(term)))

        where_clause = and_(*clauses) if clauses else True
        count_stmt = select(func.count()).select_from(ut).where(where_clause)
        data_stmt = (
            select(ut)
            .where(where_clause)
            .order_by(desc(ut.c.created_at), desc(ut.c.id))
            .offset(params.skip)
            .limit(params.page_size)
        )
        async with self.db.connect() as conn:
            total = (await conn.execute(count_stmt)).scalar_one() or 0
            rows = (await conn.execute(data_stmt)).mappings().all()

        return [_normalize_row(dict(r), C.USERS) for r in rows], int(total)

    async def get_user(self, user_id: str) -> dict:
        user = await self.db[C.USERS].find_one({"_id": oid(user_id)})
        if user is None:
            raise NotFoundError("User not found", code="user_not_found")
        return user

    async def get_user_detail(self, user_id: str) -> dict[str, Any]:
        """Detailed non-clinical view of a platform user + recent audit activity."""
        user = await self.get_user(user_id)
        profile_summary: dict[str, Any] = {}

        if user["role"] == UserRole.DOCTOR.value:
            doc = await self.db[C.DOCTORS].find_one({"user_id": user["_id"]})
            if doc:
                count = doc.get("rating_count", 0)
                profile_summary = {
                    "profile_id": doc["_id"],
                    "specialty": doc.get("specialty"),
                    "profile_status": doc.get("profile_status"),
                    "availability_status": doc.get("availability_status"),
                    "experience": doc.get("experience"),
                    "consultation_fee": doc.get("consultation_fee"),
                    "rating_average": round(doc.get("rating_sum", 0) / count, 2) if count else None,
                    "rating_count": count,
                    "hospital_ids": list(doc.get("hospital_ids") or []),
                    "department_ids": list(doc.get("department_ids") or []),
                }
        elif user["role"] == UserRole.PATIENT.value:
            pat = await self.db[C.PATIENTS].find_one({"user_id": user["_id"]})
            if pat:
                # Non-clinical identifier only; never expose health/clinical details
                profile_summary = {"profile_id": pat["_id"]}
        elif user["role"] == UserRole.ADMIN.value:
            scoped_ids = user.get("managed_hospital_ids")
            if scoped_ids:
                h_rows = await self.db[C.HOSPITALS].find({"_id": {"$in": scoped_ids}}).to_list(length=50)
                profile_summary = {
                    "managed_hospitals": [{"id": str(h["_id"]), "name": str(h["name"])} for h in h_rows]
                }

        recent_activity = await self.audit.list_user_activity(user["_id"], limit=25)
        return {
            "user": user,
            "profile_summary": profile_summary,
            "recent_activity": recent_activity,
        }

    async def set_active(
        self,
        actor: dict,
        user_id: str,
        is_active: bool,
        *,
        reason: str | None = None,
    ) -> dict:
        if actor["_id"] == oid(user_id):
            raise BadRequestError("You cannot change your own active status", code="cannot_modify_self")
        user = await self.get_user(user_id)
        prev_active = bool(user.get("is_active", True))
        clean_reason = reason.strip() if reason and reason.strip() else None
        updated = await self.db[C.USERS].find_one_and_update(
            {"_id": user["_id"]}, {"$set": {"is_active": is_active, "updated_at": utcnow()}}, return_document=True
        )
        if is_active:
            await NotificationService(self.db).notify(
                user_id=user["_id"],
                type=NotificationType.ACCOUNT_STATUS_CHANGED.value,
                title="Account activated",
                message="Your Nivara account has been reactivated by an administrator.",
                category="SYSTEM",
            )
        await self.audit.log_event(
            action=AuditAction.USER_ACTIVATED if is_active else AuditAction.USER_DEACTIVATED,
            entity_type=AuditEntityType.USER,
            entity_id=user["_id"],
            actor_id=actor["_id"],
            actor_role=str(actor["role"]),
            severity=AuditSeverity.INFO if is_active else AuditSeverity.WARNING,
            description=f"{'Reactivated' if is_active else 'Deactivated'} user account {user['email']}",
            metadata={
                "target_email": user["email"],
                "target_role": str(user["role"]),
                "previous_is_active": prev_active,
                "new_is_active": is_active,
                "reason": clean_reason,
            },
        )
        return updated

    async def set_scope(
        self,
        user_id: str,
        hospital_ids: list[str] | None,
        *,
        actor: dict | None = None,
    ) -> dict:
        user = await self.get_user(user_id)
        if user["role"] != UserRole.ADMIN:
            raise BadRequestError("Only admin users have a hospital scope", code="not_an_admin")
        previous_scope = user.get("managed_hospital_ids")
        scope = await self._validate_hospitals(hospital_ids)
        updated = await self.db[C.USERS].find_one_and_update(
            {"_id": user["_id"]}, {"$set": {"managed_hospital_ids": scope, "updated_at": utcnow()}}, return_document=True
        )
        await self.audit.log_event(
            action=AuditAction.ADMIN_SCOPE_UPDATED,
            entity_type=AuditEntityType.USER,
            entity_id=user["_id"],
            actor_id=actor["_id"] if actor else None,
            actor_role=str(actor["role"]) if actor else AuditActorRole.ADMIN,
            severity=AuditSeverity.WARNING,
            description=f"Updated hospital administration scope for {user['email']}",
            metadata={
                "target_email": user["email"],
                "previous_scope": previous_scope,
                "new_scope": scope,
            },
        )
        return updated

    # ------------------------------------------------------------------ enhanced doctor & hospital admin views

    async def list_doctors_for_admin(
        self,
        params: PageParams,
        *,
        profile_status: ProfileStatus | None = None,
        q: str | None = None,
    ) -> tuple[list[dict], int]:
        clauses: list[Any] = []
        if profile_status:
            clauses.append(dt.c.profile_status == profile_status.value)
        if q and q.strip():
            term = f"%{q.strip()}%"
            clauses.append(or_(dt.c.name.ilike(term), dt.c.specialty.ilike(term)))

        where_clause = and_(*clauses) if clauses else True
        count_stmt = select(func.count()).select_from(dt).where(where_clause)
        data_stmt = (
            select(dt)
            .where(where_clause)
            .order_by(desc(dt.c.created_at), desc(dt.c.id))
            .offset(params.skip)
            .limit(params.page_size)
        )
        async with self.db.connect() as conn:
            total = (await conn.execute(count_stmt)).scalar_one() or 0
            rows = (await conn.execute(data_stmt)).mappings().all()

        return [_normalize_row(dict(r), C.DOCTORS) for r in rows], int(total)

    async def list_doctor_verification(
        self,
        params: PageParams,
        *,
        profile_status: ProfileStatus | None = None,
        q: str | None = None,
    ) -> dict[str, Any]:
        clauses: list[Any] = []
        if profile_status:
            clauses.append(dt.c.profile_status == profile_status.value)
        if q and q.strip():
            term = f"%{q.strip()}%"
            clauses.append(or_(dt.c.name.ilike(term), dt.c.specialty.ilike(term), ut.c.email.ilike(term)))

        where_clause = and_(*clauses) if clauses else True
        base_join = dt.outerjoin(ut, dt.c.user_id == ut.c.id)

        count_stmt = select(func.count()).select_from(base_join).where(where_clause)
        data_stmt = (
            select(dt, ut.c.email.label("email"), ut.c.phone.label("phone"))
            .select_from(base_join)
            .where(where_clause)
            .order_by(desc(dt.c.created_at), desc(dt.c.id))
            .offset(params.skip)
            .limit(params.page_size)
        )
        status_counts_stmt = select(dt.c.profile_status, func.count().label("n")).group_by(dt.c.profile_status)

        async with self.db.connect() as conn:
            total = (await conn.execute(count_stmt)).scalar_one() or 0
            rows = (await conn.execute(data_stmt)).mappings().all()
            sc_rows = (await conn.execute(status_counts_stmt)).all()
            h_rows = (await conn.execute(select(ht.c.id, ht.c.name))).all()
            d_rows = (await conn.execute(select(dept_t.c.id, dept_t.c.name))).all()

            doc_ids = [str(r["id"]) for r in rows]
            latest_verif: dict[str, tuple[str | None, Any]] = {}
            if doc_ids:
                verif_stmt = (
                    select(al_t.c.entity_id, al_t.c.metadata, al_t.c.created_at)
                    .where(
                        and_(
                            al_t.c.entity_type == AuditEntityType.DOCTOR.value,
                            al_t.c.entity_id.in_(doc_ids),
                            al_t.c.action.in_([
                                AuditAction.DOCTOR_VERIFIED.value,
                                AuditAction.DOCTOR_SUSPENDED.value,
                                AuditAction.DOCTOR_SET_PENDING.value,
                            ]),
                        )
                    )
                    .order_by(desc(al_t.c.created_at))
                )
                for vr in (await conn.execute(verif_stmt)).all():
                    eid = str(vr.entity_id)
                    if eid in latest_verif:
                        continue
                    meta = vr.metadata or {}
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            meta = {}
                    latest_verif[eid] = (meta.get("reason") if isinstance(meta, dict) else None, vr.created_at)

        hosp_map = {str(r.id): str(r.name) for r in h_rows}
        dept_map = {str(r.id): str(r.name) for r in d_rows}
        counts_by_status = {str(r.profile_status): int(r.n) for r in sc_rows}

        items: list[dict[str, Any]] = []
        for raw in rows:
            doc = _normalize_row(dict(raw), C.DOCTORS)
            cnt = doc.get("rating_count", 0)
            h_ids = [str(x) for x in (doc.get("hospital_ids") or [])]
            d_ids = [str(x) for x in (doc.get("department_ids") or [])]
            verif_reason, verif_at = latest_verif.get(doc["id"], (None, None))
            items.append({
                "id": doc["id"],
                "user_id": str(doc["user_id"]),
                "name": doc["name"],
                "email": doc.get("email"),
                "phone": doc.get("phone"),
                "specialty": doc["specialty"],
                "experience": doc.get("experience", 0),
                "consultation_fee": doc.get("consultation_fee", 0.0),
                "consultation_types": list(doc.get("consultation_types") or []),
                "profile_status": str(doc["profile_status"]),
                "availability_status": str(doc["availability_status"]),
                "hospital_ids": h_ids,
                "department_ids": d_ids,
                "hospital_names": [hosp_map[hid] for hid in h_ids if hid in hosp_map],
                "department_names": [dept_map[did] for did in d_ids if did in dept_map],
                "latest_verification_reason": verif_reason,
                "latest_verification_at": verif_at,
                "rating_average": round(doc.get("rating_sum", 0) / cnt, 2) if cnt else None,
                "rating_count": cnt,
                "created_at": doc["created_at"],
                "updated_at": doc["updated_at"],
            })

        pending_cnt = counts_by_status.get(ProfileStatus.PENDING.value, 0)
        active_cnt = counts_by_status.get(ProfileStatus.ACTIVE.value, 0)
        suspended_cnt = counts_by_status.get(ProfileStatus.SUSPENDED.value, 0)

        return {
            "items": items,
            "total": int(total),
            "page": params.page,
            "page_size": params.page_size,
            "total_pages": ((int(total) + params.page_size - 1) // params.page_size) if total else 0,
            "counts": {
                "pending": pending_cnt,
                "active": active_cnt,
                "suspended": suspended_cnt,
                "total": pending_cnt + active_cnt + suspended_cnt,
            },
        }

    async def get_doctor_verification_history(self, doctor_id: str) -> list[dict[str, Any]]:
        clean_id = oid(doctor_id)
        doctor = await self.db[C.DOCTORS].find_one({"_id": clean_id})
        if doctor is None:
            raise NotFoundError("Doctor not found", code="doctor_not_found")
        return await self.audit.list_entity_history(
            entity_type=AuditEntityType.DOCTOR,
            entity_id=clean_id,
            actions=[
                AuditAction.DOCTOR_VERIFIED.value,
                AuditAction.DOCTOR_SUSPENDED.value,
                AuditAction.DOCTOR_SET_PENDING.value,
                AuditAction.DOCTOR_AFFILIATIONS_UPDATED.value,
            ],
            limit=50,
        )

    async def list_hospitals_for_admin(
        self,
        admin: dict,
        params: PageParams,
        *,
        q: str | None = None,
        city: str | None = None,
        intake_status: IntakeStatus | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses: list[Any] = []
        scope = admin.get("managed_hospital_ids")
        if scope is not None:
            allowed = [_valid_uuid_str(h) for h in scope if _valid_uuid_str(h)]
            clauses.append(ht.c.id.in_(allowed) if allowed else false())

        if q and q.strip():
            clauses.append(ht.c.name_normalized.ilike(f"%{normalize(q)}%"))
        if city and city.strip():
            city_norm = normalize(city)
            city_expr = (
                ht.c.location.op("->>")("city_normalized")
                if self._is_postgresql()
                else func.json_extract(ht.c.location, "$.city_normalized")
            )
            clauses.append(city_expr == city_norm)
        if intake_status:
            clauses.append(ht.c.appointment_intake_status == intake_status.value)

        where_clause = and_(*clauses) if clauses else True
        count_stmt = select(func.count()).select_from(ht).where(where_clause)
        data_stmt = (
            select(ht)
            .where(where_clause)
            .order_by(ht.c.name_normalized.asc(), ht.c.id.asc())
            .offset(params.skip)
            .limit(params.page_size)
        )

        async with self.db.connect() as conn:
            total = (await conn.execute(count_stmt)).scalar_one() or 0
            rows = [_normalize_row(dict(r), C.HOSPITALS) for r in (await conn.execute(data_stmt)).mappings().all()]
            hosp_ids = [r["id"] for r in rows]

            dept_counts: dict[str, int] = {}
            appt_counts: dict[str, int] = {}
            doc_counts: dict[str, int] = {}

            if hosp_ids:
                dc_rows = (
                    await conn.execute(
                        select(dept_t.c.hospital_id, func.count().label("n"))
                        .where(dept_t.c.hospital_id.in_(hosp_ids))
                        .group_by(dept_t.c.hospital_id)
                    )
                ).all()
                dept_counts = {str(r.hospital_id): int(r.n) for r in dc_rows}

                ac_rows = (
                    await conn.execute(
                        select(at.c.hospital_id, func.count().label("n"))
                        .where(and_(at.c.hospital_id.in_(hosp_ids), at.c.is_active.is_(True)))
                        .group_by(at.c.hospital_id)
                    )
                ).all()
                appt_counts = {str(r.hospital_id): int(r.n) for r in ac_rows}

                active_docs = (
                    await conn.execute(
                        select(dt.c.hospital_ids).where(dt.c.profile_status == ProfileStatus.ACTIVE.value)
                    )
                ).scalars().all()
                hosp_set = set(hosp_ids)
                for h_list in active_docs:
                    if isinstance(h_list, str):
                        try:
                            h_list = json.loads(h_list)
                        except Exception:
                            h_list = []
                    for hid in set(str(x) for x in (h_list or [])):
                        if hid in hosp_set:
                            doc_counts[hid] = doc_counts.get(hid, 0) + 1

        enriched: list[dict[str, Any]] = []
        for h in rows:
            hid = h["id"]
            enriched.append({
                "id": hid,
                "name": h["name"],
                "address": h["address"],
                "location": h.get("location") or {},
                "contact": h.get("contact") or {},
                "appointment_intake_status": str(h["appointment_intake_status"]),
                "department_ids": list(h.get("department_ids") or []),
                "department_count": dept_counts.get(hid, len(h.get("department_ids") or [])),
                "active_doctor_count": doc_counts.get(hid, 0),
                "active_appointments_count": appt_counts.get(hid, 0),
                "created_at": h["created_at"],
                "updated_at": h["updated_at"],
            })

        return enriched, int(total)

    # ------------------------------------------------------------------ statistics

    async def get_statistics(self) -> dict:
        """Basic platform counts. Every value is a live database count — never estimated or cached."""
        status_rows = await self.db[C.APPOINTMENTS].aggregate(
            [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
        ).to_list(length=None)
        by_status = {row["_id"]: row["n"] for row in status_rows}

        total_users = await self.db[C.USERS].count_documents({})
        total_patients = await self.db[C.PATIENTS].count_documents({})
        total_doctors = await self.db[C.DOCTORS].count_documents({})
        total_hospitals = await self.db[C.HOSPITALS].count_documents({})
        total_departments = await self.db[C.DEPARTMENTS].count_documents({})

        return {
            "total_users": total_users,
            "total_patients": total_patients,
            "total_doctors": total_doctors,
            "total_hospitals": total_hospitals,
            "total_departments": total_departments,
            "total_appointments": sum(by_status.values()),
            "requested_appointments": by_status.get("REQUESTED", 0),
            "confirmed_appointments": by_status.get("CONFIRMED", 0),
            "completed_appointments": by_status.get("COMPLETED", 0),
            "rejected_appointments": by_status.get("REJECTED", 0),
            "cancelled_appointments": by_status.get("CANCELLED", 0),
            "no_show_appointments": by_status.get("NO_SHOW", 0),
        }
