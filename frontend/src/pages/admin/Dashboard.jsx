import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { BarChart, Bar, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Building2, LayoutGrid, PlayCircle, Stethoscope, Users } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { StatCard } from '../../components/StatCard'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { ErrorState, LoadingSkeleton } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useToast } from '../../context/ToastContext'
import { getStatistics, listDoctorProfiles, runMaintenance } from '../../api/admin'
import { APPOINTMENT_STATUS_LABEL, PROFILE_STATUS } from '../../utils/constants'
import { errorMessage } from '../../utils/errors'

const STATUS_COLOUR = {
  REQUESTED: '#A4762A',
  CONFIRMED: '#3F7D5B',
  COMPLETED: '#3D6379',
  CANCELLED: '#8B978F',
  REJECTED: '#A8503F',
  NO_SHOW: '#A8503F',
}

/**
 * Platform admin home. Every number is a field of AdminStatistics, which the
 * backend computes live. Nothing here is estimated or rolled up in the browser.
 */
export default function AdminDashboard() {
  useDocumentTitle('Admin dashboard')
  const toast = useToast()
  const stats = useAsync(() => getStatistics(), [])
  const pendingDoctors = useAsync(
    () => listDoctorProfiles({ profile_status: PROFILE_STATUS.PENDING, page: 1, page_size: 1 }),
    [],
  )

  const chart = useMemo(() => {
    const s = stats.data
    if (!s) return []
    return [
      ['REQUESTED', s.requested_appointments],
      ['CONFIRMED', s.confirmed_appointments],
      ['COMPLETED', s.completed_appointments],
      ['CANCELLED', s.cancelled_appointments],
      ['REJECTED', s.rejected_appointments],
      ['NO_SHOW', s.no_show_appointments],
    ].map(([status, count]) => ({ status, label: APPOINTMENT_STATUS_LABEL[status], count }))
  }, [stats.data])

  const maintenance = async () => {
    try {
      const r = await runMaintenance()
      toast.success(
        `Done — ${r.expired_holds} expired hold(s), ${r.reminders_sent} reminder(s) sent, ${r.waitlist_entries_expired} waitlist entry/entries expired.`,
      )
      stats.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  const pendingCount = pendingDoctors.data?.total ?? 0

  return (
    <div className="space-y-8">
      <PageHeader
        title="Platform overview"
        description="Counted live from the database."
        actions={
          <Button variant="outline" onClick={maintenance}>
            <PlayCircle size={16} aria-hidden="true" />
            Run housekeeping
          </Button>
        }
      />

      {pendingCount > 0 && (
        <p className="rounded-xl border border-warn/30 bg-warn-soft px-4 py-3 text-sm text-forest-700">
          {pendingCount} doctor {pendingCount === 1 ? 'profile is' : 'profiles are'} waiting for
          verification.{' '}
          <Link to="/admin/doctors?profile_status=PENDING" className="rounded font-semibold underline focus-ring">
            Review them
          </Link>
        </p>
      )}

      {stats.loading ? (
        <LoadingSkeleton variant="stats" rows={5} />
      ) : stats.error ? (
        <ErrorState error={stats.error} onRetry={stats.reload} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <StatCard icon={Users} value={stats.data.total_patients} label="Patients" to="/admin/users?role=PATIENT" />
            <StatCard icon={Stethoscope} value={stats.data.total_doctors} label="Doctors" to="/admin/doctors" />
            <StatCard icon={Building2} value={stats.data.total_hospitals} label="Hospitals" to="/admin/hospitals" />
            <StatCard icon={LayoutGrid} value={stats.data.total_departments} label="Departments" to="/admin/departments" />
            <StatCard icon={Users} value={stats.data.total_users} label="User accounts" to="/admin/users" />
          </div>

          <Card>
            <CardHeader
              title="Appointments by status"
              description={`${stats.data.total_appointments} appointments in total, across the whole platform.`}
              action={
                <Link
                  to="/admin/appointments"
                  className="rounded text-sm font-medium text-forest transition-colors hover:text-forest-400 focus-ring"
                >
                  View all
                </Link>
              }
            />
            <CardBody>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chart} margin={{ top: 8, right: 8, bottom: 8, left: -18 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E4E7DF" vertical={false} />
                    <XAxis
                      dataKey="label"
                      tick={{ fontSize: 11, fill: '#5C6B61' }}
                      axisLine={{ stroke: '#E4E7DF' }}
                      tickLine={false}
                      interval={0}
                    />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#5C6B61' }} axisLine={false} tickLine={false} />
                    <Tooltip
                      cursor={{ fill: '#EEF3F0' }}
                      contentStyle={{ borderRadius: 12, border: '1px solid #E4E7DF', fontSize: 12 }}
                    />
                    <Bar dataKey="count" name="Appointments" radius={[6, 6, 0, 0]} maxBarSize={56}>
                      {chart.map((e) => (
                        <Cell key={e.status} fill={STATUS_COLOUR[e.status]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardBody>
          </Card>
        </>
      )}

      <Card>
        <CardHeader title="What administrators can and cannot do" />
        <CardBody>
          <ul className="space-y-2 text-sm leading-relaxed text-ink-muted">
            <li>You manage hospitals, departments, accounts and doctor verification.</li>
            <li>
              You can see appointments across the platform for monitoring, but you cannot accept,
              decline, complete or mark one as a no-show. That is the treating doctor&apos;s decision
              alone.
            </li>
            <li>Medical records are closed to administrators entirely.</li>
            <li>
              Closing intake for a hospital or department only stops new requests — it never cancels
              appointments that already exist.
            </li>
          </ul>
        </CardBody>
      </Card>
    </div>
  )
}
