import {
  createContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import { apiBaseUrl } from '../api/client'
import { getHealth } from '../api/health'

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

export function LiveMarketProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LiveState | null>(null)
  const [connection, setConnection] =
    useState<LiveConnectionState>('DISCONNECTED')
  const retry = useRef(500)
  const socket = useRef<WebSocket | null>(null)
  const stopped = useRef(false)

  useEffect(() => {
    stopped.current = false
    let cancelled = false
    let healthTimer: number | undefined
    let reconnectTimer: number | undefined

    const connect = () => {
      if (cancelled || stopped.current) {
        return
      }

      setConnection(retry.current === 500 ? 'CONNECTING' : 'RECONNECTING')
      const parsedApiUrl = new URL(apiBaseUrl)
      const websocketProtocol =
        parsedApiUrl.protocol === 'https:' ? 'wss:' : 'ws:'
      const websocket = new WebSocket(
        `${websocketProtocol}//${parsedApiUrl.host}/api/v1/ws/market`,
      )
      socket.current = websocket

      websocket.onopen = () => {
        setConnection('CONNECTED')
        retry.current = 500
      }
      websocket.onmessage = (event) => {
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
        } catch {
          // Ignore malformed provider messages and retain the last valid state.
        }
      }
      websocket.onclose = () => {
        if (!stopped.current) {
          setConnection('RECONNECTING')
          reconnectTimer = window.setTimeout(connect, retry.current)
          retry.current = Math.min(retry.current * 2, 10000)
        }
      }
      websocket.onerror = () => websocket.close()
    }

    const checkLiveAvailability = async (attempt: number) => {
      try {
        const health = await getHealth()
        if (cancelled) {
          return
        }

        if (health.enabled && health.configured) {
          connect()
          return
        }

        setConnection('DISCONNECTED')
      } catch {
        if (cancelled) {
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

    void checkLiveAvailability(0)

    return () => {
      cancelled = true
      stopped.current = true
      if (healthTimer !== undefined) {
        window.clearTimeout(healthTimer)
      }
      if (reconnectTimer !== undefined) {
        window.clearTimeout(reconnectTimer)
      }
      socket.current?.close()
      setConnection('DISCONNECTED')
    }
  }, [])

  const value = useMemo(
    () => ({ state, connection }),
    [state, connection],
  )

  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>
}

export { LiveContext }
