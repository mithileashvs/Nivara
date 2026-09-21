import { api, clean } from './client'

/** GET /notifications — any role. Newest first; filter with is_read. */
export const listNotifications = (params) =>
  api.get('/notifications', { params: clean(params) }).then((r) => r.data)

/** GET /notifications/unread-count → { unread }. */
export const getUnreadCount = () => api.get('/notifications/unread-count').then((r) => r.data)

/** POST /notifications/{id}/read */
export const markRead = (id) => api.post(`/notifications/${id}/read`).then((r) => r.data)

/** POST /notifications/read-all */
export const markAllRead = () => api.post('/notifications/read-all').then((r) => r.data)
