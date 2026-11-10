import { api, clean } from './client'

/* Platform-wide endpoints require a platform admin (managed_hospital_ids === null).
 * A hospital-scoped admin is limited to their own hospitals and gets 403 here. */

/** GET /admin/statistics — platform ADMIN. Live counts. */
export const getStatistics = () => api.get('/admin/statistics').then((r) => r.data)

/** GET /admin/users — platform ADMIN. Filters: role, is_active, q. */
export const listUsers = (params) =>
  api.get('/admin/users', { params: clean(params) }).then((r) => r.data)

/** GET /admin/users/{id} — platform ADMIN. Safe profile summary & recent audit activity. */
export const getUserDetail = (userId) =>
  api.get(`/admin/users/${userId}`).then((r) => r.data)

/** POST /admin/users — platform ADMIN. Creates another admin. */
export const createAdmin = (payload) => api.post('/admin/users', clean(payload)).then((r) => r.data)

/** PUT /admin/users/{id}/active — platform ADMIN. Cannot target yourself. */
export const setUserActive = (userId, is_active, reason) =>
  api.put(`/admin/users/${userId}/active`, clean({ is_active, reason })).then((r) => r.data)

/** PATCH /admin/users/{id}/status — Phase 6 enhanced status update with optional moderation reason. */
export const updateUserStatus = (userId, is_active, reason) =>
  api.patch(`/admin/users/${userId}/status`, clean({ is_active, reason })).then((r) => r.data)

/** PUT /admin/users/{id}/hospital-scope — null = platform-wide, list = hospital administrator. */
export const setUserScope = (userId, managed_hospital_ids) =>
  api.put(`/admin/users/${userId}/hospital-scope`, { managed_hospital_ids }).then((r) => r.data)

/** GET /admin/hospitals — scoped hospital list with department, doctor, and appointment counts. */
export const listAdminHospitals = (params) =>
  api.get('/admin/hospitals', { params: clean(params) }).then((r) => r.data)

/** GET /admin/doctors — platform ADMIN. Any profile status, e.g. PENDING verification. */
export const listDoctorProfiles = (params) =>
  api.get('/admin/doctors', { params: clean(params) }).then((r) => r.data)

/** GET /admin/doctor-verification — platform ADMIN. Enriched queue with status counts and search. */
export const listDoctorVerification = (params) =>
  api.get('/admin/doctor-verification', { params: clean(params) }).then((r) => r.data)

/** GET /admin/doctor-verification/{id}/history — platform ADMIN. Audit history for a doctor profile. */
export const getDoctorVerificationHistory = (doctorId, params) =>
  api.get(`/admin/doctor-verification/${doctorId}/history`, { params: clean(params) }).then((r) => r.data)

/** PATCH /admin/doctor-verification/{id} — PENDING / ACTIVE / SUSPENDED with reason & audit trail. */
export const updateDoctorVerification = (doctorId, profile_status, reason) =>
  api
    .patch(`/admin/doctor-verification/${doctorId}`, clean({ profile_status, reason }))
    .then((r) => r.data)

/** PUT /admin/doctors/{id}/profile-status — PENDING / ACTIVE / SUSPENDED. */
export const setDoctorProfileStatus = (doctorId, profile_status, reason) =>
  api
    .put(`/admin/doctors/${doctorId}/profile-status`, clean({ profile_status, reason }))
    .then((r) => r.data)

/** PUT /admin/doctors/{id}/affiliations — replaces hospitals and departments. */
export const setDoctorAffiliations = (doctorId, { hospital_ids, department_ids }) =>
  api
    .put(`/admin/doctors/${doctorId}/affiliations`, { hospital_ids, department_ids })
    .then((r) => r.data)

/** GET /admin/appointments — read-only monitoring. Hospital-scoped admins see their own
 *  hospitals only. Admins can never accept, reject, complete or no-show an appointment. */
export const listAppointments = (params) =>
  api.get('/admin/appointments', { params: clean(params) }).then((r) => r.data)

/** GET /admin/routing-rules — platform ADMIN. */
export const listRoutingRules = (params) =>
  api.get('/admin/routing-rules', { params: clean(params) }).then((r) => r.data)

/** POST /admin/routing-rules */
export const createRoutingRule = (payload) =>
  api.post('/admin/routing-rules', clean(payload)).then((r) => r.data)

/** PATCH /admin/routing-rules/{id} */
export const updateRoutingRule = (id, payload) =>
  api.patch(`/admin/routing-rules/${id}`, clean(payload)).then((r) => r.data)

/** DELETE /admin/routing-rules/{id} → 204. */
export const deleteRoutingRule = (id) => api.delete(`/admin/routing-rules/${id}`).then((r) => r.data)

/** POST /admin/maintenance/run — platform ADMIN. Expires stale holds, sends due reminders. */
export const runMaintenance = () => api.post('/admin/maintenance/run').then((r) => r.data)
