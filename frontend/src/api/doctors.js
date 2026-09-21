import { api, clean } from './client'

/** GET /doctors — any authenticated role. Page<DoctorPublicOut>. */
export const searchDoctors = (params) =>
  api.get('/doctors', { params: clean(params) }).then((r) => r.data)

/** GET /doctors/{id} — public profile of an ACTIVE doctor. */
export const getDoctor = (doctorId) => api.get(`/doctors/${doctorId}`).then((r) => r.data)

/** GET /doctors/me — DOCTOR. */
export const getMyDoctorProfile = () => api.get('/doctors/me').then((r) => r.data)

/** PATCH /doctors/me — DOCTOR. experience / consultation_fee / consultation_types only. */
export const updateMyDoctorProfile = (payload) =>
  api.patch('/doctors/me', payload).then((r) => r.data)

/** GET /doctors/me/statistics — DOCTOR. Counts computed live from appointments. */
export const getMyStatistics = () => api.get('/doctors/me/statistics').then((r) => r.data)

/** POST /doctors/me/availability — WORKING generates slots, BLOCKED is time off. */
export const createAvailability = (payload) =>
  api.post('/doctors/me/availability', payload).then((r) => r.data)

/** GET /doctors/me/availability — DOCTOR. Optional date_from / date_to. */
export const listMyAvailability = (params) =>
  api.get('/doctors/me/availability', { params: clean(params) }).then((r) => r.data)

/** DELETE /doctors/me/availability/{id} — 409 if its slots are held or booked. */
export const deleteAvailability = (id) =>
  api.delete(`/doctors/me/availability/${id}`).then((r) => r.data)

/** PUT /doctors/{id}/intake-status — the doctor themself, or an admin for their hospital. */
export const setDoctorIntake = (doctorId, availability_status, reason) =>
  api
    .put(`/doctors/${doctorId}/intake-status`, {
      availability_status,
      ...(reason ? { reason } : {}),
    })
    .then((r) => r.data)
