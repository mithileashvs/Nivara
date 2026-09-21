import { Link } from 'react-router-dom'
import { Building2, BadgeCheck } from 'lucide-react'
import { Avatar } from './ui/Avatar'
import { Badge } from './ui/StatusBadge'
import { RatingStars } from './RatingStars'
import { CONSULTATION_LABEL } from '../utils/constants'
import { currency, formatTime, pluralise } from '../utils/format'

/**
 * A doctor row. Everything shown comes from DoctorPublicOut plus, when the caller
 * has already fetched them, real bookable slots (`slots`) and resolved hospital
 * names (`hospitalNames`). Nothing here is fabricated.
 */
export function DoctorCard({ doctor, hospitalNames = [], slots = null, slotsLoading = false, to }) {
  const profilePath = to || `/doctors/${doctor.id}`
  const bookable = (slots || []).filter((s) => s.bookable)
  const closed = doctor.availability_status === 'CLOSED'

  return (
    <article className="card p-5 transition-colors hover:border-forest-200">
      <div className="flex flex-wrap items-start gap-4">
        <Avatar name={doctor.name} size="lg" />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-base font-semibold text-forest-700">
              <Link to={profilePath} className="rounded transition-colors hover:text-forest focus-ring">
                {doctor.name}
              </Link>
            </h3>
            <BadgeCheck size={16} className="shrink-0 text-forest-400" aria-label="Verified on Nivara" />
          </div>

          <p className="mt-0.5 text-sm text-ink-muted">{doctor.specialty}</p>

          {hospitalNames.length > 0 && (
            <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-muted">
              <Building2 size={14} className="shrink-0 text-ink-faint" aria-hidden="true" />
              <span className="truncate">{hospitalNames.join(' · ')}</span>
            </p>
          )}

          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
            <RatingStars average={doctor.rating_average} count={doctor.rating_count} />
            {doctor.experience > 0 && (
              <span className="text-xs text-ink-muted">
                {pluralise(doctor.experience, 'year', 'years')} of experience
              </span>
            )}
            {doctor.consultation_fee > 0 && (
              <span className="text-xs text-ink-muted">Consultation fee {currency(doctor.consultation_fee)}</span>
            )}
          </div>

          {doctor.consultation_types?.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {doctor.consultation_types.map((t) => (
                <span key={t} className="rounded-md bg-forest-50 px-2 py-0.5 text-[0.7rem] text-forest-500">
                  {CONSULTATION_LABEL[t] || t}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex shrink-0 flex-col items-stretch gap-2 sm:items-end">
          {closed ? (
            <Badge tone="neutral">Not taking new requests</Badge>
          ) : slotsLoading ? (
            <span className="skeleton h-6 w-28 rounded-full" />
          ) : slots ? (
            bookable.length > 0 ? (
              <Badge tone="positive">{pluralise(bookable.length, 'open slot', 'open slots')}</Badge>
            ) : (
              <Badge tone="neutral">No open slots</Badge>
            )
          ) : null}
          <Link
            to={profilePath}
            className="inline-flex h-9 items-center justify-center rounded-lg bg-forest px-3 text-sm font-medium text-canvas transition-colors hover:bg-forest-700 focus-ring"
          >
            View profile
          </Link>
        </div>
      </div>

      {/* Real next slots, when the caller supplied them. */}
      {bookable.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4">
          <span className="text-xs text-ink-muted">Next available</span>
          {bookable.slice(0, 4).map((slot) => (
            <Link
              key={slot.id}
              to={`${profilePath}?date=${slot.date}&slot=${slot.id}`}
              className="rounded-lg border border-line px-2.5 py-1 text-xs font-medium text-forest-600 transition-colors hover:border-forest-300 hover:bg-forest-50 focus-ring"
            >
              {formatTime(slot.start_time)}
            </Link>
          ))}
        </div>
      )}
    </article>
  )
}
