import { api, clean } from './client'

/** GET /hospitals — any authenticated role. Filters: city, q, intake_status. */
export const listHospitals = (params) =>
  api.get('/hospitals', { params: clean(params) }).then((r) => r.data)

/** GET /hospitals/{id} — hospital plus its departments. */
export const getHospital = (id) => api.get(`/hospitals/${id}`).then((r) => r.data)

/** POST /hospitals — platform ADMIN only (hospital-scoped admins cannot create hospitals). */
export const createHospital = (payload) => api.post('/hospitals', payload).then((r) => r.data)

/** PATCH /hospitals/{id} — ADMIN authorised for this hospital. */
export const updateHospital = (id, payload) =>
  api.patch(`/hospitals/${id}`, payload).then((r) => r.data)

/** PUT /hospitals/{id}/intake — OPEN/CLOSED. Existing appointments are never cancelled. */
export const setHospitalIntake = (id, status, reason) =>
  api.put(`/hospitals/${id}/intake`, { status, ...(reason ? { reason } : {}) }).then((r) => r.data)

/** GET /hospitals/{id}/availability — real bookable-slot counts, never inferred load. */
export const getHospitalAvailability = (id, params) =>
  api.get(`/hospitals/${id}/availability`, { params: clean(params) }).then((r) => r.data)
