import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  BellRing,
  CalendarCheck,
  CalendarClock,
  CalendarPlus,
  CalendarX,
  Check,
  CheckCircle2,
  Clock,
  Megaphone,
  RefreshCcw,
  Shield,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { NOTIFICATION_CATEGORY_LABEL, NOTIFICATION_LABEL } from '../utils/constants'
import { relativeTime } from '../utils/format'

const ICONS = {
  APPOINTMENT_REQUESTED: CalendarPlus,
  APPOINTMENT_ACCEPTED: CalendarCheck,
  APPOINTMENT_REJECTED: CalendarX,
  APPOINTMENT_CANCELLED: CalendarX,
  APPOINTMENT_RESCHEDULED: RefreshCcw,
  RESCHEDULE_REQUESTED: CalendarClock,
  RESCHEDULE_APPROVED: CalendarCheck,
  RESCHEDULE_REJECTED: CalendarX,
  APPOINTMENT_REMINDER: CalendarClock,
  WAITLIST_SLOT_AVAILABLE: Sparkles,
  WAITLIST_ELIGIBLE: Sparkles,
  WAITLIST_EXPIRED: Clock,
  DOCTOR_VERIFIED: CheckCircle2,
  DOCTOR_SUSPENDED: AlertTriangle,
  ACCOUNT_STATUS_CHANGED: Shield,
  SYSTEM_ANNOUNCEMENT: Megaphone,
}

const TONE = {
  APPOINTMENT_ACCEPTED: 'bg-ok-soft text-ok',
  APPOINTMENT_REJECTED: 'bg-danger-soft text-danger',
  APPOINTMENT_CANCELLED: 'bg-danger-soft text-danger',
  RESCHEDULE_APPROVED: 'bg-ok-soft text-ok',
  RESCHEDULE_REJECTED: 'bg-danger-soft text-danger',
  RESCHEDULE_REQUESTED: 'bg-warn-soft text-warn',
  APPOINTMENT_REMINDER: 'bg-warn-soft text-warn',
  WAITLIST_SLOT_AVAILABLE: 'bg-info-soft text-info',
  WAITLIST_ELIGIBLE: 'bg-info-soft text-info',
  WAITLIST_EXPIRED: 'bg-surface-sunken text-ink-muted',
  DOCTOR_VERIFIED: 'bg-ok-soft text-ok',
  DOCTOR_SUSPENDED: 'bg-danger-soft text-danger',
  ACCOUNT_STATUS_CHANGED: 'bg-info-soft text-info',
  SYSTEM_ANNOUNCEMENT: 'bg-forest-50 text-forest-600',
}

const CATEGORY_PILL_TONE = {
  APPOINTMENT: 'bg-forest-50 text-forest-700',
  RESCHEDULING: 'bg-warn-soft text-warn',
  CANCELLATION: 'bg-danger-soft text-danger',
  WAITLIST: 'bg-info-soft text-info',
  SYSTEM: 'bg-surface-sunken text-forest-700',
}

export function NotificationItem({
  notification: n,
  onMarkRead,
  onDelete,
  appointmentPathPrefix = '/appointments',
}) {
  const Icon = ICONS[n.type] || BellRing
  const tone = TONE[n.type] || 'bg-forest-50 text-forest-500'

  // Resolve target link based on action_url or related resource
  const actionTarget =
    n.action_url ||
    (n.related_appointment_id
      ? `${appointmentPathPrefix}/${n.related_appointment_id}`
      : n.data?.url || null)

  const actionText =
    n.category === 'WAITLIST'
      ? 'Book slot'
      : n.category === 'RESCHEDULING'
      ? 'View reschedule'
      : n.category === 'SYSTEM'
      ? 'View details'
      : 'View appointment'

  return (
    <li
      className={`group flex items-start gap-3.5 px-5 py-4 transition-colors ${
        n.is_read ? 'bg-surface' : 'bg-forest-50/40'
      }`}
    >
      <span className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${tone}`}>
        <Icon size={17} aria-hidden="true" />
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-forest-700">
              {n.title || NOTIFICATION_LABEL[n.type] || n.type}
            </p>
            {n.category && (
              <span
                className={`rounded px-1.5 py-0.5 text-[0.65rem] font-medium uppercase tracking-wider ${
                  CATEGORY_PILL_TONE[n.category] || 'bg-surface-sunken text-ink-muted'
                }`}
              >
                {NOTIFICATION_CATEGORY_LABEL[n.category] || n.category}
              </span>
            )}
          </div>
          <time className="shrink-0 text-xs text-ink-faint" dateTime={n.created_at}>
            {relativeTime(n.created_at)}
          </time>
        </div>

        <p className="mt-1 text-sm leading-relaxed text-ink-muted">{n.message}</p>

        <div className="mt-2.5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            {actionTarget && (
              <Link
                to={actionTarget}
                onClick={() => {
                  if (!n.is_read && onMarkRead) onMarkRead(n.id)
                }}
                className="rounded text-xs font-semibold text-forest transition-colors hover:text-forest-400 focus-ring"
              >
                {actionText} →
              </Link>
            )}
            {!n.is_read && onMarkRead && (
              <button
                type="button"
                onClick={() => onMarkRead(n.id)}
                className="inline-flex items-center gap-1 rounded text-xs text-ink-muted transition-colors hover:text-forest focus-ring"
              >
                <Check size={13} />
                Mark as read
              </button>
            )}
          </div>

          {onDelete && (
            <button
              type="button"
              onClick={() => onDelete(n.id)}
              className="opacity-70 group-hover:opacity-100 rounded p-1 text-ink-faint transition-colors hover:text-danger focus-ring"
              title="Dismiss notification"
              aria-label="Dismiss notification"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>

      {!n.is_read && (
        <span
          className="mt-2 h-2 w-2 shrink-0 rounded-full bg-forest"
          aria-label="Unread"
          title="Unread"
        />
      )}
    </li>
  )
}
