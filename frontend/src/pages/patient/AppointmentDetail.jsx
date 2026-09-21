import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Building2, CalendarDays, Clock, History, Star, Stethoscope } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { Avatar } from '../../components/ui/Avatar'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { ConfirmationModal, Modal } from '../../components/ui/Modal'
import { Textarea, Select } from '../../components/ui/Field'
import { Calendar } from '../../components/Calendar'
import { SlotSelector } from '../../components/SlotSelector'
import { ErrorState, LoadingSkeleton } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import {
  cancelAppointment, getAppointment, getAppointmentHistory, rescheduleAppointment,
} from '../../api/appointments'
import { searchSlots } from '../../api/slots'
import { createReview, listMyReviews } from '../../api/reviews'
import { APPOINTMENT_STATUS, CONSULTATION_LABEL, MAX_PAGE_SIZE } from '../../utils/constants'
import { addDays, formatDate, formatInstant, formatTimeRange, humanise, todayString } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

/**
 * One appointment, from the patient's side. Which actions appear is derived from
 * the backend's own rules: cancel is only valid while REQUESTED or CONFIRMED and
 * before the start time; reschedule moves to another slot of the same doctor and
 * returns the appointment to REQUESTED for the doctor to approve again; a review
 * is only accepted once the consultation is COMPLETED.
 */
export default function AppointmentDetail() {
  useDocumentTitle('Appointment')
  const { appointmentId } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const { hospitalName, departmentName } = useDirectory()

  const appointment = useAsync(() => getAppointment(appointmentId), [appointmentId])
  const history = useAsync(() => getAppointmentHistory(appointmentId), [appointmentId])

  const [cancelOpen, setCancelOpen] = useState(false)
  const [cancelReason, setCancelReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [rescheduleOpen, setRescheduleOpen] = useState(false)
  const [reviewOpen, setReviewOpen] = useState(false)

  const a = appointment.data

  const myReviews = useAsync(() => listMyReviews({ page: 1, page_size: MAX_PAGE_SIZE }), [], {
    enabled: a?.status === APPOINTMENT_STATUS.COMPLETED,
  })
  const alreadyReviewed = useMemo(
    () => (myReviews.data?.items ?? []).some((r) => r.appointment_id === appointmentId),
    [myReviews.data, appointmentId],
  )

  if (appointment.loading) return <LoadingSkeleton variant="cards" rows={1} />
  if (appointment.error) return <ErrorState error={appointment.error} onRetry={appointment.reload} />

  const notStarted = new Date(a.start_at) > new Date()
  const isOpen = [APPOINTMENT_STATUS.REQUESTED, APPOINTMENT_STATUS.CONFIRMED].includes(a.status)
  const canCancel = isOpen && notStarted
  const canReschedule = isOpen && notStarted
  const canReview = a.status === APPOINTMENT_STATUS.COMPLETED && !alreadyReviewed

  const doCancel = async () => {
    setBusy(true)
    try {
      await cancelAppointment(a.id, cancelReason.trim() || undefined)
      toast.success('Appointment cancelled.')
      setCancelOpen(false)
      appointment.reload()
      history.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        to="/appointments"
        className="inline-flex items-center gap-1.5 rounded text-sm font-medium text-ink-muted transition-colors hover:text-forest focus-ring"
      >
        <ArrowLeft size={16} aria-hidden="true" />
        All appointments
      </Link>

      <PageHeader
        title="Appointment details"
        actions={<StatusBadge status={a.status} />}
      />

      {a.status === APPOINTMENT_STATUS.REQUESTED && (
        <p className="rounded-xl border border-warn/30 bg-warn-soft px-4 py-3 text-sm text-forest-700">
          Your time is held while {a.doctor_name} reviews this request. You will be notified as soon
          as they accept or decline it.
        </p>
      )}
      {a.status_reason && (
        <p className="rounded-xl border border-line bg-forest-50/60 px-4 py-3 text-sm text-ink-muted">
          <span className="font-medium text-forest-700">Note from the clinic: </span>
          {a.status_reason}
        </p>
      )}

      <Card>
        <CardBody className="space-y-5">
          <div className="flex items-center gap-3">
            <Avatar name={a.doctor_name} size="lg" />
            <div className="min-w-0">
              <Link
                to={`/doctors/${a.doctor_id}`}
                className="rounded text-base font-semibold text-forest-700 transition-colors hover:text-forest focus-ring"
              >
                {a.doctor_name}
              </Link>
              <p className="mt-0.5 text-sm text-ink-muted">{hospitalName(a.hospital_id) || '—'}</p>
            </div>
          </div>

          <dl className="grid gap-4 border-t border-line pt-5 sm:grid-cols-2">
            <Row icon={CalendarDays} label="Date" value={formatDate(a.appointment_date)} />
            <Row icon={Clock} label="Time" value={formatTimeRange(a.start_time, a.end_time)} />
            <Row icon={Building2} label="Hospital" value={hospitalName(a.hospital_id) || '—'} />
            <Row icon={Stethoscope} label="Department" value={departmentName(a.department_id) || '—'} />
            <Row
              icon={CalendarDays}
              label="Consultation type"
              value={CONSULTATION_LABEL[a.consultation_type] || a.consultation_type}
            />
          </dl>

          {a.reason && (
            <div className="border-t border-line pt-5">
              <p className="text-xs font-medium text-ink-muted">Reason you gave</p>
              <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed text-forest-700">{a.reason}</p>
            </div>
          )}
        </CardBody>
      </Card>

      {(canCancel || canReschedule || canReview) && (
        <div className="flex flex-wrap gap-3">
          {canReschedule && (
            <Button variant="outline" onClick={() => setRescheduleOpen(true)}>
              Reschedule
            </Button>
          )}
          {canCancel && (
            <Button variant="danger" onClick={() => setCancelOpen(true)}>
              Cancel appointment
            </Button>
          )}
          {canReview && (
            <Button variant="secondary" onClick={() => setReviewOpen(true)}>
              <Star size={15} aria-hidden="true" />
              Leave a review
            </Button>
          )}
        </div>
      )}

      <Card>
        <CardHeader
          title="Status history"
          description="Every change to this appointment, and who made it."
        />
        {history.loading ? (
          <CardBody>
            <div className="skeleton h-16 w-full" />
          </CardBody>
        ) : history.error ? (
          <CardBody>
            <ErrorState error={history.error} onRetry={history.reload} compact />
          </CardBody>
        ) : (
          <ol className="divide-y divide-line">
            {(history.data ?? []).map((h) => (
              <li key={h.id} className="flex gap-3.5 px-5 py-4">
                <History size={16} className="mt-0.5 shrink-0 text-ink-faint" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-forest-700">
                    {h.previous_status ? `${humanise(h.previous_status)} → ` : ''}
                    <span className="font-semibold">{humanise(h.new_status)}</span>
                  </p>
                  <p className="mt-0.5 text-xs text-ink-muted">
                    by {humanise(h.changed_by_role)} · {formatInstant(h.created_at)}
                  </p>
                  {h.reason && <p className="mt-1 text-sm text-ink-muted">{h.reason}</p>}
                </div>
              </li>
            ))}
          </ol>
        )}
      </Card>

      <ConfirmationModal
        open={cancelOpen}
        onClose={() => setCancelOpen(false)}
        onConfirm={doCancel}
        loading={busy}
        tone="danger"
        title="Cancel this appointment?"
        confirmLabel="Cancel appointment"
        cancelLabel="Keep it"
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-muted">
            The time is released straight away and offered to anyone waiting for it.
          </p>
          <Textarea
            label="Reason (optional)"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            rows={3}
            maxLength={300}
          />
        </div>
      </ConfirmationModal>

      <RescheduleModal
        open={rescheduleOpen}
        onClose={() => setRescheduleOpen(false)}
        appointment={a}
        onDone={() => {
          setRescheduleOpen(false)
          appointment.reload()
          history.reload()
        }}
      />

      <ReviewModal
        open={reviewOpen}
        onClose={() => setReviewOpen(false)}
        appointmentId={a.id}
        onDone={() => {
          setReviewOpen(false)
          myReviews.reload()
          toast.success('Thanks — your review has been posted.')
        }}
      />
    </div>
  )
}

function Row({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-2.5">
      <Icon size={15} className="mt-0.5 shrink-0 text-ink-faint" aria-hidden="true" />
      <div className="min-w-0">
        <dt className="text-xs text-ink-muted">{label}</dt>
        <dd className="text-sm font-medium text-forest-700">{value}</dd>
      </div>
    </div>
  )
}

/** Reschedule is restricted to other slots of the same doctor — that is the backend rule. */
function RescheduleModal({ open, onClose, appointment, onDone }) {
  const toast = useToast()
  const [date, setDate] = useState(appointment.appointment_date)
  const [slotId, setSlotId] = useState(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  const from = todayString()
  const to = useMemo(() => addDays(from, 30), [from])

  const slots = useAsync(
    () =>
      searchSlots({
        doctor_id: appointment.doctor_id,
        date_from: from,
        date_to: to,
        page: 1,
        page_size: MAX_PAGE_SIZE,
      }),
    [appointment.doctor_id, from, to],
    { enabled: open },
  )

  const all = slots.data?.items ?? []
  const availableDates = useMemo(
    () => [...new Set(all.filter((s) => s.bookable).map((s) => s.date))],
    [all],
  )
  const daySlots = useMemo(
    () => all.filter((s) => s.date === date && s.id !== appointment.slot_id),
    [all, date, appointment.slot_id],
  )

  const submit = async () => {
    setBusy(true)
    try {
      await rescheduleAppointment(appointment.id, slotId, reason.trim() || undefined)
      toast.success('Moved. Your doctor needs to confirm the new time.')
      onDone()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Move this appointment"
      description={`Choose another time with ${appointment.doctor_name}.`}
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Keep current time
          </Button>
          <Button onClick={submit} loading={busy} disabled={!slotId}>
            Request new time
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        <p className="rounded-xl border border-warn/30 bg-warn-soft px-4 py-3 text-sm text-forest-700">
          Moving an appointment sends it back for approval. It returns to awaiting a decision until
          your doctor confirms the new time.
        </p>

        <div className="grid gap-5 sm:grid-cols-2">
          <Calendar
            value={date}
            onChange={(v) => {
              setDate(v)
              setSlotId(null)
            }}
            availableDates={availableDates}
            minDate={from}
            maxDate={to}
          />
          <div>
            <p className="mb-2 text-sm font-medium text-forest-700">{formatDate(date)}</p>
            <SlotSelector
              slots={daySlots}
              value={slotId}
              onChange={(s) => setSlotId(s.id)}
              loading={slots.loading}
              error={slots.error}
              onRetry={slots.reload}
            />
          </div>
        </div>

        <Textarea
          label="Reason (optional)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={2}
          maxLength={300}
        />
      </div>
    </Modal>
  )
}

function ReviewModal({ open, onClose, appointmentId, onDone }) {
  const toast = useToast()
  const [rating, setRating] = useState('5')
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    try {
      await createReview({
        appointment_id: appointmentId,
        rating: Number(rating),
        comment: comment.trim() || undefined,
      })
      onDone()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Review your consultation"
      description="Your name is never shown alongside a review."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Not now
          </Button>
          <Button onClick={submit} loading={busy}>
            Post review
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Select
          label="Rating"
          value={rating}
          onChange={(e) => setRating(e.target.value)}
          options={[5, 4, 3, 2, 1].map((n) => ({
            value: String(n),
            label: `${n} ${n === 1 ? 'star' : 'stars'}`,
          }))}
        />
        <Textarea
          label="Comment (optional)"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={4}
          maxLength={1000}
          placeholder="How was your appointment?"
        />
      </div>
    </Modal>
  )
}
