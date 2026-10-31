import {
  createContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { apiBaseUrl } from '../api/client'
import { getHealth } from '../api/health'
import { toWebSocketUrl } from '../config/runtime'

export type LiveConnectionState =
  | 'CONNECTING'
  | 'CONNECTED'
  | 'RECONNECTING'
  | 'DISCONNECTED'

type LiveQuote = {
  ltp?: number | null
  change_percent?: number | null
  change?: number | null
  open?: number | null
  high?: number | null
  low?: number | null
  volume?: number | null
  turnover?: number | null
  provider_timestamp?: string | null
}

export type LiveState = {
  provider: string
  market_status: string
  data_freshness: string
  index?: number | null
  quotes: Record<string, LiveQuote>
}

type LiveContextValue = {
  state: LiveState | null
  connection: LiveConnectionState
}

const LiveContext = createContext<LiveContextValue>({
  state: null,
  connection: 'DISCONNECTED',
})

const HEALTH_RETRY_DELAYS_MS = [250, 1000] as const
const RECONNECT_DELAYS_MS = [500, 1000, 2000, 4000] as const

// These close codes describe transient conditions where another attempt can help.
// Protocol, payload, policy, extension, normal, and unknown failures are terminal.
const RETRYABLE_CLOSE_CODES = new Set([1001, 1006, 1011, 1012, 1013, 1014])

export function LiveMarketProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LiveState | null>(null)
  const [connection, setConnection] =
    useState<LiveConnectionState>('DISCONNECTED')

  useEffect(() => {
    let disposed = false
    let liveMode = false
    let activeSocket: WebSocket | null = null
    let healthTimer: number | undefined
    let reconnectTimer: number | undefined
    let retryAttempt = 0
    let resumeWhenOnline = false

    const clearReconnectTimer = () => {
      if (reconnectTimer !== undefined) {
        window.clearTimeout(reconnectTimer)
        reconnectTimer = undefined
      }
    }

    const isCurrentSocket = (websocket: WebSocket) =>
      !disposed && activeSocket === websocket

    const detachSocket = (websocket: WebSocket) => {
      websocket.onopen = null
      websocket.onmessage = null
      websocket.onclose = null
      websocket.onerror = null
      if (activeSocket === websocket) {
        activeSocket = null
      }
    }

    const closeActiveSocket = () => {
      const websocket = activeSocket
      if (websocket === null) {
        return
      }

      detachSocket(websocket)
      websocket.close()
    }

    const scheduleReconnect = (connect: () => void) => {
      if (
        disposed ||
        activeSocket !== null ||
        reconnectTimer !== undefined ||
        !navigator.onLine
      ) {
        return
      }

      const delay = RECONNECT_DELAYS_MS[retryAttempt]
      if (delay === undefined) {
        setConnection('DISCONNECTED')
        return
      }

      retryAttempt += 1
      setConnection('RECONNECTING')
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = undefined
        connect()
      }, delay)
    }

    const connect = () => {
      if (disposed || !liveMode || activeSocket !== null) {
        return
      }
      if (!navigator.onLine) {
        resumeWhenOnline = true
        setConnection('DISCONNECTED')
        return
      }

      clearReconnectTimer()
      setConnection(retryAttempt === 0 ? 'CONNECTING' : 'RECONNECTING')

      const websocket = new WebSocket(toWebSocketUrl(apiBaseUrl))
      activeSocket = websocket

      websocket.onopen = () => {
        if (!isCurrentSocket(websocket)) {
          return
        }

        retryAttempt = 0
        resumeWhenOnline = false
        setConnection('CONNECTED')
      }

      websocket.onmessage = (event) => {
        if (!isCurrentSocket(websocket)) {
          return
        }

        try {
          const message = JSON.parse(event.data)
          if (message.type === 'snapshot') {
            setState(message.data)
          }
          if (message.type === 'quote_update') {
            setState((previous) =>
              previous
                ? {
                    ...previous,
                    quotes: {
                      ...previous.quotes,
                      [message.data.symbol]: message.data,
                    },
                  }
                : previous,
            )
          }
          // Heartbeats intentionally require no state update.
        } catch {
          // Ignore malformed provider messages and retain the last valid state.
        }
      }

      websocket.onclose = (event) => {
        if (!isCurrentSocket(websocket)) {
          return
        }

        detachSocket(websocket)
        setState(null)

        if (!RETRYABLE_CLOSE_CODES.has(event.code)) {
          resumeWhenOnline = false
          setConnection('DISCONNECTED')
          return
        }

        if (!navigator.onLine) {
          resumeWhenOnline = true
          setConnection('DISCONNECTED')
          return
        }

        scheduleReconnect(connect)
      }

      websocket.onerror = () => {
        // The browser follows a WebSocket error with a close event. The close
        // code is the single source of truth for the retry decision.
      }
    }

    const handleOffline = () => {
      if (disposed || !liveMode) {
        return
      }

      resumeWhenOnline = true
      clearReconnectTimer()
      closeActiveSocket()
      setState(null)
      setConnection('DISCONNECTED')
    }

    const handleOnline = () => {
      if (
        disposed ||
        !liveMode ||
        !resumeWhenOnline ||
        activeSocket !== null ||
        reconnectTimer !== undefined
      ) {
        return
      }

      resumeWhenOnline = false
      retryAttempt = 0
      connect()
    }

    const checkLiveAvailability = async (attempt: number) => {
      try {
        const health = await getHealth()
        if (disposed) {
          return
        }

        if (health.enabled && health.configured) {
          liveMode = true
          connect()
          return
        }

        setConnection('DISCONNECTED')
      } catch {
        if (disposed) {
          return
        }

        const retryDelay = HEALTH_RETRY_DELAYS_MS[attempt]
        if (retryDelay === undefined) {
          setConnection('DISCONNECTED')
          return
        }

        healthTimer = window.setTimeout(
          () => void checkLiveAvailability(attempt + 1),
          retryDelay,
        )
      }
    }

    window.addEventListener('offline', handleOffline)
    window.addEventListener('online', handleOnline)
    void checkLiveAvailability(0)

    return () => {
      disposed = true
      window.removeEventListener('offline', handleOffline)
      window.removeEventListener('online', handleOnline)
      if (healthTimer !== undefined) {
        window.clearTimeout(healthTimer)
      }
      clearReconnectTimer()
      closeActiveSocket()
    }
  }, [])

  const value = useMemo(
    () => ({ state, connection }),
    [state, connection],
  )

  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>
}

export { LiveContext }
