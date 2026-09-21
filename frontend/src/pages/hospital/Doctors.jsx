import { useEffect, useState } from 'react'
import { Stethoscope } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { SearchBar } from '../../components/SearchBar'
import { FilterBar } from '../../components/FilterBar'
import { RatingStars } from '../../components/RatingStars'
import { IntakeToggle } from '../../components/IntakeToggle'
import { Avatar } from '../../components/ui/Avatar'
import { Card } from '../../components/ui/Card'
import { DataTable } from '../../components/ui/DataTable'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDebounced } from '../../hooks/useDebounced'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { searchDoctors, setDoctorIntake } from '../../api/doctors'
import { pluralise } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

/**
 * Doctors at the hospitals this administrator manages.
 *
 * A hospital administrator can open or close a doctor's intake (the backend
 * allows it for an admin authorised for one of that doctor's hospitals) but
 * cannot verify or suspend a profile — that is a platform administrator's job,
 * so no such control is offered here.
 */
export default function HospitalDoctors() {
  useDocumentTitle('Doctors')
  const { managedHospitalIds } = useAuth()
  const { hospitalById, departmentById, departments } = useDirectory()
  const toast = useToast()

  const ids = managedHospitalIds ?? []
  const [hospitalId, setHospitalId] = useState(ids[0] ?? '')
  const [departmentId, setDepartmentId] = useState('')
  const [query, setQuery] = useState('')
  const debounced = useDebounced(query)

  useEffect(() => {
    if (!hospitalId && ids.length) setHospitalId(ids[0])
  }, [ids, hospitalId])

  const paged = usePaged(
    (p) =>
      searchDoctors({
        ...p,
        hospital_id: hospitalId || undefined,
        department_id: departmentId || undefined,
        q: debounced || undefined,
      }),
    [hospitalId, departmentId, debounced],
    { enabled: Boolean(hospitalId) },
  )

  const changeIntake = async (doctor, status, reason) => {
    try {
      await setDoctorIntake(doctor.id, status, reason)
      toast.success(
        status === 'OPEN'
          ? `${doctor.name} is accepting new requests again.`
          : `New requests to ${doctor.name} are paused. Existing appointments are unchanged.`,
      )
      paged.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Doctors"
        description="Everyone practising at the hospitals you manage."
      />

      <SearchBar value={query} onChange={setQuery} placeholder="Search by name…" label="Search doctors" />

      <FilterBar
        hasActive={Boolean(departmentId)}
        onClear={() => setDepartmentId('')}
        filters={[
          ...(ids.length > 1
            ? [
                {
                  key: 'hospital_id',
                  label: 'Hospital',
                  value: hospitalId,
                  onChange: (v) => {
                    setHospitalId(v || ids[0])
                    setDepartmentId('')
                  },
                  options: ids.map((id) => ({ value: id, label: hospitalById[id]?.name || 'Hospital' })),
                },
              ]
            : []),
          {
            key: 'department_id',
            label: 'Department',
            value: departmentId,
            onChange: setDepartmentId,
            options: departments
              .filter((d) => d.hospital_id === hospitalId)
              .map((d) => ({ value: d.id, label: d.name })),
          },
        ]}
      />

      <AsyncBoundary
        loading={paged.loading}
        error={paged.error}
        onRetry={paged.reload}
        isEmpty={paged.isEmpty}
        skeleton={<LoadingSkeleton variant="table" rows={5} />}
        empty={
          <EmptyState
            icon={Stethoscope}
            title="No doctors here yet"
            description="A platform administrator assigns doctors to a hospital and department."
          />
        }
      >
        <Card className="overflow-hidden">
          <DataTable
            caption="Doctors at this hospital"
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
                key: 'departments',
                header: 'Departments',
                hideOnMobile: true,
                render: (d) =>
                  d.department_ids?.map((id) => departmentById[id]?.name).filter(Boolean).join(', ') || '—',
              },
              {
                key: 'experience',
                header: 'Experience',
                hideOnMobile: true,
                render: (d) => (d.experience > 0 ? pluralise(d.experience, 'year', 'years') : '—'),
              },
              {
                key: 'rating',
                header: 'Rating',
                hideOnMobile: true,
                render: (d) => <RatingStars average={d.rating_average} count={d.rating_count} />,
              },
              {
                key: 'intake',
                header: 'Intake',
                render: (d) => <StatusBadge status={d.availability_status} kind="generic" />,
              },
              {
                key: 'actions',
                header: '',
                className: 'text-right',
                render: (d) => (
                  <span className="flex justify-end">
                    <IntakeToggle
                      status={d.availability_status}
                      label={d.name}
                      onChange={(status, reason) => changeIntake(d, status, reason)}
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
    </div>
  )
}
