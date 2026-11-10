import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, Calendar, CalendarSearch, Check, Clock, Users, X } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { AppointmentCard } from '../../components/AppointmentCard'
import { Button } from '../../components/ui/Button'
import { Tabs } from '../../components/ui/Tabs'
import { Pagination } from '../../components/ui/Pagination'
import { ConfirmationModal } from '../../components/ui/Modal'
import { Select, Textarea } from '../../components/ui/Field'
import { Card, CardBody } from '../../components/ui/Card'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import {
  acceptAppointment,
  approveRescheduleRequest,
  cancelAppointment,
  completeAppointment,
  listAppointments,
  listDoctorRescheduleRequests,
  markNoShow,
  rejectAppointment,
  rejectRescheduleRequest,
} from '../../api/appointments'
import { listDoctorWaitlist } from '../../api/waitlist'
import { APPOINTMENT_STATUS, CANCELLATION_REASONS } from '../../utils/constants'
import { formatDate, formatInstant, formatTime, formatTimeRange } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

const TABS = [
  { value: APPOINTMENT_STATUS.REQUESTED, label: 'Requests' },
  { value: 'RESCHEDULE_REQUESTS', label: 'Reschedule Requests' },
  { value: 'WAITLIST_QUEUE', label: 'Waitlist Queue' },
  { value: APPOINTMENT_STATUS.CONFIRMED, label: 'Confirmed' },
  { value: APPOINTMENT_STATUS.RESCHEDULE_REQUESTED, label: 'Rescheduling Pending' },
  { value: APPOINTMENT_STATUS.COMPLETED, label: 'Completed' },
  { value: APPOINTMENT_STATUS.CANCELLED, label: 'Cancelled' },
  { value: APPOINTMENT_STATUS.REJECTED, label: 'Declined' },
  { value: APPOINTMENT_STATUS.NO_SHOW, label: 'No show' },
  { value: '', label: 'All' },
]

const ACTIONS = {
  accept: { verb: 'Accept', title: 'Accept this request?', tone: 'primary', call: acceptAppointment, done: 'Appointment confirmed.' },
  reject: { verb: 'Decline', title: 'Decline this request?', tone: 'danger', call: rejectAppointment, done: 'Request declined and the time released.' },
  cancel: { verb: 'Cancel', title: 'Cancel this appointment?', tone: 'danger', call: cancelAppointment, done: 'Appointment cancelled.' },
  complete: { verb: 'Mark completed', title: 'Mark this consultation completed?', tone: 'primary', call: completeAppointment, done: 'Marked as completed.' },
  no_show: { verb: 'No show', title: 'Mark the patient as a no-show?', tone: 'danger', call: markNoShow, done: 'Marked as a no-show.' },
}

export default function DoctorAppointments() {
  useDocumentTitle('Appointments')
  const [params, setParams] = useSearchParams()
  const toast = useToast()
  const { hospitalName, departmentName } = useDirectory()

  const statusParam = params.get('status')
  const tabParam = params.get('tab')
  const status =
    statusParam ?? (tabParam === 'reschedules' ? 'RESCHEDULE_REQUESTS' : APPOINTMENT_STATUS.REQUESTED)
  const isRescheduleView = status === 'RESCHEDULE_REQUESTS'
  const isWaitlistView = status === 'WAITLIST_QUEUE'

  const [pendingAction, setPendingAction] = useState(null)
  const [reason, setReason] = useState('')
  const [cancelReasonType, setCancelReasonType] = useState('Personal reasons')
  const [customCancelReason, setCustomCancelReason] = useState('')
  const [busy, setBusy] = useState(false)

  // Reschedule approval/rejection state
  const [rescheduleDecision, setRescheduleDecision] = useState(null) // { request, action: 'approve' | 'reject' }
  const [decisionNote, setDecisionNote] = useState('')

  const pagedAppointments = usePaged(
    (p) => listAppointments({ ...p, status: status || undefined }),
    [status],
    { enabled: !isRescheduleView && !isWaitlistView }
  )

  const pagedReschedules = usePaged(
    (p) => listDoctorRescheduleRequests({ ...p, status: 'REQUESTED' }),
    [status],
    { enabled: isRescheduleView }
  )

  const pagedWaitlist = usePaged(
    (p) => listDoctorWaitlist(p),
    [status],
    { enabled: isWaitlistView }
  )

  const paged = isRescheduleView ? pagedReschedules : isWaitlistView ? pagedWaitlist : pagedAppointments

  const effectiveCancelReason = cancelReasonType === 'Other' ? customCancelReason.trim() : cancelReasonType

  const run = async () => {
    const { appointment, action } = pendingAction
    const config = ACTIONS[action]
    const finalReason = action === 'cancel' ? effectiveCancelReason : (reason.trim() || undefined)

    if (action === 'cancel' && !finalReason) {
      toast.error('Cancellation reason is required.')
      return
    }

    setBusy(true)
    try {
      await config.call(appointment.id, finalReason)
      toast.success(config.done)
      setPendingAction(null)
      setReason('')
      setCancelReasonType('Personal reasons')
      setCustomCancelReason('')
      paged.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const handleRescheduleSubmit = async () => {
    if (!rescheduleDecision) return
    const { request, action } = rescheduleDecision
    setBusy(true)
    try {
      if (action === 'approve') {
        await approveRescheduleRequest(request.id, decisionNote.trim() || undefined)
        toast.success(`Reschedule approved. Appointment moved to ${formatDate(request.requested_appointment_date)} at ${request.requested_start_time}.`)
      } else {
        await rejectRescheduleRequest(request.id, decisionNote.trim() || undefined)
        toast.success('Reschedule request declined. Original appointment remains confirmed.')
      }
      setRescheduleDecision(null)
      setDecisionNote('')
      paged.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const actionsFor = (a) => {
    const started = new Date(a.start_at) <= new Date()
    const buttons = []
    if (a.status === APPOINTMENT_STATUS.REQUESTED) {
      buttons.push(['accept', 'primary'], ['reject', 'outline'])
    } else if (a.status === APPOINTMENT_STATUS.CONFIRMED) {
      if (started) buttons.push(['complete', 'primary'], ['no_show', 'outline'])
      else buttons.push(['cancel', 'outline'])
    }
    if (!buttons.length) return null
    return (
      <div className="flex gap-2">
        {buttons.map(([action, variant]) => {
          const isDestructive = ['reject', 'cancel', 'no_show'].includes(action)
          return (
            <Button
              key={action}
              size="sm"
              variant={variant}
              className={
                isDestructive
                  ? 'border-danger/30 text-danger hover:border-danger/50 hover:bg-danger-soft'
                  : ''
              }
              onClick={() => {
                setPendingAction({ appointment: a, action })
                setReason('')
                setCancelReasonType('Personal reasons')
                setCustomCancelReason('')
              }}
            >
              {ACTIONS[action].verb}
            </Button>
          )
        })}
      </div>
    )
  }

  const config = pendingAction ? ACTIONS[pendingAction.action] : null

  return (
    <div className="space-y-6">
      <PageHeader
        title="Appointments"
        description="Review requests, manage confirmed consultations, and process rescheduling."
      />

      <Tabs tabs={TABS} value={status} onChange={(v) => setParams(v ? { status: v } : {}, { replace: true })} />

      {isWaitlistView ? (
        <AsyncBoundary
          loading={pagedWaitlist.loading}
          error={pagedWaitlist.error}
          onRetry={pagedWaitlist.reload}
          isEmpty={pagedWaitlist.isEmpty}
          skeleton={<LoadingSkeleton rows={3} />}
          empty={
            <EmptyState
              icon={Users}
              title="No patients on waitlist"
              description="Patients waiting for freed or cancelled slots with you will appear here."
            />
          }
        >
          <div className="space-y-4">
            {pagedWaitlist.items.map((entry) => (
              <Card key={entry.id} className="p-5 transition-colors hover:border-forest-200">
                <CardBody className="flex flex-wrap items-start justify-between gap-4 p-0">
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex items-center gap-1 rounded-full bg-forest-100 px-2.5 py-0.5 text-xs font-semibold text-forest-700">
                        <Users size={12} aria-hidden="true" />
                        Queue Position #{entry.queue_position || 1}
                      </span>
                      {entry.patients_ahead > 0 && (
                        <span className="text-xs text-ink-muted">
                          ({entry.patients_ahead} patient{entry.patients_ahead === 1 ? '' : 's'} ahead)
                        </span>
                      )}
                      <span className="text-sm font-semibold text-ink">
                        Patient ID: {entry.patient_id?.slice(-8)}
                      </span>
                    </div>

                    <p className="text-xs text-ink-muted">
                      Preferred dates: <strong className="text-ink">{formatDate(entry.date_from)}</strong> –{' '}
                      <strong className="text-ink">{formatDate(entry.date_to)}</strong>
                      {entry.time_from && entry.time_to && (
                        <> · Preferred window: {formatTime(entry.time_from)} – {formatTime(entry.time_to)}</>
                      )}
                    </p>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted">
                      {entry.hospital_id && (
                        <span>Hospital: {hospitalName(entry.hospital_id)}</span>
                      )}
                      {entry.department_id && (
                        <span>Department: {departmentName(entry.department_id)}</span>
                      )}
                      {entry.consultation_type && (
                        <span>Type: {entry.consultation_type.replace('_', ' ')}</span>
                      )}
                      <span>Waitlisted since {formatDate(entry.created_at)}</span>
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <StatusBadge status={entry.status} kind="generic" />
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>
          <Pagination
            className="mt-6"
            page={pagedWaitlist.page}
            totalPages={pagedWaitlist.totalPages}
            total={pagedWaitlist.total}
            pageSize={pagedWaitlist.pageSize}
            onChange={pagedWaitlist.setPage}
          />
        </AsyncBoundary>
      ) : isRescheduleView ? (
        <AsyncBoundary
          loading={pagedReschedules.loading}
          error={pagedReschedules.error}
          onRetry={pagedReschedules.reload}
          isEmpty={pagedReschedules.isEmpty}
          skeleton={<LoadingSkeleton rows={3} />}
          empty={
            <EmptyState
              icon={CalendarSearch}
              title="No pending rescheduling requests"
              description="When a patient asks to move their appointment, it will appear here for your review."
            />
          }
        >
          <div className="space-y-4">
            {pagedReschedules.items.map((req) => (
              <Card key={req.id} className="p-5 transition-colors hover:border-forest-200">
                <CardBody className="space-y-4 p-0">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-semibold text-forest-800">{req.patient_name}</h3>
                        <StatusBadge status={req.status} />
                      </div>
                      <p className="mt-1 text-xs text-ink-muted">
                        {[req.hospital_name || hospitalName(req.hospital_id), req.department_name || departmentName(req.department_id)]
                          .filter(Boolean)
                          .join(' · ')}
                        {' · '}Requested {formatInstant(req.created_at)}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="primary"
                        onClick={() => {
                          setRescheduleDecision({ request: req, action: 'approve' })
                          setDecisionNote('')
                        }}
                      >
                        <Check size={14} className="mr-1" />
                        Approve Reschedule
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setRescheduleDecision({ request: req, action: 'reject' })
                          setDecisionNote('')
                        }}
                      >
                        <X size={14} className="mr-1" />
                        Decline
                      </Button>
                      <Link
                        to={`/doctor/appointments/${req.appointment_id}`}
                        className="rounded-lg p-1.5 text-xs text-forest hover:bg-forest-50 focus-ring"
                      >
                        View Appointment
                      </Link>
                    </div>
                  </div>

                  {/* Comparison tile: Current vs Requested */}
                  <div className="grid gap-3 rounded-xl border border-line bg-forest-50/40 p-3.5 sm:grid-cols-2">
                    <div className="space-y-1">
                      <p className="text-xs font-semibold uppercase tracking-wider text-ink-muted">Current Slot</p>
                      <p className="flex items-center gap-1.5 text-sm font-medium text-forest-700">
                        <Calendar size={14} className="text-ink-faint" />
                        {formatDate(req.old_appointment_date)}
                      </p>
                      <p className="flex items-center gap-1.5 text-xs text-ink-muted">
                        <Clock size={14} className="text-ink-faint" />
                        {formatTimeRange(req.old_start_time, req.old_end_time)}
                      </p>
                    </div>

                    <div className="space-y-1 sm:border-l sm:border-line sm:pl-4">
                      <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-forest-600">
                        <ArrowRight size={13} />
                        Requested New Slot
                      </div>
                      <p className="flex items-center gap-1.5 text-sm font-semibold text-forest-800">
                        <Calendar size={14} className="text-forest" />
                        {formatDate(req.requested_appointment_date)}
                      </p>
                      <p className="flex items-center gap-1.5 text-xs font-medium text-forest-700">
                        <Clock size={14} className="text-forest" />
                        {formatTimeRange(req.requested_start_time, req.requested_end_time)}
                      </p>
                    </div>
                  </div>

                  {req.reason && (
                    <div className="rounded-lg bg-canvas px-3.5 py-2.5 text-xs">
                      <span className="font-semibold text-forest-700">Patient&apos;s reason: </span>
                      <span className="text-ink-muted">{req.reason}</span>
                    </div>
                  )}
                </CardBody>
              </Card>
            ))}
          </div>
          <Pagination
            className="mt-6"
            page={pagedReschedules.page}
            totalPages={pagedReschedules.totalPages}
            total={pagedReschedules.total}
            pageSize={pagedReschedules.pageSize}
            onChange={pagedReschedules.setPage}
          />
        </AsyncBoundary>
      ) : (
        <AsyncBoundary
          loading={pagedAppointments.loading}
          error={pagedAppointments.error}
          onRetry={pagedAppointments.reload}
          isEmpty={pagedAppointments.isEmpty}
          skeleton={<LoadingSkeleton rows={3} />}
          empty={
            <EmptyState
              icon={CalendarSearch}
              title="Nothing in this list"
              description="Try another tab to see the rest of your appointments."
            />
          }
        >
          <div className="space-y-3">
            {pagedAppointments.items.map((a) => (
              <AppointmentCard
                key={a.id}
                appointment={a}
                perspective="doctor"
                hospitalName={hospitalName(a.hospital_id)}
                departmentName={departmentName(a.department_id)}
                actions={actionsFor(a)}
              />
            ))}
          </div>
          <Pagination
            className="mt-6"
            page={pagedAppointments.page}
            totalPages={pagedAppointments.totalPages}
            total={pagedAppointments.total}
            pageSize={pagedAppointments.pageSize}
            onChange={pagedAppointments.setPage}
          />
        </AsyncBoundary>
      )}

      {/* Appointment Action Modal (Accept, Reject, Cancel, Complete, No-Show) */}
      <ConfirmationModal
        open={Boolean(pendingAction)}
        onClose={() => setPendingAction(null)}
        onConfirm={run}
        loading={busy}
        disabled={pendingAction?.action === 'cancel' && !effectiveCancelReason}
        tone={config?.tone}
        title={config?.title}
        confirmLabel={config?.verb}
        cancelLabel="Go back"
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-muted">
            {pendingAction && `${pendingAction.appointment.patient_name} · ${formatDate(pendingAction.appointment.appointment_date)} at ${pendingAction.appointment.start_time}`}
          </p>
          {pendingAction?.action === 'reject' && (
            <p className="text-sm text-ink-muted">
              The time returns to your available slots and may be offered to anyone waiting for it.
            </p>
          )}

          {pendingAction?.action === 'cancel' ? (
            <div className="space-y-3">
              <p className="text-sm text-ink-muted">
                Cancelling releases the occupied slot. A cancellation reason is mandatory.
              </p>
              <Select
                label="Cancellation reason"
                value={cancelReasonType}
                onChange={(e) => setCancelReasonType(e.target.value)}
                options={CANCELLATION_REASONS}
              />
              {cancelReasonType === 'Other' && (
                <Textarea
                  label="Custom explanation"
                  value={customCancelReason}
                  onChange={(e) => setCustomCancelReason(e.target.value)}
                  placeholder="Explain why this appointment is being cancelled..."
                  rows={3}
                  maxLength={300}
                />
              )}
            </div>
          ) : (
            <Textarea
              label="Reason (optional)"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              maxLength={300}
              hint="Shared with the patient in their appointment history."
            />
          )}
        </div>
      </ConfirmationModal>

      {/* Reschedule Request Decision Modal (Approve or Decline) */}
      <ConfirmationModal
        open={Boolean(rescheduleDecision)}
        onClose={() => setRescheduleDecision(null)}
        onConfirm={handleRescheduleSubmit}
        loading={busy}
        tone={rescheduleDecision?.action === 'approve' ? 'primary' : 'danger'}
        title={rescheduleDecision?.action === 'approve' ? 'Approve Reschedule Request?' : 'Decline Reschedule Request?'}
        confirmLabel={rescheduleDecision?.action === 'approve' ? 'Approve & Reassign Slot' : 'Decline Request'}
        cancelLabel="Cancel"
      >
        {rescheduleDecision && (
          <div className="space-y-4">
            <div className="rounded-xl border border-line bg-forest-50/50 p-3.5 text-xs text-forest-700">
              <p className="font-semibold text-forest-800">
                Patient: {rescheduleDecision.request.patient_name}
              </p>
              <div className="mt-2 space-y-1 text-ink-muted">
                <p>
                  <span className="font-medium text-forest-700">Current:</span>{' '}
                  {formatDate(rescheduleDecision.request.old_appointment_date)} at {rescheduleDecision.request.old_start_time}
                </p>
                <p>
                  <span className="font-medium text-forest-700">Requested:</span>{' '}
                  <strong className="text-forest-800">
                    {formatDate(rescheduleDecision.request.requested_appointment_date)} at {rescheduleDecision.request.requested_start_time}
                  </strong>
                </p>
                {rescheduleDecision.request.reason && (
                  <p className="mt-1">
                    <span className="font-medium text-forest-700">Patient reason:</span> {rescheduleDecision.request.reason}
                  </p>
                )}
              </div>
            </div>

            <p className="text-xs leading-relaxed text-ink-muted">
              {rescheduleDecision.action === 'approve'
                ? 'Approving reassigns the appointment to the new slot and automatically releases the previous slot.'
                : 'Declining leaves the patient\'s original appointment confirmed and releases the temporary reservation on the requested slot.'}
            </p>

            <Textarea
              label="Note to patient (optional)"
              value={decisionNote}
              onChange={(e) => setDecisionNote(e.target.value)}
              placeholder={rescheduleDecision.action === 'approve' ? 'Optional message or preparation instructions...' : 'Reason for declining...'}
              rows={2}
              maxLength={300}
            />
          </div>
        )}
      </ConfirmationModal>
    </div>
  )
}
