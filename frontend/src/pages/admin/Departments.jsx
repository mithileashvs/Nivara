import { useEffect, useState } from 'react'
import { LayoutGrid } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { FilterBar } from '../../components/FilterBar'
import { IntakeToggle } from '../../components/IntakeToggle'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { DataTable } from '../../components/ui/DataTable'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { Modal } from '../../components/ui/Modal'
import { Input, Select, Textarea } from '../../components/ui/Field'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import { listDepartments, setDepartmentIntake, updateDepartment } from '../../api/departments'
import { DEPARTMENT_STATUS, INTAKE_STATUS } from '../../utils/constants'
import { humanise } from '../../utils/format'
import { errorMessage, fieldErrors } from '../../utils/errors'

/**
 * Departments across every hospital the signed-in administrator can reach.
 * `hospitalScope` limits the hospital filter for a hospital administrator; the
 * backend still enforces the same limit on every write.
 */
export default function AdminDepartments({ hospitalScope = null }) {
  useDocumentTitle('Departments')
  const toast = useToast()
  const { hospitals, hospitalById } = useDirectory()

  const scopedHospitals = hospitalScope
    ? hospitals.filter((h) => hospitalScope.includes(h.id))
    : hospitals

  const [hospitalId, setHospitalId] = useState(
    hospitalScope?.length === 1 ? hospitalScope[0] : '',
  )
  const [status, setStatus] = useState('')
  const [editing, setEditing] = useState(null)

  const paged = usePaged(
    (p) =>
      listDepartments({
        ...p,
        hospital_id: hospitalId || undefined,
        status: status || undefined,
      }),
    [hospitalId, status],
  )

  // A hospital administrator only ever sees their own hospitals' departments.
  const rows = hospitalScope
    ? paged.items.filter((d) => hospitalScope.includes(d.hospital_id))
    : paged.items

  const changeIntake = async (department, next, reason) => {
    try {
      const r = await setDepartmentIntake(department.id, next, reason)
      toast.success(`${r.message} ${r.active_appointments_unaffected} existing appointment(s) left untouched.`)
      paged.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Departments"
        description="Each department controls whether it accepts new appointment requests."
      />

      <FilterBar
        hasActive={Boolean(hospitalId || status)}
        onClear={() => {
          setHospitalId(hospitalScope?.length === 1 ? hospitalScope[0] : '')
          setStatus('')
        }}
        filters={[
          {
            key: 'hospital_id',
            label: 'Hospital',
            value: hospitalId,
            onChange: setHospitalId,
            options: scopedHospitals.map((h) => ({ value: h.id, label: h.name })),
          },
          {
            key: 'status',
            label: 'Department status',
            value: status,
            onChange: setStatus,
            options: Object.values(DEPARTMENT_STATUS).map((s) => ({ value: s, label: humanise(s) })),
          },
        ]}
      />

      <AsyncBoundary
        loading={paged.loading}
        error={paged.error}
        onRetry={paged.reload}
        isEmpty={rows.length === 0}
        skeleton={<LoadingSkeleton variant="table" rows={5} />}
        empty={
          <EmptyState
            icon={LayoutGrid}
            title="No departments match"
            description="Departments are created from a hospital's page."
          />
        }
      >
        <Card className="overflow-hidden">
          <DataTable
            caption="Departments"
            rows={rows}
            columns={[
              {
                key: 'name',
                header: 'Department',
                render: (d) => (
                  <span className="min-w-0">
                    <span className="block truncate font-medium text-forest-700">{d.name}</span>
                    {d.description && (
                      <span className="block truncate text-xs text-ink-muted">{d.description}</span>
                    )}
                  </span>
                ),
              },
              {
                key: 'hospital',
                header: 'Hospital',
                render: (d) => hospitalById[d.hospital_id]?.name || '—',
              },
              {
                key: 'status',
                header: 'Status',
                render: (d) => <StatusBadge status={d.status} kind="generic" />,
              },
              {
                key: 'intake',
                header: 'Intake',
                render: (d) => <StatusBadge status={d.appointment_intake_status} kind="generic" />,
              },
              {
                key: 'actions',
                header: '',
                className: 'text-right',
                render: (d) => (
                  <span className="flex flex-wrap justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={() => setEditing(d)}>
                      Edit
                    </Button>
                    <IntakeToggle
                      status={d.appointment_intake_status}
                      label={d.name}
                      onChange={(next, reason) => changeIntake(d, next, reason)}
                    />
                  </span>
                ),
              },
            ]}
          />
        </Card>
        <Pagination
          className="mt-6"
          page={paged.page}
          totalPages={paged.totalPages}
          total={paged.total}
          pageSize={paged.pageSize}
          onChange={paged.setPage}
        />
      </AsyncBoundary>

      <EditDepartmentModal
        department={editing}
        onClose={() => setEditing(null)}
        onDone={() => {
          setEditing(null)
          paged.reload()
          toast.success('Department updated.')
        }}
      />
    </div>
  )
}

function EditDepartmentModal({ department, onClose, onDone }) {
  const toast = useToast()
  const [form, setForm] = useState({ name: '', description: '', status: DEPARTMENT_STATUS.ACTIVE })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  // Seed the form whenever a different department is opened.
  useEffect(() => {
    if (!department) return
    setForm({
      name: department.name,
      description: department.description || '',
      status: department.status,
    })
    setErrors({})
  }, [department])

  const submit = async () => {
    setBusy(true)
    setErrors({})
    try {
      await updateDepartment(department.id, {
        name: form.name.trim(),
        description: form.description.trim() || null,
        status: form.status,
      })
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
      open={Boolean(department)}
      onClose={onClose}
      title={`Edit ${department?.name ?? ''}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} disabled={form.name.trim().length < 2}>
            Save changes
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
        />
        <Textarea
          label="Description"
          value={form.description}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          rows={3}
          maxLength={500}
          error={errors.description}
        />
        <Select
          label="Status"
          value={form.status}
          onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
          options={[
            { value: DEPARTMENT_STATUS.ACTIVE, label: 'Active' },
            { value: DEPARTMENT_STATUS.INACTIVE, label: 'Inactive — no new bookings' },
          ]}
        />
        <p className="text-xs leading-relaxed text-ink-muted">
          Making a department inactive, or closing its intake, stops new requests. It never cancels
          appointments that already exist. Intake status is {humanise(department?.appointment_intake_status || INTAKE_STATUS.OPEN)}.
        </p>
      </div>
    </Modal>
  )
}
