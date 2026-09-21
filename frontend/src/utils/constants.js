/* Values mirrored from app/models/enums.py. Keep in sync with the backend. */

export const ROLES = { PATIENT: 'PATIENT', DOCTOR: 'DOCTOR', ADMIN: 'ADMIN' }

export const APPOINTMENT_STATUS = {
  REQUESTED: 'REQUESTED',
  CONFIRMED: 'CONFIRMED',
  REJECTED: 'REJECTED',
  CANCELLED: 'CANCELLED',
  COMPLETED: 'COMPLETED',
  NO_SHOW: 'NO_SHOW',
}

export const APPOINTMENT_STATUS_LABEL = {
  REQUESTED: 'Awaiting doctor',
  CONFIRMED: 'Confirmed',
  REJECTED: 'Declined',
  CANCELLED: 'Cancelled',
  COMPLETED: 'Completed',
  NO_SHOW: 'No show',
}

export const SLOT_STATUS = {
  AVAILABLE: 'AVAILABLE',
  HELD: 'HELD',
  BOOKED: 'BOOKED',
  BLOCKED: 'BLOCKED',
}

export const INTAKE_STATUS = { OPEN: 'OPEN', CLOSED: 'CLOSED' }
export const DEPARTMENT_STATUS = { ACTIVE: 'ACTIVE', INACTIVE: 'INACTIVE' }
export const PROFILE_STATUS = { PENDING: 'PENDING', ACTIVE: 'ACTIVE', SUSPENDED: 'SUSPENDED' }
export const AVAILABILITY_STATUS = { WORKING: 'WORKING', BLOCKED: 'BLOCKED' }
export const WAITLIST_STATUS = {
  ACTIVE: 'ACTIVE',
  FULFILLED: 'FULFILLED',
  CANCELLED: 'CANCELLED',
  EXPIRED: 'EXPIRED',
}

export const CONSULTATION_TYPES = [
  { value: 'FIRST_VISIT', label: 'First visit' },
  { value: 'FOLLOW_UP', label: 'Follow-up' },
  { value: 'ROUTINE_CHECKUP', label: 'Routine check-up' },
]

export const CONSULTATION_LABEL = Object.fromEntries(
  CONSULTATION_TYPES.map((c) => [c.value, c.label]),
)

export const GENDERS = [
  { value: 'MALE', label: 'Male' },
  { value: 'FEMALE', label: 'Female' },
  { value: 'OTHER', label: 'Other' },
  { value: 'UNDISCLOSED', label: 'Prefer not to say' },
]

export const DOCUMENT_TYPES = [
  { value: 'REPORT', label: 'Report' },
  { value: 'LAB_RESULT', label: 'Lab result' },
  { value: 'IMAGING', label: 'Imaging' },
  { value: 'REFERRAL', label: 'Referral' },
  { value: 'OTHER', label: 'Other' },
]

export const NOTIFICATION_LABEL = {
  APPOINTMENT_REQUESTED: 'Appointment requested',
  APPOINTMENT_ACCEPTED: 'Appointment confirmed',
  APPOINTMENT_REJECTED: 'Appointment declined',
  APPOINTMENT_CANCELLED: 'Appointment cancelled',
  APPOINTMENT_RESCHEDULED: 'Appointment rescheduled',
  APPOINTMENT_REMINDER: 'Appointment reminder',
  WAITLIST_SLOT_AVAILABLE: 'A matching slot opened',
}

/** Shown wherever symptom routing appears. Matches the backend disclaimer's intent. */
export const ROUTING_DISCLAIMER =
  'Nivara only helps you find the right department and book an appointment. It does not diagnose conditions, predict diseases, prescribe medicines, recommend dosages or suggest treatment. Please consult a qualified doctor for any medical concern.'

export const PAGE_SIZE = 20
export const MAX_PAGE_SIZE = 100
