import { useEffect, useState } from 'react'
import { Lock } from 'lucide-react'
import { getAuditLog } from '../../api/audit'
import { Modal } from '../ui/Modal'
import { Badge } from '../ui/StatusBadge'
import { Button } from '../ui/Button'
import { AUDIT_SEVERITY_TONE } from '../../utils/constants'
import { formatInstant, humanise, relativeTime } from '../../utils/format'

/**
 * Read-only inspector for an append-only audit_logs entry.
 * Application APIs intentionally expose zero edit or delete controls.
 */
export function AuditDetailModal({ log, onClose }) {
  const [detail, setDetail] = useState(log)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setDetail(log)
    if (!log?.id) return undefined
    let cancelled = false
    setLoading(true)
    getAuditLog(log.id)
      .then((fresh) => {
        if (!cancelled) setDetail(fresh)
      })
      .catch(() => {
        // Keep initial row snapshot if network lookup fails transiently
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [log])

  const entry = detail || log
  if (!entry) return null

  const metaEntries = Object.entries(entry.metadata || {})

  return (
    <Modal
      open={Boolean(log)}
      onClose={onClose}
      title={humanise(entry.action)}
      description={`Audit ID ${entry.id}`}
      size="lg"
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs text-ink-muted">
            <Lock size={13} aria-hidden="true" />
            Append-only audit record (read-only via API)
          </span>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-forest-50/50 px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={AUDIT_SEVERITY_TONE[entry.severity] || 'neutral'}>
              {entry.severity}
            </Badge>
            <span className="font-mono text-xs text-forest-700">{entry.action}</span>
          </div>
          <span className="text-xs text-ink-muted">
            {formatInstant(entry.created_at)}
            {relativeTime(entry.created_at) ? ` (${relativeTime(entry.created_at)})` : ''}
          </span>
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Summary</p>
          <p className="mt-1 text-sm leading-relaxed text-forest-700">{entry.description}</p>
        </div>

        <dl className="grid gap-3 rounded-xl border border-line p-4 sm:grid-cols-2">
          <DetailItem
            label="Actor"
            value={
              entry.actor_name
                ? `${entry.actor_name} (${humanise(entry.actor_role)})`
                : humanise(entry.actor_role)
            }
            sub={entry.actor_email || (entry.actor_id ? `ID: ${entry.actor_id}` : 'No user account')}
          />
          <DetailItem
            label="Target Entity"
            value={humanise(entry.entity_type)}
            sub={entry.entity_id ? `ID: ${entry.entity_id}` : '—'}
          />
          <DetailItem
            label="Hospital Scope"
            value={entry.hospital_name || (entry.hospital_id ? 'Hospital record' : 'Platform-wide')}
            sub={entry.hospital_id ? `Hospital ID: ${entry.hospital_id}` : 'Not bound to a single hospital'}
          />
          <DetailItem
            label="Request Source"
            value={entry.ip_address || 'IP unavailable'}
            sub={entry.user_agent ? truncate(entry.user_agent, 90) : 'User-Agent not recorded'}
          />
        </dl>

        <div>
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
              Sanitized Event Metadata
            </p>
            {loading && <span className="text-xs text-ink-faint">Refreshing…</span>}
          </div>

          {metaEntries.length === 0 ? (
            <p className="mt-2 rounded-xl border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
              No additional metadata attributes attached to this event.
            </p>
          ) : (
            <div className="mt-2 overflow-hidden rounded-xl border border-line">
              <table className="w-full border-collapse text-left text-xs">
                <tbody className="divide-y divide-line">
                  {metaEntries.map(([key, val]) => (
                    <tr key={key} className="align-top">
                      <th scope="row" className="w-44 bg-forest-50/40 px-3.5 py-2.5 font-mono font-medium text-forest-700">
                        {key}
                      </th>
                      <td className="px-3.5 py-2.5 font-mono text-ink-muted break-all">
                        {typeof val === 'object' && val !== null
                          ? JSON.stringify(val)
                          : String(val)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className="mt-2 text-xs text-ink-faint">
            Privacy policy: passwords, JWT tokens, file contents, symptoms, diagnoses, and clinical notes are stripped prior to persistence.
          </p>
        </div>
      </div>
    </Modal>
  )
}

function DetailItem({ label, value, sub }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className="mt-0.5 truncate text-sm font-medium text-forest-700">{value}</dd>
      {sub && <dd className="mt-0.5 truncate font-mono text-xs text-ink-faint">{sub}</dd>}
    </div>
  )
}

function truncate(s, len) {
  return s && s.length > len ? `${s.slice(0, len)}…` : s
}
