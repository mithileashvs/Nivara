import { useMemo } from 'react'
import { BarChart, Bar, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CalendarCheck, CalendarClock, CheckCircle2, Users } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { StatCard } from '../../components/StatCard'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { ErrorState, LoadingSkeleton, EmptyState } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { getMyStatistics } from '../../api/doctors'
import { listAppointments } from '../../api/appointments'
import { APPOINTMENT_STATUS_LABEL, MAX_PAGE_SIZE } from '../../utils/constants'

const STATUS_COLOUR = {
  REQUESTED: '#A4762A',
  CONFIRMED: '#3F7D5B',
  COMPLETED: '#3D6379',
  CANCELLED: '#8B978F',
  REJECTED: '#A8503F',
  NO_SHOW: '#A8503F',
}

/**
 * The headline figures are the backend's own DoctorStatistics. The breakdown
 * chart is counted from the doctor's real appointment records — it is not an
 * estimate, and the caption says exactly what it covers.
 */
export default function DoctorStatistics() {
  useDocumentTitle('Statistics')
  const stats = useAsync(() => getMyStatistics(), [])
  const appointments = useAsync(() => listAppointments({ page: 1, page_size: MAX_PAGE_SIZE }), [])

  const byStatus = useMemo(() => {
    const items = appointments.data?.items ?? []
    const counts = {}
    for (const a of items) counts[a.status] = (counts[a.status] || 0) + 1
    return Object.entries(counts)
      .map(([status, count]) => ({
        status,
        label: APPOINTMENT_STATUS_LABEL[status] || status,
        count,
      }))
      .sort((a, b) => b.count - a.count)
  }, [appointments.data])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Statistics"
        description="Counted live from your appointment records."
      />

      {stats.loading ? (
        <LoadingSkeleton variant="stats" rows={5} />
      ) : stats.error ? (
        <ErrorState error={stats.error} onRetry={stats.reload} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <StatCard icon={CalendarClock} value={stats.data.todays_appointments} label="Today" />
          <StatCard
            icon={CalendarCheck}
            value={stats.data.pending_requests}
            label="Pending requests"
            tone={stats.data.pending_requests > 0 ? 'warn' : 'default'}
          />
          <StatCard icon={CheckCircle2} value={stats.data.confirmed_appointments} label="Confirmed" />
          <StatCard icon={CheckCircle2} value={stats.data.completed_appointments} label="Completed" tone="positive" />
          <StatCard icon={Users} value={stats.data.total_patients} label="Distinct patients" />
        </div>
      )}

      <Card>
        <CardHeader
          title="Appointments by status"
          description={`Your most recent ${MAX_PAGE_SIZE} appointments.`}
        />
        <CardBody>
          {appointments.loading ? (
            <div className="skeleton h-64 w-full" />
          ) : appointments.error ? (
            <ErrorState error={appointments.error} onRetry={appointments.reload} compact />
          ) : byStatus.length === 0 ? (
            <EmptyState title="No appointments yet" description="This chart fills in as you see patients." />
          ) : (
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byStatus} margin={{ top: 8, right: 8, bottom: 8, left: -18 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E4E7DF" vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 11, fill: '#5C6B61' }}
                    axisLine={{ stroke: '#E4E7DF' }}
                    tickLine={false}
                    interval={0}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fontSize: 11, fill: '#5C6B61' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    cursor={{ fill: '#EEF3F0' }}
                    contentStyle={{
                      borderRadius: 12,
                      border: '1px solid #E4E7DF',
                      fontSize: 12,
                      boxShadow: '0 8px 24px -16px rgba(23,60,43,0.3)',
                    }}
                  />
                  <Bar dataKey="count" name="Appointments" radius={[6, 6, 0, 0]} maxBarSize={56}>
                    {byStatus.map((entry) => (
                      <Cell key={entry.status} fill={STATUS_COLOUR[entry.status] || '#4C7A64'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
