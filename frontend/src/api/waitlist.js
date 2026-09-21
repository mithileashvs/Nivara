import { api, clean } from './client'

/* The waitlist notifies a patient when a matching slot frees up. Nothing is booked
 * automatically — the patient still requests it and the doctor still confirms. */

/** POST /waitlist → 201 WaitlistOut. Needs at least one of doctor/department/hospital/specialty. */
export const joinWaitlist = (payload) => api.post('/waitlist', clean(payload)).then((r) => r.data)

/** GET /waitlist — PATIENT. Optional status filter. */
export const listMyWaitlist = (params) =>
  api.get('/waitlist', { params: clean(params) }).then((r) => r.data)

/** GET /waitlist/{id} */
export const getWaitlistEntry = (id) => api.get(`/waitlist/${id}`).then((r) => r.data)

/** DELETE /waitlist/{id} — cancels an ACTIVE entry. */
export const leaveWaitlist = (id) => api.delete(`/waitlist/${id}`).then((r) => r.data)
