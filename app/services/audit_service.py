"""Centralized append-only Audit Logging and Security Activity Service (Phase 6).

Pure SQLAlchemy 2.0 Async + PostgreSQL / SQLite compatible Core implementation.
Guarantees:
- Strictly append-only (no update/delete operations exposed).
- Never stores passwords, password hashes, JWTs, secrets, file bytes, diagnoses,
  patient symptoms, or clinical notes.
- Enforces `managed_hospital_ids` at the SQL level for hospital-scoped administrators.
- Transaction-safe with SAVEPOINT support and anti-recursion guards so audit failures
  never disrupt primary clinical or administrative workflows.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import (
    String,
    and_,
    case,
    cast,
    desc,
    false,
    func,
    insert,
    or_,
    select,
)

from app.core.audit_context import audit_guard, get_request_meta, is_inside_audit
from app.core.config import Settings
from app.core.errors import BadRequestError, ForbiddenError, NotFoundError
from app.database.tables import (
    audit_logs_table as al_t,
    hospitals_table as ht,
    users_table as ut,
)
from app.models.enums import (
    AuditAction,
    AuditActorRole,
    AuditEntityType,
    AuditSeverity,
    NotificationType,
    UserRole,
)
from app.services.notification_service import NotificationService
from app.utils.pagination import PageParams

logger = logging.getLogger("nivara.audit")

# Keys stripped recursively at the audit boundary to guarantee zero clinical/secret leakage.
_FORBIDDEN_KEY_SUBSTRINGS = (
    "password",
    "passwd",
    "secret",
    "token",
    "jwt",
    "authorization",
    "cookie",
    "credential",
    "api_key",
    "service_role",
    "private_key",
    "clinical_note",
    "clinical_reason",
    "diagnosis",
    "diagnoses",
    "symptom",
    "prescription",
    "medication",
    "medical_history",
    "chief_complaint",
    "treatment_plan",
    "bearer",
    "file_bytes",
    "file_content",
    "raw_body",
)
_FORBIDDEN_EXACT_KEYS = frozenset({"notes", "content"})

# Security monitoring thresholds (real deterministic counts, never fabricated heuristics).
FAILED_LOGIN_BURST_THRESHOLD = 5
UNAUTHORIZED_SPIKE_THRESHOLD = 5
MEDICAL_UNAUTHORIZED_THRESHOLD = 2
HIGH_DOWNLOAD_VOLUME_THRESHOLD = 15
REALTIME_ALERT_LOOKBACK_MINUTES = 15
REALTIME_ALERT_COOLDOWN_MINUTES = 30

SECURITY_RELEVANT_ACTIONS = (
    AuditAction.AUTH_LOGIN_FAILED.value,
    AuditAction.AUTH_UNAUTHORIZED_ACCESS.value,
    AuditAction.AUTH_FORBIDDEN_ACCESS.value,
    AuditAction.MEDICAL_DOCUMENT_UNAUTHORIZED_ATTEMPT.value,
    AuditAction.USER_DEACTIVATED.value,
    AuditAction.USER_ACTIVATED.value,
    AuditAction.ADMIN_CREATED.value,
    AuditAction.ADMIN_SCOPE_UPDATED.value,
    AuditAction.DOCTOR_SUSPENDED.value,
    AuditAction.DOCTOR_VERIFIED.value,
    AuditAction.SECURITY_ALERT_TRIGGERED.value,
)


def _valid_uuid_str(val: Any) -> str | None:
    if not val:
        return None
    try:
        return str(UUID(str(val).strip()))
    except (ValueError, AttributeError, TypeError):
        return None


def _require_uuid_str(val: Any) -> str:
    parsed = _valid_uuid_str(val)
    if not parsed:
        raise BadRequestError("Invalid UUID identifier.", code="invalid_id")
    return parsed


def sanitize_metadata(value: Any, *, depth: int = 0) -> Any:
    """Recursively scrub sensitive credentials, tokens, file contents, and clinical free-text."""
    if depth > 4:
        return "[truncated]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, list):
        return [sanitize_metadata(item, depth=depth + 1) for item in value[:20]]
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for k, v in list(value.items())[:30]:
            key_str = str(k).strip()
            key_lower = key_str.lower()
            if key_lower in _FORBIDDEN_EXACT_KEYS or any(sub in key_lower for sub in _FORBIDDEN_KEY_SUBSTRINGS):
                continue
            cleaned[key_str[:80]] = sanitize_metadata(getattr(v, "value", v), depth=depth + 1)
        return cleaned
    return str(getattr(value, "value", value))[:500]


def _csv_cell(v: Any) -> str:
    if v is None:
        return ""
    s = str(v)
    if s and s.lstrip()[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


class AuditService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    @asynccontextmanager
    async def _get_conn(self, for_write: bool = False):
        if getattr(self.db, "_conn", None) is not None:
            yield self.db._conn
        else:
            async with self.db.connect() as conn:
                yield conn
                if for_write:
                    await conn.commit()

    def _is_postgresql(self) -> bool:
        engine = getattr(self.db, "engine", None)
        return getattr(getattr(engine, "dialect", None), "name", "") == "postgresql"

    def _local_date_bounds_to_utc(
        self, date_from: date | None, date_to: date | None
    ) -> tuple[datetime | None, datetime | None]:
        tz = ZoneInfo(self.settings.app_timezone)
        start_utc: datetime | None = None
        end_utc: datetime | None = None
        if date_from:
            start_local = datetime.combine(date_from, time.min, tzinfo=tz)
            start_utc = start_local.astimezone(timezone.utc)
        if date_to:
            end_local = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tz)
            end_utc = end_local.astimezone(timezone.utc)
        return start_utc, end_utc

    def _row_to_out(self, row: dict[str, Any]) -> dict[str, Any]:
        meta = row.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        actor_role = str(row.get("actor_role") or AuditActorRole.SYSTEM.value)
        actor_name = row.get("actor_name")
        if not actor_name and actor_role == AuditActorRole.SYSTEM.value:
            actor_name = "System"
        return {
            "id": str(row["id"]),
            "actor_id": str(row["actor_id"]) if row.get("actor_id") else None,
            "actor_role": actor_role,
            "actor_name": actor_name,
            "actor_email": row.get("actor_email"),
            "action": str(row["action"]),
            "entity_type": str(row["entity_type"]),
            "entity_id": row.get("entity_id"),
            "hospital_id": str(row["hospital_id"]) if row.get("hospital_id") else None,
            "hospital_name": row.get("hospital_name"),
            "severity": str(row.get("severity") or AuditSeverity.INFO.value),
            "description": str(row["description"]),
            "metadata": meta if isinstance(meta, dict) else {},
            "ip_address": row.get("ip_address"),
            "user_agent": row.get("user_agent"),
            "created_at": row["created_at"],
        }

    # ------------------------------------------------------------------ write path (append-only)

    async def log_event(
        self,
        *,
        action: AuditAction | str,
        entity_type: AuditEntityType | str,
        description: str,
        actor_id: str | None = None,
        actor_role: AuditActorRole | str | None = None,
        entity_id: str | None = None,
        hospital_id: str | None = None,
        severity: AuditSeverity | str = AuditSeverity.INFO,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        check_security_thresholds: bool = False,
    ) -> dict[str, Any] | None:
        """Append an audit record (application append-only; no update/delete APIs exposed)."""
        if is_inside_audit():
            return None

        req_meta = get_request_meta()
        resolved_ip = (ip_address or req_meta.get("ip_address") or None)
        resolved_ua = (user_agent or req_meta.get("user_agent") or None)

        sev_val = getattr(severity, "value", str(severity)).upper()
        if sev_val not in (AuditSeverity.INFO.value, AuditSeverity.WARNING.value, AuditSeverity.CRITICAL.value):
            sev_val = AuditSeverity.INFO.value

        act_val = getattr(action, "value", str(action)).upper()[:80]
        ent_type = getattr(entity_type, "value", str(entity_type)).upper()[:80]
        role_val = getattr(actor_role, "value", str(actor_role or AuditActorRole.SYSTEM.value)).upper()[:50]

        safe_meta = sanitize_metadata(metadata or {})
        if not isinstance(safe_meta, dict):
            safe_meta = {}

        log_id = str(uuid4())
        now = datetime.now(timezone.utc)
        values = {
            "id": log_id,
            "actor_id": _valid_uuid_str(actor_id),
            "actor_role": role_val,
            "action": act_val,
            "entity_type": ent_type,
            "entity_id": str(entity_id)[:120] if entity_id is not None else None,
            "hospital_id": _valid_uuid_str(hospital_id),
            "severity": sev_val,
            "description": str(description).strip()[:1000] or act_val,
            "metadata": safe_meta,
            "ip_address": str(resolved_ip)[:64] if resolved_ip else None,
            "user_agent": str(resolved_ua)[:500] if resolved_ua else None,
            "created_at": now,
        }

        with audit_guard():
            try:
                stmt = insert(al_t).values(**values)
                if getattr(self.db, "_conn", None) is not None:
                    # Inside an outer transaction: isolate via SAVEPOINT so an audit write issue
                    # never aborts the enclosing business transaction.
                    async with self.db._conn.begin_nested():
                        await self.db._conn.execute(stmt)
                else:
                    async with self.db.connect() as conn:
                        await conn.execute(stmt)
                        await conn.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to append centralized audit log action=%s: %s", act_val, exc)
                return None

            if check_security_thresholds and getattr(self.db, "_conn", None) is None:
                await self._evaluate_realtime_thresholds(
                    action=act_val,
                    ip_address=values["ip_address"],
                    actor_id=values["actor_id"],
                    hospital_id=values["hospital_id"],
                    now=now,
                )

        return values

    async def _evaluate_realtime_thresholds(
        self,
        *,
        action: str,
        ip_address: str | None,
        actor_id: str | None,
        hospital_id: str | None,
        now: datetime,
    ) -> None:
        """Emit non-noisy admin notifications when real SQL threshold breaches occur."""
        try:
            since = now - timedelta(minutes=REALTIME_ALERT_LOOKBACK_MINUTES)
            cooldown_since = now - timedelta(minutes=REALTIME_ALERT_COOLDOWN_MINUTES)

            alert_key: str | None = None
            alert_title: str | None = None
            alert_message: str | None = None
            alert_count = 0
            threshold = 0

            async with self.db.connect() as conn:
                if action == AuditAction.AUTH_LOGIN_FAILED.value and ip_address:
                    cnt = (
                        await conn.execute(
                            select(func.count())
                            .select_from(al_t)
                            .where(
                                and_(
                                    al_t.c.action == AuditAction.AUTH_LOGIN_FAILED.value,
                                    al_t.c.ip_address == ip_address,
                                    al_t.c.created_at >= since,
                                )
                            )
                        )
                    ).scalar_one() or 0
                    if cnt >= FAILED_LOGIN_BURST_THRESHOLD:
                        alert_key = f"FAILED_LOGIN_BURST:{ip_address}"
                        alert_count = cnt
                        threshold = FAILED_LOGIN_BURST_THRESHOLD
                        alert_title = "Security alert: Repeated failed logins"
                        alert_message = (
                            f"{cnt} failed login attempts detected from IP {ip_address} "
                            f"within the last {REALTIME_ALERT_LOOKBACK_MINUTES} minutes."
                        )

                elif action in (
                    AuditAction.AUTH_UNAUTHORIZED_ACCESS.value,
                    AuditAction.AUTH_FORBIDDEN_ACCESS.value,
                ) and ip_address:
                    cnt = (
                        await conn.execute(
                            select(func.count())
                            .select_from(al_t)
                            .where(
                                and_(
                                    al_t.c.action.in_([
                                        AuditAction.AUTH_UNAUTHORIZED_ACCESS.value,
                                        AuditAction.AUTH_FORBIDDEN_ACCESS.value,
                                    ]),
                                    al_t.c.ip_address == ip_address,
                                    al_t.c.created_at >= since,
                                )
                            )
                        )
                    ).scalar_one() or 0
                    if cnt >= UNAUTHORIZED_SPIKE_THRESHOLD:
                        alert_key = f"UNAUTHORIZED_SPIKE:{ip_address}"
                        alert_count = cnt
                        threshold = UNAUTHORIZED_SPIKE_THRESHOLD
                        alert_title = "Security alert: Repeated unauthorized access attempts"
                        alert_message = (
                            f"{cnt} unauthorized/forbidden access attempts detected from IP {ip_address} "
                            f"within the last {REALTIME_ALERT_LOOKBACK_MINUTES} minutes."
                        )

                elif action == AuditAction.MEDICAL_DOCUMENT_UNAUTHORIZED_ATTEMPT.value:
                    cnt = (
                        await conn.execute(
                            select(func.count())
                            .select_from(al_t)
                            .where(
                                and_(
                                    al_t.c.action == AuditAction.MEDICAL_DOCUMENT_UNAUTHORIZED_ATTEMPT.value,
                                    al_t.c.created_at >= since,
                                )
                            )
                        )
                    ).scalar_one() or 0
                    if cnt >= MEDICAL_UNAUTHORIZED_THRESHOLD:
                        alert_key = "MEDICAL_DOC_UNAUTHORIZED_SPIKE"
                        alert_count = cnt
                        threshold = MEDICAL_UNAUTHORIZED_THRESHOLD
                        alert_title = "Security alert: Unauthorized medical document attempts"
                        alert_message = (
                            f"{cnt} unauthorized medical document access attempts were blocked "
                            f"in the last {REALTIME_ALERT_LOOKBACK_MINUTES} minutes."
                        )

                elif action == AuditAction.MEDICAL_DOCUMENT_DOWNLOADED.value and actor_id:
                    cnt = (
                        await conn.execute(
                            select(func.count())
                            .select_from(al_t)
                            .where(
                                and_(
                                    al_t.c.action == AuditAction.MEDICAL_DOCUMENT_DOWNLOADED.value,
                                    al_t.c.actor_id == actor_id,
                                    al_t.c.created_at >= since,
                                )
                            )
                        )
                    ).scalar_one() or 0
                    if cnt >= HIGH_DOWNLOAD_VOLUME_THRESHOLD:
                        alert_key = f"HIGH_DOC_DOWNLOAD:{actor_id}"
                        alert_count = cnt
                        threshold = HIGH_DOWNLOAD_VOLUME_THRESHOLD
                        alert_title = "Security alert: High medical document download volume"
                        alert_message = (
                            f"An account recorded {cnt} medical document downloads "
                            f"within the last {REALTIME_ALERT_LOOKBACK_MINUTES} minutes."
                        )

                if not alert_key:
                    return

                # Check cooldown to avoid spamming notifications
                recent_alerts = (
                    await conn.execute(
                        select(al_t.c.metadata)
                        .where(
                            and_(
                                al_t.c.action == AuditAction.SECURITY_ALERT_TRIGGERED.value,
                                al_t.c.created_at >= cooldown_since,
                            )
                        )
                        .limit(50)
                    )
                ).scalars().all()
                for m in recent_alerts:
                    if isinstance(m, str):
                        try:
                            m = json.loads(m)
                        except Exception:
                            m = {}
                    if isinstance(m, dict) and m.get("alert_key") == alert_key:
                        return

                # Record alert trigger event directly
                await conn.execute(
                    insert(al_t).values(
                        id=str(uuid4()),
                        actor_id=None,
                        actor_role=AuditActorRole.SYSTEM.value,
                        action=AuditAction.SECURITY_ALERT_TRIGGERED.value,
                        entity_type=AuditEntityType.SYSTEM.value,
                        entity_id=None,
                        hospital_id=hospital_id,
                        severity=AuditSeverity.CRITICAL.value,
                        description=alert_message or alert_title,
                        metadata={
                            "alert_key": alert_key,
                            "count": alert_count,
                            "threshold": threshold,
                            "source_ip": ip_address,
                        },
                        ip_address=ip_address,
                        user_agent=None,
                        created_at=now,
                    )
                )
                await conn.commit()

                # Notify active platform administrators (hospital admins are excluded from platform-wide alerts)
                admin_rows = (
                    await conn.execute(
                        select(ut.c.id, ut.c.managed_hospital_ids).where(
                            and_(
                                ut.c.role == UserRole.ADMIN.value,
                                ut.c.is_active.is_(True),
                            )
                        )
                    )
                ).all()
                admin_ids = [
                    str(r.id)
                    for r in admin_rows
                    if r.managed_hospital_ids is None or r.managed_hospital_ids == "null"
                ]

            notif = NotificationService(self.db)
            for aid in admin_ids:
                await notif.notify(
                    user_id=str(aid),
                    type=NotificationType.SECURITY_ALERT.value,
                    title=alert_title or "Security threshold exceeded",
                    message=alert_message or "Review the Security Activity dashboard for details.",
                    category="SYSTEM",
                    action_url="/admin/security",
                    data={"alert_key": alert_key, "count": alert_count, "threshold": threshold},
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Security threshold evaluation skipped: %s", exc)

    # ------------------------------------------------------------------ query & scope helpers

    def _scope_clauses(self, admin: dict, hospital_id: str | None = None) -> list[Any]:
        clauses: list[Any] = []
        scope = admin.get("managed_hospital_ids")

        norm_hid = _require_uuid_str(hospital_id) if hospital_id else None
        if scope is not None:
            allowed = [_valid_uuid_str(h) for h in scope if _valid_uuid_str(h)]
            if norm_hid is not None:
                if norm_hid not in allowed:
                    raise ForbiddenError(
                        "You are not authorised to view audit logs for this hospital.",
                        code="hospital_scope_forbidden",
                    )
                clauses.append(al_t.c.hospital_id == norm_hid)
            elif not allowed:
                clauses.append(false())
            else:
                clauses.append(al_t.c.hospital_id.in_(allowed))
        elif norm_hid is not None:
            clauses.append(al_t.c.hospital_id == norm_hid)

        return clauses

    def _build_filter_clauses(
        self,
        admin: dict,
        *,
        q: str | None = None,
        actor_role: str | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        hospital_id: str | None = None,
        severity: str | None = None,
        actor_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Any]:
        clauses = self._scope_clauses(admin, hospital_id=hospital_id)

        if actor_role and actor_role.strip():
            clauses.append(al_t.c.actor_role == actor_role.strip().upper())

        if action and action.strip():
            actions = [a.strip().upper() for a in action.split(",") if a.strip()]
            if len(actions) == 1:
                clauses.append(al_t.c.action == actions[0])
            elif actions:
                clauses.append(al_t.c.action.in_(actions))

        if entity_type and entity_type.strip():
            clauses.append(al_t.c.entity_type == entity_type.strip().upper())

        if entity_id and entity_id.strip():
            clauses.append(al_t.c.entity_id == entity_id.strip())

        if severity and severity.strip():
            clauses.append(al_t.c.severity == severity.strip().upper())

        if actor_id and actor_id.strip():
            clauses.append(al_t.c.actor_id == _require_uuid_str(actor_id))

        start_utc, end_utc = self._local_date_bounds_to_utc(date_from, date_to)
        if start_utc is not None:
            clauses.append(al_t.c.created_at >= start_utc)
        if end_utc is not None:
            clauses.append(al_t.c.created_at < end_utc)

        if q and q.strip():
            term = f"%{q.strip()}%"
            meta_attempted_email = (
                al_t.c.metadata.op("->>")("attempted_email")
                if self._is_postgresql()
                else func.json_extract(al_t.c.metadata, "$.attempted_email")
            )
            clauses.append(
                or_(
                    ut.c.name.ilike(term),
                    ut.c.email.ilike(term),
                    al_t.c.description.ilike(term),
                    al_t.c.action.ilike(term),
                    al_t.c.entity_id.ilike(term),
                    al_t.c.ip_address.ilike(term),
                    meta_attempted_email.ilike(term),
                )
            )

        return clauses

    def _joined_select(self):
        return (
            select(
                al_t,
                ut.c.name.label("actor_name"),
                ut.c.email.label("actor_email"),
                ht.c.name.label("hospital_name"),
            )
            .select_from(
                al_t.outerjoin(ut, al_t.c.actor_id == ut.c.id).outerjoin(ht, al_t.c.hospital_id == ht.c.id)
            )
        )

    async def list_audit_logs(
        self,
        admin: dict,
        params: PageParams,
        *,
        q: str | None = None,
        actor_role: str | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        hospital_id: str | None = None,
        severity: str | None = None,
        actor_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses = self._build_filter_clauses(
            admin,
            q=q,
            actor_role=actor_role,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            hospital_id=hospital_id,
            severity=severity,
            actor_id=actor_id,
            date_from=date_from,
            date_to=date_to,
        )
        where_clause = and_(*clauses) if clauses else True

        count_stmt = (
            select(func.count())
            .select_from(al_t.outerjoin(ut, al_t.c.actor_id == ut.c.id))
            .where(where_clause)
        )
        data_stmt = (
            self._joined_select()
            .where(where_clause)
            .order_by(desc(al_t.c.created_at), desc(al_t.c.id))
            .offset(params.skip)
            .limit(params.page_size)
        )

        async with self._get_conn() as conn:
            total = (await conn.execute(count_stmt)).scalar_one() or 0
            rows = (await conn.execute(data_stmt)).mappings().all()

        return [self._row_to_out(dict(r)) for r in rows], int(total)

    async def get_audit_log(self, admin: dict, log_id: str) -> dict[str, Any]:
        clean_id = _require_uuid_str(log_id)
        stmt = self._joined_select().where(al_t.c.id == clean_id).limit(1)
        async with self._get_conn() as conn:
            row = (await conn.execute(stmt)).mappings().first()

        if row is None:
            raise NotFoundError("Audit log entry not found", code="audit_log_not_found")

        item = self._row_to_out(dict(row))
        scope = admin.get("managed_hospital_ids")
        if scope is not None:
            allowed = [_valid_uuid_str(h) for h in scope if _valid_uuid_str(h)]
            if not item.get("hospital_id") or item["hospital_id"] not in allowed:
                raise ForbiddenError(
                    "You are not authorised to view this audit log entry.",
                    code="hospital_scope_forbidden",
                )
        return item

    async def export_audit_logs_csv(
        self,
        admin: dict,
        *,
        q: str | None = None,
        actor_role: str | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        hospital_id: str | None = None,
        severity: str | None = None,
        actor_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        max_rows: int = 5000,
    ) -> str:
        clauses = self._build_filter_clauses(
            admin,
            q=q,
            actor_role=actor_role,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            hospital_id=hospital_id,
            severity=severity,
            actor_id=actor_id,
            date_from=date_from,
            date_to=date_to,
        )
        where_clause = and_(*clauses) if clauses else True
        stmt = (
            self._joined_select()
            .where(where_clause)
            .order_by(desc(al_t.c.created_at), desc(al_t.c.id))
            .limit(max_rows)
        )
        async with self._get_conn() as conn:
            rows = [self._row_to_out(dict(r)) for r in (await conn.execute(stmt)).mappings().all()]

        buf = io.StringIO()
        buf.write("\ufeff")
        writer = csv.writer(buf)
        writer.writerow([
            "Timestamp (UTC)",
            "Severity",
            "Action",
            "Actor Role",
            "Actor Name",
            "Actor Email",
            "Entity Type",
            "Entity ID",
            "Hospital",
            "IP Address",
            "Description",
            "Metadata",
        ])
        for item in rows:
            ts = item["created_at"].isoformat() if hasattr(item["created_at"], "isoformat") else str(item["created_at"])
            writer.writerow([
                _csv_cell(ts),
                _csv_cell(item["severity"]),
                _csv_cell(item["action"]),
                _csv_cell(item["actor_role"]),
                _csv_cell(item.get("actor_name") or ""),
                _csv_cell(item.get("actor_email") or ""),
                _csv_cell(item["entity_type"]),
                _csv_cell(item.get("entity_id") or ""),
                _csv_cell(item.get("hospital_name") or ""),
                _csv_cell(item.get("ip_address") or ""),
                _csv_cell(item["description"]),
                _csv_cell(json.dumps(item.get("metadata") or {}, ensure_ascii=False)),
            ])
        return buf.getvalue()

    async def list_entity_history(
        self,
        *,
        entity_type: AuditEntityType | str,
        entity_id: str,
        actions: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        ent = getattr(entity_type, "value", str(entity_type)).upper()
        clauses = [al_t.c.entity_type == ent, al_t.c.entity_id == str(entity_id)]
        if actions:
            clauses.append(al_t.c.action.in_(actions))
        stmt = (
            self._joined_select()
            .where(and_(*clauses))
            .order_by(desc(al_t.c.created_at), desc(al_t.c.id))
            .limit(limit)
        )
        async with self._get_conn() as conn:
            rows = (await conn.execute(stmt)).mappings().all()
        return [self._row_to_out(dict(r)) for r in rows]

    async def list_user_activity(self, user_id: str, limit: int = 25) -> list[dict[str, Any]]:
        uid = _require_uuid_str(user_id)
        stmt = (
            self._joined_select()
            .where(
                or_(
                    al_t.c.actor_id == uid,
                    and_(al_t.c.entity_type == AuditEntityType.USER.value, al_t.c.entity_id == uid),
                )
            )
            .order_by(desc(al_t.c.created_at), desc(al_t.c.id))
            .limit(limit)
        )
        async with self._get_conn() as conn:
            rows = (await conn.execute(stmt)).mappings().all()
        return [self._row_to_out(dict(r)) for r in rows]

    # ------------------------------------------------------------------ security monitoring

    async def get_security_activity(
        self,
        admin: dict,
        *,
        hours: int = 24,
        hospital_id: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=hours)
        scope = admin.get("managed_hospital_ids")
        is_platform_scope = scope is None

        scope_clauses = self._scope_clauses(admin, hospital_id=hospital_id)
        base_clauses = [*scope_clauses, al_t.c.created_at >= since]

        # 1. Aggregated summary metrics directly from SQL
        summary_stmt = select(
            func.coalesce(func.sum(case((al_t.c.action == AuditAction.AUTH_LOGIN_FAILED.value, 1), else_=0)), 0).label("failed_logins"),
            func.coalesce(func.sum(case((al_t.c.action == AuditAction.AUTH_UNAUTHORIZED_ACCESS.value, 1), else_=0)), 0).label("unauthorized_attempts"),
            func.coalesce(func.sum(case((al_t.c.action == AuditAction.AUTH_FORBIDDEN_ACCESS.value, 1), else_=0)), 0).label("forbidden_attempts"),
            func.coalesce(
                func.sum(case((al_t.c.action == AuditAction.MEDICAL_DOCUMENT_UNAUTHORIZED_ATTEMPT.value, 1), else_=0)), 0
            ).label("medical_unauthorized_attempts"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            al_t.c.action.in_([
                                AuditAction.USER_ACTIVATED.value,
                                AuditAction.USER_DEACTIVATED.value,
                                AuditAction.ADMIN_CREATED.value,
                                AuditAction.ADMIN_SCOPE_UPDATED.value,
                            ]),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("admin_scope_and_status_changes"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            al_t.c.action.in_([
                                AuditAction.DOCTOR_VERIFIED.value,
                                AuditAction.DOCTOR_SUSPENDED.value,
                                AuditAction.DOCTOR_SET_PENDING.value,
                            ]),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("doctor_verification_changes"),
            func.coalesce(
                func.sum(case((al_t.c.action == AuditAction.SECURITY_ALERT_TRIGGERED.value, 1), else_=0)), 0
            ).label("security_alerts_triggered"),
        ).where(and_(*base_clauses))

        # 2. Recent security-relevant events
        events_stmt = (
            self._joined_select()
            .where(
                and_(
                    *base_clauses,
                    or_(
                        al_t.c.severity.in_([AuditSeverity.WARNING.value, AuditSeverity.CRITICAL.value]),
                        al_t.c.action.in_(SECURITY_RELEVANT_ACTIONS),
                    ),
                )
            )
            .order_by(desc(al_t.c.created_at), desc(al_t.c.id))
            .limit(25)
        )

        alerts: list[dict[str, Any]] = []
        suspicious_sources: list[dict[str, Any]] = []

        async with self._get_conn() as conn:
            s_row = (await conn.execute(summary_stmt)).mappings().one()
            recent_rows = (await conn.execute(events_stmt)).mappings().all()

            failed_logins = int(s_row["failed_logins"])
            unauthorized_attempts = int(s_row["unauthorized_attempts"])
            forbidden_attempts = int(s_row["forbidden_attempts"])
            medical_unauthorized_attempts = int(s_row["medical_unauthorized_attempts"])
            admin_changes = int(s_row["admin_scope_and_status_changes"])
            doctor_changes = int(s_row["doctor_verification_changes"])
            alerts_triggered = int(s_row["security_alerts_triggered"])

            # 3. Suspicious IP sources & bursts (for failed logins & unauthorized attempts within scope)
            ip_stmt = (
                select(
                    al_t.c.ip_address,
                    func.count().label("cnt"),
                    func.max(al_t.c.created_at).label("latest_at"),
                )
                .where(
                    and_(
                        *base_clauses,
                        al_t.c.ip_address.isnot(None),
                        al_t.c.action.in_([
                            AuditAction.AUTH_LOGIN_FAILED.value,
                            AuditAction.AUTH_UNAUTHORIZED_ACCESS.value,
                            AuditAction.AUTH_FORBIDDEN_ACCESS.value,
                            AuditAction.MEDICAL_DOCUMENT_UNAUTHORIZED_ATTEMPT.value,
                        ]),
                    )
                )
                .group_by(al_t.c.ip_address)
                .order_by(desc(func.count()), desc(func.max(al_t.c.created_at)))
                .limit(10)
            )
            ip_rows = (await conn.execute(ip_stmt)).mappings().all()
            for r in ip_rows:
                cnt = int(r["cnt"])
                ip_val = str(r["ip_address"])
                act_stmt = (
                    select(al_t.c.action)
                    .where(
                        and_(
                            *base_clauses,
                            al_t.c.ip_address == ip_val,
                            al_t.c.action.in_([
                                AuditAction.AUTH_LOGIN_FAILED.value,
                                AuditAction.AUTH_UNAUTHORIZED_ACCESS.value,
                                AuditAction.AUTH_FORBIDDEN_ACCESS.value,
                                AuditAction.MEDICAL_DOCUMENT_UNAUTHORIZED_ATTEMPT.value,
                            ]),
                        )
                    )
                    .distinct()
                )
                act_list = [str(a) for a in (await conn.execute(act_stmt)).scalars().all()]
                suspicious_sources.append({
                    "ip_address": ip_val,
                    "count": cnt,
                    "latest_at": r["latest_at"],
                    "actions": sorted(act_list),
                })

            # High-volume document download check
            dl_stmt = (
                select(
                    al_t.c.actor_id,
                    al_t.c.actor_role,
                    func.count().label("cnt"),
                    func.max(al_t.c.created_at).label("latest_at"),
                )
                .where(
                    and_(
                        *base_clauses,
                        al_t.c.action == AuditAction.MEDICAL_DOCUMENT_DOWNLOADED.value,
                    )
                )
                .group_by(al_t.c.actor_id, al_t.c.actor_role)
                .having(func.count() >= HIGH_DOWNLOAD_VOLUME_THRESHOLD)
                .order_by(desc(func.count()))
                .limit(5)
            )
            dl_rows = (await conn.execute(dl_stmt)).mappings().all()

        # 4. Build threshold-based alerts deterministically from real SQL counts
        if failed_logins >= FAILED_LOGIN_BURST_THRESHOLD:
            top_ip = next(
                (s["ip_address"] for s in suspicious_sources if AuditAction.AUTH_LOGIN_FAILED.value in s["actions"]),
                None,
            )
            alerts.append({
                "code": "FAILED_LOGIN_THRESHOLD",
                "severity": AuditSeverity.CRITICAL.value if failed_logins >= FAILED_LOGIN_BURST_THRESHOLD * 2 else AuditSeverity.WARNING.value,
                "title": "Elevated failed login activity",
                "description": f"{failed_logins} failed login attempts recorded in the selected {hours}h window (threshold: {FAILED_LOGIN_BURST_THRESHOLD}).",
                "count": failed_logins,
                "threshold": FAILED_LOGIN_BURST_THRESHOLD,
                "source": top_ip,
                "latest_at": recent_rows[0]["created_at"] if recent_rows else None,
            })

        total_unauth = unauthorized_attempts + forbidden_attempts
        if total_unauth >= UNAUTHORIZED_SPIKE_THRESHOLD:
            alerts.append({
                "code": "UNAUTHORIZED_ACCESS_THRESHOLD",
                "severity": AuditSeverity.CRITICAL.value if total_unauth >= UNAUTHORIZED_SPIKE_THRESHOLD * 2 else AuditSeverity.WARNING.value,
                "title": "Repeated unauthorized or forbidden access attempts",
                "description": f"{total_unauth} HTTP 401/403 security denials recorded in the selected {hours}h window (threshold: {UNAUTHORIZED_SPIKE_THRESHOLD}).",
                "count": total_unauth,
                "threshold": UNAUTHORIZED_SPIKE_THRESHOLD,
                "source": suspicious_sources[0]["ip_address"] if suspicious_sources else None,
                "latest_at": recent_rows[0]["created_at"] if recent_rows else None,
            })

        if medical_unauthorized_attempts >= MEDICAL_UNAUTHORIZED_THRESHOLD:
            alerts.append({
                "code": "MEDICAL_DOCUMENT_UNAUTHORIZED",
                "severity": AuditSeverity.CRITICAL.value,
                "title": "Blocked medical document access attempts",
                "description": f"{medical_unauthorized_attempts} unauthorized medical document access attempts blocked in the selected {hours}h window (threshold: {MEDICAL_UNAUTHORIZED_THRESHOLD}).",
                "count": medical_unauthorized_attempts,
                "threshold": MEDICAL_UNAUTHORIZED_THRESHOLD,
                "source": None,
                "latest_at": recent_rows[0]["created_at"] if recent_rows else None,
            })

        for dl in dl_rows:
            cnt = int(dl["cnt"])
            alerts.append({
                "code": "HIGH_DOCUMENT_DOWNLOAD_VOLUME",
                "severity": AuditSeverity.WARNING.value,
                "title": "High medical document download volume",
                "description": f"An account ({dl['actor_role']}) recorded {cnt} document downloads in the selected {hours}h window (threshold: {HIGH_DOWNLOAD_VOLUME_THRESHOLD}).",
                "count": cnt,
                "threshold": HIGH_DOWNLOAD_VOLUME_THRESHOLD,
                "source": str(dl["actor_id"]) if dl.get("actor_id") else dl["actor_role"],
                "latest_at": dl["latest_at"],
            })

        if is_platform_scope and admin_changes > 0:
            alerts.append({
                "code": "ADMIN_PRIVILEGE_OR_STATUS_CHANGES",
                "severity": AuditSeverity.INFO.value,
                "title": "Administrative account & scope modifications",
                "description": f"{admin_changes} admin creation, scope update, or account status change(s) occurred in the selected {hours}h window.",
                "count": admin_changes,
                "threshold": 1,
                "source": "Platform Administration",
                "latest_at": recent_rows[0]["created_at"] if recent_rows else None,
            })

        return {
            "window_hours": hours,
            "since": since,
            "is_platform_scope": is_platform_scope,
            "summary": {
                "failed_logins": failed_logins,
                "unauthorized_attempts": unauthorized_attempts,
                "forbidden_attempts": forbidden_attempts,
                "medical_unauthorized_attempts": medical_unauthorized_attempts,
                "admin_scope_and_status_changes": admin_changes,
                "doctor_verification_changes": doctor_changes,
                "security_alerts_triggered": alerts_triggered,
            },
            "thresholds": {
                "failed_login_burst_threshold": FAILED_LOGIN_BURST_THRESHOLD,
                "unauthorized_spike_threshold": UNAUTHORIZED_SPIKE_THRESHOLD,
                "medical_unauthorized_threshold": MEDICAL_UNAUTHORIZED_THRESHOLD,
                "high_download_volume_threshold": HIGH_DOWNLOAD_VOLUME_THRESHOLD,
            },
            "alerts": alerts,
            "suspicious_sources": suspicious_sources,
            "recent_security_events": [self._row_to_out(dict(r)) for r in recent_rows],
        }
