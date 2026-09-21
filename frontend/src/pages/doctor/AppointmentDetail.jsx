import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Building2, CalendarDays, Clock, FileText, History, Stethoscope, User } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { Avatar } from '../../components/ui/Avatar'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { Modal } from '../../components/ui/Modal'
import { Textarea } from '../../components/ui/Field'
import { ErrorState, LoadingSkeleton } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import { getAppointment, getAppointmentHistory } from '../../api/appointments'
import { getPatientForDoctor } from '../../api/patients'
import { createRecord, listRecords, updateRecordNotes } from '../../api/medicalRecords'
import { APPOINTMENT_STATUS, CONSULTATION_LABEL } from '../../utils/constants'
import { formatDate, formatInstant, formatTimeRange, humanise } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

/**
 * Doctor's view of one appointment, including the patient summary the backend
 * allows a treating doctor to see, and the consultation notes they author.
 * A record may only exist for a confirmed or completed appointment, one per
 * appointment — so the note editor follows that rule.
 */
export default function DoctorAppointmentDetail() {
  useDocumentTitle('Appointment')
  const { appointmentId } = useParams()
  const { hospitalName, departmentName } = useDirectory()

  const appointment = useAsync(() => getAppointment(appointmentId), [appointmentId])
  const history = useAsync(() => getAppointmentHistory(appointmentId), [appointmentId])
  const a = appointment.data

  const patient = useAsync(() => getPatientForDoctor(a.patient_id), [a?.patient_id], {
    enabled: Boolean(a?.patient_id),
  })
  const record = useAsync(
    () => listRecords({ appointment_id: appointmentId, page: 1, page_size: 1 }),
    [appointmentId],
  )

  const [notesOpen, setNotesOpen] = useState(false)

  if (appointment.loading) return <LoadingSkeleton variant="cards" rows={1} />
  if (appointment.error) return <ErrorState error={appointment.error} onRetry={appointment.reload} />

  const existing = record.data?.items?.[0] ?? null
  const canWriteNotes = [APPOINTMENT_STATUS.CONFIRMED, APPOINTMENT_STATUS.COMPLETED].includes(a.status)

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        to="/doctor/appointments"
        className="inline-flex items-center gap-1.5 rounded text-sm font-medium text-ink-muted transition-colors hover:text-forest focus-ring"
      >
        <ArrowLeft size={16} aria-hidden="true" />
        All appointments
      </Link>

      <PageHeader title="Appointment details" actions={<StatusBadge status={a.status} />} />

      <Card>
        <CardBody className="space-y-5">
          <div className="flex items-center gap-3">
            <Avatar name={a.patient_name} size="lg" />
            <div className="min-w-0">
              <p className="truncate text-base font-semibold text-forest-700">{a.patient_name}</p>
              {patient.data && (
                <p className="mt-0.5 text-sm text-ink-muted">
                  {[
                    humanise(patient.data.gender),
                    patient.data.date_of_birth ? `Born ${formatDate(patient.data.date_of_birth)}` : null,
                    patient.data.phone,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
              )}
            </div>
          </div>

          <dl className="grid gap-4 border-t border-line pt-5 sm:grid-cols-2">
            <Row icon={CalendarDays} label="Date" value={formatDate(a.appointment_date)} />
            <Row icon={Clock} label="Time" value={formatTimeRange(a.start_time, a.end_time)} />
            <Row icon={Building2} label="Hospital" value={hospitalName(a.hospital_id) || '—'} />
            <Row icon={Stethoscope} label="Department" value={departmentName(a.department_id) || '—'} />
            <Row
              icon={User}
              label="Consultation type"
              value={CONSULTATION_LABEL[a.consultation_type] || a.consultation_type}
            />
          </dl>

          {a.reason && (
            <div className="border-t border-line pt-5">
              <p className="text-xs font-medium text-ink-muted">Reason the patient gave</p>
              <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed text-forest-700">{a.reason}</p>
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Consultation notes"
          description="Written by you, visible to you and this patient. Administrators cannot open them."
          action={
            canWriteNotes && (
              <Button variant="outline" size="sm" onClick={() => setNotesOpen(true)}>
                <FileText size={14} aria-hidden="true" />
                {existing ? 'Edit notes' : 'Add notes'}
              </Button>
            )
          }
        />
        <CardBody>
          {record.loading ? (
            <div className="skeleton h-16 w-full" />
          ) : existing ? (
            <p className="whitespace-pre-wrap rounded-xl bg-forest-50/60 px-4 py-3.5 text-sm leading-relaxed text-ink">
              {existing.notes}
            </p>
          ) : (
            <p className="text-sm text-ink-muted">
              {canWriteNotes
                ? 'No notes yet for this consultation.'
                : 'Notes can be added once the appointment is confirmed.'}
            </p>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Status history" />
        {history.loading ? (
          <CardBody>
            <div className="skeleton h-16 w-full" />
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

      <NotesModal
        open={notesOpen}
        onClose={() => setNotesOpen(false)}
        appointmentId={appointmentId}
        existing={existing}
        onDone={() => {
          setNotesOpen(false)
          record.reload()
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

function NotesModal({ open, onClose, appointmentId, existing, onDone }) {
  const toast = useToast()
  const [notes, setNotes] = useState(existing?.notes ?? '')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    try {
      if (existing) await updateRecordNotes(existing.id, notes.trim())
      else await createRecord({ appointment_id: appointmentId, notes: notes.trim() })
      toast.success('Notes saved.')
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
      title={existing ? 'Edit consultation notes' : 'Add consultation notes'}
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} disabled={!notes.trim()}>
            Save notes
          </Button>
        </>
      }
    >
      <Textarea
        label="Notes"
        required
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        rows={12}
        maxLength={10000}
        hint={`${notes.length}/10,000 — Nivara never writes clinical content for you.`}
        placeholder="What you observed and discussed."
      />
    </Modal>
  )
}
