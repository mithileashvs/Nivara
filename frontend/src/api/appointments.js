import { api, clean } from './client'

/** POST /appointments → 201 AppointmentOut with status REQUESTED. The doctor decides next.
 *  409 codes: slot_booked, slot_held, slot_blocked, slot_in_past, slot_too_soon,
 *  doctor_intake_closed, hospital_intake_closed, department_intake_closed, patient_time_conflict … */
export const requestAppointment = ({ slot_id, consultation_type, reason }) =>
  api
    .post('/appointments', clean({ slot_id, consultation_type, reason }))
    .then((r) => r.data)

/** GET /appointments — PATIENT sees their own, DOCTOR sees theirs. Admins have no access here. */
export const listAppointments = (params) =>
  api.get('/appointments', { params: clean(params) }).then((r) => r.data)

/** GET /appointments/{id} — only the appointment's patient or doctor. */
export const getAppointment = (id) => api.get(`/appointments/${id}`).then((r) => r.data)

/** GET /appointments/{id}/history — every status change, who made it and why. */
export const getAppointmentHistory = (id) =>
  api.get(`/appointments/${id}/history`).then((r) => r.data)

/** POST /appointments/{id}/accept — DOCTOR only. REQUESTED → CONFIRMED. */
export const acceptAppointment = (id, reason) =>
  api.post(`/appointments/${id}/accept`, clean({ reason })).then((r) => r.data)

/** POST /appointments/{id}/reject — DOCTOR only. REQUESTED → REJECTED. */
export const rejectAppointment = (id, reason) =>
  api.post(`/appointments/${id}/reject`, clean({ reason })).then((r) => r.data)

/** POST /appointments/{id}/cancel — PATIENT or DOCTOR of the appointment, before it starts. */
export const cancelAppointment = (id, reason) =>
  api.post(`/appointments/${id}/cancel`, clean({ reason })).then((r) => r.data)

/** POST /appointments/{id}/complete — DOCTOR, once the appointment has started. */
export const completeAppointment = (id, reason) =>
  api.post(`/appointments/${id}/complete`, clean({ reason })).then((r) => r.data)

/** POST /appointments/{id}/no-show — DOCTOR, once the appointment has started. */
export const markNoShow = (id, reason) =>
  api.post(`/appointments/${id}/no-show`, clean({ reason })).then((r) => r.data)

/** POST /appointments/{id}/reschedule — new slot must belong to the same doctor.
 *  Patient reschedule requests a new slot (doctor must approve). Doctor reschedule moves directly. */
export const rescheduleAppointment = (id, new_slot_id, reason) =>
  api.post(`/appointments/${id}/reschedule`, clean({ new_slot_id, reason })).then((r) => r.data)

/** GET /appointments/{id}/reschedule-requests — list all reschedule requests for an appointment. */
export const getAppointmentRescheduleRequests = (id) =>
  api.get(`/appointments/${id}/reschedule-requests`).then((r) => r.data)

/** GET /doctors/me/reschedule-requests — DOCTOR only. List pending/all reschedule requests. */
export const listDoctorRescheduleRequests = (params) =>
  api.get('/doctors/me/reschedule-requests', { params: clean(params) }).then((r) => r.data)

/** POST /reschedule-requests/{requestId}/approve — DOCTOR only. Approves the new slot atomically. */
export const approveRescheduleRequest = (requestId, reason) =>
  api.post(`/reschedule-requests/${requestId}/approve`, clean({ reason })).then((r) => r.data)

/** POST /reschedule-requests/{requestId}/reject — DOCTOR only. Rejects the request, keeps original slot. */
export const rejectRescheduleRequest = (requestId, reason) =>
  api.post(`/reschedule-requests/${requestId}/reject`, clean({ reason })).then((r) => r.data)

/** GET /reschedule-requests/{requestId} — fetch a specific reschedule request. */
export const getRescheduleRequest = (requestId) =>
  api.get(`/reschedule-requests/${requestId}`).then((r) => r.data)
