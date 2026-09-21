import { api, clean } from './client'

/* Appointment routing and discovery only. The backend never diagnoses, predicts
 * disease, or suggests medicines, dosages or treatment, and neither does this UI. */

/** POST /smart/department-suggestion — rule-based symptom → department routing. */
export const suggestDepartment = ({ symptoms, hospital_id }) =>
  api.post('/smart/department-suggestion', clean({ symptoms, hospital_id })).then((r) => r.data)

/** POST /smart/doctor-matching — doctors that have genuinely bookable slots, with a
 *  transparent score_breakdown supplied by the backend. */
export const matchDoctors = (criteria, params) =>
  api
    .post('/smart/doctor-matching', clean(criteria), { params: clean(params) })
    .then((r) => r.data)

/** POST /smart/appointment-options — ranked real bookable slots. */
export const appointmentOptions = (criteria, params) =>
  api
    .post('/smart/appointment-options', clean(criteria), { params: clean(params) })
    .then((r) => r.data)
