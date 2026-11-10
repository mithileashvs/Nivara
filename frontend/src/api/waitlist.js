import { api, clean } from './client'

/* The waitlist notifies a patient when a matching slot frees up and offers
 * a time-limited reservation. Upon patient acceptance, a booking request is submitted
 * for doctor confirmation. */

/** POST /waitlist → 201 WaitlistOut. Needs at least one of doctor/department/hospital/specialty. */
export const joinWaitlist = (payload) => api.post('/waitlist', clean(payload)).then((r) => r.data)

/** GET /waitlist — PATIENT active entries. Optional status filter. */
export const listMyWaitlist = (params) =>
  api.get('/waitlist', { params: clean(params) }).then((r) => r.data)

/** GET /waitlist/history — PATIENT fulfilled, expired, cancelled history entries. */
export const getMyWaitlistHistory = (params) =>
  api.get('/waitlist/history', { params: clean(params) }).then((r) => r.data)

/** GET /waitlist/offers — PATIENT time-limited slot offers. Optional status filter. */
export const listMyOffers = (status) =>
  api.get('/waitlist/offers', { params: clean({ status }) }).then((r) => r.data)

/** POST /waitlist/offers/{id}/accept — converts held slot to appointment request. */
export const acceptOffer = (id, reason) =>
  api.post(`/waitlist/offers/${id}/accept`, { reason: reason || null }).then((r) => r.data)

/** POST /waitlist/offers/{id}/decline — releases held slot and advances queue. */
export const declineOffer = (id, reason) =>
  api.post(`/waitlist/offers/${id}/decline`, { reason: reason || null }).then((r) => r.data)

/** GET /waitlist/{id} */
export const getWaitlistEntry = (id) => api.get(`/waitlist/${id}`).then((r) => r.data)

/** DELETE /waitlist/{id} — cancels an ACTIVE entry. */
export const leaveWaitlist = (id) => api.delete(`/waitlist/${id}`).then((r) => r.data)

/** GET /doctors/me/waitlist/statistics — DOCTOR waitlist metrics. */
export const getDoctorWaitlistStats = () =>
  api.get('/doctors/me/waitlist/statistics').then((r) => r.data)

/** GET /doctors/me/waitlist — DOCTOR patient queue. */
export const listDoctorWaitlist = (params) =>
  api.get('/doctors/me/waitlist', { params: clean(params) }).then((r) => r.data)

/** GET /admin/waitlist/statistics — ADMIN platform/hospital waitlist metrics. */
export const getAdminWaitlistStats = () =>
  api.get('/admin/waitlist/statistics').then((r) => r.data)

/** GET /admin/waitlist — ADMIN monitor all waitlist queues. */
export const listAdminWaitlist = (params) =>
  api.get('/admin/waitlist', { params: clean(params) }).then((r) => r.data)
