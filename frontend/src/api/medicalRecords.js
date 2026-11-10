import { api, clean } from './client'

/* ===========================================================================
 * Medical Records & Documents API Client (Phase 4)
 * =========================================================================== */

/** GET /medical-records — Consultation notes: PATIENT (own) or DOCTOR (authored). */
export const listRecords = (params) =>
  api.get('/medical-records', { params: clean(params) }).then((r) => r.data)

/** GET /medical-records/{id} — Consultation notes detail. */
export const getRecord = (id) => api.get(`/medical-records/${id}`).then((r) => r.data)

/** POST /medical-records — DOCTOR adds consultation notes for appointment. */
export const createRecord = ({ appointment_id, notes }) =>
  api.post('/medical-records', { appointment_id, notes }).then((r) => r.data)

/** PATCH /medical-records/{id} — Authoring DOCTOR updates consultation notes. */
export const updateRecordNotes = (id, notes) =>
  api.patch(`/medical-records/${id}`, { notes }).then((r) => r.data)

/** POST /medical-records/{id}/documents — Legacy external URL reference attachment. */
export const addDocument = (recordId, { filename, file_url, document_type }) =>
  api
    .post(`/medical-records/${recordId}/documents`, clean({ filename, file_url, document_type }))
    .then((r) => r.data)

/** DELETE /medical-records/{recordId}/documents/{documentId} — Legacy document reference removal. */
export const removeDocument = (recordId, documentId) =>
  api.delete(`/medical-records/${recordId}/documents/${documentId}`).then((r) => r.data)

// ---------------------------------------------------------------------------
// Phase 4: Secure Medical Document Upload & Management (Patient)
// ---------------------------------------------------------------------------

/** POST /medical-records/documents/upload — PATIENT uploads document file with metadata. */
export const uploadMedicalDocument = (formData) =>
  api
    .post('/medical-records/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .then((r) => r.data)

/** GET /medical-records/documents — PATIENT lists own documents with category/search. */
export const listPatientDocuments = (params) =>
  api.get('/medical-records/documents', { params: clean(params) }).then((r) => r.data)

/** GET /medical-records/documents/{id} — PATIENT gets document metadata. */
export const getPatientDocument = (id) =>
  api.get(`/medical-records/documents/${id}`).then((r) => r.data)

/** GET /medical-records/documents/{id}/download — Downloads document binary stream. */
export const downloadMedicalDocument = (id) =>
  api.get(`/medical-records/documents/${id}/download`, { responseType: 'blob' })

/** DELETE /medical-records/documents/{id} — PATIENT deletes own document. */
export const deletePatientDocument = (id) =>
  api.delete(`/medical-records/documents/${id}`).then((r) => r.data)

// ---------------------------------------------------------------------------
// Phase 4: Patient-Controlled Doctor Sharing & Consent
// ---------------------------------------------------------------------------

/** POST /medical-records/documents/{id}/share — PATIENT grants consent to a doctor. */
export const shareDocumentWithDoctor = (documentId, { doctor_id, appointment_id, notes }) =>
  api
    .post(`/medical-records/documents/${documentId}/share`, clean({ doctor_id, appointment_id, notes }))
    .then((r) => r.data)

/** DELETE /medical-records/documents/{id}/share/{doctorId} — PATIENT revokes doctor consent. */
export const revokeDocumentShare = (documentId, doctorId) =>
  api.delete(`/medical-records/documents/${documentId}/share/${doctorId}`).then((r) => r.data)

/** GET /medical-records/documents/{id}/shares — PATIENT views consent history for document. */
export const listDocumentShares = (documentId) =>
  api.get(`/medical-records/documents/${documentId}/shares`).then((r) => r.data)

// ---------------------------------------------------------------------------
// Phase 4: Medical Timeline & Doctor Shared Access
// ---------------------------------------------------------------------------

/** GET /medical-records/timeline — Chronological medical timeline (PATIENT or DOCTOR). */
export const getMedicalTimeline = (params) =>
  api.get('/medical-records/timeline', { params: clean(params) }).then((r) => r.data)

/** GET /medical-records/shared — DOCTOR lists documents shared by patients. */
export const listSharedWithDoctor = (params) =>
  api.get('/medical-records/shared', { params: clean(params) }).then((r) => r.data)

/** GET /medical-records/shared/{id} — DOCTOR gets shared document metadata. */
export const getSharedDocumentDoctor = (id) =>
  api.get(`/medical-records/shared/${id}`).then((r) => r.data)

/** GET /medical-records/patients/{patientId}/timeline — DOCTOR views patient timeline. */
export const getPatientTimelineDoctor = (patientId, params) =>
  api.get(`/medical-records/patients/${patientId}/timeline`, { params: clean(params) }).then((r) => r.data)

// ---------------------------------------------------------------------------
// Phase 4: Audit & Admin Statistics
// ---------------------------------------------------------------------------

/** GET /medical-records/audits — Access audit trail (PATIENT or ADMIN). */
export const getMedicalAudits = (params) =>
  api.get('/medical-records/audits', { params: clean(params) }).then((r) => r.data)

/** GET /medical-records/admin/stats — ADMIN operational document statistics. */
export const getAdminMedicalStats = () =>
  api.get('/medical-records/admin/stats').then((r) => r.data)
