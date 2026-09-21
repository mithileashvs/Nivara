import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Building2, MapPin, Phone } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { SearchBar } from '../../components/SearchBar'
import { FilterBar } from '../../components/FilterBar'
import { Card, CardBody } from '../../components/ui/Card'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDebounced } from '../../hooks/useDebounced'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { listHospitals } from '../../api/hospitals'
import { INTAKE_STATUS } from '../../utils/constants'
import { pluralise } from '../../utils/format'

/**
 * Hospitals on the platform. Intake status comes from the hospital record, so a
 * patient can see at a glance where new requests are being accepted. No slot
 * counts or "load" figures are shown here — those belong to a real availability
 * query, which the doctor's profile does per-doctor.
 */
export default function PatientHospitals() {
  useDocumentTitle('Hospitals')
  const { cities } = useDirectory()

  const [query, setQuery] = useState('')
  const debounced = useDebounced(query)
  const [city, setCity] = useState('')
  const [intake, setIntake] = useState('')

  const paged = usePaged(
    (p) =>
      listHospitals({
        ...p,
        q: debounced || undefined,
        city: city || undefined,
        intake_status: intake || undefined,
      }),
    [debounced, city, intake],
  )

  const hasActive = useMemo(() => Boolean(debounced || city || intake), [debounced, city, intake])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Hospitals"
        description="Where Nivara doctors practise, and who is taking new appointments."
      />

      <SearchBar value={query} onChange={setQuery} placeholder="Search hospitals…" label="Search hospitals" />

      <FilterBar
        hasActive={hasActive}
        onClear={() => {
          setQuery('')
          setCity('')
          setIntake('')
        }}
        filters={[
          {
            key: 'city',
            label: 'Location',
            value: city,
            onChange: setCity,
            options: cities.map((c) => ({ value: c, label: c })),
          },
          {
            key: 'intake_status',
            label: 'Taking appointments',
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
        skeleton={<LoadingSkeleton variant="cards" rows={3} />}
        empty={
          <EmptyState
            icon={Building2}
            title="No hospitals match"
            description="Try a broader search or a different city."
          />
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          {paged.items.map((h) => (
            <Card key={h.id}>
              <CardBody className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <h2 className="min-w-0 text-base font-semibold text-forest-700">{h.name}</h2>
                  <StatusBadge status={h.appointment_intake_status} kind="generic" />
                </div>

                <p className="flex items-start gap-1.5 text-sm text-ink-muted">
                  <MapPin size={14} className="mt-0.5 shrink-0 text-ink-faint" aria-hidden="true" />
                  <span>
                    {h.address}
                    {h.location?.city && `, ${h.location.city}`}
                  </span>
                </p>

                {h.contact?.phone && (
                  <p className="flex items-center gap-1.5 text-sm text-ink-muted">
                    <Phone size={14} className="shrink-0 text-ink-faint" aria-hidden="true" />
                    {h.contact.phone}
                  </p>
                )}

                <p className="text-xs text-ink-muted">
                  {pluralise(h.department_ids?.length ?? 0, 'department', 'departments')}
                </p>

                <Link
                  to={`/find-doctors?hospital_id=${h.id}`}
                  className="inline-flex h-10 items-center rounded-xl bg-forest px-4 text-sm font-medium text-canvas transition-colors hover:bg-forest-700 focus-ring"
                >
                  See doctors here
                </Link>
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
    </div>
  )
}
