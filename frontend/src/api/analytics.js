import { api, clean } from './client'

/* ===========================================================================
 * Operational Healthcare Analytics API Client (Phase 5)
 * =========================================================================== */

/** GET /analytics/overview — Platform or hospital-scoped operational KPIs and trends. */
export const getAnalyticsOverview = (params) =>
  api.get('/analytics/overview', { params: clean(params) }).then((r) => r.data)

/** GET /analytics/appointments/trends — Time-series volume & paginated period summary table. */
export const getAppointmentTrends = (params) =>
  api.get('/analytics/appointments/trends', { params: clean(params) }).then((r) => r.data)

/** GET /analytics/appointments/status — Status breakdown, consultation types, and rates. */
export const getAppointmentStatusAnalytics = (params) =>
  api.get('/analytics/appointments/status', { params: clean(params) }).then((r) => r.data)

/** GET /analytics/hospitals — Hospital-wise comparison & volume metrics. */
export const getHospitalAnalytics = (params) =>
  api.get('/analytics/hospitals', { params: clean(params) }).then((r) => r.data)

/** GET /analytics/hospitals/{hospital_id} — Hospital detail drilldown (strict scope enforced). */
export const getHospitalAnalyticsDetail = (hospitalId, params) =>
  api.get(`/analytics/hospitals/${hospitalId}`, { params: clean(params) }).then((r) => r.data)

/** GET /analytics/departments — Department-wise appointment volumes and rates. */
export const getDepartmentAnalytics = (params) =>
  api.get('/analytics/departments', { params: clean(params) }).then((r) => r.data)

/** GET /analytics/doctors — Doctor workload & actual slot counts. */
export const getDoctorAnalytics = (params) =>
  api.get('/analytics/doctors', { params: clean(params) }).then((r) => r.data)

/** GET /analytics/patients — Aggregate-only patient growth & engagement metrics (no PII). */
export const getPatientAnalytics = (params) =>
  api.get('/analytics/patients', { params: clean(params) }).then((r) => r.data)

/** GET /analytics/reports/export — Downloads CSV matching exact filters and backend scope. */
export const downloadAnalyticsReport = async (params) => {
  const response = await api.get('/analytics/reports/export', {
    params: clean(params),
    responseType: 'blob',
  })

  const cd = response.headers?.['content-disposition'] || ''
  const match = cd.match(/filename="?([^"]+)"?/i)
  const fallback = `nivara_${params?.report_type || 'analytics'}.csv`
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
