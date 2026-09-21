import { useCallback, useEffect, useState } from 'react'
import { getUnreadCount } from '../api/notifications'
import { useAuth } from '../context/AuthContext'

/** Unread badge, sourced from GET /notifications/unread-count and polled gently. */
export function useUnreadCount(intervalMs = 60000) {
  const { isAuthenticated } = useAuth()
  const [unread, setUnread] = useState(0)

  const refresh = useCallback(async () => {
    if (!isAuthenticated) return
    try {
      const data = await getUnreadCount()
      setUnread(data.unread ?? 0)
    } catch {
      // A failing badge must never interrupt the page.
    }
  }, [isAuthenticated])

  useEffect(() => {
    if (!isAuthenticated) {
      setUnread(0)
      return undefined
    }
    refresh()
    const id = window.setInterval(refresh, intervalMs)
    return () => window.clearInterval(id)
  }, [isAuthenticated, refresh, intervalMs])

  return { unread, refresh, setUnread }
}
