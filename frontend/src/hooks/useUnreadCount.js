import { useCallback, useEffect, useState } from 'react'
import { getUnreadCount } from '../api/notifications'
import { useAuth } from '../context/AuthContext'

/** Unread badge, updated live via WebSocket and polled gently as fallback. */
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

    const handleRealtimeUpdate = () => {
      refresh()
    }

    window.addEventListener('nivara:notification', handleRealtimeUpdate)
    window.addEventListener('nivara:notification-read', handleRealtimeUpdate)

    const id = window.setInterval(refresh, intervalMs)
    return () => {
      window.removeEventListener('nivara:notification', handleRealtimeUpdate)
      window.removeEventListener('nivara:notification-read', handleRealtimeUpdate)
      window.clearInterval(id)
    }
  }, [isAuthenticated, refresh, intervalMs])

  return { unread, refresh, setUnread }
}
