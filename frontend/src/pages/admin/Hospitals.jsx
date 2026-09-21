import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Building2, Plus } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { SearchBar } from '../../components/SearchBar'
import { FilterBar } from '../../components/FilterBar'
import { IntakeToggle } from '../../components/IntakeToggle'
import { Button } from '../../components/ui/Button'
import { Card, CardBody } from '../../components/ui/Card'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Field'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDebounced } from '../../hooks/useDebounced'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { createHospital, listHospitals, setHospitalIntake } from '../../api/hospitals'
import { INTAKE_STATUS } from '../../utils/constants'
import { pluralise } from '../../utils/format'
import { errorMessage, fieldErrors } from '../../utils/errors'

export default function AdminHospitals() {
  useDocumentTitle('Hospitals')
  const { isPlatformAdmin } = useAuth()
  const toast = useToast()

  const [query, setQuery] = useState('')
  const debounced = useDebounced(query)
  const [intake, setIntake] = useState('')
  const [createOpen, setCreateOpen] = useState(false)

  const paged = usePaged(
    (p) => listHospitals({ ...p, q: debounced || undefined, intake_status: intake || undefined }),
    [debounced, intake],
  )

  const changeIntake = async (hospital, status, reason) => {
    try {
      const result = await setHospitalIntake(hospital.id, status, reason)
      toast.success(
        `${result.message} ${result.active_appointments_unaffected} existing appointment(s) left untouched.`,
      )
      paged.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Hospitals"
        description="Facilities on the platform and whether they are taking new appointments."
        actions={
          isPlatformAdmin && (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus size={16} aria-hidden="true" />
              New hospital
            </Button>
          )
        }
      />

      <SearchBar value={query} onChange={setQuery} placeholder="Search hospitals…" label="Search hospitals" />

      <FilterBar
        hasActive={Boolean(intake)}
        onClear={() => setIntake('')}
        filters={[
          {
            key: 'intake_status',
            label: 'Intake',
            value: intake,
            onChange: setIntake,
            options: [
              { value: INTAKE_STATUS.OPEN, label: 'Open' },
              { value: INTAKE_STATUS.CLOSED, label: 'Closed' },
            ],
          },
        ]}
      />

      <AsyncBoundary
        loading={paged.loading}
        error={paged.error}
        onRetry={paged.reload}
        isEmpty={paged.isEmpty}
        skeleton={<LoadingSkeleton rows={3} />}
        empty={
          <EmptyState
            icon={Building2}
            title="No hospitals yet"
            description={isPlatformAdmin ? 'Create the first one to get started.' : 'Nothing matches those filters.'}
            action={isPlatformAdmin && <Button onClick={() => setCreateOpen(true)}>New hospital</Button>}
          />
        }
      >
        <div className="space-y-3">
          {paged.items.map((h) => (
            <Card key={h.id}>
              <CardBody className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <Link
                    to={`/admin/hospitals/${h.id}`}
                    className="rounded text-base font-semibold text-forest-700 transition-colors hover:text-forest focus-ring"
                  >
                    {h.name}
                  </Link>
                  <p className="mt-1 text-sm text-ink-muted">{h.address}</p>
                  <p className="mt-0.5 text-xs text-ink-muted">
                    {[h.location?.city, h.location?.state].filter(Boolean).join(', ')} ·{' '}
                    {pluralise(h.department_ids?.length ?? 0, 'department', 'departments')}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-3">
                  <StatusBadge status={h.appointment_intake_status} kind="generic" />
                  <IntakeToggle
                    status={h.appointment_intake_status}
                    label={h.name}
                    onChange={(status, reason) => changeIntake(h, status, reason)}
                  />
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

      <CreateHospitalModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onDone={() => {
          setCreateOpen(false)
          paged.reload()
          toast.success('Hospital created.')
        }}
      />
    </div>
  )
}

function CreateHospitalModal({ open, onClose, onDone }) {
  const toast = useToast()
  const [form, setForm] = useState({
    name: '', address: '', city: '', state: '', latitude: '', longitude: '',
    phone: '', email: '', website: '',
  })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async () => {
    setBusy(true)
    setErrors({})
    const contact = {}
    if (form.phone.trim()) contact.phone = form.phone.trim()
    if (form.email.trim()) contact.email = form.email.trim()
    if (form.website.trim()) contact.website = form.website.trim()

    try {
      await createHospital({
        name: form.name.trim(),
        address: form.address.trim(),
        location: {
          city: form.city.trim(),
          ...(form.state.trim() ? { state: form.state.trim() } : {}),
          ...(form.latitude !== '' ? { latitude: Number(form.latitude) } : {}),
          ...(form.longitude !== '' ? { longitude: Number(form.longitude) } : {}),
        },
        ...(Object.keys(contact).length ? { contact } : {}),
      })
      setForm({ name: '', address: '', city: '', state: '', latitude: '', longitude: '', phone: '', email: '', website: '' })
      onDone()
    } catch (err) {
      setErrors(fieldErrors(err))
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const valid = form.name.trim().length >= 2 && form.address.trim().length >= 3 && form.city.trim()

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add a hospital"
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} disabled={!valid}>
            Create hospital
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Input label="Name" required value={form.name} onChange={set('name')} maxLength={120} error={errors.name} />
        <Input label="Address" required value={form.address} onChange={set('address')} maxLength={300} error={errors.address} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="City" required value={form.city} onChange={set('city')} maxLength={80} error={errors.city} />
          <Input label="State" value={form.state} onChange={set('state')} maxLength={80} error={errors.state} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Latitude"
            type="number"
            step="any"
            min="-90"
            max="90"
            value={form.latitude}
            onChange={set('latitude')}
            error={errors.latitude}
            hint="Lets patients search by distance."
          />
          <Input
            label="Longitude"
            type="number"
            step="any"
            min="-180"
            max="180"
            value={form.longitude}
            onChange={set('longitude')}
            error={errors.longitude}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Input label="Phone" type="tel" value={form.phone} onChange={set('phone')} error={errors.phone} />
          <Input label="Email" type="email" value={form.email} onChange={set('email')} error={errors.email} />
          <Input label="Website" type="url" value={form.website} onChange={set('website')} error={errors.website} placeholder="https://" />
        </div>
      </div>
    </Modal>
  )
}
