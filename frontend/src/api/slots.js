import { api, clean } from './client'

/** GET /slots — a doctor's availability. `doctor_id` is required.
 *  Every slot carries a backend-computed `bookable` flag; the UI never decides this itself. */
export const searchSlots = (params) =>
  api.get('/slots', { params: clean(params) }).then((r) => r.data)

/** GET /slots/me — DOCTOR. Full schedule in every slot state. */
export const listMySlots = (params) =>
  api.get('/slots/me', { params: clean(params) }).then((r) => r.data)

/** POST /slots/{id}/block — DOCTOR. Only an AVAILABLE slot of their own. */
export const blockSlot = (slotId) => api.post(`/slots/${slotId}/block`).then((r) => r.data)

/** POST /slots/{id}/unblock — DOCTOR. Only slots blocked manually. */
export const unblockSlot = (slotId) => api.post(`/slots/${slotId}/unblock`).then((r) => r.data)
