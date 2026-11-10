import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Award, CalendarClock, CheckCircle2, LayoutGrid, Search } from 'lucide-react'
import { getDepartmentAnalytics } from '../../api/analytics'
import { useAsync } from '../../hooks/useAsync'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Pagination } from '../../components/ui/Pagination'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { EmptyState, ErrorState, LoadingSkeleton } from '../../components/ui/States'
import { KpiCard } from '../../components/analytics/KpiCard'
import { AnalyticsChartCard } from '../../components/analytics/AnalyticsChartCard'

export default function DepartmentsSection({ apiParams, filterValid, onPeriodLoaded, refreshKey }) {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedSearch(search)
      setPage(1)
    }, 250)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    setPage(1)
  }, [JSON.stringify(apiParams)])

  const res = useAsync(
    async () => {
      const data = await getDepartmentAnalytics({ ...apiParams, page, page_size: 20, search: debouncedSearch || undefined })
      onPeriodLoaded?.(data?.period)
      return data
    },
    [JSON.stringify(apiParams), page, debouncedSearch, refreshKey],
    { enabled: filterValid },
  )

  const summary = res.data?.summary
  const deptPage = res.data?.departments
  const items = deptPage?.items || []

  const chartItems = items.slice(0, 10).map((d) => ({
    ...d,
    label: `${d.department_name} (${d.hospital_name})`,
  }))

  return (
    <div className="space-y-6">
      {summary && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            icon={LayoutGrid}
            label="Departments in Scope"
            value={summary.total_departments}
            subtitle={`${summary.active_departments} currently active`}
          />
          <KpiCard
            icon={CalendarClock}
            label="Department Appointments"
            value={summary.total_appointments}
            tone="info"
          />
          <KpiCard
            icon={CheckCircle2}
            label="Completed Visits"
            value={summary.completed_appointments}
            tone="positive"
          />
          <KpiCard
            icon={Award}
            label="Top Department"
            value={summary.most_active_department?.department_name || '—'}
            subtitle={
              summary.most_active_department
                ? `${summary.most_active_department.hospital_name} · ${summary.most_active_department.total_appointments} appts`
                : 'No activity'
            }
          />
        </div>
      )}

      <AnalyticsChartCard
        title="Department Volume Comparison"
        description="Comparing authorized departments across total, completed, cancelled, and declined outcomes."
        loading={res.loading}
        error={res.error}
        onRetry={res.reload}
        empty={!chartItems.length || chartItems.every((d) => d.total_appointments === 0)}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartItems} margin={{ top: 10, right: 12, bottom: 20, left: -12 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E4E7DF" vertical={false} />
            <XAxis
              dataKey="department_name"
              tick={{ fontSize: 11, fill: '#5C6B61' }}
              tickLine={false}
              interval={0}
              angle={chartItems.length > 5 ? -15 : 0}
              textAnchor={chartItems.length > 5 ? 'end' : 'middle'}
              height={chartItems.length > 5 ? 54 : 30}
            />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #E4E7DF', fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="total_appointments" name="Total" fill="#173C2B" radius={[4, 4, 0, 0]} maxBarSize={32} />
            <Bar dataKey="completed_appointments" name="Completed" fill="#3F7D5B" radius={[4, 4, 0, 0]} maxBarSize={32} />
            <Bar dataKey="rejected_appointments" name="Declined" fill="#A8503F" radius={[4, 4, 0, 0]} maxBarSize={32} />
          </BarChart>
        </ResponsiveContainer>
      </AnalyticsChartCard>

      <Card>
        <CardHeader
          title="Department Operational Table"
          description="Appointment metrics, intake state, active doctors, and outcome rates per department."
          action={
            <div className="relative w-full sm:w-64">
              <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
              <input
                type="search"
                aria-label="Search departments"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search departments..."
                className="h-9 w-full rounded-xl border border-line bg-canvas pl-9 pr-3 text-sm text-ink placeholder:text-ink-faint focus-ring"
              />
            </div>
          }
        />
        <CardBody className="p-0">
          {res.loading ? (
            <div className="p-5">
              <LoadingSkeleton variant="table" rows={6} />
            </div>
          ) : res.error ? (
            <div className="p-5">
              <ErrorState error={res.error} onRetry={res.reload} />
            </div>
          ) : !items.length ? (
            <div className="p-5">
              <EmptyState title="No departments found" description="Try adjusting search or facility filters." />
            </div>
          ) : (
            <>
              <div className="scroll-x overflow-x-auto">
                <table className="w-full min-w-[900px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-line bg-surface-muted/60 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                      <th scope="col" className="px-4 py-3">Department</th>
                      <th scope="col" className="px-3 py-3">Hospital</th>
                      <th scope="col" className="px-3 py-3">Status</th>
                      <th scope="col" className="px-3 py-3 text-right">Doctors</th>
                      <th scope="col" className="px-3 py-3 text-right">Total</th>
                      <th scope="col" className="px-3 py-3 text-right">Completed</th>
                      <th scope="col" className="px-3 py-3 text-right">Cancelled</th>
                      <th scope="col" className="px-3 py-3 text-right">Declined</th>
                      <th scope="col" className="px-3 py-3 text-right">Completion %</th>
                      <th scope="col" className="px-4 py-3 text-right">Cancel %</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {items.map((d) => (
                      <tr key={d.department_id} className="transition-colors hover:bg-canvas/50">
                        <td className="px-4 py-3 font-medium text-forest-700">{d.department_name}</td>
                        <td className="px-3 py-3 text-ink-muted">{d.hospital_name}</td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-1.5">
                            <StatusBadge status={d.status} kind="generic" />
                            <StatusBadge status={d.intake_status} kind="generic" />
                          </div>
                        </td>
                        <td className="px-3 py-3 text-right tabular-nums text-ink-muted">{d.doctor_count}</td>
                        <td className="px-3 py-3 text-right font-semibold tabular-nums text-forest-700">
                          {d.total_appointments.toLocaleString()}
                        </td>
                        <td className="px-3 py-3 text-right tabular-nums text-ok">{d.completed_appointments}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-ink-muted">{d.cancelled_appointments}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-danger">{d.rejected_appointments}</td>
                        <td className="px-3 py-3 text-right font-medium tabular-nums text-forest-700">
                          {d.completion_rate}%
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{d.cancellation_rate}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="border-t border-line px-4 py-3">
                <Pagination
                  page={deptPage.page}
                  totalPages={deptPage.total_pages}
                  total={deptPage.total}
                  pageSize={deptPage.page_size}
                  onChange={setPage}
                />
              </div>
            </>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
