import { useEffect, useRef, useCallback } from 'react'
import { getNotificationsWsUrl, getToken } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'

/**
 * Real-time notification WebSocket hook.
 *
 * Connects to /api/v1/notifications/ws using the active JWT access token.
 * Reconnects automatically with exponential backoff if disconnected.
 * Dispatches a custom window event 'nivara:notification' when an event arrives
 * so that unread badges, popovers, and notification lists update live.
 */
export function useNotificationsWebSocket() {
  const { isAuthenticated } = useAuth()
  const toast = useToast()
  const socketRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const retryCountRef = useRef(0)
  const pingIntervalRef = useRef(null)

  const connect = useCallback(() => {
    if (!isAuthenticated) return

    const token = getToken()
    if (!token) return

    // Clean up existing socket if any
    if (socketRef.current) {
      try {
        socketRef.current.close()
      } catch {
        // Ignore close error
      }
      socketRef.current = null
    }

    const wsUrl = getNotificationsWsUrl(token)

    try {
      const ws = new WebSocket(wsUrl)
      socketRef.current = ws

      ws.onopen = () => {
        retryCountRef.current = 0
        // Periodic ping to keep connection alive across proxies
        pingIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping')
          }
        }, 30000)
      }

      ws.onmessage = (event) => {
        try {
          if (event.data === 'pong') return
          const payload = JSON.parse(event.data)

          if (payload.event === 'notification') {
            const notif = payload.data
            // Notify other hooks / components
            window.dispatchEvent(
              new CustomEvent('nivara:notification', { detail: notif }),
            )

            // Optional non-intrusive toast alert
            if (notif?.title) {
              toast.info(notif.title)
            }
          } else if (payload.event === 'system_announcement') {
            const ann = payload.data
            window.dispatchEvent(
              new CustomEvent('nivara:announcement', { detail: ann }),
            )
            if (ann?.title) {
              toast.info(`Announcement: ${ann.title}`)
            }
          }
        } catch {
          // Ignore malformed payloads
        }
      }

      ws.onclose = () => {
        if (pingIntervalRef.current) {
          window.clearInterval(pingIntervalRef.current)
          pingIntervalRef.current = null
        }
        socketRef.current = null

        // Exponential backoff reconnection: min 2s, max 30s
        if (isAuthenticated) {
          const delay = Math.min(2000 * Math.pow(1.5, retryCountRef.current), 30000)
          retryCountRef.current += 1
          reconnectTimeoutRef.current = window.setTimeout(connect, delay)
        }
      }

      ws.onerror = () => {
        try {
          ws.close()
        } catch {
          // Ignore error on close
        }
      }
    } catch {
      // WebSocket initialization error; fallback to polling
    }
  }, [isAuthenticated, toast])

  useEffect(() => {
    if (isAuthenticated) {
      connect()
    }

    return () => {
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current)
      }
      if (pingIntervalRef.current) {
        window.clearInterval(pingIntervalRef.current)
      }
      if (socketRef.current) {
        try {
          socketRef.current.close()
        } catch {
          // Ignore
        }
        socketRef.current = null
      }
    }
  }, [isAuthenticated, connect])
}
