import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { SearchX } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { SearchBar } from '../../components/SearchBar'
import { FilterBar } from '../../components/FilterBar'
import { DoctorCard } from '../../components/DoctorCard'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { Pagination } from '../../components/ui/Pagination'
import { Checkbox } from '../../components/ui/Field'
import { usePaged } from '../../hooks/usePaged'
import { useDebounced } from '../../hooks/useDebounced'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { searchDoctors } from '../../api/doctors'
import { searchSlots } from '../../api/slots'
import { CONSULTATION_TYPES } from '../../utils/constants'
import { addDays, todayString } from '../../utils/format'

/**
 * Doctor search. Filters map one-to-one onto DoctorSearchParams, so the backend
 * does all the matching. `available=true` asks it for doctors that have at least
 * one genuinely bookable slot in the window — the UI never decides that itself.
 */
export default function FindDoctors() {
  useDocumentTitle('Find doctors')
  const [params, setParams] = useSearchParams()
  const { hospitals, departments, cities, hospitalNames } = useDirectory()

  const [query, setQuery] = useState(params.get('q') || '')
  const debounced = useDebounced(query)

  const [filters, setFilters] = useState({
    specialty: params.get('specialty') || '',
    hospital_id: params.get('hospital_id') || '',
    department_id: params.get('department_id') || '',
    city: params.get('city') || '',
    consultation_type: params.get('consultation_type') || '',
    available: params.get('available') === 'true',
  })

  const dateFrom = todayString()
  const dateTo = useMemo(() => addDays(dateFrom, 14), [dateFrom])

  // Keep the URL shareable and reload-safe.
  useEffect(() => {
    const next = {}
    if (debounced) next.q = debounced
    for (const [k, v] of Object.entries(filters)) {
      if (v === true) next[k] = 'true'
      else if (v) next[k] = v
    }
    setParams(next, { replace: true })
  }, [debounced, filters, setParams])

  const set = (key) => (value) => setFilters((f) => ({ ...f, [key]: value }))
  const hasActive = Boolean(debounced) || Object.values(filters).some(Boolean)

  const paged = usePaged(
    (p) =>
      searchDoctors({
        ...p,
        q: debounced || undefined,
        specialty: filters.specialty || undefined,
        hospital_id: filters.hospital_id || undefined,
        department_id: filters.department_id || undefined,
        city: filters.city || undefined,
        consultation_type: filters.consultation_type || undefined,
        ...(filters.available ? { available: true, date_from: dateFrom, date_to: dateTo } : {}),
      }),
    [debounced, filters, dateFrom, dateTo],
  )

  // Next open times per doctor, from the real slot endpoint.
  const [slotsByDoctor, setSlotsByDoctor] = useState({})
  const [slotsLoading, setSlotsLoading] = useState(false)

  useEffect(() => {
    const doctors = paged.items
    if (!doctors.length) {
      setSlotsByDoctor({})
      return undefined
    }
    let cancelled = false
    setSlotsLoading(true)
    Promise.all(
      doctors.map((d) =>
        searchSlots({ doctor_id: d.id, date_from: dateFrom, date_to: dateTo, page: 1, page_size: 8 })
          .then((r) => [d.id, r.items ?? []])
          .catch(() => [d.id, []]),
      ),
    )
      .then((pairs) => {
        if (!cancelled) setSlotsByDoctor(Object.fromEntries(pairs))
      })
      .finally(() => {
        if (!cancelled) setSlotsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [paged.items, dateFrom, dateTo])

  // Specialties come from the doctors actually returned, not a hardcoded list.
  const specialties = useMemo(
    () => [...new Set(paged.items.map((d) => d.specialty).filter(Boolean))].sort(),
    [paged.items],
  )

  const departmentOptions = useMemo(
    () =>
      departments
        .filter((d) => !filters.hospital_id || d.hospital_id === filters.hospital_id)
        .map((d) => ({ value: d.id, label: d.name })),
    [departments, filters.hospital_id],
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Find doctors"
        description="Search and book appointments with verified healthcare professionals."
      />

      <div className="space-y-3">
        <SearchBar
          value={query}
          onChange={setQuery}
          placeholder="Search by doctor name, specialty or hospital…"
          label="Search doctors"
        />

        <FilterBar
          hasActive={hasActive}
          onClear={() => {
            setQuery('')
            setFilters({
              specialty: '',
              hospital_id: '',
              department_id: '',
              city: '',
              consultation_type: '',
              available: false,
            })
          }}
          filters={[
            {
              key: 'specialty',
              label: 'Specialty',
              value: filters.specialty,
              onChange: set('specialty'),
              options: specialties.map((s) => ({ value: s, label: s })),
            },
            {
              key: 'city',
              label: 'Location',
              value: filters.city,
              onChange: set('city'),
              options: cities.map((c) => ({ value: c, label: c })),
            },
            {
              key: 'hospital_id',
              label: 'Hospital',
              value: filters.hospital_id,
              onChange: (v) => setFilters((f) => ({ ...f, hospital_id: v, department_id: '' })),
              options: hospitals.map((h) => ({ value: h.id, label: h.name })),
            },
            {
              key: 'department_id',
              label: 'Department',
              value: filters.department_id,
              onChange: set('department_id'),
              options: departmentOptions,
            },
            {
              key: 'consultation_type',
              label: 'Consultation type',
              value: filters.consultation_type,
              onChange: set('consultation_type'),
              options: CONSULTATION_TYPES,
            },
          ]}
          extra={
            <Checkbox
              label="Has open times in the next 14 days"
              checked={filters.available}
              onChange={(e) => setFilters((f) => ({ ...f, available: e.target.checked }))}
              className="rounded-xl border border-line bg-surface px-3.5 py-2"
            />
          }
        />
      </div>

      <AsyncBoundary
        loading={paged.loading}
        error={paged.error}
        onRetry={paged.reload}
        isEmpty={paged.isEmpty}
        skeleton={<LoadingSkeleton variant="cards" rows={3} />}
        empty={
          <EmptyState
            icon={SearchX}
            title="No doctors match those filters"
            description="Try a broader search — fewer filters, a different specialty, or another hospital."
          />
        }
      >
        <p className="text-sm text-ink-muted" aria-live="polite">
          {paged.total} {paged.total === 1 ? 'doctor' : 'doctors'} found
        </p>
        <div className="mt-4 space-y-3">
          {paged.items.map((doctor) => (
            <DoctorCard
              key={doctor.id}
              doctor={doctor}
              hospitalNames={hospitalNames(doctor.hospital_ids)}
              slots={slotsByDoctor[doctor.id] ?? null}
              slotsLoading={slotsLoading && !slotsByDoctor[doctor.id]}
            />
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
