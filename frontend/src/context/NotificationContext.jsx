/**
 * Notification bell context — WebSocket primary, polling fallback.
 *
 * Strategy:
 *   1. On login, open a WebSocket to /ws/notifications/?token=<key>
 *   2. Server pushes {type:"notification", unread:<n>, ...} when a watched
 *      thread gets a new post — bell updates instantly, no round-trip needed.
 *   3. If the WebSocket is unavailable or drops, fall back to 60s polling
 *      (same behaviour as before this change) so Tor users and degraded
 *      connections still get notifications.
 *   4. On logout, close the socket and clear state.
 *
 * ActivityPub hook: when federated activities arrive they push to the same
 * channel group — this context needs no changes to handle them.
 */
import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react'
import api from '../api/client'
import { useAuth } from './AuthContext'

const POLL_MS = 60_000
const WS_RETRY_MS = 5_000   // retry WebSocket after 5s on unexpected close
const WS_MAX_RETRIES = 5     // give up after 5 attempts and stay on polling

const NotificationContext = createContext({ unread: 0, refresh: () => {} })

function getWsUrl() {
  const token = localStorage.getItem('token')
  if (!token) return null
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/notifications/?token=${token}`
}

export function NotificationProvider({ children }) {
  const { user } = useAuth()
  const [unread, setUnread] = useState(0)

  // Refs so callbacks always close over current values without re-renders
  const wsRef       = useRef(null)
  const pollTimer   = useRef(null)
  const retryTimer  = useRef(null)
  const retryCount  = useRef(0)
  const usingWs     = useRef(false)

  // ── Polling fallback ──────────────────────────────────────────────────────
  const refresh = useCallback(() => {
    const token = localStorage.getItem('token')
    if (!token) { setUnread(0); return }
    api.get('/me/notifications/unread-count/')
      .then(r => setUnread(r.data.unread || 0))
      .catch(() => {})
  }, [])

  const startPolling = useCallback(() => {
    clearInterval(pollTimer.current)
    refresh()
    pollTimer.current = setInterval(refresh, POLL_MS)
  }, [refresh])

  const stopPolling = useCallback(() => {
    clearInterval(pollTimer.current)
  }, [])

  // ── WebSocket ─────────────────────────────────────────────────────────────
  const closeWs = useCallback(() => {
    clearTimeout(retryTimer.current)
    if (wsRef.current) {
      wsRef.current.onclose = null   // prevent retry loop on manual close
      wsRef.current.close()
      wsRef.current = null
    }
    usingWs.current = false
  }, [])

  const connectWs = useCallback(() => {
    const url = getWsUrl()
    if (!url) return

    closeWs()

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      usingWs.current = true
      retryCount.current = 0
      stopPolling()        // WebSocket is up — stop polling
      refresh()            // sync count immediately on connect
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'notification' && typeof data.unread === 'number') {
          setUnread(data.unread)
        }
      } catch (_) {}
    }

    ws.onclose = (event) => {
      usingWs.current = false
      wsRef.current = null

      // 4001 = auth rejected — don't retry
      if (event.code === 4001) {
        startPolling()
        return
      }

      if (retryCount.current < WS_MAX_RETRIES) {
        retryCount.current += 1
        retryTimer.current = setTimeout(connectWs, WS_RETRY_MS)
      } else {
        // Exhausted retries — fall back to polling permanently for this session
        startPolling()
      }
    }

    ws.onerror = () => {
      // onclose fires after onerror — retry logic handled there
    }
  }, [closeWs, refresh, startPolling, stopPolling])

  // ── Lifecycle ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!user) {
      closeWs()
      stopPolling()
      setUnread(0)
      return
    }

    // Try WebSocket first; polling is the fallback
    connectWs()

    return () => {
      closeWs()
      stopPolling()
    }
  }, [user?.id])  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <NotificationContext.Provider value={{ unread, refresh }}>
      {children}
    </NotificationContext.Provider>
  )
}

export const useNotifications = () => useContext(NotificationContext)
