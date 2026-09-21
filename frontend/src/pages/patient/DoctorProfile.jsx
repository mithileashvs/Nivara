import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, BadgeCheck, Bell, Building2, MapPin, Stethoscope } from 'lucide-react'
import { Calendar } from '../../components/Calendar'
import { SlotSelector } from '../../components/SlotSelector'
import { RatingStars } from '../../components/RatingStars'
import { Avatar } from '../../components/ui/Avatar'
import { Badge } from '../../components/ui/StatusBadge'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Tabs } from '../../components/ui/Tabs'
import { AsyncBoundary, EmptyState, ErrorState, LoadingBlock, LoadingSkeleton } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { getDoctor } from '../../api/doctors'
import { searchSlots } from '../../api/slots'
import { listDoctorReviews } from '../../api/reviews'
import { CONSULTATION_LABEL, MAX_PAGE_SIZE } from '../../utils/constants'
import { addDays, currency, formatInstant, formatLongDate, pluralise, todayString } from '../../utils/format'

/**
 * A doctor's public profile. Availability is drawn entirely from GET /slots for
 * this doctor: the calendar only marks days that actually contain bookable
 * slots, and times come straight from the response.
 */
export default function DoctorProfile() {
  const { doctorId } = useParams()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const { hospitalById, departmentById } = useDirectory()

  const [tab, setTab] = useState('availability')
  const [selectedDate, setSelectedDate] = useState(params.get('date') || todayString())
  const [selectedSlot, setSelectedSlot] = useState(null)

  const doctor = useAsync(() => getDoctor(doctorId), [doctorId])
  useDocumentTitle(doctor.data?.name)

  const horizonFrom = todayString()
  const horizonTo = useMemo(() => addDays(horizonFrom, 30), [horizonFrom])

  /* One request covers the whole horizon, so the calendar can mark real
     availability without a round trip per day. */
  const slots = useAsync(
    () =>
      searchSlots({
        doctor_id: doctorId,
        date_from: horizonFrom,
        date_to: horizonTo,
        page: 1,
        page_size: MAX_PAGE_SIZE,
      }),
    [doctorId, horizonFrom, horizonTo],
  )

  const allSlots = slots.data?.items ?? []
  const availableDates = useMemo(
    () => [...new Set(allSlots.filter((s) => s.bookable).map((s) => s.date))],
    [allSlots],
  )
  const daySlots = useMemo(
    () => allSlots.filter((s) => s.date === selectedDate).sort((a, b) => a.start_time.localeCompare(b.start_time)),
    [allSlots, selectedDate],
  )

  // Land on the first day that genuinely has openings.
  useEffect(() => {
    if (slots.loading || params.get('date')) return
    if (availableDates.length && !availableDates.includes(selectedDate)) {
      setSelectedDate([...availableDates].sort()[0])
    }
  }, [slots.loading, availableDates, selectedDate, params])

  useEffect(() => {
    setSelectedSlot(null)
  }, [selectedDate])

  const reviews = useAsync(
    () => listDoctorReviews(doctorId, { page: 1, page_size: 10 }),
    [doctorId],
    { enabled: tab === 'reviews' },
  )

  if (doctor.loading) return <LoadingSkeleton variant="cards" rows={1} />
  if (doctor.error) return <ErrorState error={doctor.error} onRetry={doctor.reload} />

  const d = doctor.data
  const hospitals = d.hospital_ids.map((id) => hospitalById[id]).filter(Boolean)
  const departments = d.department_ids.map((id) => departmentById[id]).filter(Boolean)
  const intakeClosed = d.availability_status === 'CLOSED'

  const book = () => {
    if (!selectedSlot) return
    navigate(`/book/${d.id}?slot=${selectedSlot.id}`)
  }

  return (
    <div className="space-y-6">
      <Link
        to="/find-doctors"
        className="inline-flex items-center gap-1.5 rounded text-sm font-medium text-ink-muted transition-colors hover:text-forest focus-ring"
      >
        <ArrowLeft size={16} aria-hidden="true" />
        Back to search
      </Link>

      <Card>
        <CardBody className="flex flex-wrap items-start gap-5">
          <Avatar name={d.name} size="xl" />

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-bold text-forest-700 sm:text-2xl">{d.name}</h1>
              <BadgeCheck size={18} className="text-forest-400" aria-label="Verified on Nivara" />
            </div>

            <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-muted">
              <Stethoscope size={14} aria-hidden="true" />
              {d.specialty}
            </p>

            {hospitals.map((h) => (
              <p key={h.id} className="mt-1 flex items-center gap-1.5 text-sm text-ink-muted">
                <Building2 size={14} aria-hidden="true" />
                {h.name}
                {h.location?.city && (
                  <>
                    <MapPin size={13} className="ml-1" aria-hidden="true" />
                    {h.location.city}
                  </>
                )}
              </p>
            ))}

            <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2">
              <RatingStars average={d.rating_average} count={d.rating_count} />
              {d.experience > 0 && (
                <span className="text-sm text-ink-muted">
                  {pluralise(d.experience, 'year', 'years')} of experience
                </span>
              )}
              {d.consultation_fee > 0 && (
                <span className="text-sm text-ink-muted">Fee {currency(d.consultation_fee)}</span>
              )}
            </div>
          </div>

          <div className="shrink-0">
            {intakeClosed ? (
              <Badge tone="negative">Not taking new requests</Badge>
            ) : (
              <Badge tone="positive">Accepting requests</Badge>
            )}
          </div>
        </CardBody>
      </Card>

      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { value: 'about', label: 'About' },
          { value: 'availability', label: 'Availability' },
          { value: 'reviews', label: 'Reviews' },
        ]}
      />

      {tab === 'about' && (
        <Card>
          <CardHeader title="Practice details" description="Everything Nivara holds on this profile." />
          <CardBody>
            <dl className="grid gap-5 sm:grid-cols-2">
              <Detail label="Specialty" value={d.specialty} />
              <Detail
                label="Experience"
                value={d.experience > 0 ? pluralise(d.experience, 'year', 'years') : 'Not stated'}
              />
              <Detail
                label="Consultation fee"
                value={d.consultation_fee > 0 ? currency(d.consultation_fee) : 'Not stated'}
              />
              <Detail
                label="Consultation types"
                value={
                  d.consultation_types?.length
                    ? d.consultation_types.map((t) => CONSULTATION_LABEL[t] || t).join(', ')
                    : 'Not stated'
                }
              />
              <Detail
                label="Hospitals"
                value={hospitals.length ? hospitals.map((h) => h.name).join(', ') : 'Not assigned'}
              />
              <Detail
                label="Departments"
                value={departments.length ? departments.map((x) => x.name).join(', ') : 'Not assigned'}
              />
            </dl>
            {/* The backend stores no free-text biography, so none is shown. */}
          </CardBody>
        </Card>
      )}

      {tab === 'availability' && (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
          <Card>
            <CardBody>
              {slots.loading ? (
                <LoadingBlock label="Loading availability" />
              ) : (
                <Calendar
                  value={selectedDate}
                  onChange={(date) => {
                    setSelectedDate(date)
                    setParams({ date }, { replace: true })
                  }}
                  availableDates={availableDates}
                  minDate={horizonFrom}
                  maxDate={horizonTo}
                />
              )}
              <p className="mt-4 flex items-center gap-2 border-t border-line pt-4 text-xs text-ink-muted">
                <span className="h-1.5 w-1.5 rounded-full bg-forest-300" aria-hidden="true" />
                Days with open times in the next 30 days
              </p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Available slots"
              description={formatLongDate(selectedDate)}
            />
            <CardBody className="space-y-5">
              {intakeClosed && (
                <p className="rounded-xl border border-warn/30 bg-warn-soft px-4 py-3 text-sm text-forest-700">
                  This doctor has paused new appointment requests. Appointments already booked with
                  them are unaffected.
                </p>
              )}

              <SlotSelector
                slots={daySlots}
                value={selectedSlot?.id}
                onChange={setSelectedSlot}
                loading={slots.loading}
                error={slots.error}
                onRetry={slots.reload}
              />

              <div className="flex flex-wrap gap-3 border-t border-line pt-5">
                <Button
                  size="lg"
                  className="flex-1 justify-center"
                  disabled={!selectedSlot || intakeClosed}
                  onClick={book}
                >
                  {selectedSlot ? 'Continue to booking' : 'Select a time'}
                </Button>
                <Link to={`/waitlist?doctor_id=${d.id}`} className="flex-1">
                  <Button variant="outline" size="lg" className="w-full justify-center">
                    <Bell size={16} aria-hidden="true" />
                    Notify me of openings
                  </Button>
                </Link>
              </div>

              <p className="text-xs leading-relaxed text-ink-muted">
                Choosing a time sends a request to {d.name}. They confirm or decline it — nothing is
                booked until they do.
              </p>
            </CardBody>
          </Card>
        </div>
      )}

      {tab === 'reviews' && (
        <Card>
          <CardHeader
            title="Reviews"
            description="Written by patients after a completed consultation. Names are never shown."
          />
          <AsyncBoundary
            loading={reviews.loading}
            error={reviews.error}
            onRetry={reviews.reload}
            isEmpty={(reviews.data?.items ?? []).length === 0}
            skeleton={<LoadingBlock label="Loading reviews" />}
            empty={
              <CardBody>
                <EmptyState title="No reviews yet" description="This doctor has not been reviewed on Nivara." />
              </CardBody>
            }
          >
            <ul className="divide-y divide-line">
              {(reviews.data?.items ?? []).map((r) => (
                <li key={r.id} className="px-5 py-4">
                  <div className="flex items-center justify-between gap-4">
                    <RatingStars average={r.rating} showCount={false} />
                    <time className="text-xs text-ink-faint" dateTime={r.created_at}>
                      {formatInstant(r.created_at)}
                    </time>
                  </div>
                  {r.comment && <p className="mt-2 text-sm leading-relaxed text-ink-muted">{r.comment}</p>}
                </li>
              ))}
            </ul>
          </AsyncBoundary>
        </Card>
      )}
    </div>
  )
}

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className="mt-1 text-sm text-forest-700">{value}</dd>
    </div>
  )
}
