from enum import StrEnum


class UserRole(StrEnum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"


class AppointmentStatus(StrEnum):
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


# Statuses in which an appointment occupies (holds or books) a slot.
ACTIVE_APPOINTMENT_STATUSES = frozenset({AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED})


class SlotStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    HELD = "HELD"  # a patient's request is awaiting the doctor's decision
    BOOKED = "BOOKED"  # doctor confirmed
    BLOCKED = "BLOCKED"  # not bookable (doctor time-off / manual block)


class IntakeStatus(StrEnum):
    """Whether NEW appointment requests are accepted (hospital / department / doctor)."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class DepartmentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ProfileStatus(StrEnum):
    PENDING = "PENDING"  # registered, awaiting platform verification
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class AvailabilityStatus(StrEnum):
    WORKING = "WORKING"  # generates bookable slots
    BLOCKED = "BLOCKED"  # time off — blocks overlapping free slots


class ConsultationType(StrEnum):
    FIRST_VISIT = "FIRST_VISIT"
    FOLLOW_UP = "FOLLOW_UP"
    ROUTINE_CHECKUP = "ROUTINE_CHECKUP"


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"
    UNDISCLOSED = "UNDISCLOSED"


class NotificationType(StrEnum):
    APPOINTMENT_REQUESTED = "APPOINTMENT_REQUESTED"
    APPOINTMENT_ACCEPTED = "APPOINTMENT_ACCEPTED"
    APPOINTMENT_REJECTED = "APPOINTMENT_REJECTED"
    APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
    APPOINTMENT_RESCHEDULED = "APPOINTMENT_RESCHEDULED"
    APPOINTMENT_REMINDER = "APPOINTMENT_REMINDER"
    WAITLIST_SLOT_AVAILABLE = "WAITLIST_SLOT_AVAILABLE"


class WaitlistStatus(StrEnum):
    ACTIVE = "ACTIVE"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class DocumentType(StrEnum):
    REPORT = "REPORT"
    LAB_RESULT = "LAB_RESULT"
    IMAGING = "IMAGING"
    REFERRAL = "REFERRAL"
    OTHER = "OTHER"


class SystemActor(StrEnum):
    SYSTEM = "SYSTEM"
