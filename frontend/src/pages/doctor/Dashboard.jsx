import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { CalendarCheck, CalendarClock, CheckCircle2, Users } from 'lucide-react'
import { PageHeader, NotificationBell } from '../../components/Topbar'
import { StatCard } from '../../components/StatCard'
import { AppointmentCard } from '../../components/AppointmentCard'
import { IntakeToggle } from '../../components/IntakeToggle'
import { Avatar } from '../../components/ui/Avatar'
import { Badge } from '../../components/ui/StatusBadge'
import { Card, CardBody } from '../../components/ui/Card'
import { AsyncBoundary, EmptyState, LoadingSkeleton, ErrorState } from '../../components/ui/States'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import { useDirectory } from '../../hooks/useDirectory'
import { useUnreadCount } from '../../hooks/useUnreadCount'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { getMyStatistics, setDoctorIntake } from '../../api/doctors'
import { listAppointments } from '../../api/appointments'
import { APPOINTMENT_STATUS, MAX_PAGE_SIZE, PROFILE_STATUS } from '../../utils/constants'
import { greeting, todayString } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

/**
 * Doctor home. The four figures come straight from GET /doctors/me/statistics,
 * which the backend computes live from appointment records.
 */
export default function DoctorDashboard() {
  useDocumentTitle('Dashboard')
  const { user, doctorProfile, refreshDoctorProfile } = useAuth()
  const { unread } = useUnreadCount()
  const { hospitalName, departmentName } = useDirectory()
  const toast = useToast()

  const stats = useAsync(() => getMyStatistics(), [])
  const today = todayString()

  const pending = useAsync(
    () =>
      listAppointments({
        status: APPOINTMENT_STATUS.REQUESTED,
        page: 1,
        page_size: 5,
      }),
    [],
  )

  const todays = useAsync(
    () => listAppointments({ date_from: today, date_to: today, page: 1, page_size: MAX_PAGE_SIZE }),
    [today],
  )

  const todaysConfirmed = useMemo(
    () =>
      (todays.data?.items ?? [])
        .filter((a) => a.status === APPOINTMENT_STATUS.CONFIRMED)
        .sort((a, b) => a.start_time.localeCompare(b.start_time)),
    [todays.data],
  )

  const changeIntake = async (status, reason) => {
    try {
      await setDoctorIntake(doctorProfile.id, status, reason)
      await refreshDoctorProfile()
      toast.success(
        status === 'OPEN'
          ? 'You are accepting new requests again.'
          : 'New requests are paused. Existing appointments are unchanged.',
      )
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  const firstName = user?.name?.split(' ')[0] || 'Doctor'

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageHeader
          eyebrow={`${greeting()},`}
          title={firstName}
          description="Here's how your day looks."
        />
        <div className="flex items-center gap-3">
          <NotificationBell unread={unread} to="/doctor/notifications" />
          <Link to="/doctor/profile" aria-label="Profile" className="hidden rounded-full focus-ring lg:block">
            <Avatar name={user?.name} />
          </Link>
        </div>
      </div>

      {/* A pending or suspended profile cannot publish availability or take requests. */}
      {doctorProfile && doctorProfile.profile_status !== PROFILE_STATUS.ACTIVE && (
        <p className="rounded-xl border border-warn/30 bg-warn-soft px-4 py-3 text-sm text-forest-700" role="status">
          {doctorProfile.profile_status === PROFILE_STATUS.PENDING
            ? 'Your profile is awaiting verification. An administrator needs to activate it and assign your hospital and department before you can publish availability or receive requests.'
            : 'Your profile is suspended. Contact your administrator to restore it.'}
        </p>
      )}

      {doctorProfile?.profile_status === PROFILE_STATUS.ACTIVE && (
        <Card>
          <CardBody className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-forest-700">New appointment requests</p>
              <p className="mt-0.5 text-sm text-ink-muted">
                Pausing stops new requests reaching you. Appointments you have already accepted stay
                exactly as they are.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge tone={doctorProfile.availability_status === 'OPEN' ? 'positive' : 'negative'}>
                {doctorProfile.availability_status === 'OPEN' ? 'Accepting' : 'Paused'}
              </Badge>
              <IntakeToggle status={doctorProfile.availability_status} onChange={changeIntake} />
            </div>
          </CardBody>
        </Card>
      )}

      <section aria-label="Your statistics">
        {stats.loading ? (
          <LoadingSkeleton variant="stats" rows={4} />
        ) : stats.error ? (
          <ErrorState error={stats.error} onRetry={stats.reload} />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              icon={CalendarClock}
              value={stats.data.todays_appointments}
              label="Today's appointments"
              to="/doctor/appointments"
            />
            <StatCard
              icon={CalendarCheck}
              value={stats.data.pending_requests}
              label="Pending requests"
              tone={stats.data.pending_requests > 0 ? 'warn' : 'default'}
              to="/doctor/appointments?status=REQUESTED"
            />
            <StatCard
              icon={CheckCircle2}
              value={stats.data.confirmed_appointments}
              label="Confirmed appointments"
              to="/doctor/appointments?status=CONFIRMED"
            />
            <StatCard icon={Users} value={stats.data.total_patients} label="Patients seen" to="/doctor/patients" />
          </div>
        )}
      </section>

      <section aria-labelledby="pending-heading">
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 id="pending-heading" className="text-lg font-semibold text-forest-700">
            Waiting for your decision
          </h2>
          <Link
            to="/doctor/appointments?status=REQUESTED"
            className="rounded text-sm font-medium text-forest transition-colors hover:text-forest-400 focus-ring"
          >
            View all
          </Link>
        </div>

        <AsyncBoundary
          loading={pending.loading}
          error={pending.error}
          onRetry={pending.reload}
          isEmpty={(pending.data?.items ?? []).length === 0}
          skeleton={<LoadingSkeleton rows={2} />}
          empty={
            <EmptyState
              icon={CheckCircle2}
              title="No requests waiting"
              description="Every appointment request has had a decision."
            />
          }
        >
          <div className="space-y-3">
            {(pending.data?.items ?? []).map((a) => (
              <AppointmentCard
                key={a.id}
                appointment={a}
                perspective="doctor"
                hospitalName={hospitalName(a.hospital_id)}
                departmentName={departmentName(a.department_id)}
              />
            ))}
          </div>
        </AsyncBoundary>
      </section>

      <section aria-labelledby="today-heading">
        <h2 id="today-heading" className="mb-4 text-lg font-semibold text-forest-700">
          Confirmed for today
        </h2>
        <AsyncBoundary
          loading={todays.loading}
          error={todays.error}
          onRetry={todays.reload}
          isEmpty={todaysConfirmed.length === 0}
          skeleton={<LoadingSkeleton rows={2} />}
          empty={<EmptyState title="Nothing confirmed today" description="Your day is clear." />}
        >
          <div className="space-y-3">
            {todaysConfirmed.map((a) => (
              <AppointmentCard
                key={a.id}
                appointment={a}
                perspective="doctor"
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
