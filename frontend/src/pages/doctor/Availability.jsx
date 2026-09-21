import { useMemo, useState } from 'react'
import { CalendarPlus, CalendarX2, Clock, Lock, Unlock } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Modal, ConfirmationModal } from '../../components/ui/Modal'
import { Input, Select, Textarea } from '../../components/ui/Field'
import { StatusBadge, Badge } from '../../components/ui/StatusBadge'
import { Tabs } from '../../components/ui/Tabs'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { createAvailability, deleteAvailability, listMyAvailability } from '../../api/doctors'
import { blockSlot, listMySlots, unblockSlot } from '../../api/slots'
import { AVAILABILITY_STATUS, MAX_PAGE_SIZE, PROFILE_STATUS, SLOT_STATUS } from '../../utils/constants'
import { addDays, formatDate, formatTime, formatTimeRange, todayString } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

/**
 * Working windows generate bookable slots; blocked windows are time off and only
 * block slots that are still free. Deleting a working window is refused (409) if
 * any of its slots already carry a request or booking — the backend protects
 * that, and the error is surfaced verbatim.
 */
export default function DoctorAvailability() {
  useDocumentTitle('Availability')
  const { doctorProfile } = useAuth()
  const toast = useToast()
  const { hospitalById, departmentById } = useDirectory()

  const [view, setView] = useState('windows')
  const [addOpen, setAddOpen] = useState(false)
  const [toDelete, setToDelete] = useState(null)
  const [busy, setBusy] = useState(false)

  const from = todayString()
  const to = useMemo(() => addDays(from, 45), [from])

  const windows = useAsync(
    () => listMyAvailability({ date_from: from, date_to: to, page: 1, page_size: MAX_PAGE_SIZE }),
    [from, to],
  )
  const slots = useAsync(
    () => listMySlots({ date_from: from, date_to: to, page: 1, page_size: MAX_PAGE_SIZE }),
    [from, to],
    { enabled: view === 'slots' },
  )

  const isActive = doctorProfile?.profile_status === PROFILE_STATUS.ACTIVE

  const remove = async () => {
    setBusy(true)
    try {
      const result = await deleteAvailability(toDelete.id)
      toast.success(result?.message || 'Window removed.')
      setToDelete(null)
      windows.reload()
      slots.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const toggleSlot = async (slot) => {
    try {
      if (slot.status === SLOT_STATUS.BLOCKED) {
        await unblockSlot(slot.id)
        toast.success('Slot reopened.')
      } else {
        await blockSlot(slot.id)
        toast.success('Slot blocked.')
      }
      slots.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  const slotsByDate = useMemo(() => {
    const grouped = {}
    for (const s of slots.data?.items ?? []) {
      ;(grouped[s.date] ||= []).push(s)
    }
    for (const list of Object.values(grouped)) list.sort((a, b) => a.start_time.localeCompare(b.start_time))
    return Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b))
  }, [slots.data])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Availability"
        description="Publish the hours you work. Nivara turns them into bookable slots."
        actions={
          <Button onClick={() => setAddOpen(true)} disabled={!isActive}>
            <CalendarPlus size={16} aria-hidden="true" />
            Add hours
          </Button>
        }
      />

      {!isActive && (
        <p className="rounded-xl border border-warn/30 bg-warn-soft px-4 py-3 text-sm text-forest-700">
          Your profile must be active, with a hospital and department assigned, before you can
          publish availability. An administrator does that.
        </p>
      )}

      <Tabs
        value={view}
        onChange={setView}
        tabs={[
          { value: 'windows', label: 'Working hours' },
          { value: 'slots', label: 'Slot schedule' },
        ]}
      />

      {view === 'windows' && (
        <AsyncBoundary
          loading={windows.loading}
          error={windows.error}
          onRetry={windows.reload}
          isEmpty={(windows.data?.items ?? []).length === 0}
          skeleton={<LoadingSkeleton rows={3} />}
          empty={
            <EmptyState
              icon={Clock}
              title="No hours published"
              description="Add the hours you work and patients will be able to request those times."
              action={
                <Button onClick={() => setAddOpen(true)} disabled={!isActive}>
                  Add hours
                </Button>
              }
            />
          }
        >
          <div className="space-y-3">
            {(windows.data?.items ?? []).map((w) => (
              <Card key={w.id}>
                <CardBody className="flex flex-wrap items-center justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-forest-700">{formatDate(w.date)}</p>
                      <StatusBadge status={w.status} kind="generic" />
                    </div>
                    <p className="mt-1 text-sm text-ink-muted">
                      {formatTimeRange(w.start_time, w.end_time)}
                      {w.status === AVAILABILITY_STATUS.WORKING && ` · ${w.slot_duration} min slots`}
                    </p>
                    <p className="mt-0.5 text-xs text-ink-muted">
                      {[departmentById[w.department_id]?.name, hospitalById[w.hospital_id]?.name]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                    {w.note && <p className="mt-1 text-xs text-ink-muted">{w.note}</p>}
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => setToDelete(w)}>
                    Remove
                  </Button>
                </CardBody>
              </Card>
            ))}
          </div>
        </AsyncBoundary>
      )}

      {view === 'slots' && (
        <AsyncBoundary
          loading={slots.loading}
          error={slots.error}
          onRetry={slots.reload}
          isEmpty={slotsByDate.length === 0}
          skeleton={<LoadingSkeleton rows={3} />}
          empty={
            <EmptyState
              icon={CalendarX2}
              title="No slots in the next 45 days"
              description="Publish working hours and your slots will appear here."
            />
          }
        >
          <div className="space-y-4">
            {slotsByDate.map(([date, list]) => (
              <Card key={date}>
                <CardHeader title={formatDate(date)} description={`${list.length} slots`} />
                <CardBody>
                  <ul className="flex flex-wrap gap-2">
                    {list.map((s) => {
                      const free = s.status === SLOT_STATUS.AVAILABLE
                      const blocked = s.status === SLOT_STATUS.BLOCKED
                      const toggleable = free || (blocked && s.block_source === 'MANUAL')
                      return (
                        <li key={s.id}>
                          <button
                            type="button"
                            disabled={!toggleable}
                            onClick={() => toggleSlot(s)}
                            title={
                              toggleable
                                ? free
                                  ? 'Block this slot'
                                  : 'Reopen this slot'
                                : s.unavailable_reason || 'Reserved'
                            }
                            className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors focus-ring ${
                              free
                                ? 'border-ok/30 bg-ok-soft text-ok hover:border-ok/60'
                                : s.status === SLOT_STATUS.BOOKED
                                  ? 'border-info/30 bg-info-soft text-info'
                                  : s.status === SLOT_STATUS.HELD
                                    ? 'border-warn/30 bg-warn-soft text-warn'
                                    : 'border-line bg-forest-50 text-ink-muted'
                            } ${toggleable ? 'cursor-pointer' : 'cursor-not-allowed'}`}
                          >
                            {blocked ? <Unlock size={11} aria-hidden="true" /> : free ? <Lock size={11} aria-hidden="true" /> : null}
                            {formatTime(s.start_time)}
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                  <p className="mt-4 flex flex-wrap gap-3 border-t border-line pt-3 text-xs text-ink-muted">
                    <Badge tone="positive">Open</Badge>
                    <Badge tone="pending">Awaiting your decision</Badge>
                    <Badge tone="info">Booked</Badge>
                    <Badge tone="neutral">Blocked</Badge>
                  </p>
                </CardBody>
              </Card>
            ))}
          </div>
        </AsyncBoundary>
      )}

      <AddWindowModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        doctorProfile={doctorProfile}
        onDone={() => {
          setAddOpen(false)
          windows.reload()
          slots.reload()
        }}
      />

      <ConfirmationModal
        open={Boolean(toDelete)}
        onClose={() => setToDelete(null)}
        onConfirm={remove}
        loading={busy}
        tone="danger"
        title="Remove these hours?"
        confirmLabel="Remove"
      >
        <p className="text-sm text-ink-muted">
          Free slots in this window are deleted. If any already carry a request or a booking, the
          window is kept and nothing changes — cancel those appointments first.
        </p>
      </ConfirmationModal>
    </div>
  )
}

function AddWindowModal({ open, onClose, doctorProfile, onDone }) {
  const toast = useToast()
  const { hospitalById, departmentById } = useDirectory()
  const today = todayString()

  const [form, setForm] = useState({
    hospital_id: '',
    department_id: '',
    date: today,
    start_time: '09:00',
    end_time: '13:00',
    slot_duration: '30',
    status: AVAILABILITY_STATUS.WORKING,
    note: '',
  })
  const [busy, setBusy] = useState(false)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  // Only the doctor's own affiliations are offered — the backend rejects anything else.
  const hospitals = (doctorProfile?.hospital_ids ?? [])
    .map((id) => hospitalById[id])
    .filter(Boolean)
  const departments = (doctorProfile?.department_ids ?? [])
    .map((id) => departmentById[id])
    .filter(Boolean)
    .filter((d) => !form.hospital_id || d.hospital_id === form.hospital_id)

  const submit = async () => {
    setBusy(true)
    try {
      const result = await createAvailability({
        hospital_id: form.hospital_id,
        department_id: form.department_id,
        date: form.date,
        start_time: form.start_time,
        end_time: form.end_time,
        slot_duration: Number(form.slot_duration),
        status: form.status,
        ...(form.note.trim() ? { note: form.note.trim() } : {}),
      })
      toast.success(
        form.status === AVAILABILITY_STATUS.WORKING
          ? `${result.slots_created} slot${result.slots_created === 1 ? '' : 's'} published.`
          : `Time off saved. ${result.slots_blocked} free slot(s) blocked; ${result.reserved_slots_unaffected} already-reserved slot(s) left untouched.`,
      )
      onDone()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const valid = form.hospital_id && form.department_id && form.date && form.start_time && form.end_time

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add working hours or time off"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} disabled={!valid}>
            Save
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {hospitals.length === 0 && (
          <p className="rounded-xl border border-warn/30 bg-warn-soft px-4 py-3 text-sm text-forest-700">
            You are not assigned to a hospital or department yet. An administrator needs to do that
            before you can publish hours.
          </p>
        )}

        <Select
          label="Hospital"
          required
          placeholder="Choose a hospital"
          value={form.hospital_id}
          onChange={(e) => setForm((f) => ({ ...f, hospital_id: e.target.value, department_id: '' }))}
          options={hospitals.map((h) => ({ value: h.id, label: h.name }))}
        />
        <Select
          label="Department"
          required
          placeholder="Choose a department"
          value={form.department_id}
          onChange={set('department_id')}
          options={departments.map((d) => ({ value: d.id, label: d.name }))}
        />
        <Select
          label="Type"
          value={form.status}
          onChange={set('status')}
          options={[
            { value: AVAILABILITY_STATUS.WORKING, label: 'Working hours — creates bookable slots' },
            { value: AVAILABILITY_STATUS.BLOCKED, label: 'Time off — blocks free slots' },
          ]}
        />
        <Input label="Date" type="date" required min={today} value={form.date} onChange={set('date')} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Start" type="time" required step="300" value={form.start_time} onChange={set('start_time')} />
          <Input label="End" type="time" required step="300" value={form.end_time} onChange={set('end_time')} />
        </div>
        {form.status === AVAILABILITY_STATUS.WORKING && (
          <Select
            label="Slot length"
            value={form.slot_duration}
            onChange={set('slot_duration')}
            options={[10, 15, 20, 30, 45, 60, 90, 120].map((n) => ({
              value: String(n),
              label: `${n} minutes`,
            }))}
          />
        )}
        <Textarea label="Note (optional)" value={form.note} onChange={set('note')} rows={2} maxLength={200} />
      </div>
    </Modal>
  )
}
