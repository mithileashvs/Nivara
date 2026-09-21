import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Building2, CalendarDays, CheckCircle2, Clock, Stethoscope } from 'lucide-react'
import { Stepper } from '../../components/Stepper'
import { SlotSelector } from '../../components/SlotSelector'
import { Calendar } from '../../components/Calendar'
import { Avatar } from '../../components/ui/Avatar'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Select, Textarea } from '../../components/ui/Field'
import { ErrorState, LoadingSkeleton } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import { getDoctor } from '../../api/doctors'
import { searchSlots } from '../../api/slots'
import { requestAppointment } from '../../api/appointments'
import { CONSULTATION_LABEL, CONSULTATION_TYPES, MAX_PAGE_SIZE } from '../../utils/constants'
import { addDays, formatDate, formatTimeRange, todayString } from '../../utils/format'
import { errorMessage, isSlotConflict } from '../../utils/errors'

const STEPS = ['Select slot', 'Appointment details', 'Confirmation']

/**
 * Three-step booking. Step three submits POST /appointments, which creates a
 * REQUESTED appointment and holds the slot — it does not confirm anything. A 409
 * (slot taken, intake closed) drops the patient back to step one with the
 * backend's own reason and freshly reloaded availability.
 */
export default function BookAppointment() {
  useDocumentTitle('Book an appointment')
  const { doctorId } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const toast = useToast()
  const { hospitalById, departmentById } = useDirectory()

  const [step, setStep] = useState(1)
  const [selectedDate, setSelectedDate] = useState(todayString())
  const [slotId, setSlotId] = useState(params.get('slot') || null)
  const [consultationType, setConsultationType] = useState('')
  const [reason, setReason] = useState('')
  const [submitError, setSubmitError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const doctor = useAsync(() => getDoctor(doctorId), [doctorId])

  const from = todayString()
  const to = useMemo(() => addDays(from, 30), [from])
  const slots = useAsync(
    () => searchSlots({ doctor_id: doctorId, date_from: from, date_to: to, page: 1, page_size: MAX_PAGE_SIZE }),
    [doctorId, from, to],
  )

  const allSlots = slots.data?.items ?? []
  const slot = useMemo(() => allSlots.find((s) => s.id === slotId) || null, [allSlots, slotId])
  const availableDates = useMemo(
    () => [...new Set(allSlots.filter((s) => s.bookable).map((s) => s.date))],
    [allSlots],
  )
  const daySlots = useMemo(
    () => allSlots.filter((s) => s.date === selectedDate).sort((a, b) => a.start_time.localeCompare(b.start_time)),
    [allSlots, selectedDate],
  )

  // Follow a slot passed in from the profile page.
  useEffect(() => {
    if (slot) setSelectedDate(slot.date)
  }, [slot])

  // Default the consultation type to one this doctor actually offers.
  useEffect(() => {
    const offered = doctor.data?.consultation_types
    if (offered?.length && !consultationType) setConsultationType(offered[0])
  }, [doctor.data, consultationType])

  if (doctor.loading) return <LoadingSkeleton variant="cards" rows={1} />
  if (doctor.error) return <ErrorState error={doctor.error} onRetry={doctor.reload} />

  const d = doctor.data
  const hospital = slot ? hospitalById[slot.hospital_id] : null
  const department = slot ? departmentById[slot.department_id] : null

  const typeOptions = (d.consultation_types?.length
    ? CONSULTATION_TYPES.filter((t) => d.consultation_types.includes(t.value))
    : CONSULTATION_TYPES)

  const submit = async () => {
    setSubmitting(true)
    setSubmitError(null)
    try {
      const appointment = await requestAppointment({
        slot_id: slot.id,
        consultation_type: consultationType || undefined,
        reason: reason.trim() || undefined,
      })
      toast.success('Request sent. Your doctor will confirm or decline it.')
      navigate(`/appointments/${appointment.id}`, { replace: true })
    } catch (err) {
      setSubmitError(err)
      if (isSlotConflict(err)) {
        // The slot moved on — reload real availability and send them back to pick again.
        setSlotId(null)
        setStep(1)
        slots.reload()
      }
      toast.error(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        to={`/doctors/${doctorId}`}
        className="inline-flex items-center gap-1.5 rounded text-sm font-medium text-ink-muted transition-colors hover:text-forest focus-ring"
      >
        <ArrowLeft size={16} aria-hidden="true" />
        Back to profile
      </Link>

      <h1 className="text-2xl font-bold text-forest-700">Book appointment</h1>

      <Stepper steps={STEPS} current={step} />

      {submitError && <ErrorState error={submitError} compact />}

      {/* ---------------------------------------------------------- step 1 */}
      {step === 1 && (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
          <Card>
            <CardBody>
              <Calendar
                value={selectedDate}
                onChange={setSelectedDate}
                availableDates={availableDates}
                minDate={from}
                maxDate={to}
              />
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Choose a time" description={formatDate(selectedDate)} />
            <CardBody className="space-y-5">
              <SlotSelector
                slots={daySlots}
                value={slotId}
                onChange={(s) => setSlotId(s.id)}
                loading={slots.loading}
                error={slots.error}
                onRetry={slots.reload}
              />
              <Button
                size="lg"
                className="w-full justify-center"
                disabled={!slot?.bookable}
                onClick={() => setStep(2)}
              >
                Continue
              </Button>
            </CardBody>
          </Card>
        </div>
      )}

      {/* ---------------------------------------------------------- step 2 */}
      {step === 2 && slot && (
        <>
          <Summary doctor={d} slot={slot} hospital={hospital} department={department} consultationType={consultationType} />
          <Card>
            <CardHeader title="Appointment details" />
            <CardBody className="space-y-5">
              <Select
                label="Consultation type"
                value={consultationType}
                onChange={(e) => setConsultationType(e.target.value)}
                options={typeOptions}
                hint="Only the types this doctor offers are listed."
                required
              />
              <Textarea
                label="Reason for visit (optional)"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={4}
                maxLength={500}
                placeholder="Briefly describe what you'd like to discuss."
                hint={`${reason.length}/500 — shared with your doctor only.`}
              />
              <div className="flex flex-wrap gap-3">
                <Button variant="outline" size="lg" className="flex-1 justify-center" onClick={() => setStep(1)}>
                  Back
                </Button>
                <Button size="lg" className="flex-1 justify-center" onClick={() => setStep(3)} disabled={!consultationType}>
                  Continue
                </Button>
              </div>
            </CardBody>
          </Card>
        </>
      )}

      {/* ---------------------------------------------------------- step 3 */}
      {step === 3 && slot && (
        <>
          <Summary doctor={d} slot={slot} hospital={hospital} department={department} consultationType={consultationType} />

          {reason.trim() && (
            <Card>
              <CardHeader title="Reason for visit" />
              <CardBody>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-muted">{reason}</p>
              </CardBody>
            </Card>
          )}

          <Card className="border-forest-200 bg-forest-50/60">
            <CardBody className="flex gap-3">
              <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-forest-400" aria-hidden="true" />
              <div className="text-sm leading-relaxed text-ink-muted">
                <p className="font-semibold text-forest-700">What happens next</p>
                <p className="mt-1">
                  This sends a request to {d.name} and holds the time while they decide. The
                  appointment shows as awaiting a decision until they accept it. You will be notified
                  either way.
                </p>
              </div>
            </CardBody>
          </Card>

          <div className="flex flex-wrap gap-3">
            <Button variant="outline" size="lg" className="flex-1 justify-center" onClick={() => setStep(2)} disabled={submitting}>
              Back
            </Button>
            <Button size="lg" className="flex-1 justify-center" onClick={submit} loading={submitting}>
              Send request
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

function Summary({ doctor, slot, hospital, department, consultationType }) {
  return (
    <Card>
      <CardHeader title="Appointment summary" />
      <CardBody className="space-y-4">
        <div className="flex items-center gap-3">
          <Avatar name={doctor.name} size="md" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-forest-700">{doctor.name}</p>
            <p className="truncate text-xs text-ink-muted">{doctor.specialty}</p>
          </div>
        </div>

        <dl className="grid gap-3 sm:grid-cols-2">
          <Row icon={CalendarDays} label="Date" value={formatDate(slot.date)} />
          <Row icon={Clock} label="Time" value={formatTimeRange(slot.start_time, slot.end_time)} />
          <Row icon={Building2} label="Hospital" value={hospital?.name || '—'} />
          <Row icon={Stethoscope} label="Department" value={department?.name || '—'} />
          <Row
            icon={CheckCircle2}
            label="Consultation type"
            value={CONSULTATION_LABEL[consultationType] || '—'}
          />
        </dl>
      </CardBody>
    </Card>
  )
}

function Row({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-2.5">
      <Icon size={15} className="mt-0.5 shrink-0 text-ink-faint" aria-hidden="true" />
      <div className="min-w-0">
        <dt className="text-xs text-ink-muted">{label}</dt>
        <dd className="truncate text-sm font-medium text-forest-700">{value}</dd>
      </div>
    </div>
  )
}
