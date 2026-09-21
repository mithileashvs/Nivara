import { Link } from 'react-router-dom'
import {
  BellRing, CalendarCheck, CalendarClock, CalendarX, CalendarPlus, RefreshCcw, Sparkles,
} from 'lucide-react'
import { NOTIFICATION_LABEL } from '../utils/constants'
import { relativeTime } from '../utils/format'

const ICONS = {
  APPOINTMENT_REQUESTED: CalendarPlus,
  APPOINTMENT_ACCEPTED: CalendarCheck,
  APPOINTMENT_REJECTED: CalendarX,
  APPOINTMENT_CANCELLED: CalendarX,
  APPOINTMENT_RESCHEDULED: RefreshCcw,
  APPOINTMENT_REMINDER: CalendarClock,
  WAITLIST_SLOT_AVAILABLE: Sparkles,
}

const TONE = {
  APPOINTMENT_ACCEPTED: 'bg-ok-soft text-ok',
  APPOINTMENT_REJECTED: 'bg-danger-soft text-danger',
  APPOINTMENT_CANCELLED: 'bg-danger-soft text-danger',
  APPOINTMENT_REMINDER: 'bg-warn-soft text-warn',
  WAITLIST_SLOT_AVAILABLE: 'bg-info-soft text-info',
}

export function NotificationItem({ notification: n, onMarkRead, appointmentPathPrefix = '/appointments' }) {
  const Icon = ICONS[n.type] || BellRing
  const tone = TONE[n.type] || 'bg-forest-50 text-forest-500'

  return (
    <li
      className={`flex gap-3.5 px-5 py-4 transition-colors ${n.is_read ? '' : 'bg-forest-50/50'}`}
    >
      <span className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${tone}`}>
        <Icon size={17} aria-hidden="true" />
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <p className="text-sm font-semibold text-forest-700">
            {n.title || NOTIFICATION_LABEL[n.type] || n.type}
          </p>
          <time className="shrink-0 text-xs text-ink-faint" dateTime={n.created_at}>
            {relativeTime(n.created_at)}
          </time>
        </div>

        <p className="mt-1 text-sm leading-relaxed text-ink-muted">{n.message}</p>

        <div className="mt-2 flex flex-wrap items-center gap-4">
          {n.related_appointment_id && (
            <Link
              to={`${appointmentPathPrefix}/${n.related_appointment_id}`}
              className="rounded text-xs font-medium text-forest transition-colors hover:text-forest-400 focus-ring"
            >
              View appointment
            </Link>
          )}
          {!n.is_read && onMarkRead && (
            <button
              type="button"
              onClick={() => onMarkRead(n.id)}
              className="rounded text-xs text-ink-muted transition-colors hover:text-forest focus-ring"
            >
              Mark as read
            </button>
          )}
        </div>
      </div>

      {!n.is_read && (
        <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-forest" aria-label="Unread" />
      )}
    </li>
  )
}
