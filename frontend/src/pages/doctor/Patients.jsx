import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Users } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { SearchBar } from '../../components/SearchBar'
import { Avatar } from '../../components/ui/Avatar'
import { Card } from '../../components/ui/Card'
import { DataTable } from '../../components/ui/DataTable'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { listAppointments } from '../../api/appointments'
import { MAX_PAGE_SIZE } from '../../utils/constants'
import { formatDate, pluralise } from '../../utils/format'

/**
 * There is no "list my patients" endpoint. The backend's position is that a
 * doctor sees a patient because of an appointment, so this list is derived from
 * the doctor's own appointments — real data, grouped, with no invented fields.
 */
export default function DoctorPatients() {
  useDocumentTitle('Patients')
  const [query, setQuery] = useState('')

  const appointments = useAsync(
    () => listAppointments({ page: 1, page_size: MAX_PAGE_SIZE }),
    [],
  )

  const patients = useMemo(() => {
    const byId = new Map()
    for (const a of appointments.data?.items ?? []) {
      const entry = byId.get(a.patient_id) || {
        id: a.patient_id,
        name: a.patient_name,
        count: 0,
        last: a.appointment_date,
        lastAppointmentId: a.id,
      }
      entry.count += 1
      if (a.appointment_date > entry.last) {
        entry.last = a.appointment_date
        entry.lastAppointmentId = a.id
      }
      byId.set(a.patient_id, entry)
    }
    const list = [...byId.values()].sort((a, b) => b.last.localeCompare(a.last))
    const q = query.trim().toLowerCase()
    return q ? list.filter((p) => p.name.toLowerCase().includes(q)) : list
  }, [appointments.data, query])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Patients"
        description="Everyone you have an appointment with, most recent first."
      />

      <SearchBar value={query} onChange={setQuery} placeholder="Search by patient name…" label="Search patients" />

      <AsyncBoundary
        loading={appointments.loading}
        error={appointments.error}
        onRetry={appointments.reload}
        isEmpty={patients.length === 0}
        skeleton={<LoadingSkeleton variant="table" rows={4} />}
        empty={
          <EmptyState
            icon={Users}
            title={query ? 'No patient matches that name' : 'No patients yet'}
            description={
              query
                ? 'Try a different spelling.'
                : 'Patients appear here once they have an appointment with you.'
            }
          />
        }
      >
        <Card className="overflow-hidden">
          <DataTable
            caption="Patients you have appointments with"
            rows={patients}
            columns={[
              {
                key: 'name',
                header: 'Patient',
                render: (p) => (
                  <span className="flex items-center gap-3">
                    <Avatar name={p.name} size="sm" />
                    <span className="font-medium text-forest-700">{p.name}</span>
                  </span>
                ),
              },
              {
                key: 'count',
                header: 'Appointments',
                render: (p) => pluralise(p.count, 'appointment', 'appointments'),
              },
              { key: 'last', header: 'Most recent', render: (p) => formatDate(p.last) },
              {
                key: 'actions',
                header: '',
                className: 'text-right',
                render: (p) => (
                  <Link
                    to={`/doctor/appointments/${p.lastAppointmentId}`}
                    className="rounded text-sm font-medium text-forest transition-colors hover:text-forest-400 focus-ring"
                  >
                    View latest
                  </Link>
                ),
              },
            ]}
          />
        </Card>
        <p className="mt-3 text-xs text-ink-faint">
          Built from your most recent {MAX_PAGE_SIZE} appointments.
        </p>
      </AsyncBoundary>
    </div>
  )
}
