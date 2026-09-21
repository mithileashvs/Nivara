import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CalendarSearch } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { AppointmentCard } from '../../components/AppointmentCard'
import { Button } from '../../components/ui/Button'
import { Tabs } from '../../components/ui/Tabs'
import { Pagination } from '../../components/ui/Pagination'
import { ConfirmationModal } from '../../components/ui/Modal'
import { Textarea } from '../../components/ui/Field'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import {
  acceptAppointment, cancelAppointment, completeAppointment, listAppointments, markNoShow, rejectAppointment,
} from '../../api/appointments'
import { APPOINTMENT_STATUS } from '../../utils/constants'
import { errorMessage } from '../../utils/errors'

const TABS = [
  { value: APPOINTMENT_STATUS.REQUESTED, label: 'Requests' },
  { value: APPOINTMENT_STATUS.CONFIRMED, label: 'Confirmed' },
  { value: APPOINTMENT_STATUS.COMPLETED, label: 'Completed' },
  { value: APPOINTMENT_STATUS.CANCELLED, label: 'Cancelled' },
  { value: APPOINTMENT_STATUS.REJECTED, label: 'Declined' },
  { value: APPOINTMENT_STATUS.NO_SHOW, label: 'No show' },
  { value: '', label: 'All' },
]

/* Which actions are offered follows the backend's rules exactly:
 *   REQUESTED  → accept, decline (the doctor is the only decision-maker)
 *   CONFIRMED  → cancel before it starts; complete or mark no-show once it has
 * Nothing else is shown, so no button can produce a 409 by design. */
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

  const status = params.get('status') ?? APPOINTMENT_STATUS.REQUESTED
  const [pendingAction, setPendingAction] = useState(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  const paged = usePaged((p) => listAppointments({ ...p, status: status || undefined }), [status])

  const run = async () => {
    const { appointment, action } = pendingAction
    const config = ACTIONS[action]
    setBusy(true)
    try {
      await config.call(appointment.id, reason.trim() || undefined)
      toast.success(config.done)
      setPendingAction(null)
      setReason('')
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
        {buttons.map(([action, variant]) => (
          <Button
            key={action}
            size="sm"
            variant={variant}
            onClick={() => {
              setPendingAction({ appointment: a, action })
              setReason('')
            }}
          >
            {ACTIONS[action].verb}
          </Button>
        ))}
      </div>
    )
  }

  const config = pendingAction ? ACTIONS[pendingAction.action] : null

  return (
    <div className="space-y-6">
      <PageHeader
        title="Appointments"
        description="You decide every request. Administrators never accept or decline on your behalf."
      />

      <Tabs tabs={TABS} value={status} onChange={(v) => setParams(v ? { status: v } : {}, { replace: true })} />

      <AsyncBoundary
        loading={paged.loading}
        error={paged.error}
        onRetry={paged.reload}
        isEmpty={paged.isEmpty}
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
          {paged.items.map((a) => (
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
          page={paged.page}
          totalPages={paged.totalPages}
          total={paged.total}
          pageSize={paged.pageSize}
          onChange={paged.setPage}
        />
      </AsyncBoundary>

      <ConfirmationModal
        open={Boolean(pendingAction)}
        onClose={() => setPendingAction(null)}
        onConfirm={run}
        loading={busy}
        tone={config?.tone}
        title={config?.title}
        confirmLabel={config?.verb}
        cancelLabel="Go back"
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-muted">
            {pendingAction && `${pendingAction.appointment.patient_name} · ${pendingAction.appointment.appointment_date} at ${pendingAction.appointment.start_time}`}
          </p>
          {pendingAction?.action === 'reject' && (
            <p className="text-sm text-ink-muted">
              The time returns to your available slots and may be offered to anyone waiting for it.
            </p>
          )}
          <Textarea
            label="Reason (optional)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            maxLength={300}
            hint="Shared with the patient in their appointment history."
          />
        </div>
      </ConfirmationModal>
    </div>
  )
}
