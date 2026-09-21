import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Stethoscope } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { FilterBar } from '../../components/FilterBar'
import { RatingStars } from '../../components/RatingStars'
import { Avatar } from '../../components/ui/Avatar'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { DataTable } from '../../components/ui/DataTable'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { Modal } from '../../components/ui/Modal'
import { Select, Textarea } from '../../components/ui/Field'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import { listDoctorProfiles, setDoctorAffiliations, setDoctorProfileStatus } from '../../api/admin'
import { PROFILE_STATUS } from '../../utils/constants'
import { humanise, pluralise } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

/**
 * Doctor verification and affiliation. A profile must be ACTIVE, with a hospital
 * and a department, before the doctor can publish availability or take requests.
 */
export default function AdminDoctors() {
  useDocumentTitle('Doctors')
  const [params, setParams] = useSearchParams()
  const toast = useToast()
  const { hospitalById, departmentById } = useDirectory()

  const profileStatus = params.get('profile_status') || ''
  const [statusFor, setStatusFor] = useState(null)
  const [affiliationsFor, setAffiliationsFor] = useState(null)

  const paged = usePaged(
    (p) => listDoctorProfiles({ ...p, profile_status: profileStatus || undefined }),
    [profileStatus],
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Doctors"
        description="Verify profiles and set which hospitals and departments each doctor works in."
      />

      <FilterBar
        hasActive={Boolean(profileStatus)}
        onClear={() => setParams({}, { replace: true })}
        filters={[
          {
            key: 'profile_status',
            label: 'Profile status',
            value: profileStatus,
            onChange: (v) => setParams(v ? { profile_status: v } : {}, { replace: true }),
            options: Object.values(PROFILE_STATUS).map((s) => ({ value: s, label: humanise(s) })),
          },
        ]}
      />

      <AsyncBoundary
        loading={paged.loading}
        error={paged.error}
        onRetry={paged.reload}
        isEmpty={paged.isEmpty}
        skeleton={<LoadingSkeleton variant="table" rows={5} />}
        empty={<EmptyState icon={Stethoscope} title="No doctor profiles match" />}
      >
        <Card className="overflow-hidden">
          <DataTable
            caption="Doctor profiles"
            rows={paged.items}
            columns={[
              {
                key: 'name',
                header: 'Doctor',
                render: (d) => (
                  <span className="flex items-center gap-3">
                    <Avatar name={d.name} size="sm" />
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-forest-700">{d.name}</span>
                      <span className="block truncate text-xs text-ink-muted">{d.specialty}</span>
                    </span>
                  </span>
                ),
              },
              {
                key: 'profile_status',
                header: 'Profile',
                render: (d) => <StatusBadge status={d.profile_status} kind="generic" />,
              },
              {
                key: 'availability_status',
                header: 'Intake',
                render: (d) => <StatusBadge status={d.availability_status} kind="generic" />,
              },
              {
                key: 'affiliations',
                header: 'Affiliations',
                hideOnMobile: true,
                render: (d) =>
                  d.hospital_ids?.length ? (
                    <span className="text-xs text-ink-muted">
                      {d.hospital_ids.map((id) => hospitalById[id]?.name).filter(Boolean).join(', ') || '—'}
                      {' · '}
                      {pluralise(d.department_ids?.length ?? 0, 'department', 'departments')}
                    </span>
                  ) : (
                    <span className="text-xs text-warn">Not assigned</span>
                  ),
              },
              {
                key: 'rating',
                header: 'Rating',
                hideOnMobile: true,
                render: (d) => <RatingStars average={d.rating_average} count={d.rating_count} />,
              },
              {
                key: 'actions',
                header: '',
                className: 'text-right',
                render: (d) => (
                  <span className="flex justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={() => setAffiliationsFor(d)}>
                      Affiliations
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setStatusFor(d)}>
                      Status
                    </Button>
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

      <StatusModal
        doctor={statusFor}
        onClose={() => setStatusFor(null)}
        onDone={() => {
          setStatusFor(null)
          paged.reload()
          toast.success('Profile status updated.')
        }}
      />

      <AffiliationsModal
        doctor={affiliationsFor}
        onClose={() => setAffiliationsFor(null)}
        onDone={() => {
          setAffiliationsFor(null)
          paged.reload()
          toast.success('Affiliations updated.')
        }}
      />
    </div>
  )
}

function StatusModal({ doctor, onClose, onDone }) {
  const toast = useToast()
  const [status, setStatus] = useState(PROFILE_STATUS.ACTIVE)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (doctor) {
      setStatus(doctor.profile_status)
      setReason('')
    }
  }, [doctor])

  const submit = async () => {
    setBusy(true)
    try {
      await setDoctorProfileStatus(doctor.id, status, reason.trim() || undefined)
      onDone()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={Boolean(doctor)}
      onClose={onClose}
      title={`Profile status for ${doctor?.name ?? ''}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy}>
            Save status
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Select
          label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={[
            { value: PROFILE_STATUS.PENDING, label: 'Pending — not yet verified' },
            { value: PROFILE_STATUS.ACTIVE, label: 'Active — can publish hours and take requests' },
            { value: PROFILE_STATUS.SUSPENDED, label: 'Suspended — cannot take new requests' },
          ]}
        />
        <Textarea
          label="Reason (optional)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          maxLength={300}
        />
        <p className="text-xs leading-relaxed text-ink-muted">
          A doctor needs an active profile plus a hospital and department before patients can request
          appointments with them.
        </p>
      </div>
    </Modal>
  )
}

function AffiliationsModal({ doctor, onClose, onDone }) {
  const toast = useToast()
  const { hospitals, departments } = useDirectory()
  const [hospitalIds, setHospitalIds] = useState([])
  const [departmentIds, setDepartmentIds] = useState([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (doctor) {
      setHospitalIds(doctor.hospital_ids ?? [])
      setDepartmentIds(doctor.department_ids ?? [])
    }
  }, [doctor])

  // The backend requires every department to belong to one of the listed hospitals.
  const selectableDepartments = departments.filter((d) => hospitalIds.includes(d.hospital_id))

  const toggle = (list, setList) => (id) =>
    setList(list.includes(id) ? list.filter((x) => x !== id) : [...list, id])

  const submit = async () => {
    setBusy(true)
    try {
      await setDoctorAffiliations(doctor.id, {
        hospital_ids: hospitalIds,
        department_ids: departmentIds.filter((id) =>
          selectableDepartments.some((d) => d.id === id),
        ),
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
      open={Boolean(doctor)}
      onClose={onClose}
      title={`Affiliations for ${doctor?.name ?? ''}`}
      description="Replaces the doctor's current hospitals and departments."
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy}>
            Save affiliations
          </Button>
        </>
      }
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-forest-700">Hospitals</legend>
          <CheckList
            items={hospitals.map((h) => ({ id: h.id, label: h.name }))}
            selected={hospitalIds}
            onToggle={(id) => {
              const next = hospitalIds.includes(id)
                ? hospitalIds.filter((x) => x !== id)
                : [...hospitalIds, id]
              setHospitalIds(next)
              setDepartmentIds((ds) =>
                ds.filter((did) => departments.find((d) => d.id === did && next.includes(d.hospital_id))),
              )
            }}
          />
        </fieldset>
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-forest-700">Departments</legend>
          <CheckList
            items={selectableDepartments.map((d) => ({ id: d.id, label: d.name }))}
            selected={departmentIds}
            onToggle={toggle(departmentIds, setDepartmentIds)}
            empty="Choose a hospital first."
          />
        </fieldset>
      </div>
    </Modal>
  )
}

function CheckList({ items, selected, onToggle, empty = 'Nothing to choose from.' }) {
  if (!items.length) return <p className="rounded-xl border border-line px-3 py-4 text-sm text-ink-muted">{empty}</p>
  return (
    <ul className="max-h-56 space-y-1 overflow-y-auto rounded-xl border border-line p-2">
      {items.map((item) => (
        <li key={item.id}>
          <label className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-forest-50">
            <input
              type="checkbox"
              checked={selected.includes(item.id)}
              onChange={() => onToggle(item.id)}
              className="h-4 w-4 rounded border-line accent-[#173C2B] focus-ring"
            />
            <span className="min-w-0 flex-1 truncate text-sm text-ink">{item.label}</span>
          </label>
        </li>
      ))}
    </ul>
  )
}
