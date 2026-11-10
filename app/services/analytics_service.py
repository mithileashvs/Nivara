"""Operational Healthcare Analytics Service (Phase 5).

Pure SQLAlchemy 2.0 Async + PostgreSQL aggregate implementation.
Guarantees:
- Database-level aggregation (COUNT, GROUP BY, conditional CASE) with zero full-table Python scans.
- Strict hospital scope enforcement via `managed_hospital_ids` at the SQL level.
- Consistent calculations using existing AppointmentStatus and SlotStatus enums.
- Zero double-counting from joins (independent pre-aggregated subqueries).
- Zero clinical notes, diagnoses, or patient PII exposure.
"""
from __future__ import annotations

import csv
import io
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import (
    String,
    and_,
    asc,
    case,
    cast,
    desc,
    exists,
    false,
    func,
    literal,
    or_,
    select,
    true,
)

from app.core.config import Settings
from app.core.errors import BadRequestError, ForbiddenError, NotFoundError
from app.database.tables import (
    appointment_slots_table as st,
    appointments_table as at,
    departments_table as dept_t,
    doctors_table as dt,
    hospitals_table as ht,
    patients_table as pt,
)
from app.models.enums import (
    AnalyticsGranularity,
    AnalyticsPreset,
    AnalyticsReportType,
    AppointmentStatus as S,
    ConsultationType,
    ProfileStatus,
    SlotStatus,
    UserRole,
)
from app.utils.pagination import PageParams
from app.utils.time_utils import parse_date, today_local


def _uuid_str(value: Any) -> str:
    if not value:
        raise BadRequestError("Invalid UUID identifier.", code="invalid_id")
    try:
        return str(UUID(str(value).strip()))
    except (ValueError, AttributeError, TypeError) as exc:
        raise BadRequestError("Invalid UUID identifier.", code="invalid_id") from exc


def _norm_uuid_or_str(value: Any) -> str:
    try:
        return str(UUID(str(value).strip()))
    except (ValueError, AttributeError, TypeError):
        return str(value)

logger = logging.getLogger("nivara.analytics")

# Human-readable labels mirroring frontend constants
STATUS_LABELS: dict[str, str] = {
    S.REQUESTED.value: "Awaiting doctor",
    S.CONFIRMED.value: "Confirmed",
    S.RESCHEDULE_REQUESTED.value: "Rescheduling pending",
    S.COMPLETED.value: "Completed",
    S.REJECTED.value: "Declined",
    S.CANCELLED.value: "Cancelled",
    S.NO_SHOW.value: "No show",
}

CONSULTATION_LABELS: dict[str, str] = {
    ConsultationType.FIRST_VISIT.value: "First visit",
    ConsultationType.FOLLOW_UP.value: "Follow-up",
    ConsultationType.ROUTINE_CHECKUP.value: "Routine check-up",
}

FORMULA_DEFINITIONS: dict[str, str] = {
    "completion_rate": (
        "COMPLETED / (CONFIRMED + RESCHEDULE_REQUESTED + COMPLETED + NO_SHOW + CANCELLED) * 100. "
        "Excludes pending (REQUESTED) and declined (REJECTED) appointments."
    ),
    "rejection_rate": (
        "REJECTED / (REJECTED + CONFIRMED + RESCHEDULE_REQUESTED + COMPLETED + NO_SHOW) * 100. "
        "Excludes pending (REQUESTED) and cancelled appointments."
    ),
    "cancellation_rate": (
        "CANCELLED / (CONFIRMED + RESCHEDULE_REQUESTED + COMPLETED + NO_SHOW + CANCELLED) * 100. "
        "Excludes pending (REQUESTED) and declined (REJECTED) appointments."
    ),
    "no_show_rate": (
        "NO_SHOW / (CONFIRMED + RESCHEDULE_REQUESTED + COMPLETED + NO_SHOW) * 100. "
        "Excludes pending, rejected, and cancelled appointments."
    ),
    "active_patients": (
        "Count of distinct patients with at least 1 appointment matching the selected period and scope."
    ),
    "returning_patients": (
        "Count of active patients in the selected period who have non-rejected, non-cancelled appointments "
        "on 2 or more distinct calendar dates across their authorized history up to date_to."
    ),
}

MAX_RANGE_DAYS = 1095  # 3 years safeguard


@dataclass(frozen=True)
class ResolvedScope:
    is_platform_admin: bool
    managed_hospital_ids: list[str] | None  # None = all platform hospitals
    effective_hospital_ids: list[str] | None  # None = unconstrained; [] = zero hospitals
    hospital_id: str | None
    department_id: str | None
    doctor_id: str | None
    status: str | None

    @property
    def scope_type(self) -> str:
        return "platform" if self.is_platform_admin else "hospital"


@dataclass(frozen=True)
class ResolvedPeriod:
    preset: str
    date_from: date
    date_to: date
    prev_from: date
    prev_to: date
    granularity: str
    timezone_name: str

    @property
    def days(self) -> int:
        return (self.date_to - self.date_from).days + 1

    @property
    def date_from_str(self) -> str:
        return self.date_from.isoformat()

    @property
    def date_to_str(self) -> str:
        return self.date_to.isoformat()

    @property
    def prev_from_str(self) -> str:
        return self.prev_from.isoformat()

    @property
    def prev_to_str(self) -> str:
        return self.prev_to.isoformat()

    def utc_bounds(self, start_d: date, end_d: date) -> tuple[datetime, datetime]:
        """Converts inclusive clinic-local date bounds [start_d, end_d] into UTC [start_utc, end_excl_utc)."""
        tz = ZoneInfo(self.timezone_name)
        start_local = datetime.combine(start_d, time.min, tzinfo=tz)
        end_excl_local = datetime.combine(end_d + timedelta(days=1), time.min, tzinfo=tz)
        return start_local.astimezone(timezone.utc), end_excl_local.astimezone(timezone.utc)

    def to_meta(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "date_from": self.date_from_str,
            "date_to": self.date_to_str,
            "days": self.days,
            "granularity": self.granularity,
            "timezone": self.timezone_name,
            "previous_date_from": self.prev_from_str,
            "previous_date_to": self.prev_to_str,
        }


def _safe_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 1)


def _metric_cmp(curr: int, prev: int) -> dict[str, Any]:
    delta = curr - prev
    change_pct: float | None
    if prev == 0:
        change_pct = 0.0 if curr == 0 else None
    else:
        change_pct = round((delta / prev) * 100.0, 1)
    return {"current": curr, "previous": prev, "delta": delta, "change_pct": change_pct}


def _compute_rates(counts: dict[str, int]) -> dict[str, dict[str, Any]]:
    total = counts["total"]
    req = counts["requested"]
    conf = counts["confirmed"]
    resched = counts["reschedule_requested"]
    comp = counts["completed"]
    rej = counts["rejected"]
    canc = counts["cancelled"]
    noshow = counts["no_show"]

    comp_denom = conf + resched + comp + noshow + canc
    rej_denom = rej + conf + resched + comp + noshow
    canc_denom = conf + resched + comp + noshow + canc
    noshow_denom = conf + resched + comp + noshow

    return {
        "completion_rate": {
            "rate": _safe_pct(comp, comp_denom),
            "numerator": comp,
            "denominator": comp_denom,
            "formula": FORMULA_DEFINITIONS["completion_rate"],
        },
        "rejection_rate": {
            "rate": _safe_pct(rej, rej_denom),
            "numerator": rej,
            "denominator": rej_denom,
            "formula": FORMULA_DEFINITIONS["rejection_rate"],
        },
        "cancellation_rate": {
            "rate": _safe_pct(canc, canc_denom),
            "numerator": canc,
            "denominator": canc_denom,
            "formula": FORMULA_DEFINITIONS["cancellation_rate"],
        },
        "no_show_rate": {
            "rate": _safe_pct(noshow, noshow_denom),
            "numerator": noshow,
            "denominator": noshow_denom,
            "formula": FORMULA_DEFINITIONS["no_show_rate"],
        },
    }


def _rate_cmp(curr_info: dict[str, Any], prev_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "current": curr_info["rate"],
        "previous": prev_info["rate"],
        "delta_points": round(curr_info["rate"] - prev_info["rate"], 1),
        "numerator": curr_info["numerator"],
        "denominator": curr_info["denominator"],
        "formula": curr_info["formula"],
    }


def _extract_counts(row: Any | None) -> dict[str, int]:
    if row is None:
        return {
            "total": 0,
            "requested": 0,
            "confirmed": 0,
            "reschedule_requested": 0,
            "completed": 0,
            "rejected": 0,
            "cancelled": 0,
            "no_show": 0,
        }
    return {
        "total": int(row.total or 0),
        "requested": int(row.requested or 0),
        "confirmed": int(row.confirmed or 0),
        "reschedule_requested": int(row.reschedule_requested or 0),
        "completed": int(row.completed or 0),
        "rejected": int(row.rejected or 0),
        "cancelled": int(row.cancelled or 0),
        "no_show": int(row.no_show or 0),
    }


def _csv_safe(val: Any) -> Any:
    """Neutralizes spreadsheet formula injection in CSV exports."""
    if isinstance(val, str) and val and val[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + val
    return val


def _bucket_label(bucket_date_str: str, granularity: str) -> str:
    d = parse_date(bucket_date_str)
    if granularity == AnalyticsGranularity.MONTHLY.value:
        return d.strftime("%b %Y")
    if granularity == AnalyticsGranularity.WEEKLY.value:
        return f"Wk {d.strftime('%d %b')}"
    return d.strftime("%d %b")


def _iter_buckets(start_d: date, end_d: date, granularity: str) -> list[tuple[str, str]]:
    """Generates contiguous (bucket_date_iso, display_label) tuples for a period."""
    buckets: list[tuple[str, str]] = []
    if granularity == AnalyticsGranularity.DAILY.value:
        cur = start_d
        while cur <= end_d:
            iso = cur.isoformat()
            buckets.append((iso, _bucket_label(iso, granularity)))
            cur += timedelta(days=1)
    elif granularity == AnalyticsGranularity.WEEKLY.value:
        # Align to ISO Monday
        cur = start_d - timedelta(days=start_d.weekday())
        end_monday = end_d - timedelta(days=end_d.weekday())
        while cur <= end_monday:
            iso = cur.isoformat()
            buckets.append((iso, _bucket_label(iso, granularity)))
            cur += timedelta(days=7)
    else:  # monthly
        cur = start_d.replace(day=1)
        end_m = end_d.replace(day=1)
        while cur <= end_m:
            iso = cur.isoformat()
            buckets.append((iso, _bucket_label(iso, granularity)))
            if cur.month == 12:
                cur = date(cur.year + 1, 1, 1)
            else:
                cur = date(cur.year, cur.month + 1, 1)
    return buckets


class AnalyticsService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    @property
    def is_postgres(self) -> bool:
        engine = getattr(self.db, "engine", None)
        return engine is not None and engine.dialect.name == "postgresql"

    @asynccontextmanager
    async def _get_conn(self):
        if getattr(self.db, "_conn", None) is not None:
            yield self.db._conn
        else:
            async with self.db.connect() as conn:
                yield conn

    # ------------------------------------------------------------------ Scope & Period Resolution

    def resolve_period(
        self,
        preset: AnalyticsPreset = AnalyticsPreset.LAST_30_DAYS,
        date_from: str | None = None,
        date_to: str | None = None,
        granularity: AnalyticsGranularity = AnalyticsGranularity.DAILY,
    ) -> ResolvedPeriod:
        today = today_local(self.settings.app_timezone)
        effective_preset = preset

        if (date_from or date_to) and preset != AnalyticsPreset.CUSTOM:
            # Explicit custom bounds override preset cleanly
            effective_preset = AnalyticsPreset.CUSTOM

        if effective_preset == AnalyticsPreset.TODAY:
            d_from, d_to = today, today
        elif effective_preset == AnalyticsPreset.LAST_7_DAYS:
            d_from, d_to = today - timedelta(days=6), today
        elif effective_preset == AnalyticsPreset.LAST_30_DAYS:
            d_from, d_to = today - timedelta(days=29), today
        elif effective_preset == AnalyticsPreset.LAST_90_DAYS:
            d_from, d_to = today - timedelta(days=89), today
        elif effective_preset == AnalyticsPreset.THIS_MONTH:
            d_from, d_to = today.replace(day=1), today
        elif effective_preset == AnalyticsPreset.PREVIOUS_MONTH:
            first_this = today.replace(day=1)
            d_to = first_this - timedelta(days=1)
            d_from = d_to.replace(day=1)
        elif effective_preset == AnalyticsPreset.THIS_YEAR:
            d_from, d_to = date(today.year, 1, 1), today
        elif effective_preset == AnalyticsPreset.CUSTOM:
            if not date_from or not date_to:
                raise BadRequestError(
                    "Both date_from and date_to are required for a custom date range.",
                    code="invalid_date_range",
                )
            try:
                d_from = parse_date(date_from)
                d_to = parse_date(date_to)
            except ValueError as exc:
                raise BadRequestError("Dates must use YYYY-MM-DD format.", code="invalid_date_format") from exc
        else:
            d_from, d_to = today - timedelta(days=29), today

        if d_from > d_to:
            raise BadRequestError("date_from cannot be after date_to.", code="invalid_date_range")

        span_days = (d_to - d_from).days + 1
        if span_days > MAX_RANGE_DAYS:
            raise BadRequestError(
                f"Date range cannot exceed {MAX_RANGE_DAYS} days.",
                code="date_range_too_large",
            )

        # Previous equivalent non-overlapping period
        if effective_preset == AnalyticsPreset.PREVIOUS_MONTH:
            prev_to = d_from - timedelta(days=1)
            prev_from = prev_to.replace(day=1)
        else:
            prev_to = d_from - timedelta(days=1)
            prev_from = prev_to - timedelta(days=span_days - 1)

        return ResolvedPeriod(
            preset=effective_preset.value,
            date_from=d_from,
            date_to=d_to,
            prev_from=prev_from,
            prev_to=prev_to,
            granularity=granularity.value,
            timezone_name=self.settings.app_timezone,
        )

    async def resolve_scope(
        self,
        admin: dict,
        *,
        hospital_id: str | None = None,
        department_id: str | None = None,
        doctor_id: str | None = None,
        status: S | None = None,
    ) -> ResolvedScope:
        if admin.get("role") != UserRole.ADMIN.value:
            raise ForbiddenError("Administrator access required.", code="forbidden_role")

        managed_raw = admin.get("managed_hospital_ids")
        is_platform = managed_raw is None
        managed_ids = [_norm_uuid_or_str(x) for x in managed_raw] if managed_raw is not None else None

        clean_h_id: str | None = None
        if hospital_id:
            clean_h_id = _uuid_str(hospital_id)
            if not is_platform and clean_h_id not in (managed_ids or []):
                raise ForbiddenError(
                    "You are not authorized to access analytics for this hospital.",
                    code="hospital_scope_forbidden",
                )
            async with self._get_conn() as conn:
                h_row = (await conn.execute(select(ht.c.id).where(ht.c.id == clean_h_id))).first()
            if h_row is None:
                raise NotFoundError("Hospital not found.", code="hospital_not_found")
            effective_hospitals: list[str] | None = [clean_h_id]
        else:
            effective_hospitals = managed_ids

        clean_dept_id: str | None = None
        if department_id:
            clean_dept_id = _uuid_str(department_id)
            async with self._get_conn() as conn:
                d_row = (
                    await conn.execute(
                        select(dept_t.c.id, dept_t.c.hospital_id).where(dept_t.c.id == clean_dept_id)
                    )
                ).mappings().first()
            if d_row is None:
                if not is_platform:
                    raise ForbiddenError(
                        "You are not authorized to access analytics for this department.",
                        code="hospital_scope_forbidden",
                    )
                raise NotFoundError("Department not found.", code="department_not_found")
            dept_hosp_id = str(d_row["hospital_id"])
            if not is_platform and dept_hosp_id not in (managed_ids or []):
                raise ForbiddenError(
                    "You are not authorized to access analytics for this department.",
                    code="hospital_scope_forbidden",
                )

        clean_doc_id: str | None = None
        if doctor_id:
            clean_doc_id = _uuid_str(doctor_id)
            async with self._get_conn() as conn:
                doc_row = (
                    await conn.execute(select(dt.c.id, dt.c.hospital_ids).where(dt.c.id == clean_doc_id))
                ).mappings().first()
            if doc_row is None:
                if not is_platform:
                    raise ForbiddenError(
                        "You are not authorized to access analytics for this doctor.",
                        code="hospital_scope_forbidden",
                    )
                raise NotFoundError("Doctor not found.", code="doctor_not_found")
            doc_hospitals = {str(h) for h in (doc_row["hospital_ids"] or [])}
            if not is_platform and not (doc_hospitals & set(managed_ids or [])):
                raise ForbiddenError(
                    "You are not authorized to access analytics for this doctor.",
                    code="hospital_scope_forbidden",
                )

        return ResolvedScope(
            is_platform_admin=is_platform,
            managed_hospital_ids=managed_ids,
            effective_hospital_ids=effective_hospitals,
            hospital_id=clean_h_id,
            department_id=clean_dept_id,
            doctor_id=clean_doc_id,
            status=status.value if status else None,
        )

    # ------------------------------------------------------------------ SQL Clause Builders

    def _appt_scope_clauses(
        self,
        scope: ResolvedScope,
        *,
        include_status: bool = True,
        table=at,
    ) -> list[Any]:
        clauses: list[Any] = []
        if scope.effective_hospital_ids is not None:
            if not scope.effective_hospital_ids:
                clauses.append(false())
            else:
                clauses.append(table.c.hospital_id.in_(scope.effective_hospital_ids))
        if scope.department_id:
            clauses.append(table.c.department_id == scope.department_id)
        if scope.doctor_id:
            clauses.append(table.c.doctor_id == scope.doctor_id)
        if include_status and scope.status:
            clauses.append(table.c.status == scope.status)
        return clauses

    def _slot_scope_clauses(self, scope: ResolvedScope) -> list[Any]:
        clauses: list[Any] = []
        if scope.effective_hospital_ids is not None:
            if not scope.effective_hospital_ids:
                clauses.append(false())
            else:
                clauses.append(st.c.hospital_id.in_(scope.effective_hospital_ids))
        if scope.department_id:
            clauses.append(st.c.department_id == scope.department_id)
        if scope.doctor_id:
            clauses.append(st.c.doctor_id == scope.doctor_id)
        return clauses

    def _doctor_scope_clauses(self, scope: ResolvedScope) -> list[Any]:
        clauses: list[Any] = []
        if scope.effective_hospital_ids is not None:
            if not scope.effective_hospital_ids:
                clauses.append(false())
            else:
                clauses.append(
                    or_(*[dt.c.hospital_ids.cast(String).contains(f'"{hid}"') for hid in scope.effective_hospital_ids])
                )
        if scope.department_id:
            clauses.append(dt.c.department_ids.cast(String).contains(f'"{scope.department_id}"'))
        if scope.doctor_id:
            clauses.append(dt.c.id == scope.doctor_id)
        return clauses

    def _appt_cond_cols(self) -> list[Any]:
        return [
            func.count().label("total"),
            func.coalesce(func.sum(case((at.c.status == S.REQUESTED.value, 1), else_=0)), 0).label("requested"),
            func.coalesce(func.sum(case((at.c.status == S.CONFIRMED.value, 1), else_=0)), 0).label("confirmed"),
            func.coalesce(
                func.sum(case((at.c.status == S.RESCHEDULE_REQUESTED.value, 1), else_=0)), 0
            ).label("reschedule_requested"),
            func.coalesce(func.sum(case((at.c.status == S.COMPLETED.value, 1), else_=0)), 0).label("completed"),
            func.coalesce(func.sum(case((at.c.status == S.REJECTED.value, 1), else_=0)), 0).label("rejected"),
            func.coalesce(func.sum(case((at.c.status == S.CANCELLED.value, 1), else_=0)), 0).label("cancelled"),
            func.coalesce(func.sum(case((at.c.status == S.NO_SHOW.value, 1), else_=0)), 0).label("no_show"),
        ]

    def _date_str_bucket_expr(self, col: Any, granularity: str) -> Any:
        if self.is_postgres:
            if granularity == AnalyticsGranularity.DAILY.value:
                return col
            if granularity == AnalyticsGranularity.WEEKLY.value:
                return func.to_char(func.date_trunc("week", func.to_date(col, "YYYY-MM-DD")), "YYYY-MM-DD")
            return func.to_char(func.date_trunc("month", func.to_date(col, "YYYY-MM-DD")), "YYYY-MM-DD")
        # SQLite fallback for lightweight non-PG environments
        if granularity == AnalyticsGranularity.DAILY.value:
            return col
        if granularity == AnalyticsGranularity.WEEKLY.value:
            return func.date(col, "weekday 0", "-6 days")
        return func.strftime("%Y-%m-01", col)

    def _ts_bucket_expr(self, col: Any, granularity: str) -> Any:
        if self.is_postgres:
            local_ts = func.timezone(self.settings.app_timezone, col)
            trunc_unit = (
                "day"
                if granularity == AnalyticsGranularity.DAILY.value
                else "week"
                if granularity == AnalyticsGranularity.WEEKLY.value
                else "month"
            )
            return func.to_char(func.date_trunc(trunc_unit, local_ts), "YYYY-MM-DD")
        # SQLite fallback
        if granularity == AnalyticsGranularity.DAILY.value:
            return func.strftime("%Y-%m-%d", col)
        if granularity == AnalyticsGranularity.WEEKLY.value:
            return func.date(col, "weekday 0", "-6 days")
        return func.strftime("%Y-%m-01", col)

    async def _get_appt_counts(
        self, scope: ResolvedScope, date_from_str: str, date_to_str: str
    ) -> dict[str, int]:
        clauses = [
            at.c.appointment_date >= date_from_str,
            at.c.appointment_date <= date_to_str,
            *self._appt_scope_clauses(scope),
        ]
        stmt = select(*self._appt_cond_cols()).where(and_(*clauses))
        async with self._get_conn() as conn:
            row = (await conn.execute(stmt)).first()
        return _extract_counts(row)

    async def _get_appt_trends(
        self,
        scope: ResolvedScope,
        period: ResolvedPeriod,
        *,
        fill_empty: bool = True,
    ) -> list[dict[str, Any]]:
        bucket_expr = self._date_str_bucket_expr(at.c.appointment_date, period.granularity).label("bucket_date")
        clauses = [
            at.c.appointment_date >= period.date_from_str,
            at.c.appointment_date <= period.date_to_str,
            *self._appt_scope_clauses(scope),
        ]
        stmt = (
            select(bucket_expr, *self._appt_cond_cols())
            .where(and_(*clauses))
            .group_by(bucket_expr)
            .order_by(asc(bucket_expr))
        )
        async with self._get_conn() as conn:
            rows = (await conn.execute(stmt)).fetchall()

        by_bucket: dict[str, dict[str, int]] = {}
        for r in rows:
            if r.bucket_date:
                by_bucket[str(r.bucket_date)] = _extract_counts(r)

        if fill_empty:
            ordered_buckets = _iter_buckets(period.date_from, period.date_to, period.granularity)
        else:
            ordered_buckets = [(b, _bucket_label(b, period.granularity)) for b in sorted(by_bucket.keys())]

        points: list[dict[str, Any]] = []
        for b_iso, label in ordered_buckets:
            c = by_bucket.get(b_iso) or _extract_counts(None)
            rates = _compute_rates(c)
            points.append(
                {
                    "bucket_date": b_iso,
                    "label": label,
                    **c,
                    "completion_rate": rates["completion_rate"]["rate"],
                    "rejection_rate": rates["rejection_rate"]["rate"],
                    "cancellation_rate": rates["cancellation_rate"]["rate"],
                    "no_show_rate": rates["no_show_rate"]["rate"],
                }
            )
        return points

    def _patient_scope_exists_clause(self, scope: ResolvedScope) -> Any | None:
        """If filtered to specific hospital(s), department, or doctor, restricts patients to those
        with appointments inside that exact authorized scope."""
        if (
            scope.effective_hospital_ids is None
            and scope.department_id is None
            and scope.doctor_id is None
        ):
            return None
        sub_clauses = [at.c.patient_id == pt.c.id, *self._appt_scope_clauses(scope, include_status=False)]
        return exists(select(at.c.id).where(and_(*sub_clauses)))

    async def _get_patient_registration_counts(
        self, scope: ResolvedScope, start_d: date, end_d: date, period: ResolvedPeriod
    ) -> tuple[int, int]:
        """Returns (total_registered_in_scope, new_registrations_in_window)."""
        start_utc, end_excl_utc = period.utc_bounds(start_d, end_d)
        scope_exists = self._patient_scope_exists_clause(scope)

        total_clauses = [scope_exists] if scope_exists is not None else [true()]
        new_clauses = [pt.c.created_at >= start_utc, pt.c.created_at < end_excl_utc]
        if scope_exists is not None:
            new_clauses.append(scope_exists)

        async with self._get_conn() as conn:
            total_reg = (
                await conn.execute(select(func.count()).select_from(pt).where(and_(*total_clauses)))
            ).scalar_one() or 0
            new_reg = (
                await conn.execute(select(func.count()).select_from(pt).where(and_(*new_clauses)))
            ).scalar_one() or 0
        return int(total_reg), int(new_reg)

    async def _get_patient_registration_trends(
        self, scope: ResolvedScope, period: ResolvedPeriod
    ) -> dict[str, int]:
        start_utc, end_excl_utc = period.utc_bounds(period.date_from, period.date_to)
        bucket_expr = self._ts_bucket_expr(pt.c.created_at, period.granularity).label("bucket_date")
        clauses = [pt.c.created_at >= start_utc, pt.c.created_at < end_excl_utc]
        scope_exists = self._patient_scope_exists_clause(scope)
        if scope_exists is not None:
            clauses.append(scope_exists)

        stmt = (
            select(bucket_expr, func.count().label("cnt"))
            .where(and_(*clauses))
            .group_by(bucket_expr)
            .order_by(asc(bucket_expr))
        )
        async with self._get_conn() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return {str(r.bucket_date): int(r.cnt or 0) for r in rows if r.bucket_date}

    # ------------------------------------------------------------------ 1. Overview Dashboard

    async def get_overview(self, scope: ResolvedScope, period: ResolvedPeriod) -> dict[str, Any]:
        curr_counts = await self._get_appt_counts(scope, period.date_from_str, period.date_to_str)
        prev_counts = await self._get_appt_counts(scope, period.prev_from_str, period.prev_to_str)

        curr_rates = _compute_rates(curr_counts)
        prev_rates = _compute_rates(prev_counts)

        total_reg_patients, new_curr_patients = await self._get_patient_registration_counts(
            scope, period.date_from, period.date_to, period
        )
        _, new_prev_patients = await self._get_patient_registration_counts(
            scope, period.prev_from, period.prev_to, period
        )

        # Active doctors & accessible hospitals in scope
        doc_clauses = [dt.c.profile_status == ProfileStatus.ACTIVE.value, *self._doctor_scope_clauses(scope)]
        hosp_clauses = []
        if scope.effective_hospital_ids is not None:
            if not scope.effective_hospital_ids:
                hosp_clauses.append(false())
            else:
                hosp_clauses.append(ht.c.id.in_(scope.effective_hospital_ids))
        else:
            hosp_clauses.append(true())

        async with self._get_conn() as conn:
            active_doctors = int(
                (await conn.execute(select(func.count()).select_from(dt).where(and_(*doc_clauses)))).scalar_one() or 0
            )
            accessible_hospitals = int(
                (await conn.execute(select(func.count()).select_from(ht).where(and_(*hosp_clauses)))).scalar_one() or 0
            )

        # Trends
        appt_trends = await self._get_appt_trends(scope, period, fill_empty=True)
        reg_by_bucket = await self._get_patient_registration_trends(scope, period)
        patient_reg_trends = [
            {
                "bucket_date": b["bucket_date"],
                "label": b["label"],
                "new_patients": reg_by_bucket.get(b["bucket_date"], 0),
            }
            for b in appt_trends
        ]

        # Status distribution
        total_curr = curr_counts["total"]
        status_distribution = [
            {
                "status": s.value,
                "label": STATUS_LABELS.get(s.value, s.value),
                "count": curr_counts[s.value.lower()],
                "percentage": _safe_pct(curr_counts[s.value.lower()], total_curr),
                "previous_count": prev_counts[s.value.lower()],
            }
            for s in S
        ]

        # Highlights derived from real data
        highest_period = None
        non_zero_periods = [p for p in appt_trends if p["total"] > 0]
        if non_zero_periods:
            top_p = max(non_zero_periods, key=lambda x: x["total"])
            highest_period = {
                "bucket_date": top_p["bucket_date"],
                "label": top_p["label"],
                "count": top_p["total"],
            }

        appt_period_clauses = [
            at.c.appointment_date >= period.date_from_str,
            at.c.appointment_date <= period.date_to_str,
            *self._appt_scope_clauses(scope),
        ]
        top_dept_stmt = (
            select(
                at.c.department_id,
                dept_t.c.name.label("department_name"),
                ht.c.name.label("hospital_name"),
                func.count().label("cnt"),
            )
            .select_from(
                at.join(dept_t, at.c.department_id == dept_t.c.id).join(ht, at.c.hospital_id == ht.c.id)
            )
            .where(and_(*appt_period_clauses))
            .group_by(at.c.department_id, dept_t.c.name, ht.c.name)
            .order_by(desc(func.count()))
            .limit(1)
        )
        top_hosp_stmt = (
            select(
                at.c.hospital_id,
                ht.c.name.label("hospital_name"),
                func.count().label("cnt"),
            )
            .select_from(at.join(ht, at.c.hospital_id == ht.c.id))
            .where(and_(*appt_period_clauses))
            .group_by(at.c.hospital_id, ht.c.name)
            .order_by(desc(func.count()))
            .limit(1)
        )
        async with self._get_conn() as conn:
            top_dept_row = (await conn.execute(top_dept_stmt)).mappings().first()
            top_hosp_row = (await conn.execute(top_hosp_stmt)).mappings().first()

        most_active_dept = (
            {
                "department_id": str(top_dept_row["department_id"]),
                "department_name": top_dept_row["department_name"],
                "hospital_name": top_dept_row["hospital_name"],
                "count": int(top_dept_row["cnt"]),
            }
            if top_dept_row
            else None
        )
        most_active_hosp = (
            {
                "hospital_id": str(top_hosp_row["hospital_id"]),
                "hospital_name": top_hosp_row["hospital_name"],
                "count": int(top_hosp_row["cnt"]),
            }
            if top_hosp_row
            else None
        )

        scope_note = (
            "Platform-wide operational analytics across all registered facilities."
            if self._patient_scope_exists_clause(scope) is None
            else "Patient metrics scoped to patients with appointments matching your authorized facility/filter scope."
        )

        return {
            "scope": scope.scope_type,
            "scope_note": scope_note,
            "period": period.to_meta(),
            "total_appointments": _metric_cmp(curr_counts["total"], prev_counts["total"]),
            "requested_appointments": _metric_cmp(curr_counts["requested"], prev_counts["requested"]),
            "confirmed_appointments": _metric_cmp(curr_counts["confirmed"], prev_counts["confirmed"]),
            "reschedule_requested_appointments": _metric_cmp(
                curr_counts["reschedule_requested"], prev_counts["reschedule_requested"]
            ),
            "completed_appointments": _metric_cmp(curr_counts["completed"], prev_counts["completed"]),
            "rejected_appointments": _metric_cmp(curr_counts["rejected"], prev_counts["rejected"]),
            "cancelled_appointments": _metric_cmp(curr_counts["cancelled"], prev_counts["cancelled"]),
            "no_show_appointments": _metric_cmp(curr_counts["no_show"], prev_counts["no_show"]),
            "completion_rate": _rate_cmp(curr_rates["completion_rate"], prev_rates["completion_rate"]),
            "rejection_rate": _rate_cmp(curr_rates["rejection_rate"], prev_rates["rejection_rate"]),
            "cancellation_rate": _rate_cmp(curr_rates["cancellation_rate"], prev_rates["cancellation_rate"]),
            "no_show_rate": _rate_cmp(curr_rates["no_show_rate"], prev_rates["no_show_rate"]),
            "total_registered_patients": total_reg_patients,
            "new_patients_in_period": _metric_cmp(new_curr_patients, new_prev_patients),
            "active_doctors": active_doctors,
            "accessible_hospitals": accessible_hospitals,
            "status_distribution": status_distribution,
            "appointment_trends": appt_trends,
            "patient_registration_trends": patient_reg_trends,
            "highlights": {
                "highest_volume_period": highest_period,
                "most_active_department": most_active_dept,
                "most_active_hospital": most_active_hosp,
            },
            "formula_definitions": FORMULA_DEFINITIONS,
        }

    # ------------------------------------------------------------------ 2. Appointment Analytics

    async def get_appointment_trends_and_summary(
        self, scope: ResolvedScope, period: ResolvedPeriod, params: PageParams
    ) -> dict[str, Any]:
        trends = await self._get_appt_trends(scope, period, fill_empty=True)
        # Summary table uses chronological buckets in reverse (most recent first)
        desc_rows = list(reversed(trends))
        total_rows = len(desc_rows)
        paged_rows = desc_rows[params.skip : params.skip + params.page_size]
        import math

        return {
            "scope": scope.scope_type,
            "period": period.to_meta(),
            "trends": trends,
            "summary_table": {
                "items": paged_rows,
                "page": params.page,
                "page_size": params.page_size,
                "total": total_rows,
                "total_pages": math.ceil(total_rows / params.page_size) if total_rows else 0,
            },
            "formula_definitions": FORMULA_DEFINITIONS,
        }

    async def get_appointment_status_analytics(
        self, scope: ResolvedScope, period: ResolvedPeriod
    ) -> dict[str, Any]:
        curr_counts = await self._get_appt_counts(scope, period.date_from_str, period.date_to_str)
        prev_counts = await self._get_appt_counts(scope, period.prev_from_str, period.prev_to_str)
        curr_rates = _compute_rates(curr_counts)
        prev_rates = _compute_rates(prev_counts)

        total_curr = curr_counts["total"]
        status_distribution = [
            {
                "status": s.value,
                "label": STATUS_LABELS.get(s.value, s.value),
                "count": curr_counts[s.value.lower()],
                "percentage": _safe_pct(curr_counts[s.value.lower()], total_curr),
                "previous_count": prev_counts[s.value.lower()],
            }
            for s in S
        ]

        clauses = [
            at.c.appointment_date >= period.date_from_str,
            at.c.appointment_date <= period.date_to_str,
            *self._appt_scope_clauses(scope),
        ]
        ctype_stmt = (
            select(at.c.consultation_type, func.count().label("cnt"))
            .where(and_(*clauses))
            .group_by(at.c.consultation_type)
            .order_by(desc(func.count()))
        )
        async with self._get_conn() as conn:
            ctype_rows = (await conn.execute(ctype_stmt)).fetchall()

        c_map = {str(r.consultation_type): int(r.cnt or 0) for r in ctype_rows}
        consultation_types = [
            {
                "consultation_type": ct.value,
                "label": CONSULTATION_LABELS.get(ct.value, ct.value),
                "count": c_map.get(ct.value, 0),
                "percentage": _safe_pct(c_map.get(ct.value, 0), total_curr),
            }
            for ct in ConsultationType
        ]

        return {
            "scope": scope.scope_type,
            "period": period.to_meta(),
            "total_appointments": _metric_cmp(curr_counts["total"], prev_counts["total"]),
            "status_distribution": status_distribution,
            "consultation_types": consultation_types,
            "rates": {
                k: _rate_cmp(curr_rates[k], prev_rates[k])
                for k in ("completion_rate", "rejection_rate", "cancellation_rate", "no_show_rate")
            },
            "formula_definitions": FORMULA_DEFINITIONS,
        }

    # ------------------------------------------------------------------ 3. Hospital Analytics

    async def _build_hospital_rows_query(
        self, scope: ResolvedScope, period: ResolvedPeriod, search: str | None = None
    ) -> list[dict[str, Any]]:
        # Independent pre-aggregated subqueries prevent Cartesian row multiplication!
        appt_clauses = [
            at.c.appointment_date >= period.date_from_str,
            at.c.appointment_date <= period.date_to_str,
            *self._appt_scope_clauses(scope),
        ]
        appt_sub = (
            select(at.c.hospital_id.label("h_id"), *self._appt_cond_cols())
            .where(and_(*appt_clauses))
            .group_by(at.c.hospital_id)
            .subquery("appt_agg")
        )
        dept_sub = (
            select(dept_t.c.hospital_id.label("h_id"), func.count().label("dept_cnt"))
            .group_by(dept_t.c.hospital_id)
            .subquery("dept_agg")
        )
        doc_count_scalar = (
            select(func.count())
            .select_from(dt)
            .where(
                and_(
                    dt.c.profile_status == ProfileStatus.ACTIVE.value,
                    dt.c.hospital_ids.cast(String).like(literal('%"') + ht.c.id.cast(String) + literal('"%')),
                )
            )
            .scalar_subquery()
            .label("active_doctor_count")
        )

        hosp_clauses: list[Any] = []
        if scope.effective_hospital_ids is not None:
            if not scope.effective_hospital_ids:
                hosp_clauses.append(false())
            else:
                hosp_clauses.append(ht.c.id.in_(scope.effective_hospital_ids))
        if search and search.strip():
            hosp_clauses.append(func.lower(ht.c.name).like(f"%{search.strip().lower()}%"))

        stmt = (
            select(
                ht.c.id.label("hospital_id"),
                ht.c.name.label("hospital_name"),
                ht.c.location,
                ht.c.appointment_intake_status.label("intake_status"),
                func.coalesce(dept_sub.c.dept_cnt, 0).label("department_count"),
                doc_count_scalar,
                func.coalesce(appt_sub.c.total, 0).label("total"),
                func.coalesce(appt_sub.c.requested, 0).label("requested"),
                func.coalesce(appt_sub.c.confirmed, 0).label("confirmed"),
                func.coalesce(appt_sub.c.reschedule_requested, 0).label("reschedule_requested"),
                func.coalesce(appt_sub.c.completed, 0).label("completed"),
                func.coalesce(appt_sub.c.rejected, 0).label("rejected"),
                func.coalesce(appt_sub.c.cancelled, 0).label("cancelled"),
                func.coalesce(appt_sub.c.no_show, 0).label("no_show"),
            )
            .select_from(
                ht.outerjoin(appt_sub, ht.c.id == appt_sub.c.h_id).outerjoin(
                    dept_sub, ht.c.id == dept_sub.c.h_id
                )
            )
            .where(and_(*hosp_clauses) if hosp_clauses else true())
            .order_by(desc(func.coalesce(appt_sub.c.total, 0)), asc(ht.c.name))
        )
        async with self._get_conn() as conn:
            raw_rows = (await conn.execute(stmt)).mappings().all()

        results: list[dict[str, Any]] = []
        import json

        for r in raw_rows:
            loc = r["location"]
            if isinstance(loc, str):
                try:
                    loc = json.loads(loc)
                except Exception:
                    loc = {}
            counts = _extract_counts(r)
            rates = _compute_rates(counts)
            results.append(
                {
                    "hospital_id": str(r["hospital_id"]),
                    "hospital_name": r["hospital_name"],
                    "city": loc.get("city") if isinstance(loc, dict) else None,
                    "intake_status": str(r["intake_status"]),
                    "department_count": int(r["department_count"] or 0),
                    "active_doctor_count": int(r["active_doctor_count"] or 0),
                    "total_appointments": counts["total"],
                    "requested_appointments": counts["requested"],
                    "confirmed_appointments": counts["confirmed"],
                    "reschedule_requested_appointments": counts["reschedule_requested"],
                    "completed_appointments": counts["completed"],
                    "rejected_appointments": counts["rejected"],
                    "cancelled_appointments": counts["cancelled"],
                    "no_show_appointments": counts["no_show"],
                    "completion_rate": rates["completion_rate"]["rate"],
                    "rejection_rate": rates["rejection_rate"]["rate"],
                    "cancellation_rate": rates["cancellation_rate"]["rate"],
                    "no_show_rate": rates["no_show_rate"]["rate"],
                }
            )
        return results

    async def get_hospital_analytics(
        self,
        scope: ResolvedScope,
        period: ResolvedPeriod,
        params: PageParams,
        search: str | None = None,
    ) -> dict[str, Any]:
        import math

        all_rows = await self._build_hospital_rows_query(scope, period, search=search)
        total = len(all_rows)
        paged = all_rows[params.skip : params.skip + params.page_size]
        return {
            "scope": scope.scope_type,
            "period": period.to_meta(),
            "hospitals": {
                "items": paged,
                "page": params.page,
                "page_size": params.page_size,
                "total": total,
                "total_pages": math.ceil(total / params.page_size) if total else 0,
            },
            "formula_definitions": FORMULA_DEFINITIONS,
        }

    async def get_hospital_detail_analytics(
        self,
        admin: dict,
        hospital_id: str,
        period: ResolvedPeriod,
        *,
        department_id: str | None = None,
        doctor_id: str | None = None,
        status: S | None = None,
    ) -> dict[str, Any]:
        # Strictly validate hospital access and scope via resolve_scope
        scope = await self.resolve_scope(
            admin,
            hospital_id=hospital_id,
            department_id=department_id,
            doctor_id=doctor_id,
            status=status,
        )
        hosp_rows = await self._build_hospital_rows_query(scope, period)
        if not hosp_rows:
            raise NotFoundError("Hospital not found.", code="hospital_not_found")
        hospital_row = hosp_rows[0]

        curr_counts = await self._get_appt_counts(scope, period.date_from_str, period.date_to_str)
        prev_counts = await self._get_appt_counts(scope, period.prev_from_str, period.prev_to_str)
        curr_rates = _compute_rates(curr_counts)
        prev_rates = _compute_rates(prev_counts)

        trends = await self._get_appt_trends(scope, period, fill_empty=True)
        dept_rows = await self._build_department_rows_query(scope, period)

        return {
            "scope": scope.scope_type,
            "period": period.to_meta(),
            "hospital": hospital_row,
            "total_appointments_comparison": _metric_cmp(curr_counts["total"], prev_counts["total"]),
            "completed_comparison": _metric_cmp(curr_counts["completed"], prev_counts["completed"]),
            "completion_rate": _rate_cmp(curr_rates["completion_rate"], prev_rates["completion_rate"]),
            "trends": trends,
            "departments": dept_rows,
            "formula_definitions": FORMULA_DEFINITIONS,
        }

    # ------------------------------------------------------------------ 4. Department Analytics

    async def _build_department_rows_query(
        self, scope: ResolvedScope, period: ResolvedPeriod, search: str | None = None
    ) -> list[dict[str, Any]]:
        appt_clauses = [
            at.c.appointment_date >= period.date_from_str,
            at.c.appointment_date <= period.date_to_str,
            *self._appt_scope_clauses(scope),
        ]
        appt_sub = (
            select(at.c.department_id.label("d_id"), *self._appt_cond_cols())
            .where(and_(*appt_clauses))
            .group_by(at.c.department_id)
            .subquery("appt_dept_agg")
        )
        doc_count_scalar = (
            select(func.count())
            .select_from(dt)
            .where(
                and_(
                    dt.c.profile_status == ProfileStatus.ACTIVE.value,
                    dt.c.department_ids.cast(String).like(literal('%"') + dept_t.c.id.cast(String) + literal('"%')),
                )
            )
            .scalar_subquery()
            .label("doctor_count")
        )

        dept_clauses: list[Any] = []
        if scope.effective_hospital_ids is not None:
            if not scope.effective_hospital_ids:
                dept_clauses.append(false())
            else:
                dept_clauses.append(dept_t.c.hospital_id.in_(scope.effective_hospital_ids))
        if scope.department_id:
            dept_clauses.append(dept_t.c.id == scope.department_id)
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            dept_clauses.append(or_(func.lower(dept_t.c.name).like(term), func.lower(ht.c.name).like(term)))

        stmt = (
            select(
                dept_t.c.id.label("department_id"),
                dept_t.c.name.label("department_name"),
                dept_t.c.hospital_id.label("hospital_id"),
                ht.c.name.label("hospital_name"),
                dept_t.c.status.label("status"),
                dept_t.c.appointment_intake_status.label("intake_status"),
                doc_count_scalar,
                func.coalesce(appt_sub.c.total, 0).label("total"),
                func.coalesce(appt_sub.c.requested, 0).label("requested"),
                func.coalesce(appt_sub.c.confirmed, 0).label("confirmed"),
                func.coalesce(appt_sub.c.reschedule_requested, 0).label("reschedule_requested"),
                func.coalesce(appt_sub.c.completed, 0).label("completed"),
                func.coalesce(appt_sub.c.rejected, 0).label("rejected"),
                func.coalesce(appt_sub.c.cancelled, 0).label("cancelled"),
                func.coalesce(appt_sub.c.no_show, 0).label("no_show"),
            )
            .select_from(
                dept_t.join(ht, dept_t.c.hospital_id == ht.c.id).outerjoin(
                    appt_sub, dept_t.c.id == appt_sub.c.d_id
                )
            )
            .where(and_(*dept_clauses) if dept_clauses else true())
            .order_by(desc(func.coalesce(appt_sub.c.total, 0)), asc(dept_t.c.name))
        )
        async with self._get_conn() as conn:
            raw_rows = (await conn.execute(stmt)).mappings().all()

        results: list[dict[str, Any]] = []
        for r in raw_rows:
            counts = _extract_counts(r)
            rates = _compute_rates(counts)
            results.append(
                {
                    "department_id": str(r["department_id"]),
                    "department_name": r["department_name"],
                    "hospital_id": str(r["hospital_id"]),
                    "hospital_name": r["hospital_name"],
                    "status": str(r["status"]),
                    "intake_status": str(r["intake_status"]),
                    "doctor_count": int(r["doctor_count"] or 0),
                    "total_appointments": counts["total"],
                    "requested_appointments": counts["requested"],
                    "confirmed_appointments": counts["confirmed"],
                    "reschedule_requested_appointments": counts["reschedule_requested"],
                    "completed_appointments": counts["completed"],
                    "rejected_appointments": counts["rejected"],
                    "cancelled_appointments": counts["cancelled"],
                    "no_show_appointments": counts["no_show"],
                    "completion_rate": rates["completion_rate"]["rate"],
                    "rejection_rate": rates["rejection_rate"]["rate"],
                    "cancellation_rate": rates["cancellation_rate"]["rate"],
                    "no_show_rate": rates["no_show_rate"]["rate"],
                }
            )
        return results

    async def get_department_analytics(
        self,
        scope: ResolvedScope,
        period: ResolvedPeriod,
        params: PageParams,
        search: str | None = None,
    ) -> dict[str, Any]:
        import math

        all_rows = await self._build_department_rows_query(scope, period, search=search)
        trends = await self._get_appt_trends(scope, period, fill_empty=True)

        total_appts = sum(r["total_appointments"] for r in all_rows)
        completed_appts = sum(r["completed_appointments"] for r in all_rows)
        cancelled_appts = sum(r["cancelled_appointments"] for r in all_rows)
        rejected_appts = sum(r["rejected_appointments"] for r in all_rows)

        summary = {
            "total_departments": len(all_rows),
            "active_departments": sum(1 for r in all_rows if r["status"] == "ACTIVE"),
            "total_appointments": total_appts,
            "completed_appointments": completed_appts,
            "cancelled_appointments": cancelled_appts,
            "rejected_appointments": rejected_appts,
            "most_active_department": all_rows[0] if all_rows and all_rows[0]["total_appointments"] > 0 else None,
        }

        total = len(all_rows)
        paged = all_rows[params.skip : params.skip + params.page_size]
        return {
            "scope": scope.scope_type,
            "period": period.to_meta(),
            "summary": summary,
            "departments": {
                "items": paged,
                "page": params.page,
                "page_size": params.page_size,
                "total": total,
                "total_pages": math.ceil(total / params.page_size) if total else 0,
            },
            "trends": trends,
            "formula_definitions": FORMULA_DEFINITIONS,
        }

    # ------------------------------------------------------------------ 5. Doctor Analytics

    async def _build_doctor_rows_query(
        self, scope: ResolvedScope, period: ResolvedPeriod, search: str | None = None
    ) -> list[dict[str, Any]]:
        appt_clauses = [
            at.c.appointment_date >= period.date_from_str,
            at.c.appointment_date <= period.date_to_str,
            *self._appt_scope_clauses(scope),
        ]
        appt_sub = (
            select(at.c.doctor_id.label("doc_id"), *self._appt_cond_cols())
            .where(and_(*appt_clauses))
            .group_by(at.c.doctor_id)
            .subquery("appt_doc_agg")
        )

        # Actual slots query (never mixed or inferred from appointment counts)
        slot_clauses = [
            st.c.date >= period.date_from_str,
            st.c.date <= period.date_to_str,
            *self._slot_scope_clauses(scope),
        ]
        slot_sub = (
            select(
                st.c.doctor_id.label("doc_id"),
                func.count().label("total_slots"),
                func.coalesce(func.sum(case((st.c.status == SlotStatus.AVAILABLE.value, 1), else_=0)), 0).label(
                    "available_slots"
                ),
                func.coalesce(func.sum(case((st.c.status == SlotStatus.HELD.value, 1), else_=0)), 0).label(
                    "held_slots"
                ),
                func.coalesce(func.sum(case((st.c.status == SlotStatus.BOOKED.value, 1), else_=0)), 0).label(
                    "booked_slots"
                ),
                func.coalesce(func.sum(case((st.c.status == SlotStatus.BLOCKED.value, 1), else_=0)), 0).label(
                    "blocked_slots"
                ),
            )
            .where(and_(*slot_clauses))
            .group_by(st.c.doctor_id)
            .subquery("slot_doc_agg")
        )

        doc_clauses = list(self._doctor_scope_clauses(scope))
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            doc_clauses.append(or_(func.lower(dt.c.name).like(term), func.lower(dt.c.specialty).like(term)))

        stmt = (
            select(
                dt.c.id.label("doctor_id"),
                dt.c.name.label("doctor_name"),
                dt.c.specialty.label("specialty"),
                dt.c.profile_status.label("profile_status"),
                dt.c.availability_status.label("availability_status"),
                func.coalesce(appt_sub.c.total, 0).label("total"),
                func.coalesce(appt_sub.c.requested, 0).label("requested"),
                func.coalesce(appt_sub.c.confirmed, 0).label("confirmed"),
                func.coalesce(appt_sub.c.reschedule_requested, 0).label("reschedule_requested"),
                func.coalesce(appt_sub.c.completed, 0).label("completed"),
                func.coalesce(appt_sub.c.rejected, 0).label("rejected"),
                func.coalesce(appt_sub.c.cancelled, 0).label("cancelled"),
                func.coalesce(appt_sub.c.no_show, 0).label("no_show"),
                func.coalesce(slot_sub.c.total_slots, 0).label("total_slots"),
                func.coalesce(slot_sub.c.available_slots, 0).label("available_slots"),
                func.coalesce(slot_sub.c.held_slots, 0).label("held_slots"),
                func.coalesce(slot_sub.c.booked_slots, 0).label("booked_slots"),
                func.coalesce(slot_sub.c.blocked_slots, 0).label("blocked_slots"),
            )
            .select_from(
                dt.outerjoin(appt_sub, dt.c.id == appt_sub.c.doc_id).outerjoin(slot_sub, dt.c.id == slot_sub.c.doc_id)
            )
            .where(and_(*doc_clauses) if doc_clauses else true())
            .order_by(desc(func.coalesce(appt_sub.c.total, 0)), asc(dt.c.name))
        )
        async with self._get_conn() as conn:
            raw_rows = (await conn.execute(stmt)).mappings().all()

        results: list[dict[str, Any]] = []
        for r in raw_rows:
            counts = _extract_counts(r)
            rates = _compute_rates(counts)
            results.append(
                {
                    "doctor_id": str(r["doctor_id"]),
                    "doctor_name": r["doctor_name"],
                    "specialty": r["specialty"],
                    "profile_status": str(r["profile_status"]),
                    "availability_status": str(r["availability_status"]),
                    "total_appointments": counts["total"],
                    "requested_appointments": counts["requested"],
                    "confirmed_appointments": counts["confirmed"],
                    "reschedule_requested_appointments": counts["reschedule_requested"],
                    "completed_appointments": counts["completed"],
                    "rejected_appointments": counts["rejected"],
                    "cancelled_appointments": counts["cancelled"],
                    "no_show_appointments": counts["no_show"],
                    "completion_rate": rates["completion_rate"]["rate"],
                    "rejection_rate": rates["rejection_rate"]["rate"],
                    "cancellation_rate": rates["cancellation_rate"]["rate"],
                    "no_show_rate": rates["no_show_rate"]["rate"],
                    "total_slots": int(r["total_slots"] or 0),
                    "available_slots": int(r["available_slots"] or 0),
                    "held_slots": int(r["held_slots"] or 0),
                    "booked_slots": int(r["booked_slots"] or 0),
                    "blocked_slots": int(r["blocked_slots"] or 0),
                }
            )
        return results

    async def get_doctor_analytics(
        self,
        scope: ResolvedScope,
        period: ResolvedPeriod,
        params: PageParams,
        search: str | None = None,
    ) -> dict[str, Any]:
        import math

        all_rows = await self._build_doctor_rows_query(scope, period, search=search)
        trends = await self._get_appt_trends(scope, period, fill_empty=True)

        summary = {
            "total_doctors": len(all_rows),
            "active_doctors": sum(1 for r in all_rows if r["profile_status"] == ProfileStatus.ACTIVE.value),
            "total_appointments": sum(r["total_appointments"] for r in all_rows),
            "total_slots": sum(r["total_slots"] for r in all_rows),
            "booked_slots": sum(r["booked_slots"] for r in all_rows),
            "available_slots": sum(r["available_slots"] for r in all_rows),
        }

        total = len(all_rows)
        paged = all_rows[params.skip : params.skip + params.page_size]
        return {
            "scope": scope.scope_type,
            "period": period.to_meta(),
            "summary": summary,
            "doctors": {
                "items": paged,
                "page": params.page,
                "page_size": params.page_size,
                "total": total,
                "total_pages": math.ceil(total / params.page_size) if total else 0,
            },
            "trends": trends,
            "formula_definitions": FORMULA_DEFINITIONS,
        }

    # ------------------------------------------------------------------ 6. Patient Analytics (Aggregate Only)

    async def get_patient_analytics(self, scope: ResolvedScope, period: ResolvedPeriod) -> dict[str, Any]:
        total_reg, new_curr = await self._get_patient_registration_counts(
            scope, period.date_from, period.date_to, period
        )
        _, new_prev = await self._get_patient_registration_counts(
            scope, period.prev_from, period.prev_to, period
        )

        # Active patients = distinct patients with >= 1 appointment in selected period + scope
        curr_appt_clauses = [
            at.c.appointment_date >= period.date_from_str,
            at.c.appointment_date <= period.date_to_str,
            *self._appt_scope_clauses(scope),
        ]
        prev_appt_clauses = [
            at.c.appointment_date >= period.prev_from_str,
            at.c.appointment_date <= period.prev_to_str,
            *self._appt_scope_clauses(scope),
        ]

        async with self._get_conn() as conn:
            active_curr = int(
                (
                    await conn.execute(
                        select(func.count(func.distinct(at.c.patient_id))).where(and_(*curr_appt_clauses))
                    )
                ).scalar_one()
                or 0
            )
            active_prev = int(
                (
                    await conn.execute(
                        select(func.count(func.distinct(at.c.patient_id))).where(and_(*prev_appt_clauses))
                    )
                ).scalar_one()
                or 0
            )

            # Returning patients: active patients in the selected period who have >= 2 distinct
            # non-rejected/non-cancelled appointment_date values up to date_to in authorized scope.
            active_in_period_sub = (
                select(at.c.patient_id).where(and_(*curr_appt_clauses)).distinct().subquery("active_p")
            )
            history_clauses = [
                at.c.appointment_date <= period.date_to_str,
                at.c.status.notin_([S.REJECTED.value, S.CANCELLED.value]),
                *self._appt_scope_clauses(scope, include_status=False),
            ]
            returning_sub = (
                select(at.c.patient_id)
                .select_from(at.join(active_in_period_sub, at.c.patient_id == active_in_period_sub.c.patient_id))
                .where(and_(*history_clauses))
                .group_by(at.c.patient_id)
                .having(func.count(func.distinct(at.c.appointment_date)) >= 2)
                .subquery("ret_p")
            )
            returning_curr = int(
                (await conn.execute(select(func.count()).select_from(returning_sub))).scalar_one() or 0
            )

            # Patient activity trend per bucket
            bucket_expr = self._date_str_bucket_expr(at.c.appointment_date, period.granularity).label("bucket_date")
            act_trend_stmt = (
                select(
                    bucket_expr,
                    func.count(func.distinct(at.c.patient_id)).label("active_patients"),
                    func.count().label("appointments"),
                )
                .where(and_(*curr_appt_clauses))
                .group_by(bucket_expr)
                .order_by(asc(bucket_expr))
            )
            act_rows = (await conn.execute(act_trend_stmt)).fetchall()

        reg_map = await self._get_patient_registration_trends(scope, period)
        act_map = {
            str(r.bucket_date): (int(r.active_patients or 0), int(r.appointments or 0))
            for r in act_rows
            if r.bucket_date
        }

        trends = []
        for b_iso, label in _iter_buckets(period.date_from, period.date_to, period.granularity):
            act_p, appts_c = act_map.get(b_iso, (0, 0))
            trends.append(
                {
                    "bucket_date": b_iso,
                    "label": label,
                    "new_registrations": reg_map.get(b_iso, 0),
                    "active_patients": act_p,
                    "appointments": appts_c,
                }
            )

        single_visit = max(0, active_curr - returning_curr)
        returning_rate = _safe_pct(returning_curr, active_curr)
        scope_note = (
            "Platform-wide aggregate patient statistics. Individual patient PII is never exposed."
            if self._patient_scope_exists_clause(scope) is None
            else "Scoped aggregate metrics for patients with appointments in your authorized facility/filter scope. Individual patient PII is never exposed."
        )

        return {
            "scope": scope.scope_type,
            "scope_note": scope_note,
            "period": period.to_meta(),
            "total_registered_patients": total_reg,
            "new_registrations": _metric_cmp(new_curr, new_prev),
            "active_patients": _metric_cmp(active_curr, active_prev),
            "returning_patients": returning_curr,
            "single_visit_active_patients": single_visit,
            "returning_rate": returning_rate,
            "trends": trends,
            "formula_definitions": FORMULA_DEFINITIONS,
        }

    # ------------------------------------------------------------------ 7. CSV Report Export (No PII)

    async def export_csv_report(
        self,
        report_type: AnalyticsReportType,
        scope: ResolvedScope,
        period: ResolvedPeriod,
    ) -> tuple[str, str]:
        """Generates sanitized CSV content and safe filename matching exact dashboard analytics."""
        buf = io.StringIO()
        writer = csv.writer(buf)

        def write_row(cells: list[Any]) -> None:
            writer.writerow([_csv_safe(c) for c in cells])

        if report_type == AnalyticsReportType.APPOINTMENT_SUMMARY:
            rows = await self._get_appt_trends(scope, period, fill_empty=True)
            write_row(
                [
                    "Period",
                    "Bucket Date",
                    "Total",
                    "Requested",
                    "Confirmed",
                    "Rescheduling Pending",
                    "Completed",
                    "Rejected",
                    "Cancelled",
                    "No Show",
                    "Completion Rate (%)",
                    "Rejection Rate (%)",
                    "Cancellation Rate (%)",
                    "No-Show Rate (%)",
                ]
            )
            for r in rows:
                write_row(
                    [
                        r["label"],
                        r["bucket_date"],
                        r["total"],
                        r["requested"],
                        r["confirmed"],
                        r["reschedule_requested"],
                        r["completed"],
                        r["rejected"],
                        r["cancelled"],
                        r["no_show"],
                        r["completion_rate"],
                        r["rejection_rate"],
                        r["cancellation_rate"],
                        r["no_show_rate"],
                    ]
                )

        elif report_type == AnalyticsReportType.HOSPITAL_PERFORMANCE:
            rows = await self._build_hospital_rows_query(scope, period)
            write_row(
                [
                    "Hospital ID",
                    "Hospital Name",
                    "City",
                    "Intake Status",
                    "Departments",
                    "Active Doctors",
                    "Total Appointments",
                    "Requested",
                    "Confirmed",
                    "Rescheduling Pending",
                    "Completed",
                    "Rejected",
                    "Cancelled",
                    "No Show",
                    "Completion Rate (%)",
                    "Rejection Rate (%)",
                    "Cancellation Rate (%)",
                    "No-Show Rate (%)",
                ]
            )
            for r in rows:
                write_row(
                    [
                        r["hospital_id"],
                        r["hospital_name"],
                        r["city"] or "",
                        r["intake_status"],
                        r["department_count"],
                        r["active_doctor_count"],
                        r["total_appointments"],
                        r["requested_appointments"],
                        r["confirmed_appointments"],
                        r["reschedule_requested_appointments"],
                        r["completed_appointments"],
                        r["rejected_appointments"],
                        r["cancelled_appointments"],
                        r["no_show_appointments"],
                        r["completion_rate"],
                        r["rejection_rate"],
                        r["cancellation_rate"],
                        r["no_show_rate"],
                    ]
                )

        elif report_type == AnalyticsReportType.DEPARTMENT_PERFORMANCE:
            rows = await self._build_department_rows_query(scope, period)
            write_row(
                [
                    "Department ID",
                    "Department Name",
                    "Hospital Name",
                    "Status",
                    "Intake Status",
                    "Active Doctors",
                    "Total Appointments",
                    "Confirmed",
                    "Completed",
                    "Rejected",
                    "Cancelled",
                    "No Show",
                    "Completion Rate (%)",
                    "Rejection Rate (%)",
                    "Cancellation Rate (%)",
                    "No-Show Rate (%)",
                ]
            )
            for r in rows:
                write_row(
                    [
                        r["department_id"],
                        r["department_name"],
                        r["hospital_name"],
                        r["status"],
                        r["intake_status"],
                        r["doctor_count"],
                        r["total_appointments"],
                        r["confirmed_appointments"],
                        r["completed_appointments"],
                        r["rejected_appointments"],
                        r["cancelled_appointments"],
                        r["no_show_appointments"],
                        r["completion_rate"],
                        r["rejection_rate"],
                        r["cancellation_rate"],
                        r["no_show_rate"],
                    ]
                )

        elif report_type == AnalyticsReportType.DOCTOR_STATISTICS:
            rows = await self._build_doctor_rows_query(scope, period)
            write_row(
                [
                    "Doctor ID",
                    "Doctor Name",
                    "Specialty",
                    "Profile Status",
                    "Availability",
                    "Total Appointments",
                    "Completed",
                    "Confirmed",
                    "Rejected",
                    "Cancelled",
                    "No Show",
                    "Completion Rate (%)",
                    "Rejection Rate (%)",
                    "Cancellation Rate (%)",
                    "Total Slots",
                    "Available Slots",
                    "Held Slots",
                    "Booked Slots",
                    "Blocked Slots",
                ]
            )
            for r in rows:
                write_row(
                    [
                        r["doctor_id"],
                        r["doctor_name"],
                        r["specialty"],
                        r["profile_status"],
                        r["availability_status"],
                        r["total_appointments"],
                        r["completed_appointments"],
                        r["confirmed_appointments"],
                        r["rejected_appointments"],
                        r["cancelled_appointments"],
                        r["no_show_appointments"],
                        r["completion_rate"],
                        r["rejection_rate"],
                        r["cancellation_rate"],
                        r["total_slots"],
                        r["available_slots"],
                        r["held_slots"],
                        r["booked_slots"],
                        r["blocked_slots"],
                    ]
                )

        elif report_type == AnalyticsReportType.PATIENT_REGISTRATIONS:
            data = await self.get_patient_analytics(scope, period)
            write_row(["Period", "Bucket Date", "New Registrations", "Active Patients", "Total Appointments"])
            for r in data["trends"]:
                write_row(
                    [
                        r["label"],
                        r["bucket_date"],
                        r["new_registrations"],
                        r["active_patients"],
                        r["appointments"],
                    ]
                )

        filename = f"nivara_{report_type.value}_{period.date_from_str}_to_{period.date_to_str}.csv"
        return buf.getvalue(), filename
