import { useMemo } from 'react'
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ShieldCheck, UserCheck, UserPlus, Users, Repeat } from 'lucide-react'
import { getPatientAnalytics } from '../../api/analytics'
import { useAsync } from '../../hooks/useAsync'
import { Alert } from '../../components/ui/Alert'
import { KpiCard } from '../../components/analytics/KpiCard'
import { AnalyticsChartCard } from '../../components/analytics/AnalyticsChartCard'

export default function PatientsSection({ apiParams, filterValid, onPeriodLoaded, refreshKey }) {
  const { data, loading, error, reload } = useAsync(
    async () => {
      const res = await getPatientAnalytics(apiParams)
      onPeriodLoaded?.(res?.period)
      return res
    },
    [JSON.stringify(apiParams), refreshKey],
    { enabled: filterValid },
  )

  const retentionMix = useMemo(() => {
    if (!data) return []
    const items = [
      { name: 'Returning patients', value: data.returning_patients, color: '#3F7D5B' },
      { name: 'Single-visit active patients', value: data.single_visit_active_patients, color: '#3D6379' },
    ]
    return items.filter((i) => i.value > 0)
  }, [data])

  const trends = data?.trends || []
  const formulas = data?.formula_definitions || {}

  return (
    <div className="space-y-6">
      <Alert tone="info" icon={ShieldCheck} title="Privacy-safe aggregate analytics">
        {data?.scope_note ||
          'All metrics on this screen are database-computed aggregate counts only. Individual patient names, contact details, and clinical information are never exposed.'}
      </Alert>

      {data && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <KpiCard
            icon={Users}
            label="Total Registered Patients"
            value={data.total_registered_patients}
            subtitle="All-time in scope"
            tone="info"
          />
          <KpiCard
            icon={UserPlus}
            label="New Registrations"
            value={data.new_registrations.current}
            comparison={data.new_registrations}
            tone="positive"
          />
          <KpiCard
            icon={UserCheck}
            label="Active Patients"
            value={data.active_patients.current}
            comparison={data.active_patients}
            formula={formulas.active_patients}
          />
          <KpiCard
            icon={Repeat}
            label="Returning Patients"
            value={data.returning_patients}
            subtitle={`${data.single_visit_active_patients.toLocaleString()} single-visit active`}
            formula={formulas.returning_patients}
            tone="positive"
          />
          <KpiCard
            icon={Repeat}
            label="Returning Share"
            value={data.returning_rate}
            suffix="%"
            subtitle="Share of active patients in period"
          />
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-3">
        <AnalyticsChartCard
          className="xl:col-span-2"
          title="Registration & Patient Activity Trends"
          description="Comparing newly registered patients with distinct active patients and total appointments."
          loading={loading}
          error={error}
          onRetry={reload}
          empty={!trends.length || trends.every((t) => t.new_registrations === 0 && t.active_patients === 0)}
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={trends} margin={{ top: 10, right: 12, bottom: 0, left: -12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E4E7DF" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#5C6B61' }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #E4E7DF', fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="new_registrations" name="New Registrations" fill="#3D6379" radius={[4, 4, 0, 0]} maxBarSize={30} />
              <Bar dataKey="active_patients" name="Active Patients" fill="#3F7D5B" radius={[4, 4, 0, 0]} maxBarSize={30} />
              <Line
                type="monotone"
                dataKey="appointments"
                name="Appointments"
                stroke="#173C2B"
                strokeWidth={2.2}
                dot={{ r: 2.5 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </AnalyticsChartCard>

        <AnalyticsChartCard
          title="Returning vs Single-Visit Mix"
          description="Active patients with >= 2 non-cancelled/non-rejected dates vs single visit."
          loading={loading}
          error={error}
          onRetry={reload}
          empty={retentionMix.length === 0}
        >
          <div className="flex h-full flex-col justify-between">
            <div className="h-52 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={retentionMix}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={48}
                    outerRadius={78}
                    paddingAngle={2}
                  >
                    {retentionMix.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #E4E7DF', fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <ul className="space-y-1.5 text-xs">
              {retentionMix.map((item) => (
                <li key={item.name} className="flex items-center justify-between rounded-lg bg-canvas/80 px-2.5 py-1.5">
                  <span className="flex items-center gap-2 font-medium text-ink">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                    {item.name}
                  </span>
                  <strong className="tabular-nums text-forest-700">{item.value.toLocaleString()}</strong>
                </li>
              ))}
            </ul>
          </div>
        </AnalyticsChartCard>
      </div>
    </div>
  )
}
