import { ROUTING_DISCLAIMER } from './constants'

/* The backend's error `code` is stable, so the copy below is keyed off it rather
 * than off message text. Anything unmapped falls back to the backend's own
 * message, which is always user-safe (no stack traces are ever returned). */

const CODE_MESSAGES = {
  // slot bookability (app/services/slot_rules.py — codes are the lower-cased reasons)
  slot_booked: 'That slot has just been booked. Choose another time.',
  slot_held: 'Another patient is already waiting on a decision for that slot. Choose another time.',
  slot_blocked: 'That slot is not open for booking.',
  slot_in_past: 'That slot has already started. Choose a later time.',
  slot_too_soon: 'That slot starts too soon to accept a new request. Choose a later time.',
  slot_unavailable: 'That slot is no longer available. Please choose another slot.',
  doctor_not_active: 'This doctor is not currently accepting patients on Nivara.',
  doctor_intake_closed: 'This doctor is not taking new appointment requests right now.',
  doctor_not_affiliated: 'This doctor no longer works in that department.',
  hospital_intake_closed: 'This hospital is not taking new appointment requests right now.',
  department_intake_closed: 'This department is not taking new appointment requests right now.',
  department_inactive: 'This department is not active.',
  hospital_not_found: 'That hospital is no longer available.',
  department_not_found: 'That department is no longer available.',

  // appointment lifecycle
  invalid_status_transition: 'This appointment has already moved on. Refresh to see its current state.',
  appointment_changed: 'This appointment changed while you were working on it. Refresh and try again.',
  appointment_not_pending: 'This request is no longer awaiting a decision.',
  appointment_not_started: 'You can only do this once the appointment has started.',
  appointment_started: 'This appointment has already started and can no longer be changed.',
  appointment_not_completed: 'This is only available after the consultation is completed.',
  request_expired: 'This request held its slot for too long and has expired.',
  patient_time_conflict: 'You already have an appointment that overlaps this time.',
  different_doctor: 'You can only move an appointment to another slot of the same doctor.',
  same_slot: 'That is the slot the appointment is already in.',
  too_many_pending: 'You have reached the limit of pending requests. Wait for a decision first.',

  // records, reviews, waitlist
  record_exists: 'Notes already exist for this appointment. Edit them instead.',
  review_exists: 'You have already reviewed this appointment.',
  invalid_file_url: 'That link is not an allowed document location.',
  waitlist_limit_reached: 'You have reached the limit of active waitlist entries.',
  waitlist_not_active: 'This waitlist entry is no longer active.',

  // scheduling windows
  window_too_short: 'That window is shorter than one slot. Widen it or shorten the slot length.',
  invalid_time_range: 'The end time must be after the start time.',
  invalid_date_range: 'Check the date range — the end date must not be before the start date.',
  date_in_past: 'Choose a date that has not already passed.',
  date_too_far: 'That date is beyond the scheduling window the hospital allows.',
  consultation_type_not_offered: 'This doctor does not offer that consultation type.',

  // auth and access
  email_taken: 'An account with that email already exists.',
  invalid_credentials: 'That email and password do not match an account.',
  not_authenticated: 'Sign in to continue.',
  token_expired: 'Your session has ended. Sign in again to continue.',
  invalid_token: 'Your session is no longer valid. Sign in again.',
  forbidden_role: 'Your account type cannot do this.',
  profile_missing: 'Your profile is incomplete. Contact support to finish setting it up.',
  platform_admin_required: 'This needs a platform-wide administrator account.',
  hospital_scope_forbidden: 'You can only manage the hospitals assigned to you.',
  cannot_modify_self: 'You cannot change your own account status.',
  rate_limited: 'Too many attempts. Wait a moment and try again.',
}

/** Pick the clearest message we can show for a normalised API error. */
export function errorMessage(error) {
  if (!error) return 'Something went wrong.'
  if (typeof error === 'string') return error
  return CODE_MESSAGES[error.code] || error.message || 'Something went wrong.'
}

/** True when the failure is worth re-picking a slot for. */
export function isSlotConflict(error) {
  return (
    error?.status === 409 &&
    [
      'slot_booked',
      'slot_held',
      'slot_blocked',
      'slot_in_past',
      'slot_too_soon',
      'slot_unavailable',
    ].includes(error.code)
  )
}

export function isIntakeClosed(error) {
  return ['doctor_intake_closed', 'hospital_intake_closed', 'department_intake_closed'].includes(
    error?.code,
  )
}

/** 422 bodies carry [{loc, message, type}] — turn them into { field: message }. */
export function fieldErrors(error) {
  if (error?.status !== 422 || !Array.isArray(error.details)) return {}
  const out = {}
  for (const d of error.details) {
    const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : null
    if (field && !out[field]) out[field] = d.message
  }
  return out
}

export { ROUTING_DISCLAIMER }
