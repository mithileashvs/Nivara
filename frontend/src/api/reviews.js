import { api, clean } from './client'

/** POST /reviews — PATIENT, once per COMPLETED appointment. */
export const createReview = ({ appointment_id, rating, comment }) =>
  api.post('/reviews', clean({ appointment_id, rating, comment })).then((r) => r.data)

/** GET /reviews?doctor_id=… — any authenticated role. Patient identities are not exposed. */
export const listDoctorReviews = (doctor_id, params) =>
  api.get('/reviews', { params: clean({ doctor_id, ...params }) }).then((r) => r.data)

/** GET /reviews/mine — PATIENT. */
export const listMyReviews = (params) =>
  api.get('/reviews/mine', { params: clean(params) }).then((r) => r.data)

/** DELETE /reviews/{id} — ADMIN moderation. */
export const deleteReview = (id) => api.delete(`/reviews/${id}`).then((r) => r.data)
