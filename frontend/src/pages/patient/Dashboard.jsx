import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CalendarPlus, FileText, Search, Sparkles, CalendarCheck2 } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { SearchBar } from '../../components/SearchBar'
import { QuickAction } from '../../components/QuickAction'
import { AppointmentCard } from '../../components/AppointmentCard'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { Badge } from '../../components/ui/StatusBadge'
import { useAuth } from '../../context/AuthContext'
import { useAsync } from '../../hooks/useAsync'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { listAppointments } from '../../api/appointments'
import { APPOINTMENT_STATUS, PAGE_SIZE } from '../../utils/constants'
import { greeting, todayString } from '../../utils/format'

/**
 * Patient home. Every figure and row is fetched — there is no placeholder data.
 * "Upcoming" means REQUESTED or CONFIRMED appointments dated today or later,
 * which is exactly what the backend's date filter returns.
 */
export default function PatientDashboard() {
  useDocumentTitle('Dashboard')
  const { user } = useAuth()
  const navigate = useNavigate()
  const { hospitalName, departmentName } = useDirectory()
  const [query, setQuery] = useState('')

  const today = todayString()

  const upcoming = useAsync(
    () => listAppointments({ date_from: today, page: 1, page_size: PAGE_SIZE }),
    [today],
  )

  const rows = useMemo(() => {
    const items = upcoming.data?.items ?? []
    return items
      .filter((a) =>
        [APPOINTMENT_STATUS.REQUESTED, APPOINTMENT_STATUS.CONFIRMED].includes(a.status),
      )
      .sort((a, b) => new Date(a.start_at) - new Date(b.start_at))
  }, [upcoming.data])

  const firstName = user?.name?.split(' ')[0] || 'there'

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={`${greeting()}`}
        title={firstName}
        description="Take charge of your health — search verified specialists, manage appointments, or review your records."
      />

      <SearchBar
        value={query}
        onChange={setQuery}
        onSubmit={(q) => navigate(`/find-doctors?q=${encodeURIComponent(q)}`)}
        placeholder="Search doctors, departments or hospitals…"
        label="Search doctors, departments or hospitals"
      />

      <section aria-label="Quick actions" className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <QuickAction
          icon={Search}
          title="Find doctors"
          description="Search by specialty"
          to="/find-doctors"
        />
        <QuickAction
          icon={Sparkles}
          title="Symptom routing"
          description="Find the right department"
          to="/smart-suggestions"
        />
        <QuickAction
          icon={CalendarPlus}
          title="Book appointment"
          description="Pick a time that's open"
          to="/find-doctors?available=true"
        />
        <QuickAction
          icon={FileText}
          title="My records"
          description="View your history"
          to="/records"
        />
      </section>

      <section aria-labelledby="upcoming-heading">
        <div className="mb-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <h2 id="upcoming-heading" className="text-lg font-semibold text-forest-700">
              Upcoming appointments
            </h2>
            {!upcoming.loading && rows.length > 0 && (
              <Badge tone="neutral">{rows.length}</Badge>
            )}
          </div>
          <Link
            to="/appointments"
            className="rounded text-sm font-medium text-forest transition-colors hover:text-forest-400 focus-ring"
          >
            View all
          </Link>
        </div>

        <AsyncBoundary
          loading={upcoming.loading}
          error={upcoming.error}
          onRetry={upcoming.reload}
          isEmpty={rows.length === 0}
          skeleton={<LoadingSkeleton rows={2} />}
          empty={
            <EmptyState
              icon={CalendarCheck2}
              title="Nothing booked yet"
              description="Find a doctor and request a time that suits you. They'll confirm it from their side."
              action={
                <Link
                  to="/find-doctors"
                  className="inline-flex h-11 items-center rounded-xl bg-forest px-5 text-sm font-medium text-canvas transition-colors hover:bg-forest-700 focus-ring"
                >
                  Find a doctor
                </Link>
              }
            />
          }
        >
          <div className="space-y-3">
            {rows.slice(0, 5).map((a) => (
              <AppointmentCard
                key={a.id}
                appointment={a}
                perspective="patient"
                hospitalName={hospitalName(a.hospital_id)}
                departmentName={departmentName(a.department_id)}
              />
            ))}
          </div>
        </AsyncBoundary>
      </section>
    </div>
  )
}
