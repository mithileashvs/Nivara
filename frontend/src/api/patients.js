import { api, clean } from './client'

/** GET /patients/me — PATIENT. */
export const getMyProfile = () => api.get('/patients/me').then((r) => r.data)

/** PATCH /patients/me — PATIENT. */
export const updateMyProfile = (payload) => api.patch('/patients/me', payload).then((r) => r.data)

/** GET /patients — platform ADMIN. Identity fields only, no contact or health data. */
export const listPatients = (params) =>
  api.get('/patients', { params: clean(params) }).then((r) => r.data)

/** GET /patients/{id} — DOCTOR, only for a patient they have an appointment with. */
export const getPatientForDoctor = (patientId) =>
  api.get(`/patients/${patientId}`).then((r) => r.data)
