import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CalendarCheck, LayoutGrid, Plus } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { IntakeToggle } from '../../components/IntakeToggle'
import { StatCard } from '../../components/StatCard'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { Modal } from '../../components/ui/Modal'
import { Input, Textarea } from '../../components/ui/Field'
import { EmptyState, ErrorState, LoadingSkeleton } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import { getHospital, getHospitalAvailability, setHospitalIntake } from '../../api/hospitals'
import { createDepartment, setDepartmentIntake } from '../../api/departments'
import { addDays, todayString } from '../../utils/format'
import { errorMessage, fieldErrors } from '../../utils/errors'

/**
 * One hospital, its departments and its real availability. The availability
 * figures are counts of actually-open slots from GET /hospitals/{id}/availability.
 * Nivara does not infer or display hospital "load".
 */
export default function HospitalDetail({ basePath = '/admin' }) {
  const { hospitalId } = useParams()
  const toast = useToast()
  const [addOpen, setAddOpen] = useState(false)

  const hospital = useAsync(() => getHospital(hospitalId), [hospitalId])
  useDocumentTitle(hospital.data?.name)

  const from = todayString()
  const to = useMemo(() => addDays(from, 14), [from])
  const availability = useAsync(
    () => getHospitalAvailability(hospitalId, { date_from: from, date_to: to }),
    [hospitalId, from, to],
  )

  if (hospital.loading) return <LoadingSkeleton variant="cards" rows={1} />
  if (hospital.error) return <ErrorState error={hospital.error} onRetry={hospital.reload} />

  const h = hospital.data

  const changeHospitalIntake = async (status, reason) => {
    try {
      const r = await setHospitalIntake(h.id, status, reason)
      toast.success(`${r.message} ${r.active_appointments_unaffected} existing appointment(s) left untouched.`)
      hospital.reload()
      availability.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  const changeDepartmentIntake = async (department, status, reason) => {
    try {
      const r = await setDepartmentIntake(department.id, status, reason)
      toast.success(`${r.message} ${r.active_appointments_unaffected} existing appointment(s) left untouched.`)
      hospital.reload()
      availability.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  const availByDepartment = Object.fromEntries(
    (availability.data?.departments ?? []).map((d) => [d.department_id, d]),
  )

  return (
    <div className="space-y-6">
      <Link
        to={`${basePath}/hospitals`}
        className="inline-flex items-center gap-1.5 rounded text-sm font-medium text-ink-muted transition-colors hover:text-forest focus-ring"
      >
        <ArrowLeft size={16} aria-hidden="true" />
        All hospitals
      </Link>

      <PageHeader
        title={h.name}
        description={`${h.address} · ${[h.location?.city, h.location?.state].filter(Boolean).join(', ')}`}
        actions={
          <>
            <StatusBadge status={h.appointment_intake_status} kind="generic" />
            <IntakeToggle status={h.appointment_intake_status} label={h.name} onChange={changeHospitalIntake} />
          </>
        }
      />

      <p className="rounded-xl border border-line bg-forest-50/60 px-4 py-3 text-sm text-ink-muted">
        Closing intake stops new requests only. Appointments that are already requested or confirmed
        are never cancelled by it.
      </p>

      {availability.loading ? (
        <LoadingSkeleton variant="stats" rows={2} />
      ) : availability.error ? (
        <ErrorState error={availability.error} onRetry={availability.reload} compact />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <StatCard
              icon={CalendarCheck}
              value={availability.data.total_bookable_slots}
              label="Open slots in the next 14 days"
              hint="Counted from real slots, not estimated."
              tone={availability.data.total_bookable_slots > 0 ? 'positive' : 'warn'}
            />
            <StatCard
              icon={LayoutGrid}
              value={h.departments?.length ?? 0}
              label="Departments"
            />
          </div>
          <p className="text-sm text-ink-muted">{availability.data.message}</p>
        </>
      )}

      <Card>
        <CardHeader
          title="Departments"
          description="Each one controls its own appointment intake."
          action={
            <Button variant="outline" size="sm" onClick={() => setAddOpen(true)}>
              <Plus size={14} aria-hidden="true" />
              Add department
            </Button>
          }
        />
        {h.departments?.length ? (
          <ul className="divide-y divide-line">
            {h.departments.map((d) => {
              const avail = availByDepartment[d.id]
              return (
                <li key={d.id} className="flex flex-wrap items-start justify-between gap-4 px-5 py-4">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-forest-700">{d.name}</p>
                    {d.description && <p className="mt-0.5 text-sm text-ink-muted">{d.description}</p>}
                    {avail && (
                      <p className="mt-1 text-xs text-ink-muted">
                        {avail.bookable_slots} open slot{avail.bookable_slots === 1 ? '' : 's'} ·{' '}
                        {avail.message}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-2">
                    <StatusBadge status={d.status} kind="generic" />
                    <StatusBadge status={d.appointment_intake_status} kind="generic" />
                    <IntakeToggle
                      status={d.appointment_intake_status}
                      label={d.name}
                      onChange={(status, reason) => changeDepartmentIntake(d, status, reason)}
                    />
                  </div>
                </li>
              )
            })}
          </ul>
        ) : (
          <CardBody>
            <EmptyState
              icon={LayoutGrid}
              title="No departments yet"
              description="Add one so doctors can be assigned and patients can book."
              action={<Button onClick={() => setAddOpen(true)}>Add department</Button>}
            />
          </CardBody>
        )}
      </Card>

      <AddDepartmentModal
        open={addOpen}
        hospitalId={h.id}
        onClose={() => setAddOpen(false)}
        onDone={() => {
          setAddOpen(false)
          hospital.reload()
          availability.reload()
          toast.success('Department created.')
        }}
      />
    </div>
  )
}

function AddDepartmentModal({ open, hospitalId, onClose, onDone }) {
  const toast = useToast()
  const [form, setForm] = useState({ name: '', description: '' })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    setErrors({})
    try {
      await createDepartment({
        hospital_id: hospitalId,
        name: form.name.trim(),
        ...(form.description.trim() ? { description: form.description.trim() } : {}),
      })
      setForm({ name: '', description: '' })
      onDone()
    } catch (err) {
      setErrors(fieldErrors(err))
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add a department"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} disabled={form.name.trim().length < 2}>
            Create department
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Input
          label="Name"
          required
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          maxLength={80}
          error={errors.name}
          placeholder="Cardiology"
        />
        <Textarea
          label="Description (optional)"
          value={form.description}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          rows={3}
          maxLength={500}
          error={errors.description}
        />
      </div>
    </Modal>
  )
}
