import { api, clean } from './client'

/** GET /notifications — any role. Filter by is_read and category. */
export const listNotifications = (params) =>
  api.get('/notifications', { params: clean(params) }).then((r) => r.data)

/** GET /notifications/unread-count → { unread }. */
export const getUnreadCount = (category) =>
  api.get('/notifications/unread-count', { params: clean({ category }) }).then((r) => r.data)

/** PATCH /notifications/{id}/read */
export const markRead = (id) =>
  api.patch(`/notifications/${id}/read`).then((r) => r.data)

/** PATCH /notifications/read-all */
export const markAllRead = (category) =>
  api.patch('/notifications/read-all', null, { params: clean({ category }) }).then((r) => r.data)

/** DELETE /notifications/{id} */
export const deleteNotification = (id) =>
  api.delete(`/notifications/${id}`).then((r) => r.data)

/** GET /notifications/preferences */
export const getNotificationPreferences = () =>
  api.get('/notifications/preferences').then((r) => r.data)

/** PUT /notifications/preferences */
export const updateNotificationPreferences = (payload) =>
  api.put('/notifications/preferences', payload).then((r) => r.data)
