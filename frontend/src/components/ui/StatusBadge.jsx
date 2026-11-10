import {
  AlertTriangle,
  Ban,
  CalendarCheck,
  CheckCheck,
  CheckCircle2,
  Clock,
  Lock,
  RefreshCw,
  XCircle,
} from 'lucide-react'
import { APPOINTMENT_STATUS_LABEL } from '../../utils/constants'
import { humanise } from '../../utils/format'

const TONES = {
  neutral: 'bg-forest-50 text-forest-600 border-forest-100',
  positive: 'bg-ok-soft text-ok border-ok/25',
  ok: 'bg-ok-soft text-ok border-ok/25',
  pending: 'bg-warn-soft text-warn border-warn/25',
  warn: 'bg-warn-soft text-warn border-warn/25',
  negative: 'bg-danger-soft text-danger border-danger/25',
  info: 'bg-info-soft text-info border-info/25',
}

const APPOINTMENT_TONE = {
  REQUESTED: 'pending',
  CONFIRMED: 'positive',
  RESCHEDULE_REQUESTED: 'pending',
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
  APPROVED: 'positive',
  REJECTED: 'negative',
  DECLINED: 'negative',
  CANCELLED: 'neutral',
  ACCEPTED: 'positive',
  GRANTED: 'positive',
  REVOKED: 'negative',
}

const STATUS_ICON = {
  REQUESTED: Clock,
  CONFIRMED: CheckCircle2,
  RESCHEDULE_REQUESTED: RefreshCw,
  COMPLETED: CheckCheck,
  REJECTED: XCircle,
  CANCELLED: Ban,
  NO_SHOW: AlertTriangle,
  OPEN: CheckCircle2,
  CLOSED: Lock,
  ACTIVE: CheckCircle2,
  INACTIVE: Ban,
  PENDING: Clock,
  SUSPENDED: AlertTriangle,
  AVAILABLE: CheckCircle2,
  HELD: Clock,
  BOOKED: CalendarCheck,
  BLOCKED: Lock,
  WORKING: CheckCircle2,
  FULFILLED: CheckCheck,
  EXPIRED: Clock,
  APPROVED: CheckCircle2,
  DECLINED: XCircle,
  ACCEPTED: CheckCircle2,
  GRANTED: CheckCircle2,
  REVOKED: Ban,
}

export function Badge({ tone = 'neutral', icon: Icon, className = '', children }) {
  const toneClass = TONES[tone] || TONES.neutral
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${toneClass} ${className}`}
    >
      {Icon && <Icon size={12} strokeWidth={2.2} className="shrink-0" aria-hidden="true" />}
      {children}
    </span>
  )
}

/** Appointment statuses get patient-facing wording; everything else is title-cased. */
export function StatusBadge({ status, kind = 'appointment', showIcon = true, className = '' }) {
  if (!status) return null
  const isAppointment = kind === 'appointment' && status in APPOINTMENT_TONE
  const tone = isAppointment ? APPOINTMENT_TONE[status] : GENERIC_TONE[status] || 'neutral'
  const label = isAppointment ? APPOINTMENT_STATUS_LABEL[status] : humanise(status)
  const Icon = showIcon ? STATUS_ICON[status] : null
  return (
    <Badge tone={tone} icon={Icon} className={className}>
      {label}
    </Badge>
  )
}
