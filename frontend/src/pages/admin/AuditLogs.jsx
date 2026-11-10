import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Download, Eye, ScrollText, ShieldAlert } from 'lucide-react'
import { PageHeader } from '../../components/Topbar'
import { SearchBar } from '../../components/SearchBar'
import { FilterBar } from '../../components/FilterBar'
import { AuditDetailModal } from '../../components/audit/AuditDetailModal'
import { Badge } from '../../components/ui/StatusBadge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { DataTable } from '../../components/ui/DataTable'
import { Pagination } from '../../components/ui/Pagination'
import { AsyncBoundary, EmptyState, LoadingSkeleton } from '../../components/ui/States'
import { usePaged } from '../../hooks/usePaged'
import { useDebounced } from '../../hooks/useDebounced'
import { useDirectory } from '../../hooks/useDirectory'
import { useDocumentTitle } from '../../hooks/useDocumentTitle'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { downloadAuditLogsCsv, listAuditLogs } from '../../api/audit'
import {
  AUDIT_ACTION_OPTIONS,
  AUDIT_ENTITY_OPTIONS,
  AUDIT_ROLE_OPTIONS,
  AUDIT_SEVERITY_OPTIONS,
  AUDIT_SEVERITY_TONE,
} from '../../utils/constants'
import { formatInstant, humanise, relativeTime } from '../../utils/format'
import { errorMessage } from '../../utils/errors'

/**
 * Shared Centralized Audit Logs Explorer.
 * Available to both platform administrators (/admin/audit-logs) and
 * hospital-scoped administrators (/hospital/audit-logs).
 * Backend enforces strict managed_hospital_ids filtering on all queries & exports.
 */
export default function AuditLogs() {
  useDocumentTitle('Audit logs')
  const [params, setParams] = useSearchParams()
  const { isHospitalAdmin, managedHospitalIds } = useAuth()
  const { hospitals } = useDirectory()
  const toast = useToast()

  const [searchInput, setSearchInput] = useState(params.get('q') || '')
  const debouncedQ = useDebounced(searchInput.trim())

  const severity = params.get('severity') || ''
  const actorRole = params.get('actor_role') || ''
  const entityType = params.get('entity_type') || ''
  const action = params.get('action') || ''
  const hospitalId = params.get('hospital_id') || ''
  const dateFrom = params.get('date_from') || ''
  const dateTo = params.get('date_to') || ''

  const [selectedLog, setSelectedLog] = useState(null)
  const [exporting, setExporting] = useState(false)

  const visibleHospitals = useMemo(() => {
    if (!isHospitalAdmin) return hospitals
    const allowed = new Set(managedHospitalIds || [])
    return hospitals.filter((h) => allowed.has(h.id))
  }, [hospitals, isHospitalAdmin, managedHospitalIds])

  const queryFilters = useMemo(
    () => ({
      q: debouncedQ || undefined,
      severity: severity || undefined,
      actor_role: actorRole || undefined,
      entity_type: entityType || undefined,
      action: action || undefined,
      hospital_id: hospitalId || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    }),
    [debouncedQ, severity, actorRole, entityType, action, hospitalId, dateFrom, dateTo],
  )

  const paged = usePaged(
    (p) => listAuditLogs({ ...p, ...queryFilters }),
    [queryFilters],
  )

  const setParam = (key) => (value) => {
    const next = Object.fromEntries(params)
    if (value) next[key] = value
    else delete next[key]
    setParams(next, { replace: true })
  }

  const handleSearchChange = (value) => {
    setSearchInput(value)
    const next = Object.fromEntries(params)
    if (value.trim()) next.q = value.trim()
    else delete next.q
    setParams(next, { replace: true })
  }

  const clearAllFilters = () => {
    setSearchInput('')
    setParams({}, { replace: true })
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const filename = await downloadAuditLogsCsv(queryFilters)
      toast.success(`Exported ${filename}.`)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setExporting(false)
    }
  }

  const hasFilters = Boolean(
    debouncedQ || severity || actorRole || entityType || action || hospitalId || dateFrom || dateTo,
  )

  const securityPath = isHospitalAdmin ? '/hospital/security' : '/admin/security'

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit logs"
        description={
          isHospitalAdmin
            ? 'Append-only operational and security events across your assigned hospitals.'
            : 'Append-only platform operational, access-control, and security audit trail.'
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={securityPath}
              className="inline-flex h-10 items-center gap-2 rounded-xl border border-line bg-surface px-3.5 text-sm font-medium text-forest-700 transition-colors hover:border-forest-200 hover:bg-forest-50 focus-ring"
            >
              <ShieldAlert size={16} aria-hidden="true" />
              Security activity
            </Link>
            <Button variant="outline" onClick={handleExport} loading={exporting}>
              <Download size={16} aria-hidden="true" />
              Export CSV
            </Button>
          </div>
        }
      />

      <SearchBar
        value={searchInput}
        onChange={handleSearchChange}
        placeholder="Search actor name, email, action, description, entity ID or IP…"
        label="Search audit logs"
      />

      <FilterBar
        hasActive={hasFilters}
        onClear={clearAllFilters}
        filters={[
          {
            key: 'severity',
            label: 'Severity',
            value: severity,
            onChange: setParam('severity'),
            options: AUDIT_SEVERITY_OPTIONS,
          },
          {
            key: 'actor_role',
            label: 'Actor role',
            value: actorRole,
            onChange: setParam('actor_role'),
            options: AUDIT_ROLE_OPTIONS,
          },
          {
            key: 'entity_type',
            label: 'Entity',
            value: entityType,
            onChange: setParam('entity_type'),
            options: AUDIT_ENTITY_OPTIONS,
          },
          {
            key: 'action',
            label: 'Action',
            value: action,
            onChange: setParam('action'),
            options: AUDIT_ACTION_OPTIONS,
          },
          ...(visibleHospitals.length > 0
            ? [
                {
                  key: 'hospital_id',
                  label: 'Hospital',
                  value: hospitalId,
                  onChange: setParam('hospital_id'),
                  options: visibleHospitals.map((h) => ({ value: h.id, label: h.name })),
                },
              ]
            : []),
        ]}
        extra={
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-1.5 text-xs text-ink-muted">
              <span>From</span>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setParam('date_from')(e.target.value)}
                aria-label="Date from"
                className="h-10 rounded-xl border border-line bg-surface px-3 text-sm text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-forest"
              />
            </label>
            <label className="flex items-center gap-1.5 text-xs text-ink-muted">
              <span>To</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setParam('date_to')(e.target.value)}
                aria-label="Date to"
                className="h-10 rounded-xl border border-line bg-surface px-3 text-sm text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-forest"
              />
            </label>
          </div>
        }
      />

      <AsyncBoundary
        loading={paged.loading}
        error={paged.error}
        onRetry={paged.reload}
        isEmpty={paged.isEmpty}
        skeleton={<LoadingSkeleton variant="table" rows={6} />}
        empty={
          <EmptyState
            icon={ScrollText}
            title="No audit events match those filters"
            description="Adjust your search term, date range, or severity filters."
          />
        }
      >
        <Card className="overflow-hidden">
          <DataTable
            caption="Centralized audit log events"
            rows={paged.items}
            onRowClick={setSelectedLog}
            columns={[
              {
                key: 'created_at',
                header: 'Timestamp',
                render: (row) => (
                  <div className="whitespace-nowrap">
                    <p className="text-xs font-medium text-forest-700">{formatInstant(row.created_at)}</p>
                    <p className="text-xs text-ink-faint">{relativeTime(row.created_at)}</p>
                  </div>
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
                    <p className="font-medium text-forest-700">{humanise(row.action)}</p>
                    <p className="mt-0.5 truncate text-xs text-ink-muted">{row.description}</p>
                  </div>
                ),
              },
              {
                key: 'actor',
                header: 'Actor',
                render: (row) => (
                  <div className="max-w-[12rem]">
                    <p className="truncate font-medium text-ink">
                      {row.actor_name || humanise(row.actor_role)}
                    </p>
                    <p className="truncate text-xs text-ink-muted">
                      {row.actor_email || humanise(row.actor_role)}
                    </p>
                  </div>
                ),
              },
              {
                key: 'target',
                header: 'Entity / Scope',
                hideOnMobile: true,
                render: (row) => (
                  <div className="max-w-[12rem]">
                    <p className="truncate text-xs font-medium text-forest-700">
                      {humanise(row.entity_type)}
                    </p>
                    <p className="truncate text-xs text-ink-faint">
                      {row.hospital_name || row.entity_id || 'Platform'}
                    </p>
                  </div>
                ),
              },
              {
                key: 'ip_address',
                header: 'IP Address',
                hideOnMobile: true,
                render: (row) => (
                  <span className="font-mono text-xs text-ink-muted">
                    {row.ip_address || '—'}
                  </span>
                ),
              },
              {
                key: 'actions',
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
                    Inspect
                  </Button>
                ),
              },
            ]}
          />
        </Card>

        <Pagination
          className="mt-6"
          page={paged.page}
          totalPages={paged.totalPages}
          total={paged.total}
          pageSize={paged.pageSize}
          onChange={paged.setPage}
        />
      </AsyncBoundary>

      <AuditDetailModal log={selectedLog} onClose={() => setSelectedLog(null)} />
    </div>
  )
}
