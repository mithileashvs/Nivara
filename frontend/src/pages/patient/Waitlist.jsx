import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BellRing, Plus } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { Button } from '../../components/ui/Button'
import { Card, CardBody } from '../../components/ui/Card'
import { Modal } from '../../components/ui/Modal'
import { Input, Select } from '../../components/ui/Field'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { Tabs } from '../../components/ui/Tabs'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import { joinWaitlist, leaveWaitlist, listMyWaitlist } from '../../api/waitlist'
import { CONSULTATION_TYPES, WAITLIST_STATUS } from '../../utils/constants'
import { addDays, formatDate, formatTime, todayString } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

const TABS = [
  { value: WAITLIST_STATUS.ACTIVE, label: 'Active' },
  { value: WAITLIST_STATUS.FULFILLED, label: 'Fulfilled' },
  { value: WAITLIST_STATUS.CANCELLED, label: 'Cancelled' },
  { value: WAITLIST_STATUS.EXPIRED, label: 'Expired' },
  { value: '', label: 'All' },
]

/**
 * "Tell me when something opens up." Joining a waitlist books nothing: when a
 * slot frees, the backend notifies eligible patients and they still request it
 * and still need the doctor's confirmation.
 */
export default function Waitlist() {
  useDocumentTitle('Waitlist')
  const [params] = useSearchParams()
  const [status, setStatus] = useState(WAITLIST_STATUS.ACTIVE)
  const [open, setOpen] = useState(Boolean(params.get('doctor_id')))
  const toast = useToast()
  const { hospitalById, departmentById } = useDirectory()

  const paged = usePaged((p) => listMyWaitlist({ ...p, status: status || undefined }), [status])

  const leave = async (id) => {
    try {
      await leaveWaitlist(id)
      toast.success('Removed from the waitlist.')
      paged.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Waitlist"
        description="Get notified when an earlier or matching time opens up."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus size={16} aria-hidden="true" />
            Join a waitlist
          </Button>
        }
      />

      <p className="rounded-xl border border-line bg-forest-50/60 px-4 py-3 text-sm text-ink-muted">
        Nothing is booked automatically. When a matching time frees up you get a notification, then
        you request it and your doctor confirms as usual.
      </p>

      <Tabs tabs={TABS} value={status} onChange={setStatus} />

      <AsyncBoundary
        loading={paged.loading}
        error={paged.error}
        onRetry={paged.reload}
        isEmpty={paged.isEmpty}
        skeleton={<LoadingSkeleton rows={2} />}
        empty={
          <EmptyState
            icon={BellRing}
            title="Nothing on your waitlist"
            description="Add a doctor, department or specialty and Nivara will watch for openings."
            action={<Button onClick={() => setOpen(true)}>Join a waitlist</Button>}
          />
        }
      >
        <div className="space-y-3">
          {paged.items.map((entry) => (
            <Card key={entry.id}>
              <CardBody className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-forest-700">
                    {entry.specialty ||
                      departmentById[entry.department_id]?.name ||
                      hospitalById[entry.hospital_id]?.name ||
                      'Any matching appointment'}
                  </p>
                  <p className="mt-1 text-xs text-ink-muted">
                    {formatDate(entry.date_from)} – {formatDate(entry.date_to)}
                    {entry.time_from && entry.time_to &&
                      ` · ${formatTime(entry.time_from)}–${formatTime(entry.time_to)}`}
                  </p>
                  {entry.existing_appointment_id && (
                    <p className="mt-1 text-xs text-ink-muted">
                      Only times earlier than an appointment you already have.
                    </p>
                  )}
                  {entry.notified_slot_ids?.length > 0 && (
                    <p className="mt-1 text-xs text-forest-500">
                      You have been notified about {entry.notified_slot_ids.length} opening
                      {entry.notified_slot_ids.length === 1 ? '' : 's'}.
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <StatusBadge status={entry.status} kind="generic" />
                  {entry.status === WAITLIST_STATUS.ACTIVE && (
                    <Button variant="ghost" size="sm" onClick={() => leave(entry.id)}>
                      Leave
                    </Button>
                  )}
                </div>
              </CardBody>
            </Card>
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

      <JoinModal
        open={open}
        onClose={() => setOpen(false)}
        presetDoctorId={params.get('doctor_id')}
        onDone={() => {
          setOpen(false)
          setStatus(WAITLIST_STATUS.ACTIVE)
          paged.reload()
        }}
      />
    </div>
  )
}

function JoinModal({ open, onClose, presetDoctorId, onDone }) {
  const toast = useToast()
  const { hospitals, departments } = useDirectory()
  const today = todayString()

  const [form, setForm] = useState({
    doctor_id: presetDoctorId || '',
    hospital_id: '',
    department_id: '',
    specialty: '',
    date_from: today,
    date_to: addDays(today, 30),
    time_from: '',
    time_to: '',
    consultation_type: '',
  })
  const [busy, setBusy] = useState(false)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  // The backend requires at least one of doctor / department / hospital / specialty.
  const valid =
    Boolean(form.doctor_id || form.department_id || form.hospital_id || form.specialty.trim()) &&
    form.date_from &&
    form.date_to

  const submit = async () => {
    setBusy(true)
    try {
      await joinWaitlist({
        doctor_id: form.doctor_id || undefined,
        hospital_id: form.hospital_id || undefined,
        department_id: form.department_id || undefined,
        specialty: form.specialty.trim() || undefined,
        date_from: form.date_from,
        date_to: form.date_to,
        time_from: form.time_from || undefined,
        time_to: form.time_to || undefined,
        consultation_type: form.consultation_type || undefined,
      })
      toast.success("You're on the waitlist. We'll notify you when something opens.")
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
      title="Join a waitlist"
      description="Tell Nivara what you're waiting for."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} disabled={!valid}>
            Join waitlist
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-xs text-ink-muted">
          Give at least one of hospital, department or specialty.
        </p>
        <Select
          label="Hospital"
          placeholder="Any hospital"
          value={form.hospital_id}
          onChange={(e) => setForm((f) => ({ ...f, hospital_id: e.target.value, department_id: '' }))}
          options={hospitals.map((h) => ({ value: h.id, label: h.name }))}
        />
        <Select
          label="Department"
          placeholder="Any department"
          value={form.department_id}
          onChange={set('department_id')}
          options={departments
            .filter((d) => !form.hospital_id || d.hospital_id === form.hospital_id)
            .map((d) => ({ value: d.id, label: d.name }))}
        />
        <Input
          label="Specialty"
          value={form.specialty}
          onChange={set('specialty')}
          maxLength={80}
          placeholder="Dermatology"
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="From" type="date" required min={today} value={form.date_from} onChange={set('date_from')} />
          <Input label="To" type="date" required min={form.date_from} value={form.date_to} onChange={set('date_to')} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Earliest time (optional)" type="time" value={form.time_from} onChange={set('time_from')} />
          <Input label="Latest time (optional)" type="time" value={form.time_to} onChange={set('time_to')} />
        </div>
        <Select
          label="Consultation type (optional)"
          placeholder="Any type"
          value={form.consultation_type}
          onChange={set('consultation_type')}
          options={CONSULTATION_TYPES}
        />
      </div>
    </Modal>
  )
}
