import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertOctagon,
  Eye,
  FileWarning,
  RefreshCw,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
  UserCog,
} from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { StatCard } from '../../components/StatCard'
import { AuditDetailModal } from '../../components/audit/AuditDetailModal'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/StatusBadge'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { DataTable } from '../../components/ui/DataTable'
import { Select } from '../../components/ui/Field'
import { EmptyState, ErrorState, LoadingSkeleton } from '../../components/ui/States'
import { useAsync } from '../../hooks/useAsync'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useAuth } from '../../context/AuthContext'
import { getSecurityActivity } from '../../api/audit'
import { AUDIT_SEVERITY_TONE } from '../../utils/constants'
import { formatInstant, humanise, relativeTime } from '../../utils/format'

const WINDOW_OPTIONS = [
  { value: '24', label: 'Last 24 hours' },
  { value: '168', label: 'Last 7 days' },
  { value: '720', label: 'Last 30 days' },
]

/**
 * Threshold-Based Security Activity & Anomaly Monitoring.
 * Every counter, threshold rule, suspicious IP summary, and event timeline comes
 * directly from PostgreSQL audit_logs via GET /admin/security/activity.
 */
export default function SecurityActivity() {
  useDocumentTitle('Security activity')
  const { isHospitalAdmin, managedHospitalIds } = useAuth()
  const { hospitals } = useDirectory()

  const [hours, setHours] = useState('24')
  const [hospitalId, setHospitalId] = useState('')
  const [selectedLog, setSelectedLog] = useState(null)

  const visibleHospitals = useMemo(() => {
    if (!isHospitalAdmin) return hospitals
    const allowed = new Set(managedHospitalIds || [])
    return hospitals.filter((h) => allowed.has(h.id))
  }, [hospitals, isHospitalAdmin, managedHospitalIds])

  const activity = useAsync(
    () =>
      getSecurityActivity({
        hours: Number(hours),
        hospital_id: hospitalId || undefined,
      }),
    [hours, hospitalId],
  )

  const auditLogsPath = isHospitalAdmin ? '/hospital/audit-logs' : '/admin/audit-logs'

  const d = activity.data
  const s = d?.summary
  const t = d?.thresholds

  return (
    <div className="space-y-8">
      <PageHeader
        title="Security activity"
        description={
          isHospitalAdmin
            ? 'Deterministic security monitoring and threshold alerts scoped to your assigned hospitals.'
            : 'Deterministic security monitoring, failed-auth bursts, and access-control alerts counted from audit logs.'
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Select
              aria-label="Time window"
              value={hours}
              onChange={(e) => setHours(e.target.value)}
              options={WINDOW_OPTIONS}
              className="min-w-[10rem]"
            />
            {visibleHospitals.length > 0 && (
              <Select
                aria-label="Hospital filter"
                value={hospitalId}
                onChange={(e) => setHospitalId(e.target.value)}
                placeholder={isHospitalAdmin ? 'All my hospitals' : 'All hospitals'}
                options={visibleHospitals.map((h) => ({ value: h.id, label: h.name }))}
                className="min-w-[12rem]"
              />
            )}
            <Button variant="outline" onClick={activity.reload} disabled={activity.loading}>
              <RefreshCw size={15} aria-hidden="true" />
              Refresh
            </Button>
            <Link
              to={auditLogsPath}
              className="inline-flex h-11 items-center gap-2 rounded-xl bg-forest px-4 text-sm font-medium text-canvas transition-colors hover:bg-forest-700 focus-ring"
            >
              <ScrollText size={16} aria-hidden="true" />
              Full audit logs
            </Link>
          </div>
        }
      />

      {activity.loading ? (
        <LoadingSkeleton variant="stats" rows={5} />
      ) : activity.error ? (
        <ErrorState error={activity.error} onRetry={activity.reload} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <StatCard
              icon={AlertOctagon}
              value={s.failed_logins}
              label="Failed logins"
              hint={d.is_platform_scope ? `Burst threshold >= ${t.failed_login_burst_threshold} / 15m` : 'Platform-wide logins excluded in hospital scope'}
              tone={s.failed_logins >= t.failed_login_burst_threshold ? 'warn' : 'default'}
              to={`${auditLogsPath}?action=AUTH_LOGIN_FAILED`}
            />
            <StatCard
              icon={ShieldAlert}
              value={s.unauthorized_attempts}
              label="Unauthorized (401)"
              hint={`Spike threshold >= ${t.unauthorized_spike_threshold} / 15m`}
              tone={s.unauthorized_attempts >= t.unauthorized_spike_threshold ? 'warn' : 'default'}
              to={`${auditLogsPath}?action=AUTH_UNAUTHORIZED_ACCESS`}
            />
            <StatCard
              icon={ShieldAlert}
              value={s.forbidden_attempts}
              label="Forbidden (403)"
              hint="Privilege or scope denials"
              tone={s.forbidden_attempts > 0 ? 'warn' : 'default'}
              to={`${auditLogsPath}?action=AUTH_FORBIDDEN_ACCESS`}
            />
            <StatCard
              icon={FileWarning}
              value={s.medical_unauthorized_attempts}
              label="Medical doc blocks"
              hint={`Alert threshold >= ${t.medical_unauthorized_threshold} / 60m`}
              tone={s.medical_unauthorized_attempts >= t.medical_unauthorized_threshold ? 'warn' : 'default'}
              to={`${auditLogsPath}?action=MEDICAL_DOCUMENT_UNAUTHORIZED_ATTEMPT`}
            />
            <StatCard
              icon={UserCog}
              value={s.admin_scope_and_status_changes + s.doctor_verification_changes}
              label="Privileged governance"
              hint={`${s.doctor_verification_changes} doctor, ${s.admin_scope_and_status_changes} account/scope`}
              to={`${auditLogsPath}?entity_type=USER`}
            />
          </div>

          <Card>
            <CardHeader
              title="Active threshold alerts"
              description={`Evaluated live since ${formatInstant(d.since)}. Threshold checks operate purely on deterministic database event counts.`}
              action={
                <Badge tone={d.alerts.length ? 'negative' : 'positive'}>
                  {d.alerts.length ? `${d.alerts.length} active alert(s)` : 'All clear'}
                </Badge>
              }
            />
            {d.alerts.length === 0 ? (
              <CardBody>
                <Alert tone="positive" icon={ShieldCheck}>
                  No security monitoring thresholds were breached in the selected {d.window_hours}-hour window.
                </Alert>
              </CardBody>
            ) : (
              <ul className="divide-y divide-line">
                {d.alerts.map((alert, idx) => (
                  <li key={`${alert.code}-${alert.source || idx}`} className="flex flex-wrap items-start justify-between gap-4 px-5 py-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={AUDIT_SEVERITY_TONE[alert.severity] || 'pending'}>
                          {alert.severity}
                        </Badge>
                        <p className="text-sm font-semibold text-forest-700">{alert.title}</p>
                        {alert.source && (
                          <span className="rounded bg-forest-50 px-2 py-0.5 font-mono text-xs text-ink-muted">
                            {alert.source}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-sm text-ink-muted">{alert.description}</p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="text-sm font-semibold tabular-nums text-danger">
                        {alert.count} / {alert.threshold}
                      </p>
                      {alert.latest_at && (
                        <p className="text-xs text-ink-faint">{relativeTime(alert.latest_at)}</p>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardHeader
                title="Repeated source IPs"
                description="Top IPs generating failed logins, 401/403 rejections, or unauthorized medical attempts."
              />
              {d.suspicious_sources.length === 0 ? (
                <CardBody>
                  <p className="text-sm text-ink-muted">
                    No suspicious IP sources observed in this window.
                  </p>
                </CardBody>
              ) : (
                <ul className="divide-y divide-line">
                  {d.suspicious_sources.map((src) => (
                    <li key={src.ip_address} className="px-5 py-3.5">
                      <div className="flex items-center justify-between gap-2">
                        <Link
                          to={`${auditLogsPath}?q=${encodeURIComponent(src.ip_address)}`}
                          className="rounded font-mono text-sm font-semibold text-forest hover:underline focus-ring"
                        >
                          {src.ip_address}
                        </Link>
                        <Badge tone={src.count >= t.failed_login_burst_threshold ? 'negative' : 'pending'}>
                          {src.count} event(s)
                        </Badge>
                      </div>
                      <p className="mt-1 text-xs text-ink-muted">
                        {src.actions.map(humanise).join(', ')}
                      </p>
                      {src.latest_at && (
                        <p className="mt-0.5 text-xs text-ink-faint">
                          Last seen {relativeTime(src.latest_at)}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card className="overflow-hidden lg:col-span-2">
              <CardHeader
                title="Recent security events"
                description="Latest authentication failures, denied access attempts, threshold alerts, and privilege updates."
                action={
                  <Link
                    to={auditLogsPath}
                    className="rounded text-sm font-medium text-forest transition-colors hover:text-forest-400 focus-ring"
                  >
                    Explore all
                  </Link>
                }
              />
              {d.recent_security_events.length === 0 ? (
                <CardBody>
                  <EmptyState
                    icon={ShieldCheck}
                    title="No security events recorded"
                    description="Authentication failures, access denials, and privileged administrative changes appear here automatically."
                  />
                </CardBody>
              ) : (
                <DataTable
                  caption="Recent security events"
                  rows={d.recent_security_events}
                  onRowClick={setSelectedLog}
                  columns={[
                    {
                      key: 'created_at',
                      header: 'Time',
                      render: (row) => (
                        <span className="whitespace-nowrap text-xs text-ink-muted">
                          {formatInstant(row.created_at)}
                        </span>
                      ),
                    },
                    {
                      key: 'severity',
                      header: 'Severity',
                      render: (row) => (
                        <Badge tone={AUDIT_SEVERITY_TONE[row.severity] || 'neutral'}>
                          {row.severity}
                        </Badge>
                      ),
                    },
                    {
                      key: 'action',
                      header: 'Event',
                      render: (row) => (
                        <div className="max-w-xs">
                          <p className="text-xs font-semibold text-forest-700">{humanise(row.action)}</p>
                          <p className="truncate text-xs text-ink-muted">{row.description}</p>
                        </div>
                      ),
                    },
                    {
                      key: 'ip',
                      header: 'Source IP',
                      hideOnMobile: true,
                      render: (row) => (
                        <span className="font-mono text-xs text-ink-muted">
                          {row.ip_address || '—'}
                        </span>
                      ),
                    },
                    {
                      key: 'inspect',
                      header: '',
                      className: 'text-right',
                      render: (row) => (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedLog(row)
                          }}
                        >
                          <Eye size={14} aria-hidden="true" />
                        </Button>
                      ),
                    },
                  ]}
                />
              )}
            </Card>
          </div>
        </>
      )}

      <AuditDetailModal log={selectedLog} onClose={() => setSelectedLog(null)} />
    </div>
  )
}
