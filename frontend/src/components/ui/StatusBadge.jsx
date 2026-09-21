import { APPOINTMENT_STATUS_LABEL } from '../../utils/constants'
import { humanise } from '../../utils/format'

const TONES = {
  neutral: 'bg-forest-50 text-forest-600 border-forest-100',
  positive: 'bg-ok-soft text-ok border-ok/25',
  pending: 'bg-warn-soft text-warn border-warn/25',
  negative: 'bg-danger-soft text-danger border-danger/25',
  info: 'bg-info-soft text-info border-info/25',
}

const APPOINTMENT_TONE = {
  REQUESTED: 'pending',
  CONFIRMED: 'positive',
  COMPLETED: 'info',
  REJECTED: 'negative',
  CANCELLED: 'neutral',
  NO_SHOW: 'negative',
}

const GENERIC_TONE = {
  OPEN: 'positive',
  CLOSED: 'negative',
  ACTIVE: 'positive',
  INACTIVE: 'neutral',
  PENDING: 'pending',
  SUSPENDED: 'negative',
  AVAILABLE: 'positive',
  HELD: 'pending',
  BOOKED: 'info',
  BLOCKED: 'neutral',
  WORKING: 'positive',
  FULFILLED: 'info',
  EXPIRED: 'neutral',
}

export function Badge({ tone = 'neutral', className = '', children }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  )
}

/** Appointment statuses get patient-facing wording; everything else is title-cased. */
export function StatusBadge({ status, kind = 'appointment', className = '' }) {
  if (!status) return null
  const isAppointment = kind === 'appointment' && status in APPOINTMENT_TONE
  const tone = isAppointment ? APPOINTMENT_TONE[status] : GENERIC_TONE[status] || 'neutral'
  const label = isAppointment ? APPOINTMENT_STATUS_LABEL[status] : humanise(status)
  return (
    <Badge tone={tone} className={className}>
      {label}
    </Badge>
  )
}
