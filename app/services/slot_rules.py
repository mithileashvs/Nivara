"""Pure bookability rules (no database access).

One place decides whether a slot can receive a NEW appointment request, so slot listings,
discovery, and the request endpoint can never disagree.
"""
from datetime import datetime, timedelta
from typing import Any

from app.models.enums import DepartmentStatus, IntakeStatus, ProfileStatus, SlotStatus

# reason code -> human-readable message (the API error `code` is the lower-cased reason)
REASON_MESSAGES: dict[str, str] = {
    "SLOT_BOOKED": "This slot has already been booked.",
    "SLOT_HELD": "This slot is currently reserved by another pending request.",
    "SLOT_BLOCKED": "This slot is not available for booking.",
    "SLOT_IN_PAST": "This slot has already started or passed.",
    "SLOT_TOO_SOON": "This slot starts too soon to accept new requests.",
    "DOCTOR_NOT_ACTIVE": "This doctor is not currently accepting patients on SmartCare.",
    "DOCTOR_INTAKE_CLOSED": "This doctor is not accepting new appointment requests right now.",
    "DOCTOR_NOT_AFFILIATED": "This doctor is not currently affiliated with this hospital/department.",
    "HOSPITAL_NOT_FOUND": "Hospital not found.",
    "HOSPITAL_INTAKE_CLOSED": "This hospital is not accepting new appointment requests right now.",
    "DEPARTMENT_NOT_FOUND": "Department not found.",
    "DEPARTMENT_INACTIVE": "This department is not active.",
    "DEPARTMENT_INTAKE_CLOSED": "This department is not accepting new appointment requests right now.",
}


def effective_status(slot: dict[str, Any], now: datetime) -> SlotStatus:
    """A HELD slot whose hold has expired is effectively AVAILABLE (the sweeper/lazy expiry
    will formally release it before it is re-claimed)."""
    status = SlotStatus(slot["status"])
    if status == SlotStatus.HELD:
        held_until = slot.get("held_until")
        if held_until is not None and held_until < now:
            return SlotStatus.AVAILABLE
    return status


def facility_block_reason(
    doctor: dict[str, Any] | None,
    hospital: dict[str, Any] | None,
    department: dict[str, Any] | None,
) -> str | None:
    """Explicit intake rules — never inferred from appointment counts."""
    if doctor is None or doctor.get("profile_status") != ProfileStatus.ACTIVE:
        return "DOCTOR_NOT_ACTIVE"
    if doctor.get("availability_status") != IntakeStatus.OPEN:
        return "DOCTOR_INTAKE_CLOSED"
    if hospital is None:
        return "HOSPITAL_NOT_FOUND"
    if hospital.get("appointment_intake_status") != IntakeStatus.OPEN:
        return "HOSPITAL_INTAKE_CLOSED"
    if department is None or department.get("hospital_id") != hospital["_id"]:
        return "DEPARTMENT_NOT_FOUND"
    if department.get("status") != DepartmentStatus.ACTIVE:
        return "DEPARTMENT_INACTIVE"
    if department.get("appointment_intake_status") != IntakeStatus.OPEN:
        return "DEPARTMENT_INTAKE_CLOSED"
    if hospital["_id"] not in doctor.get("hospital_ids", []) or department["_id"] not in doctor.get(
        "department_ids", []
    ):
        return "DOCTOR_NOT_AFFILIATED"
    return None


def slot_block_reason(
    slot: dict[str, Any],
    doctor: dict[str, Any] | None,
    hospital: dict[str, Any] | None,
    department: dict[str, Any] | None,
    *,
    now: datetime,
    min_lead_minutes: int,
) -> str | None:
    """Return why a NEW request cannot be made for this slot, or None if it is bookable."""
    status = effective_status(slot, now)
    if status == SlotStatus.BOOKED:
        return "SLOT_BOOKED"
    if status == SlotStatus.HELD:
        return "SLOT_HELD"
    if status == SlotStatus.BLOCKED:
        return "SLOT_BLOCKED"
    if slot["start_at"] <= now:
        return "SLOT_IN_PAST"
    if slot["start_at"] < now + timedelta(minutes=min_lead_minutes):
        return "SLOT_TOO_SOON"
    return facility_block_reason(doctor, hospital, department)
