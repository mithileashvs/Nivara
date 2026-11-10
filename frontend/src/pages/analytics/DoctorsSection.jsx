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
import { CalendarCheck, CalendarClock, CalendarDays, Search, Stethoscope } from 'lucide-react'
import { getDoctorAnalytics } from '../../api/analytics'
import { useAsync } from '../../hooks/useAsync'
import { Alert } from '../../components/ui/Alert'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Pagination } from '../../components/ui/Pagination'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { EmptyState, ErrorState, LoadingSkeleton } from '../../components/ui/States'
import { KpiCard } from '../../components/analytics/KpiCard'
import { AnalyticsChartCard } from '../../components/analytics/AnalyticsChartCard'

export default function DoctorsSection({ apiParams, filterValid, onPeriodLoaded, refreshKey }) {
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
      const data = await getDoctorAnalytics({ ...apiParams, page, page_size: 20, search: debouncedSearch || undefined })
      onPeriodLoaded?.(data?.period)
      return data
    },
    [JSON.stringify(apiParams), page, debouncedSearch, refreshKey],
    { enabled: filterValid },
  )

  const summary = res.data?.summary
  const docPage = res.data?.doctors
  const items = docPage?.items || []

  const chartItems = items.slice(0, 10)

  return (
    <div className="space-y-6">
      <Alert tone="info" className="text-xs">
        Workload figures reflect real records from <code className="font-mono">appointments</code>, while slot counts
        reflect real capacity published in <code className="font-mono">appointment_slots</code>. Nivara does not compute
        synthetic clinical performance scores or doctor rankings.
      </Alert>

      {summary && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            icon={Stethoscope}
            label="Doctors in Scope"
            value={summary.total_doctors}
            subtitle={`${summary.active_doctors} active profiles`}
          />
          <KpiCard
            icon={CalendarClock}
            label="Total Appointments"
            value={summary.total_appointments}
            tone="info"
          />
          <KpiCard
            icon={CalendarDays}
            label="Published Slots in Period"
            value={summary.total_slots}
            subtitle={`${summary.available_slots.toLocaleString()} currently available`}
          />
          <KpiCard
            icon={CalendarCheck}
            label="Booked Slots in Period"
            value={summary.booked_slots}
            tone="positive"
          />
        </div>
      )}

      <AnalyticsChartCard
        title="Doctor Workload & Slot Distribution"
        description="Comparing actual appointment outcomes against published and booked slots."
        loading={res.loading}
        error={res.error}
        onRetry={res.reload}
        empty={!chartItems.length || chartItems.every((d) => d.total_appointments === 0 && d.total_slots === 0)}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartItems} margin={{ top: 10, right: 12, bottom: 20, left: -12 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E4E7DF" vertical={false} />
            <XAxis
              dataKey="doctor_name"
              tick={{ fontSize: 11, fill: '#5C6B61' }}
              tickLine={false}
              interval={0}
              angle={chartItems.length > 4 ? -14 : 0}
              textAnchor={chartItems.length > 4 ? 'end' : 'middle'}
              height={chartItems.length > 4 ? 54 : 30}
            />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #E4E7DF', fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="total_appointments" name="Total Appointments" fill="#173C2B" radius={[4, 4, 0, 0]} maxBarSize={28} />
            <Bar dataKey="completed_appointments" name="Completed" fill="#3F7D5B" radius={[4, 4, 0, 0]} maxBarSize={28} />
            <Bar dataKey="total_slots" name="Published Slots" fill="#3D6379" radius={[4, 4, 0, 0]} maxBarSize={28} />
            <Bar dataKey="booked_slots" name="Booked Slots" fill="#A4762A" radius={[4, 4, 0, 0]} maxBarSize={28} />
          </BarChart>
        </ResponsiveContainer>
      </AnalyticsChartCard>

      <Card>
        <CardHeader
          title="Doctor Operational Workload & Slot Inventory"
          description="Live database counts separated between appointments and appointment_slots."
          action={
            <div className="relative w-full sm:w-64">
              <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
              <input
                type="search"
                aria-label="Search doctors"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search doctor or specialty..."
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
              <EmptyState title="No doctors found" description="Try adjusting search or scope filters." />
            </div>
          ) : (
            <>
              <div className="scroll-x overflow-x-auto">
                <table className="w-full min-w-[980px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-line bg-surface-muted/60 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                      <th scope="col" className="px-4 py-3">Doctor</th>
                      <th scope="col" className="px-3 py-3">Status</th>
                      <th scope="col" className="px-3 py-3 text-right">Appts</th>
                      <th scope="col" className="px-3 py-3 text-right">Completed</th>
                      <th scope="col" className="px-3 py-3 text-right">Rejected</th>
                      <th scope="col" className="px-3 py-3 text-right">Cancelled</th>
                      <th scope="col" className="px-3 py-3 text-right">Compl %</th>
                      <th scope="col" className="px-3 py-3 text-right">Slots</th>
                      <th scope="col" className="px-3 py-3 text-right">Booked</th>
                      <th scope="col" className="px-3 py-3 text-right">Available</th>
                      <th scope="col" className="px-4 py-3 text-right">Blocked</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {items.map((doc) => (
                      <tr key={doc.doctor_id} className="transition-colors hover:bg-canvas/50">
                        <td className="px-4 py-3">
                          <p className="font-medium text-forest-700">{doc.doctor_name}</p>
                          <p className="text-xs text-ink-faint">{doc.specialty}</p>
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-1.5">
                            <StatusBadge status={doc.profile_status} kind="generic" />
                            <StatusBadge status={doc.availability_status} kind="generic" />
                          </div>
                        </td>
                        <td className="px-3 py-3 text-right font-semibold tabular-nums text-forest-700">
                          {doc.total_appointments}
                        </td>
                        <td className="px-3 py-3 text-right tabular-nums text-ok">{doc.completed_appointments}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-danger">{doc.rejected_appointments}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-ink-muted">{doc.cancelled_appointments}</td>
                        <td className="px-3 py-3 text-right font-medium tabular-nums text-forest-700">
                          {doc.completion_rate}%
                        </td>
                        <td className="px-3 py-3 text-right font-medium tabular-nums text-info">{doc.total_slots}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-forest-700">{doc.booked_slots}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-ok">{doc.available_slots}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-ink-faint">{doc.blocked_slots}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="border-t border-line px-4 py-3">
                <Pagination
                  page={docPage.page}
                  totalPages={docPage.total_pages}
                  total={docPage.total}
                  pageSize={docPage.page_size}
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
