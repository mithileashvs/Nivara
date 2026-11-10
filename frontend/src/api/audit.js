import { api, clean } from './client'

/* ===========================================================================
 * Centralized Audit Logs & Security Activity API Client (Phase 6)
 * =========================================================================== */

/** GET /admin/audit-logs — Search & filter centralized append-only audit logs. */
export const listAuditLogs = (params) =>
  api.get('/admin/audit-logs', { params: clean(params) }).then((r) => r.data)

/** GET /admin/audit-logs/{id} — Full details for a single audit event. */
export const getAuditLog = (logId) =>
  api.get(`/admin/audit-logs/${logId}`).then((r) => r.data)

/** GET /admin/audit-logs/export — Streams UTF-8 CSV matching exact query filters and RBAC scope. */
export const downloadAuditLogsCsv = async (params) => {
  const response = await api.get('/admin/audit-logs/export', {
    params: clean(params),
    responseType: 'blob',
  })

  const cd = response.headers?.['content-disposition'] || ''
  const match = cd.match(/filename="?([^"]+)"?/i)
  const fallback = `nivara_audit_logs_${new Date().toISOString().slice(0, 10)}.csv`
  const filename = match ? match[1] : fallback

  const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
  return filename
}

/** GET /admin/security/activity — Threshold-based security metrics, alerts, and recent events. */
export const getSecurityActivity = (params) =>
  api.get('/admin/security/activity', { params: clean(params) }).then((r) => r.data)
