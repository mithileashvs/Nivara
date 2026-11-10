import { useMemo } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  Activity,
  Award,
  Building2,
  CalendarCheck,
  CalendarClock,
  CalendarX2,
  CheckCircle2,
  Clock,
  LayoutGrid,
  Stethoscope,
  UserPlus,
  Users,
  XCircle,
} from 'lucide-react'
import { getAnalyticsOverview } from '../../api/analytics'
import { useAsync } from '../../hooks/useAsync'
import { ANALYTICS_STATUS_COLORS } from '../../utils/constants'
import { KpiCard } from '../../components/analytics/KpiCard'
import { AnalyticsChartCard } from '../../components/analytics/AnalyticsChartCard'

export default function OverviewSection({ apiParams, filterValid, onPeriodLoaded, refreshKey }) {
  const { data, loading, error, reload } = useAsync(
    async () => {
      const res = await getAnalyticsOverview(apiParams)
      onPeriodLoaded?.(res?.period)
      return res
    },
    [JSON.stringify(apiParams), refreshKey],
    { enabled: filterValid },
  )

  const statusChartData = useMemo(
    () => (data?.status_distribution || []).filter((s) => s.count > 0),
    [data],
  )

  const trends = data?.appointment_trends || []
  const regTrends = data?.patient_registration_trends || []
  const formulas = data?.formula_definitions || {}

  return (
    <div className="space-y-6">
      {/* Scope context banner & Operational Highlights */}
      {data && (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="card flex items-start gap-3 p-4">
            <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-forest-50 text-forest-600">
              <Award size={18} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Peak Volume Period</p>
              {data.highlights?.highest_volume_period ? (
                <>
                  <p className="mt-0.5 truncate text-base font-semibold text-forest-700">
                    {data.highlights.highest_volume_period.label}
                  </p>
                  <p className="text-xs text-ink-muted">
                    {data.highlights.highest_volume_period.count.toLocaleString()} appointments (
                    {data.highlights.highest_volume_period.bucket_date})
                  </p>
                </>
              ) : (
                <p className="mt-0.5 text-sm text-ink-muted">No appointments recorded in period</p>
              )}
            </div>
          </div>

          <div className="card flex items-start gap-3 p-4">
            <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-ok-soft text-ok">
              <LayoutGrid size={18} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Most Active Department</p>
              {data.highlights?.most_active_department ? (
                <>
                  <p className="mt-0.5 truncate text-base font-semibold text-forest-700">
                    {data.highlights.most_active_department.department_name}
                  </p>
                  <p className="truncate text-xs text-ink-muted">
                    {data.highlights.most_active_department.hospital_name} ·{' '}
                    {data.highlights.most_active_department.count.toLocaleString()} appointments
                  </p>
                </>
              ) : (
                <p className="mt-0.5 text-sm text-ink-muted">No department activity recorded</p>
              )}
            </div>
          </div>

          <div className="card flex items-start gap-3 p-4">
            <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-info-soft text-info">
              <Building2 size={18} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Most Active Hospital</p>
              {data.highlights?.most_active_hospital ? (
                <>
                  <p className="mt-0.5 truncate text-base font-semibold text-forest-700">
                    {data.highlights.most_active_hospital.hospital_name}
                  </p>
                  <p className="text-xs text-ink-muted">
                    {data.highlights.most_active_hospital.count.toLocaleString()} appointments
                  </p>
                </>
              ) : (
                <p className="mt-0.5 text-sm text-ink-muted">No hospital activity recorded</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Primary KPI Grid */}
      {loading && !data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="card p-5">
              <div className="skeleton h-4 w-24" />
              <div className="skeleton mt-4 h-8 w-20" />
              <div className="skeleton mt-3 h-3 w-32" />
            </div>
          ))}
        </div>
      ) : data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              icon={CalendarClock}
              label="Total Appointments"
              value={data.total_appointments.current}
              comparison={data.total_appointments}
            />
            <KpiCard
              icon={CheckCircle2}
              label="Completed Appointments"
              value={data.completed_appointments.current}
              comparison={data.completed_appointments}
              tone="positive"
            />
            <KpiCard
              icon={CalendarCheck}
              label="Confirmed Appointments"
              value={data.confirmed_appointments.current}
              comparison={data.confirmed_appointments}
              tone="positive"
            />
            <KpiCard
              icon={Clock}
              label="Awaiting Doctor"
              value={data.requested_appointments.current}
              comparison={data.requested_appointments}
              tone="warn"
            />
            <KpiCard
              icon={XCircle}
              label="Declined Appointments"
              value={data.rejected_appointments.current}
              comparison={data.rejected_appointments}
              invertTrend
              tone="danger"
            />
            <KpiCard
              icon={CalendarX2}
              label="Cancelled Appointments"
              value={data.cancelled_appointments.current}
              comparison={data.cancelled_appointments}
              invertTrend
            />
            <KpiCard
              icon={Users}
              label="Total Registered Patients"
              value={data.total_registered_patients}
              subtitle={
                data.new_patients_in_period.current > 0
                  ? `+${data.new_patients_in_period.current.toLocaleString()} registered in period`
                  : 'Scoped aggregate'
              }
              tone="info"
            />
            <KpiCard
              icon={Stethoscope}
              label="Active Doctors"
              value={data.active_doctors}
              subtitle={`Across ${data.accessible_hospitals} accessible ${data.accessible_hospitals === 1 ? 'hospital' : 'hospitals'}`}
            />
          </div>

          {/* Operational Rates & No-Show Row */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <KpiCard
              icon={Activity}
              label="Completion Rate"
              value={data.completion_rate.current}
              suffix="%"
              comparison={data.completion_rate}
              isRate
              tone="positive"
              formula={formulas.completion_rate}
              subtitle={`${data.completion_rate.numerator} / ${data.completion_rate.denominator}`}
            />
            <KpiCard
              icon={XCircle}
              label="Rejection Rate"
              value={data.rejection_rate.current}
              suffix="%"
              comparison={data.rejection_rate}
              isRate
              invertTrend
              tone="danger"
              formula={formulas.rejection_rate}
              subtitle={`${data.rejection_rate.numerator} / ${data.rejection_rate.denominator}`}
            />
            <KpiCard
              icon={CalendarX2}
              label="Cancellation Rate"
              value={data.cancellation_rate.current}
              suffix="%"
              comparison={data.cancellation_rate}
              isRate
              invertTrend
              tone="warn"
              formula={formulas.cancellation_rate}
              subtitle={`${data.cancellation_rate.numerator} / ${data.cancellation_rate.denominator}`}
            />
            <KpiCard
              icon={Clock}
              label="No-Show Rate"
              value={data.no_show_rate.current}
              suffix="%"
              comparison={data.no_show_rate}
              isRate
              invertTrend
              formula={formulas.no_show_rate}
              subtitle={`${data.no_show_appointments.current} no-show(s)`}
            />
            <KpiCard
              icon={UserPlus}
              label="New Patients (Period)"
              value={data.new_patients_in_period.current}
              comparison={data.new_patients_in_period}
              tone="info"
            />
          </div>
        </>
      ) : null}

      {/* 4 Core Visualizations */}
      <div className="grid gap-6 xl:grid-cols-2">
        <AnalyticsChartCard
          title="Appointment Volume Over Time"
          description="Total scheduled volume compared with completed visits."
          loading={loading}
          error={error}
          onRetry={reload}
          empty={!trends.length || trends.every((t) => t.total === 0)}
        >
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trends} margin={{ top: 10, right: 12, bottom: 0, left: -12 }}>
              <defs>
                <linearGradient id="nivTotalGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#173C2B" stopOpacity={0.22} />
                  <stop offset="95%" stopColor="#173C2B" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="nivCompGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3F7D5B" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#3F7D5B" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#E4E7DF" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #E4E7DF', fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area
                type="monotone"
                dataKey="total"
                name="Total Appointments"
                stroke="#173C2B"
                strokeWidth={2}
                fill="url(#nivTotalGrad)"
              />
              <Area
                type="monotone"
                dataKey="completed"
                name="Completed"
                stroke="#3F7D5B"
                strokeWidth={2}
                fill="url(#nivCompGrad)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </AnalyticsChartCard>

        <AnalyticsChartCard
          title="Appointment Status Distribution"
          description="Breakdown across lifecycle states in the selected window."
          loading={loading}
          error={error}
          onRetry={reload}
          empty={statusChartData.length === 0}
        >
          <div className="grid h-full items-center gap-4 sm:grid-cols-2">
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusChartData}
                    dataKey="count"
                    nameKey="label"
                    innerRadius={52}
                    outerRadius={84}
                    paddingAngle={2}
                  >
                    {statusChartData.map((entry) => (
                      <Cell key={entry.status} fill={ANALYTICS_STATUS_COLORS[entry.status] || '#4C7A64'} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #E4E7DF', fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <ul className="space-y-2 text-xs">
              {(data?.status_distribution || []).map((s) => (
                <li key={s.status} className="flex items-center justify-between gap-2 rounded-lg px-2 py-1 odd:bg-canvas/70">
                  <span className="flex items-center gap-2 font-medium text-ink">
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: ANALYTICS_STATUS_COLORS[s.status] || '#4C7A64' }}
                    />
                    {s.label}
                  </span>
                  <span className="tabular-nums text-ink-muted">
                    <strong className="text-forest-700">{s.count.toLocaleString()}</strong> ({s.percentage}%)
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </AnalyticsChartCard>

        <AnalyticsChartCard
          title="Completed vs Cancelled vs Declined"
          description="Outcome comparison across time buckets."
          loading={loading}
          error={error}
          onRetry={reload}
          empty={!trends.length || trends.every((t) => t.completed + t.cancelled + t.rejected + t.no_show === 0)}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={trends} margin={{ top: 10, right: 12, bottom: 0, left: -12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E4E7DF" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #E4E7DF', fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="completed" name="Completed" fill={ANALYTICS_STATUS_COLORS.COMPLETED} radius={[4, 4, 0, 0]} />
              <Bar dataKey="cancelled" name="Cancelled" fill={ANALYTICS_STATUS_COLORS.CANCELLED} radius={[4, 4, 0, 0]} />
              <Bar dataKey="rejected" name="Declined" fill={ANALYTICS_STATUS_COLORS.REJECTED} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </AnalyticsChartCard>

        <AnalyticsChartCard
          title="Patient Registration Trends"
          description="New patient profiles created over the active date range."
          loading={loading}
          error={error}
          onRetry={reload}
          empty={!regTrends.length || regTrends.every((p) => p.new_patients === 0)}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={regTrends} margin={{ top: 10, right: 12, bottom: 0, left: -12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E4E7DF" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #E4E7DF', fontSize: 12 }} />
              <Bar dataKey="new_patients" name="New Patients" fill="#3D6379" radius={[5, 5, 0, 0]} maxBarSize={42} />
            </BarChart>
          </ResponsiveContainer>
        </AnalyticsChartCard>
      </div>
    </div>
  )
}
