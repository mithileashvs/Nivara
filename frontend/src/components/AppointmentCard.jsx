import { Clock, Building2, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { DateBlock } from './DateBlock'
import { StatusBadge } from './ui/StatusBadge'
import { Avatar } from './ui/Avatar'
import { CONSULTATION_LABEL } from '../utils/constants'
import { formatTimeRange } from '../utils/format'

/**
 * One appointment, as in the reference: date tile, who/where, time, status pill.
 * `perspective` decides whether the patient or the doctor is the named party.
 */
export function AppointmentCard({
  appointment: a,
  perspective = 'patient',
  hospitalName,
  departmentName,
  to,
  actions,
  compact = false,
}) {
  const counterparty = perspective === 'patient' ? a.doctor_name : a.patient_name
  const subtitle = perspective === 'patient' ? a.specialty : null
  const detailPath = to || (perspective === 'patient' ? `/appointments/${a.id}` : `/doctor/appointments/${a.id}`)

  return (
    <article className="card flex flex-wrap items-center gap-4 p-4 transition-colors hover:border-forest-200">
      <DateBlock date={a.appointment_date} size={compact ? 'sm' : 'md'} />

      <div className="flex min-w-0 flex-1 items-center gap-3">
        <Avatar name={counterparty} size="sm" className="hidden sm:inline-flex" />
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-forest-700">{counterparty}</h3>
          <p className="mt-0.5 truncate text-xs text-ink-muted">
            {[subtitle, hospitalName || null, departmentName || null].filter(Boolean).join(' · ') || '\u00A0'}
          </p>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
            <span className="inline-flex items-center gap-1">
              <Clock size={13} aria-hidden="true" />
              {formatTimeRange(a.start_time, a.end_time)}
            </span>
            <span className="inline-flex items-center gap-1">
              <Building2 size={13} aria-hidden="true" />
              {CONSULTATION_LABEL[a.consultation_type] || a.consultation_type}
            </span>
          </p>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <StatusBadge status={a.status} />
        {actions}
        <Link
          to={detailPath}
          className="rounded-lg p-1.5 text-ink-faint transition-colors hover:bg-forest-50 hover:text-forest focus-ring"
          aria-label={`View appointment with ${counterparty}`}
        >
          <ChevronRight size={18} />
        </Link>
      </div>
    </article>
  )
}
