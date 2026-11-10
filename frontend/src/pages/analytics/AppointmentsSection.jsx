import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getAppointmentStatusAnalytics, getAppointmentTrends } from '../../api/analytics'
import { useAsync } from '../../hooks/useAsync'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { Pagination } from '../../components/ui/Pagination'
import { EmptyState, ErrorState, LoadingSkeleton } from '../../components/ui/States'
import { AnalyticsChartCard } from '../../components/analytics/AnalyticsChartCard'
import { ANALYTICS_STATUS_COLORS } from '../../utils/constants'

const CONSULT_COLORS = ['#173C2B', '#3D6379', '#6F8569']

export default function AppointmentsSection({ apiParams, filterValid, onPeriodLoaded, refreshKey }) {
  const [page, setPage] = useState(1)

  useEffect(() => {
    setPage(1)
  }, [JSON.stringify(apiParams)])

  const trendsRes = useAsync(
    async () => {
      const res = await getAppointmentTrends({ ...apiParams, page, page_size: 15 })
      onPeriodLoaded?.(res?.period)
      return res
    },
    [JSON.stringify(apiParams), page, refreshKey],
    { enabled: filterValid },
  )

  const statusRes = useAsync(
    () => getAppointmentStatusAnalytics(apiParams),
    [JSON.stringify(apiParams), refreshKey],
    { enabled: filterValid },
  )

  const trends = trendsRes.data?.trends || []
  const summaryTable = trendsRes.data?.summary_table
  const statuses = statusRes.data?.status_distribution || []
  const consultationTypes = statusRes.data?.consultation_types || []

  return (
    <div className="space-y-6">
      {/* Status breakdown + Consultation Types */}
      <div className="grid gap-6 xl:grid-cols-2">
        <AnalyticsChartCard
          title="Completion, Cancellation & Rejection Rate Trends"
          description="Percentage outcome rates calculated per bucket using backend operational formulas."
          loading={trendsRes.loading}
          error={trendsRes.error}
          onRetry={trendsRes.reload}
          empty={!trends.length || trends.every((t) => t.total === 0)}
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trends} margin={{ top: 10, right: 12, bottom: 0, left: -12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E4E7DF" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} />
              <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} axisLine={false} />
              <Tooltip
                formatter={(val) => `${val}%`}
                contentStyle={{ borderRadius: 12, border: '1px solid #E4E7DF', fontSize: 12 }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line
                type="monotone"
                dataKey="completion_rate"
                name="Completion Rate"
                stroke="#3F7D5B"
                strokeWidth={2.2}
                dot={{ r: 2.5 }}
              />
              <Line
                type="monotone"
                dataKey="cancellation_rate"
                name="Cancellation Rate"
                stroke="#A4762A"
                strokeWidth={2}
                dot={{ r: 2 }}
              />
              <Line
                type="monotone"
                dataKey="rejection_rate"
                name="Rejection Rate"
                stroke="#A8503F"
                strokeWidth={2}
                dot={{ r: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </AnalyticsChartCard>

        <AnalyticsChartCard
          title="Consultation Type Breakdown"
          description="Appointment mix by visit type in the selected scope and period."
          loading={statusRes.loading}
          error={statusRes.error}
          onRetry={statusRes.reload}
          empty={consultationTypes.every((c) => c.count === 0)}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={consultationTypes} layout="vertical" margin={{ top: 10, right: 24, bottom: 0, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E4E7DF" horizontal={false} />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: '#5C6B61' }} />
              <YAxis type="category" dataKey="label" width={110} tick={{ fontSize: 12, fill: '#1B241F' }} tickLine={false} />
              <Tooltip
                formatter={(val, _n, props) => [`${val} (${props.payload.percentage}%)`, 'Appointments']}
                contentStyle={{ borderRadius: 12, border: '1px solid #E4E7DF', fontSize: 12 }}
              />
              <Bar dataKey="count" name="Appointments" radius={[0, 6, 6, 0]} maxBarSize={32}>
                {consultationTypes.map((entry, idx) => (
                  <Cell key={entry.consultation_type} fill={CONSULT_COLORS[idx % CONSULT_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </AnalyticsChartCard>
      </div>

      {/* Status comparison pills */}
      {statuses.length > 0 && (
        <Card>
          <CardHeader
            title="Detailed Status Comparison"
            description="Current period counts vs previous equivalent window."
          />
          <CardBody>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
              {statuses.map((s) => {
                const diff = s.count - s.previous_count
                return (
                  <div key={s.status} className="rounded-xl border border-line bg-canvas/60 p-3.5">
                    <div className="flex items-center gap-2">
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: ANALYTICS_STATUS_COLORS[s.status] || '#4C7A64' }}
                      />
                      <span className="truncate text-xs font-medium text-ink-muted">{s.label}</span>
                    </div>
                    <p className="mt-2 text-2xl font-bold tabular-nums text-forest-700">{s.count.toLocaleString()}</p>
                    <p className="mt-1 text-xs tabular-nums text-ink-faint">
                      {s.percentage}% · {diff >= 0 ? `+${diff}` : diff} vs prev
                    </p>
                  </div>
                )
              })}
            </div>
          </CardBody>
        </Card>
      )}

      {/* Paginated Appointment Summary Table */}
      <Card>
        <CardHeader
          title="Chronological Appointment Summary"
          description="Aggregated directly from the appointments table (most recent periods first)."
        />
        <CardBody className="p-0">
          {trendsRes.loading ? (
            <div className="p-5">
              <LoadingSkeleton variant="table" rows={6} />
            </div>
          ) : trendsRes.error ? (
            <div className="p-5">
              <ErrorState error={trendsRes.error} onRetry={trendsRes.reload} />
            </div>
          ) : !summaryTable?.items?.length ? (
            <div className="p-5">
              <EmptyState title="No periods to summarize" description="Adjust your date range filters." />
            </div>
          ) : (
            <>
              <div className="scroll-x overflow-x-auto">
                <table className="w-full min-w-[780px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-line bg-surface-muted/60 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                      <th scope="col" className="px-4 py-3">Period</th>
                      <th scope="col" className="px-3 py-3 text-right">Total</th>
                      <th scope="col" className="px-3 py-3 text-right">Requested</th>
                      <th scope="col" className="px-3 py-3 text-right">Confirmed</th>
                      <th scope="col" className="px-3 py-3 text-right">Completed</th>
                      <th scope="col" className="px-3 py-3 text-right">Declined</th>
                      <th scope="col" className="px-3 py-3 text-right">Cancelled</th>
                      <th scope="col" className="px-3 py-3 text-right">No Show</th>
                      <th scope="col" className="px-3 py-3 text-right">Completion %</th>
                      <th scope="col" className="px-4 py-3 text-right">Cancel %</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {summaryTable.items.map((row) => (
                      <tr key={row.bucket_date} className="transition-colors hover:bg-canvas/50">
                        <td className="px-4 py-3 font-medium text-forest-700">
                          {row.label}
                          <span className="ml-1.5 text-xs font-normal text-ink-faint">{row.bucket_date}</span>
                        </td>
                        <td className="px-3 py-3 text-right font-semibold tabular-nums text-forest-700">
                          {row.total.toLocaleString()}
                        </td>
                        <td className="px-3 py-3 text-right tabular-nums text-ink-muted">{row.requested}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-ok">{row.confirmed}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-info">{row.completed}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-danger">{row.rejected}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-ink-muted">{row.cancelled}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-warn">{row.no_show}</td>
                        <td className="px-3 py-3 text-right font-medium tabular-nums text-forest-700">
                          {row.completion_rate}%
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-ink-muted">{row.cancellation_rate}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="border-t border-line px-4 py-3">
                <Pagination
                  page={summaryTable.page}
                  totalPages={summaryTable.total_pages}
                  total={summaryTable.total}
                  pageSize={summaryTable.page_size}
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
