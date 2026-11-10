/* Values mirrored from app/models/enums.py. Keep in sync with the backend. */

export const ROLES = { PATIENT: 'PATIENT', DOCTOR: 'DOCTOR', ADMIN: 'ADMIN' }

export const APPOINTMENT_STATUS = {
  REQUESTED: 'REQUESTED',
  CONFIRMED: 'CONFIRMED',
  RESCHEDULE_REQUESTED: 'RESCHEDULE_REQUESTED',
  REJECTED: 'REJECTED',
  CANCELLED: 'CANCELLED',
  COMPLETED: 'COMPLETED',
  NO_SHOW: 'NO_SHOW',
}

export const APPOINTMENT_STATUS_LABEL = {
  REQUESTED: 'Awaiting doctor',
  CONFIRMED: 'Confirmed',
  RESCHEDULE_REQUESTED: 'Rescheduling pending',
  REJECTED: 'Declined',
  CANCELLED: 'Cancelled',
  COMPLETED: 'Completed',
  NO_SHOW: 'No show',
}

export const RESCHEDULE_STATUS = {
  REQUESTED: 'REQUESTED',
  APPROVED: 'APPROVED',
  REJECTED: 'REJECTED',
  CANCELLED: 'CANCELLED',
}

export const RESCHEDULE_STATUS_LABEL = {
  REQUESTED: 'Rescheduling pending',
  APPROVED: 'Reschedule approved',
  REJECTED: 'Reschedule declined',
  CANCELLED: 'Cancelled',
}

export const CANCELLATION_REASONS = [
  { value: 'Personal reasons', label: 'Personal reasons' },
  { value: 'Schedule conflict', label: 'Schedule conflict' },
  { value: 'Found another appointment', label: 'Found another appointment' },
  { value: 'Unable to attend', label: 'Unable to attend' },
  { value: 'Other', label: 'Other (custom reason)' },
]

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

export const WAITLIST_OFFER_STATUS = {
  PENDING: 'PENDING',
  ACCEPTED: 'ACCEPTED',
  DECLINED: 'DECLINED',
  EXPIRED: 'EXPIRED',
  CANCELLED: 'CANCELLED',
}

export const WAITLIST_OFFER_STATUS_LABEL = {
  PENDING: 'Offer Pending',
  ACCEPTED: 'Accepted',
  DECLINED: 'Declined',
  EXPIRED: 'Expired',
  CANCELLED: 'Cancelled',
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

export const MEDICAL_DOCUMENT_CATEGORIES = [
  { value: 'LAB_REPORT', label: 'Lab Reports' },
  { value: 'PRESCRIPTION', label: 'Prescriptions' },
  { value: 'IMAGING', label: 'Medical Scans & Imaging' },
  { value: 'DISCHARGE_SUMMARY', label: 'Discharge Summaries' },
  { value: 'CONSULTATION_REPORT', label: 'Consultation Reports' },
  { value: 'OTHER', label: 'Other Medical Documents' },
]

export const MEDICAL_CATEGORY_LABEL = Object.fromEntries(
  MEDICAL_DOCUMENT_CATEGORIES.map((c) => [c.value, c.label]),
)

export const NOTIFICATION_CATEGORY = {
  APPOINTMENT: 'APPOINTMENT',
  RESCHEDULING: 'RESCHEDULING',
  CANCELLATION: 'CANCELLATION',
  WAITLIST: 'WAITLIST',
  SYSTEM: 'SYSTEM',
}

export const NOTIFICATION_CATEGORY_LABEL = {
  APPOINTMENT: 'Appointments',
  RESCHEDULING: 'Rescheduling',
  CANCELLATION: 'Cancellations',
  WAITLIST: 'Waitlist',
  SYSTEM: 'System & Account',
}

export const NOTIFICATION_LABEL = {
  APPOINTMENT_REQUESTED: 'Appointment requested',
  APPOINTMENT_ACCEPTED: 'Appointment confirmed',
  APPOINTMENT_REJECTED: 'Appointment declined',
  APPOINTMENT_CANCELLED: 'Appointment cancelled',
  APPOINTMENT_RESCHEDULED: 'Appointment rescheduled',
  RESCHEDULE_REQUESTED: 'Rescheduling requested',
  RESCHEDULE_APPROVED: 'Reschedule approved',
  RESCHEDULE_REJECTED: 'Reschedule declined',
  APPOINTMENT_REMINDER: 'Appointment reminder',
  WAITLIST_SLOT_AVAILABLE: 'A matching slot opened',
  WAITLIST_OFFER_AVAILABLE: 'Exclusive slot offer reserved',
  WAITLIST_OFFER_ACCEPTED: 'Slot offer accepted',
  WAITLIST_OFFER_DECLINED: 'Slot offer declined',
  WAITLIST_ELIGIBLE: 'Slot eligibility update',
  WAITLIST_EXPIRED: 'Waitlist entry expired',
  DOCTOR_VERIFIED: 'Doctor profile verified',
  DOCTOR_SUSPENDED: 'Doctor profile suspended',
  ACCOUNT_STATUS_CHANGED: 'Account status updated',
  SECURITY_ALERT: 'Security threshold alert',
  SYSTEM_ANNOUNCEMENT: 'System announcement',
}

/** Shown wherever symptom routing appears. Matches the backend disclaimer's intent. */
export const ROUTING_DISCLAIMER =
  'Nivara only helps you find the right department and book an appointment. It does not diagnose conditions, predict diseases, prescribe medicines, recommend dosages or suggest treatment. Please consult a qualified doctor for any medical concern.'

export const PAGE_SIZE = 20
export const MAX_PAGE_SIZE = 100

/* Phase 5 Operational Analytics */
export const ANALYTICS_PRESETS = [
  { value: 'today', label: 'Today' },
  { value: 'last_7_days', label: 'Last 7 days' },
  { value: 'last_30_days', label: 'Last 30 days' },
  { value: 'last_90_days', label: 'Last 90 days' },
  { value: 'this_month', label: 'This month' },
  { value: 'previous_month', label: 'Previous month' },
  { value: 'this_year', label: 'This year' },
  { value: 'custom', label: 'Custom range' },
]

export const ANALYTICS_GRANULARITIES = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
]

export const ANALYTICS_STATUS_COLORS = {
  REQUESTED: '#A4762A',
  CONFIRMED: '#3F7D5B',
  RESCHEDULE_REQUESTED: '#6E7F47',
  COMPLETED: '#3D6379',
  CANCELLED: '#8B978F',
  REJECTED: '#A8503F',
  NO_SHOW: '#C06E52',
}

export const ANALYTICS_REPORT_TYPES = [
  {
    value: 'appointment_summary',
    label: 'Appointment Summary Report',
    description: 'Chronological bucket totals, status counts, and completion/rejection/cancellation/no-show rates.',
    columns: ['Period', 'Bucket Date', 'Total', 'Requested', 'Confirmed', 'Rescheduling Pending', 'Completed', 'Rejected', 'Cancelled', 'No Show', 'Rates (%)'],
  },
  {
    value: 'hospital_performance',
    label: 'Hospital Performance Report',
    description: 'Facility-level appointment volumes, status distribution, active doctors, departments, and outcome rates.',
    columns: ['Hospital', 'City', 'Intake Status', 'Departments', 'Active Doctors', 'Total', 'Status Counts', 'Rates (%)'],
  },
  {
    value: 'department_performance',
    label: 'Department Performance Report',
    description: 'Department-level appointment volume, active doctors, status counts, and operational rates.',
    columns: ['Department', 'Hospital', 'Status', 'Intake Status', 'Active Doctors', 'Total', 'Status Counts', 'Rates (%)'],
  },
  {
    value: 'doctor_statistics',
    label: 'Doctor Workload & Slot Report',
    description: 'Doctor appointment counts, outcome rates, and actual slot breakdown from appointment_slots.',
    columns: ['Doctor', 'Specialty', 'Profile & Intake', 'Appointments & Rates (%)', 'Total / Available / Held / Booked / Blocked Slots'],
  },
  {
    value: 'patient_registrations',
    label: 'Patient Registration & Activity Report',
    description: 'Aggregate patient registration trends and active patient engagement counts (strictly zero PII).',
    columns: ['Period', 'Bucket Date', 'New Registrations', 'Active Patients', 'Total Appointments'],
  },
]

/* Phase 6 Centralized Audit & Security Governance */
export const AUDIT_SEVERITY_TONE = {
  INFO: 'info',
  WARNING: 'pending',
  CRITICAL: 'negative',
}

export const AUDIT_SEVERITY_OPTIONS = [
  { value: 'INFO', label: 'Info' },
  { value: 'WARNING', label: 'Warning' },
  { value: 'CRITICAL', label: 'Critical' },
]

export const AUDIT_ROLE_OPTIONS = [
  { value: 'ADMIN', label: 'Admin' },
  { value: 'DOCTOR', label: 'Doctor' },
  { value: 'PATIENT', label: 'Patient' },
  { value: 'SYSTEM', label: 'System' },
  { value: 'ANONYMOUS', label: 'Anonymous' },
]

export const AUDIT_ENTITY_OPTIONS = [
  { value: 'AUTH', label: 'Authentication' },
  { value: 'USER', label: 'User Account' },
  { value: 'DOCTOR', label: 'Doctor' },
  { value: 'HOSPITAL', label: 'Hospital' },
  { value: 'DEPARTMENT', label: 'Department' },
  { value: 'APPOINTMENT', label: 'Appointment' },
  { value: 'RESCHEDULE_REQUEST', label: 'Reschedule Request' },
  { value: 'WAITLIST_ENTRY', label: 'Waitlist Entry' },
  { value: 'WAITLIST_OFFER', label: 'Waitlist Offer' },
  { value: 'MEDICAL_DOCUMENT', label: 'Medical Document' },
  { value: 'ROUTING_RULE', label: 'Routing Rule' },
  { value: 'SYSTEM', label: 'System' },
]

export const AUDIT_ACTION_OPTIONS = [
  { value: 'AUTH_REGISTER', label: 'Auth: Register' },
  { value: 'AUTH_LOGIN_SUCCESS', label: 'Auth: Login success' },
  { value: 'AUTH_LOGIN_FAILED', label: 'Auth: Login failed' },
  { value: 'AUTH_LOGOUT', label: 'Auth: Logout' },
  { value: 'AUTH_UNAUTHORIZED_ACCESS', label: 'Auth: Unauthorized access (401)' },
  { value: 'AUTH_FORBIDDEN_ACCESS', label: 'Auth: Forbidden access (403)' },
  { value: 'APPOINTMENT_REQUESTED', label: 'Appointment requested' },
  { value: 'APPOINTMENT_CONFIRMED', label: 'Appointment confirmed' },
  { value: 'APPOINTMENT_REJECTED', label: 'Appointment declined' },
  { value: 'APPOINTMENT_CANCELLED', label: 'Appointment cancelled' },
  { value: 'APPOINTMENT_COMPLETED', label: 'Appointment completed' },
  { value: 'APPOINTMENT_NO_SHOW', label: 'Appointment no-show' },
  { value: 'APPOINTMENT_EXPIRED', label: 'Appointment hold expired' },
  { value: 'APPOINTMENT_RESCHEDULE_REQUESTED', label: 'Reschedule requested' },
  { value: 'APPOINTMENT_RESCHEDULE_APPROVED', label: 'Reschedule approved' },
  { value: 'APPOINTMENT_RESCHEDULE_REJECTED', label: 'Reschedule declined' },
  { value: 'APPOINTMENT_DIRECT_RESCHEDULED', label: 'Direct doctor reschedule' },
  { value: 'WAITLIST_JOINED', label: 'Waitlist joined' },
  { value: 'WAITLIST_CANCELLED', label: 'Waitlist cancelled' },
  { value: 'WAITLIST_EXPIRED', label: 'Waitlist expired' },
  { value: 'WAITLIST_OFFER_CREATED', label: 'Waitlist offer created' },
  { value: 'WAITLIST_OFFER_ACCEPTED', label: 'Waitlist offer accepted' },
  { value: 'WAITLIST_OFFER_DECLINED', label: 'Waitlist offer declined' },
  { value: 'WAITLIST_OFFER_EXPIRED', label: 'Waitlist offer expired' },
  { value: 'ADMIN_CREATED', label: 'Admin created' },
  { value: 'USER_ACTIVATED', label: 'User activated' },
  { value: 'USER_DEACTIVATED', label: 'User deactivated' },
  { value: 'ADMIN_SCOPE_UPDATED', label: 'Admin scope updated' },
  { value: 'DOCTOR_VERIFIED', label: 'Doctor verified' },
  { value: 'DOCTOR_SUSPENDED', label: 'Doctor suspended' },
  { value: 'DOCTOR_SET_PENDING', label: 'Doctor set pending' },
  { value: 'DOCTOR_AFFILIATIONS_UPDATED', label: 'Doctor affiliations updated' },
  { value: 'DOCTOR_INTAKE_UPDATED', label: 'Doctor intake updated' },
  { value: 'HOSPITAL_CREATED', label: 'Hospital created' },
  { value: 'HOSPITAL_UPDATED', label: 'Hospital updated' },
  { value: 'HOSPITAL_INTAKE_UPDATED', label: 'Hospital intake updated' },
  { value: 'DEPARTMENT_CREATED', label: 'Department created' },
  { value: 'DEPARTMENT_UPDATED', label: 'Department updated' },
  { value: 'DEPARTMENT_INTAKE_UPDATED', label: 'Department intake updated' },
  { value: 'ROUTING_RULE_CREATED', label: 'Routing rule created' },
  { value: 'ROUTING_RULE_UPDATED', label: 'Routing rule updated' },
  { value: 'ROUTING_RULE_DELETED', label: 'Routing rule deleted' },
  { value: 'MAINTENANCE_RUN', label: 'Housekeeping run' },
  { value: 'MEDICAL_DOCUMENT_UPLOADED', label: 'Medical doc uploaded (meta)' },
  { value: 'MEDICAL_DOCUMENT_VIEWED', label: 'Medical doc viewed (meta)' },
  { value: 'MEDICAL_DOCUMENT_DOWNLOADED', label: 'Medical doc downloaded (meta)' },
  { value: 'MEDICAL_DOCUMENT_DELETED', label: 'Medical doc deleted (meta)' },
  { value: 'MEDICAL_DOCUMENT_SHARED', label: 'Medical doc shared (meta)' },
  { value: 'MEDICAL_DOCUMENT_REVOKED', label: 'Medical doc access revoked (meta)' },
  { value: 'MEDICAL_DOCUMENT_UNAUTHORIZED_ATTEMPT', label: 'Medical doc unauthorized attempt' },
  { value: 'SECURITY_ALERT_TRIGGERED', label: 'Security threshold alert triggered' },
]
