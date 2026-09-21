import { api, clean } from './client'

/* Medical records are visible to the patient and the authoring doctor only.
 * Administrators are refused by the backend (403). */

/** GET /medical-records — PATIENT (own) or DOCTOR (authored). */
export const listRecords = (params) =>
  api.get('/medical-records', { params: clean(params) }).then((r) => r.data)

/** GET /medical-records/{id} */
export const getRecord = (id) => api.get(`/medical-records/${id}`).then((r) => r.data)

/** POST /medical-records — DOCTOR. One record per confirmed/completed appointment. */
export const createRecord = ({ appointment_id, notes }) =>
  api.post('/medical-records', { appointment_id, notes }).then((r) => r.data)

/** PATCH /medical-records/{id} — authoring DOCTOR. */
export const updateRecordNotes = (id, notes) =>
  api.patch(`/medical-records/${id}`, { notes }).then((r) => r.data)

/** POST /medical-records/{id}/documents — registers a link to a file already in object storage.
 *  The backend stores metadata only; there is no file-upload endpoint. */
export const addDocument = (recordId, { filename, file_url, document_type }) =>
  api
    .post(`/medical-records/${recordId}/documents`, clean({ filename, file_url, document_type }))
    .then((r) => r.data)

/** DELETE /medical-records/{recordId}/documents/{documentId} — only whoever attached it. */
export const removeDocument = (recordId, documentId) =>
  api.delete(`/medical-records/${recordId}/documents/${documentId}`).then((r) => r.data)
