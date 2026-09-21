import { api, clean } from './client'

/** GET /departments — any authenticated role. Filters: hospital_id, status. */
export const listDepartments = (params) =>
  api.get('/departments', { params: clean(params) }).then((r) => r.data)

/** GET /departments/{id} */
export const getDepartment = (id) => api.get(`/departments/${id}`).then((r) => r.data)

/** POST /departments — ADMIN authorised for the hospital. */
export const createDepartment = (payload) => api.post('/departments', payload).then((r) => r.data)

/** PATCH /departments/{id} — ADMIN authorised for the hospital. */
export const updateDepartment = (id, payload) =>
  api.patch(`/departments/${id}`, payload).then((r) => r.data)

/** PUT /departments/{id}/intake — OPEN/CLOSED. Existing appointments untouched. */
export const setDepartmentIntake = (id, status, reason) =>
  api.put(`/departments/${id}/intake`, { status, ...(reason ? { reason } : {}) }).then((r) => r.data)
