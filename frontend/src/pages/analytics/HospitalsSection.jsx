import { useEffect, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ArrowLeft, Building2, Eye, Search } from 'lucide-react'
import { getHospitalAnalytics, getHospitalAnalyticsDetail } from '../../api/analytics'
import { useAsync } from '../../hooks/useAsync'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Pagination } from '../../components/ui/Pagination'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { EmptyState, ErrorState, LoadingSkeleton } from '../../components/ui/States'
import { KpiCard } from '../../components/analytics/KpiCard'
import { AnalyticsChartCard } from '../../components/analytics/AnalyticsChartCard'

export default function HospitalsSection({ apiParams, filterValid, onPeriodLoaded, refreshKey }) {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedHospitalId, setSelectedHospitalId] = useState(null)

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

  useEffect(() => {
    if (apiParams.hospital_id && selectedHospitalId && apiParams.hospital_id !== selectedHospitalId) {
      setSelectedHospitalId(null)
    }
  }, [apiParams.hospital_id, selectedHospitalId])

  const listRes = useAsync(
    async () => {
      const res = await getHospitalAnalytics({ ...apiParams, page, page_size: 20, search: debouncedSearch || undefined })
      onPeriodLoaded?.(res?.period)
      return res
    },
    [JSON.stringify(apiParams), page, debouncedSearch, refreshKey],
    { enabled: filterValid && !selectedHospitalId },
  )

  const detailRes = useAsync(
    () =>
      getHospitalAnalyticsDetail(selectedHospitalId, {
        preset: apiParams.preset,
        date_from: apiParams.date_from,
        date_to: apiParams.date_to,
        granularity: apiParams.granularity,
        department_id: apiParams.department_id,
        doctor_id: apiParams.doctor_id,
        status: apiParams.status,
      }),
    [selectedHospitalId, JSON.stringify(apiParams), refreshKey],
    { enabled: filterValid && Boolean(selectedHospitalId) },
  )

  if (selectedHospitalId) {
    const d = detailRes.data
    return (
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button variant="outline" size="sm" onClick={() => setSelectedHospitalId(null)}>
            <ArrowLeft size={15} aria-hidden="true" />
            Back to all hospitals
          </Button>
          {d?.hospital && (
            <div className="flex items-center gap-2 text-sm text-ink-muted">
              <Building2 size={15} className="text-forest-500" aria-hidden="true" />
              <span className="font-semibold text-forest-700">{d.hospital.hospital_name}</span>
              {d.hospital.city && <span>· {d.hospital.city}</span>}
              <StatusBadge status={d.hospital.intake_status} kind="generic" />
            </div>
          )}
        </div>

        {detailRes.loading ? (
          <LoadingSkeleton variant="stats" rows={4} />
        ) : detailRes.error ? (
          <ErrorState error={detailRes.error} onRetry={detailRes.reload} />
        ) : d ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <KpiCard
                icon={Building2}
                label="Total Appointments"
                value={d.total_appointments_comparison.current}
                comparison={d.total_appointments_comparison}
              />
              <KpiCard
                icon={Building2}
                label="Completed Visits"
                value={d.completed_comparison.current}
                comparison={d.completed_comparison}
                tone="positive"
              />
              <KpiCard
                icon={Building2}
                label="Completion Rate"
                value={d.completion_rate.current}
                suffix="%"
                comparison={d.completion_rate}
                isRate
                tone="positive"
                formula={d.formula_definitions?.completion_rate}
              />
              <KpiCard
                icon={Building2}
                label="Active Doctors / Depts"
                value={d.hospital.active_doctor_count}
                subtitle={`Across ${d.hospital.department_count} departments`}
                tone="info"
              />
            </div>

            <AnalyticsChartCard
              title={`${d.hospital.hospital_name} — Appointment Volume Trend`}
              description="Scheduled vs completed appointments across time buckets."
              empty={!d.trends?.length || d.trends.every((t) => t.total === 0)}
            >
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={d.trends} margin={{ top: 10, right: 12, bottom: 0, left: -12 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E4E7DF" vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #E4E7DF', fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Area type="monotone" dataKey="total" name="Total" stroke="#173C2B" fill="#173C2B" fillOpacity={0.14} />
                  <Area type="monotone" dataKey="completed" name="Completed" stroke="#3F7D5B" fill="#3F7D5B" fillOpacity={0.18} />
                </AreaChart>
              </ResponsiveContainer>
            </AnalyticsChartCard>

            <Card>
              <CardHeader
                title="Department Breakdown"
                description={`Performance across all departments inside ${d.hospital.hospital_name}.`}
              />
              <CardBody className="p-0">
                {!d.departments?.length ? (
                  <div className="p-5">
                    <EmptyState title="No departments found" description="No departments match your active filters." />
                  </div>
                ) : (
                  <div className="scroll-x overflow-x-auto">
                    <table className="w-full min-w-[700px] text-left text-sm">
                      <thead>
                        <tr className="border-b border-line bg-surface-muted/60 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                          <th scope="col" className="px-4 py-3">Department</th>
                          <th scope="col" className="px-3 py-3">Intake</th>
                          <th scope="col" className="px-3 py-3 text-right">Doctors</th>
                          <th scope="col" className="px-3 py-3 text-right">Total</th>
                          <th scope="col" className="px-3 py-3 text-right">Completed</th>
                          <th scope="col" className="px-3 py-3 text-right">Cancelled</th>
                          <th scope="col" className="px-3 py-3 text-right">Completion %</th>
                          <th scope="col" className="px-4 py-3 text-right">Rejection %</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-line">
                        {d.departments.map((dept) => (
                          <tr key={dept.department_id} className="hover:bg-canvas/50">
                            <td className="px-4 py-3 font-medium text-forest-700">{dept.department_name}</td>
                            <td className="px-3 py-3">
                              <StatusBadge status={dept.intake_status} kind="generic" />
                            </td>
                            <td className="px-3 py-3 text-right tabular-nums text-ink-muted">{dept.doctor_count}</td>
                            <td className="px-3 py-3 text-right font-semibold tabular-nums text-forest-700">
                              {dept.total_appointments}
                            </td>
                            <td className="px-3 py-3 text-right tabular-nums text-ok">{dept.completed_appointments}</td>
                            <td className="px-3 py-3 text-right tabular-nums text-ink-muted">{dept.cancelled_appointments}</td>
                            <td className="px-3 py-3 text-right font-medium tabular-nums text-forest-700">
                              {dept.completion_rate}%
                            </td>
                            <td className="px-4 py-3 text-right tabular-nums text-danger">{dept.rejection_rate}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardBody>
            </Card>
          </>
        ) : null}
      </div>
    )
  }

  const pageData = listRes.data?.hospitals
  const items = pageData?.items || []

  return (
    <div className="space-y-6">
      <AnalyticsChartCard
        title="Hospital Volume Comparison"
        description="Comparing authorized hospitals by total, completed, and cancelled appointments."
        loading={listRes.loading}
        error={listRes.error}
        onRetry={listRes.reload}
        empty={!items.length || items.every((h) => h.total_appointments === 0)}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={items.slice(0, 10)} margin={{ top: 10, right: 12, bottom: 16, left: -12 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E4E7DF" vertical={false} />
            <XAxis
              dataKey="hospital_name"
              tick={{ fontSize: 11, fill: '#5C6B61' }}
              tickLine={false}
              interval={0}
              angle={items.length > 4 ? -12 : 0}
              textAnchor={items.length > 4 ? 'end' : 'middle'}
              height={items.length > 4 ? 52 : 30}
            />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #E4E7DF', fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="total_appointments" name="Total" fill="#173C2B" radius={[4, 4, 0, 0]} maxBarSize={36} />
            <Bar dataKey="completed_appointments" name="Completed" fill="#3F7D5B" radius={[4, 4, 0, 0]} maxBarSize={36} />
            <Bar dataKey="cancelled_appointments" name="Cancelled" fill="#8B978F" radius={[4, 4, 0, 0]} maxBarSize={36} />
          </BarChart>
        </ResponsiveContainer>
      </AnalyticsChartCard>

      <Card>
        <CardHeader
          title="Hospital Operational Breakdown"
          description="Click any hospital to inspect detailed trends and department-level performance."
          action={
            <div className="relative w-full sm:w-64">
              <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
              <input
                type="search"
                aria-label="Search hospitals"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search hospitals..."
                className="h-9 w-full rounded-xl border border-line bg-canvas pl-9 pr-3 text-sm text-ink placeholder:text-ink-faint focus-ring"
              />
            </div>
          }
        />
        <CardBody className="p-0">
          {listRes.loading ? (
            <div className="p-5">
              <LoadingSkeleton variant="table" rows={5} />
            </div>
          ) : listRes.error ? (
            <div className="p-5">
              <ErrorState error={listRes.error} onRetry={listRes.reload} />
            </div>
          ) : !items.length ? (
            <div className="p-5">
              <EmptyState title="No hospitals found" description="No hospitals match your search or scope." />
            </div>
          ) : (
            <>
              <div className="scroll-x overflow-x-auto">
                <table className="w-full min-w-[880px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-line bg-surface-muted/60 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                      <th scope="col" className="px-4 py-3">Hospital</th>
                      <th scope="col" className="px-3 py-3">Intake</th>
                      <th scope="col" className="px-3 py-3 text-right">Depts</th>
                      <th scope="col" className="px-3 py-3 text-right">Doctors</th>
                      <th scope="col" className="px-3 py-3 text-right">Total</th>
                      <th scope="col" className="px-3 py-3 text-right">Completed</th>
                      <th scope="col" className="px-3 py-3 text-right">Cancelled</th>
                      <th scope="col" className="px-3 py-3 text-right">Declined</th>
                      <th scope="col" className="px-3 py-3 text-right">Completion %</th>
                      <th scope="col" className="px-4 py-3 text-right">Drilldown</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {items.map((h) => (
                      <tr key={h.hospital_id} className="transition-colors hover:bg-canvas/50">
                        <td className="px-4 py-3">
                          <p className="font-medium text-forest-700">{h.hospital_name}</p>
                          {h.city && <p className="text-xs text-ink-faint">{h.city}</p>}
                        </td>
                        <td className="px-3 py-3">
                          <StatusBadge status={h.intake_status} kind="generic" />
                        </td>
                        <td className="px-3 py-3 text-right tabular-nums text-ink-muted">{h.department_count}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-ink-muted">{h.active_doctor_count}</td>
                        <td className="px-3 py-3 text-right font-semibold tabular-nums text-forest-700">
                          {h.total_appointments.toLocaleString()}
                        </td>
                        <td className="px-3 py-3 text-right tabular-nums text-ok">{h.completed_appointments}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-ink-muted">{h.cancelled_appointments}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-danger">{h.rejected_appointments}</td>
                        <td className="px-3 py-3 text-right font-medium tabular-nums text-forest-700">
                          {h.completion_rate}%
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setSelectedHospitalId(h.hospital_id)}
                          >
                            <Eye size={14} aria-hidden="true" />
                            Inspect
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="border-t border-line px-4 py-3">
                <Pagination
                  page={pageData.page}
                  totalPages={pageData.total_pages}
                  total={pageData.total}
                  pageSize={pageData.page_size}
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
