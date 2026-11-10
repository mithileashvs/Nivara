import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  Building2,
  CalendarDays,
  Clock,
  Download,
  FileCheck,
  FileText,
  History,
  RotateCw,
  Stethoscope,
  User,
} from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { Avatar } from '../../components/ui/Avatar'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { ConfirmationModal, Modal } from '../../components/ui/Modal'
import { Select, Textarea } from '../../components/ui/Field'
import { ErrorState, LoadingSkeleton } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import {
  approveRescheduleRequest,
  cancelAppointment,
  getAppointment,
  getAppointmentHistory,
  getAppointmentRescheduleRequests,
  rejectRescheduleRequest,
} from '../../api/appointments'
import { getPatientForDoctor } from '../../api/patients'
import {
  createRecord,
  downloadMedicalDocument,
  getPatientTimelineDoctor,
  listRecords,
  listSharedWithDoctor,
  updateRecordNotes,
} from '../../api/medicalRecords'
import {
  APPOINTMENT_STATUS,
  CANCELLATION_REASONS,
  CONSULTATION_LABEL,
  MEDICAL_CATEGORY_LABEL,
} from '../../utils/constants'
import {
  formatBytes,
  formatDate,
  formatInstant,
  formatTimeRange,
  humanise,
} from '../../utils/format'
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
  const toast = useToast()

  const appointment = useAsync(() => getAppointment(appointmentId), [appointmentId])
  const history = useAsync(() => getAppointmentHistory(appointmentId), [appointmentId])
  const reschedules = useAsync(() => getAppointmentRescheduleRequests(appointmentId), [appointmentId])
  const a = appointment.data

  const patient = useAsync(() => getPatientForDoctor(a.patient_id), [a?.patient_id], {
    enabled: Boolean(a?.patient_id),
  })
  const record = useAsync(
    () => listRecords({ appointment_id: appointmentId, page: 1, page_size: 1 }),
    [appointmentId],
  )
  const sharedDocs = useAsync(
    () => (a?.patient_id ? listSharedWithDoctor({ patient_id: a.patient_id, page_size: 50 }) : Promise.resolve({ items: [] })),
    [a?.patient_id],
    { enabled: Boolean(a?.patient_id) },
  )

  const [notesOpen, setNotesOpen] = useState(false)
  const [timelineOpen, setTimelineOpen] = useState(false)
  const [downloadingDocId, setDownloadingDocId] = useState(null)
  const timeline = useAsync(
    () => (timelineOpen && a?.patient_id ? getPatientTimelineDoctor(a.patient_id, { page: 1, page_size: 50 }) : Promise.resolve({ items: [] })),
    [timelineOpen, a?.patient_id],
    { enabled: timelineOpen && Boolean(a?.patient_id) },
  )

  const [cancelOpen, setCancelOpen] = useState(false)
  const [cancelReasonKey, setCancelReasonKey] = useState('')
  const [customCancelReason, setCustomCancelReason] = useState('')
  const [cancelling, setCancelling] = useState(false)

  const [rescheduleDecision, setRescheduleDecision] = useState(null)
  const [decisionNote, setDecisionNote] = useState('')
  const [reschedulingBusy, setReschedulingBusy] = useState(false)

  if (appointment.loading) return <LoadingSkeleton variant="cards" rows={1} />
  if (appointment.error) return <ErrorState error={appointment.error} onRetry={appointment.reload} />

  const existing = record.data?.items?.[0] ?? null
  const canWriteNotes = [APPOINTMENT_STATUS.CONFIRMED, APPOINTMENT_STATUS.COMPLETED].includes(a.status)
  const canCancel = [
    APPOINTMENT_STATUS.REQUESTED,
    APPOINTMENT_STATUS.CONFIRMED,
    APPOINTMENT_STATUS.RESCHEDULE_REQUESTED,
  ].includes(a.status)

  const pendingReschedule = (reschedules.data ?? []).find((r) => r.status === 'REQUESTED')

  const handleDownloadDoc = async (doc) => {
    setDownloadingDocId(doc.id)
    try {
      toast.info(`Preparing secure download for ${doc.filename}...`)
      const blob = await downloadMedicalDocument(doc.id)
      const url = window.URL.createObjectURL(new Blob([blob.data || blob], { type: doc.file_type }))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', doc.filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      toast.success('Download started.')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setDownloadingDocId(null)
    }
  }

  const handleCancelSubmit = async () => {
    const finalReason =
      cancelReasonKey === 'Other'
        ? customCancelReason.trim()
        : cancelReasonKey
        ? `${cancelReasonKey}${customCancelReason.trim() ? `: ${customCancelReason.trim()}` : ''}`
        : customCancelReason.trim()

    if (!finalReason) {
      toast.error('Please provide a reason for cancelling this appointment.')
      return
    }

    setCancelling(true)
    try {
      await cancelAppointment(appointmentId, finalReason)
      toast.success('Appointment cancelled. Patient has been notified and the slot released.')
      setCancelOpen(false)
      appointment.reload()
      history.reload()
      reschedules.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setCancelling(false)
    }
  }

  const handleRescheduleSubmit = async () => {
    if (!rescheduleDecision) return
    const { request, action } = rescheduleDecision
    setReschedulingBusy(true)
    try {
      if (action === 'approve') {
        await approveRescheduleRequest(request.id, decisionNote.trim() || undefined)
        toast.success(
          `Reschedule approved. Appointment moved to ${formatDate(request.requested_appointment_date)} at ${request.requested_start_time}.`,
        )
      } else {
        await rejectRescheduleRequest(request.id, decisionNote.trim() || undefined)
        toast.success('Reschedule request declined. Original appointment remains confirmed.')
      }
      setRescheduleDecision(null)
      setDecisionNote('')
      appointment.reload()
      history.reload()
      reschedules.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setReschedulingBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        to="/doctor/appointments"
        className="inline-flex items-center gap-1.5 rounded text-sm font-medium text-ink-muted transition-colors hover:text-forest focus-ring"
      >
        <ArrowLeft size={16} aria-hidden="true" />
        All appointments
      </Link>

      <PageHeader
        title="Appointment details"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={a.status} />
            {canCancel && (
              <Button
                variant="outline"
                size="sm"
                className="border-danger/30 text-danger hover:border-danger/50 hover:bg-danger-soft"
                onClick={() => setCancelOpen(true)}
              >
                Cancel appointment
              </Button>
            )}
          </div>
        }
      />

      {/* Reschedule Request Notification Card */}
      {a.status === APPOINTMENT_STATUS.RESCHEDULE_REQUESTED && pendingReschedule && (
        <Card className="border-warn/40 bg-warn-soft/45">
          <CardBody className="space-y-4 p-5">
            <div className="flex items-center gap-2 font-semibold text-forest-800">
              <RotateCw className="h-5 w-5 text-warn" aria-hidden="true" />
              Patient requested to reschedule this appointment
            </div>

            <div className="grid gap-3 rounded-xl border border-warn/25 bg-surface p-3.5 sm:grid-cols-2">
              <div>
                <p className="text-xs font-medium text-ink-muted">Current confirmed slot</p>
                <p className="text-sm font-medium text-ink-muted line-through">
                  {formatDate(pendingReschedule.old_appointment_date)} · {pendingReschedule.old_start_time} -{' '}
                  {pendingReschedule.old_end_time}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-forest-700">Requested new slot</p>
                <p className="text-sm font-bold text-forest-900">
                  {formatDate(pendingReschedule.requested_appointment_date)} ·{' '}
                  {pendingReschedule.requested_start_time} - {pendingReschedule.requested_end_time}
                </p>
              </div>
            </div>

            {pendingReschedule.reason && (
              <div>
                <p className="text-xs font-medium text-ink-muted">Patient&apos;s reason</p>
                <p className="mt-0.5 text-sm italic text-forest-800">&ldquo;{pendingReschedule.reason}&rdquo;</p>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button
                size="sm"
                variant="primary"
                onClick={() => setRescheduleDecision({ request: pendingReschedule, action: 'approve' })}
              >
                Approve Reschedule
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="border-danger/30 text-danger hover:border-danger/50 hover:bg-danger-soft"
                onClick={() => setRescheduleDecision({ request: pendingReschedule, action: 'reject' })}
              >
                Decline Reschedule
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

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

      {/* Phase 4: Patient Shared Medical Documents */}
      <Card>
        <CardHeader
          title="Shared medical documents"
          description="Documents explicitly shared with you by this patient under active consent."
          action={
            <Button variant="outline" size="sm" onClick={() => setTimelineOpen(true)}>
              <History size={14} aria-hidden="true" />
              Patient timeline
            </Button>
          }
        />
        <CardBody>
          {sharedDocs.loading ? (
            <div className="skeleton h-14 w-full" />
          ) : (sharedDocs.data?.items ?? []).length === 0 ? (
            <p className="text-sm text-ink-muted">
              No medical documents have been shared by this patient for this consultation.
            </p>
          ) : (
            <ul className="divide-y divide-line">
              {(sharedDocs.data?.items ?? []).map((doc) => (
                <li key={doc.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="rounded-lg bg-forest-50 p-2 text-forest shrink-0">
                      <FileText size={16} />
                    </div>
                    <div className="min-w-0">
                      <p className="font-semibold text-forest-800 text-sm truncate">{doc.title}</p>
                      <p className="text-xs text-ink-muted truncate mt-0.5">
                        {doc.filename} · {formatBytes(doc.file_size)} · Uploaded {formatDate(doc.created_at)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-md bg-forest-50 px-2 py-0.5 text-xs text-forest-600 font-medium">
                      {MEDICAL_CATEGORY_LABEL[doc.category] || humanise(doc.category)}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDownloadDoc(doc)}
                      disabled={downloadingDocId === doc.id}
                      title="Download private document"
                    >
                      <Download size={13} />
                      Download
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
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
                  {h.previous_date && h.new_date && (
                    <p className="mt-1 text-xs text-forest-800">
                      Slot: {formatDate(h.previous_date)} {h.previous_time} → {formatDate(h.new_date)} {h.new_time}
                    </p>
                  )}
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

      {/* Cancellation Modal */}
      <Modal
        open={cancelOpen}
        onClose={() => {
          if (!cancelling) {
            setCancelOpen(false)
            setCancelReasonKey('')
            setCustomCancelReason('')
          }
        }}
        title="Cancel appointment"
        size="md"
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => {
                setCancelOpen(false)
                setCancelReasonKey('')
                setCustomCancelReason('')
              }}
              disabled={cancelling}
            >
              Keep appointment
            </Button>
            <Button
              variant="danger"
              onClick={handleCancelSubmit}
              loading={cancelling}
              disabled={
                !cancelReasonKey ||
                (cancelReasonKey === 'Other' && !customCancelReason.trim())
              }
            >
              Confirm Cancellation
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-muted">
            Cancelling will release the reserved time slot immediately and notify the patient.
          </p>
          <Select
            label="Reason for cancellation"
            required
            placeholder="Select a reason..."
            value={cancelReasonKey}
            onChange={(e) => setCancelReasonKey(e.target.value)}
            options={CANCELLATION_REASONS}
          />
          <Textarea
            label={cancelReasonKey === 'Other' ? 'Please specify reason' : 'Additional details (optional)'}
            required={cancelReasonKey === 'Other'}
            rows={3}
            placeholder={
              cancelReasonKey === 'Other'
                ? 'Explain the reason for cancellation...'
                : 'Any instructions or note for the patient...'
            }
            value={customCancelReason}
            onChange={(e) => setCustomCancelReason(e.target.value)}
          />
        </div>
      </Modal>

      {/* Reschedule Decision Confirmation Modal */}
      <ConfirmationModal
        open={Boolean(rescheduleDecision)}
        onClose={() => {
          if (!reschedulingBusy) {
            setRescheduleDecision(null)
            setDecisionNote('')
          }
        }}
        title={
          rescheduleDecision?.action === 'approve'
            ? 'Approve appointment reschedule?'
            : 'Decline appointment reschedule?'
        }
        confirmLabel={
          rescheduleDecision?.action === 'approve'
            ? 'Approve Reschedule'
            : 'Decline Reschedule'
        }
        tone={rescheduleDecision?.action === 'approve' ? 'primary' : 'danger'}
        onConfirm={handleRescheduleSubmit}
        loading={reschedulingBusy}
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-muted">
            {rescheduleDecision?.action === 'approve'
              ? `You are confirming the appointment change for ${a?.patient_name} to ${formatDate(rescheduleDecision?.request?.requested_appointment_date)} at ${rescheduleDecision?.request?.requested_start_time}. The previous slot will be released atomically.`
              : `You are declining this reschedule request. The original appointment on ${formatDate(rescheduleDecision?.request?.old_appointment_date)} at ${rescheduleDecision?.request?.old_start_time} will remain active.`}
          </p>
          <Textarea
            label={rescheduleDecision?.action === 'approve' ? 'Optional note for patient' : 'Reason / note for declining'}
            placeholder={
              rescheduleDecision?.action === 'approve'
                ? 'e.g. Approved. Please arrive 10 minutes early.'
                : 'e.g. I am unavailable at this requested time. Please request an alternative slot.'
            }
            value={decisionNote}
            onChange={(e) => setDecisionNote(e.target.value)}
            rows={3}
          />
        </div>
      </ConfirmationModal>

      {/* Patient Medical Timeline Modal */}
      <Modal
        open={timelineOpen}
        onClose={() => setTimelineOpen(false)}
        title={`Medical Timeline: ${a?.patient_name || 'Patient'}`}
        description="Chronological record of consultations, appointments, and shared documents."
        footer={
          <Button variant="ghost" onClick={() => setTimelineOpen(false)}>
            Close
          </Button>
        }
      >
        <div className="max-h-[60vh] overflow-y-auto pr-1">
          {timeline.loading ? (
            <div className="space-y-3">
              <div className="skeleton h-12 w-full" />
              <div className="skeleton h-12 w-full" />
            </div>
          ) : (timeline.data?.items ?? []).length === 0 ? (
            <p className="rounded-xl border border-line bg-forest-50/40 p-4 text-xs text-ink-muted">
              No historical timeline entries found for this patient.
            </p>
          ) : (
            <ol className="relative border-l border-line pl-5 space-y-4">
              {(timeline.data?.items ?? []).map((item) => (
                <li key={item.id} className="relative text-xs">
                  <span className="absolute -left-7 flex h-5 w-5 items-center justify-center rounded-full border border-forest-300 bg-surface">
                    {item.item_type === 'DOCUMENT' ? (
                      <FileText size={11} className="text-info" />
                    ) : item.item_type === 'APPOINTMENT' ? (
                      <CalendarDays size={11} className="text-ok" />
                    ) : (
                      <FileCheck size={11} className="text-forest-500" />
                    )}
                  </span>
                  <div className="rounded-lg border border-line bg-surface p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold text-forest-800">{item.title}</p>
                      <span className="text-ink-faint text-[0.68rem]">{formatDate(item.date)}</span>
                    </div>
                    {item.doctor_name && (
                      <p className="text-forest-600 mt-0.5">Dr. {item.doctor_name}</p>
                    )}
                    {item.description && (
                      <p className="text-ink-muted mt-1 leading-relaxed bg-forest-50/40 p-2 rounded">
                        {item.description}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </Modal>
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
