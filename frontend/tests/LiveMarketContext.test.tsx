import { StrictMode } from 'react'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getHealth, type HealthResponse } from '../src/api/health'
import { LiveMarketProvider } from '../src/live/LiveMarketContext'
import { useLiveMarket } from '../src/live/useLiveMarket'

vi.mock('../src/api/health', () => ({
  getHealth: vi.fn(),
}))

const getHealthMock = vi.mocked(getHealth)

class MockWebSocket {
  static instances: MockWebSocket[] = []

  readonly url: string
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onerror: (() => void) | null = null
  close = vi.fn()

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }
}

function health(overrides: Partial<HealthResponse> = {}): HealthResponse {
  return {
    status: 'ok',
    service: 'marketmitra-api',
    market_data_source: 'postgres',
    database_status: 'connected',
    market_status: 'CLOSED',
    data_freshness: 'HISTORICAL',
    market_snapshot_date: null,
    last_ingestion: null,
    provider: 'unconfigured',
    enabled: false,
    configured: false,
    connection_status: 'DISCONNECTED',
    failure_count: 0,
    circuit_state: 'CLOSED',
    ...overrides,
  }
}

const liveHealth = health({
  provider: 'authorized_provider',
  enabled: true,
  configured: true,
  connection_status: 'CONNECTED',
  data_freshness: 'LIVE',
})

function LiveStateObserver() {
  const { connection, state } = useLiveMarket()
  return (
    <>
      <span data-testid="connection">{connection}</span>
      <span data-testid="provider">{state?.provider ?? 'none'}</span>
      <span data-testid="quote">{state?.quotes.TEST?.ltp ?? 'none'}</span>
    </>
  )
}

function renderProvider(child = <LiveStateObserver />) {
  return render(<LiveMarketProvider>{child}</LiveMarketProvider>)
}

function setOnline(value: boolean) {
  vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(value)
}

async function renderLiveProvider() {
  getHealthMock.mockResolvedValue(liveHealth)
  const view = renderProvider()
  await act(async () => {
    await Promise.resolve()
  })
  expect(MockWebSocket.instances).toHaveLength(1)
  return view
}

beforeEach(() => {
  getHealthMock.mockReset()
  MockWebSocket.instances = []
  vi.stubGlobal('WebSocket', MockWebSocket)
  setOnline(true)
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('LiveMarketProvider conditional activation', () => {
  it('creates no WebSocket in historical mode', async () => {
    getHealthMock.mockResolvedValue(health())
    renderProvider()

    await waitFor(() => expect(getHealthMock).toHaveBeenCalledTimes(1))
    expect(MockWebSocket.instances).toHaveLength(0)
    expect(screen.getByTestId('connection').textContent).toBe('DISCONNECTED')
    expect(screen.getByTestId('provider').textContent).toBe('none')
  })

  it('creates one WebSocket when live mode is enabled and configured', async () => {
    getHealthMock.mockResolvedValue(liveHealth)
    renderProvider()

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1))
    expect(MockWebSocket.instances[0].url).toBe(
      'ws://127.0.0.1:8000/api/v1/ws/market',
    )
    expect(screen.getByTestId('connection').textContent).toBe('CONNECTING')
  })

  it('does not connect when live mode is enabled but unconfigured', async () => {
    getHealthMock.mockResolvedValue(
      health({ enabled: true, configured: false, provider: 'unconfigured' }),
    )
    renderProvider()

    await waitFor(() => expect(getHealthMock).toHaveBeenCalledTimes(1))
    expect(MockWebSocket.instances).toHaveLength(0)
  })

  it('does not connect or poll when live mode is disabled', async () => {
    vi.useFakeTimers()
    getHealthMock.mockResolvedValue(
      health({
        enabled: false,
        configured: true,
        provider: 'authorized_provider',
      }),
    )

    renderProvider()
    await act(async () => {
      await Promise.resolve()
      await vi.runAllTimersAsync()
    })

    expect(getHealthMock).toHaveBeenCalledTimes(1)
    expect(MockWebSocket.instances).toHaveLength(0)
  })

  it('bounds failed health checks and never opens a WebSocket', async () => {
    vi.useFakeTimers()
    getHealthMock.mockRejectedValue(new Error('health unavailable'))

    renderProvider()
    await act(async () => {
      await Promise.resolve()
      await vi.runAllTimersAsync()
    })

    expect(getHealthMock).toHaveBeenCalledTimes(3)
    expect(MockWebSocket.instances).toHaveLength(0)
    expect(screen.getByTestId('connection').textContent).toBe('DISCONNECTED')
  })

  it('ignores a live health response that resolves after unmount', async () => {
    let resolveHealth: ((response: HealthResponse) => void) | undefined
    getHealthMock.mockReturnValue(
      new Promise((resolve) => {
        resolveHealth = resolve
      }),
    )
    const view = renderProvider()

    view.unmount()
    await act(async () => {
      resolveHealth?.(liveHealth)
      await Promise.resolve()
    })

    expect(MockWebSocket.instances).toHaveLength(0)
  })

  it('continues rendering historical REST-backed children', async () => {
    getHealthMock.mockResolvedValue(health())
    renderProvider(<main>Historical REST content</main>)

    await waitFor(() => expect(getHealthMock).toHaveBeenCalledTimes(1))
    expect(screen.getByText('Historical REST content')).toBeTruthy()
    expect(MockWebSocket.instances).toHaveLength(0)
  })

  it('preserves snapshot, quote-update, and heartbeat handling', async () => {
    getHealthMock.mockResolvedValue(liveHealth)
    renderProvider()
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1))

    const websocket = MockWebSocket.instances[0]
    act(() => {
      websocket.onopen?.()
      websocket.onmessage?.({
        data: JSON.stringify({
          type: 'snapshot',
          data: {
            provider: 'authorized_provider',
            market_status: 'OPEN',
            data_freshness: 'LIVE',
            quotes: {
              TEST: { ltp: 105, change: 5, change_percent: 5 },
            },
          },
        }),
      })
      websocket.onmessage?.({
        data: JSON.stringify({
          type: 'quote_update',
          data: {
            symbol: 'TEST',
            ltp: 106,
            change: 6,
            change_percent: 6,
          },
        }),
      })
      websocket.onmessage?.({ data: JSON.stringify({ type: 'heartbeat' }) })
    })

    expect(screen.getByTestId('connection').textContent).toBe('CONNECTED')
    expect(screen.getByTestId('provider').textContent).toBe(
      'authorized_provider',
    )
    expect(screen.getByTestId('quote').textContent).toBe('106')
  })
})

describe('LiveMarketProvider reconnection lifecycle', () => {
  it('creates one socket across React Strict Mode effect cleanup', async () => {
    getHealthMock.mockResolvedValue(liveHealth)
    render(
      <StrictMode>
        <LiveMarketProvider>
          <LiveStateObserver />
        </LiveMarketProvider>
      </StrictMode>,
    )

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1))
  })

  it('detaches and ignores stale callbacks after cleanup', async () => {
    vi.useFakeTimers()
    const view = await renderLiveProvider()
    const websocket = MockWebSocket.instances[0]
    const staleClose = websocket.onclose
    const staleMessage = websocket.onmessage

    view.unmount()
    expect(websocket.onclose).toBeNull()
    expect(websocket.onmessage).toBeNull()
    act(() => {
      staleClose?.({ code: 1006 })
      staleMessage?.({
        data: JSON.stringify({ type: 'snapshot', data: { quotes: {} } }),
      })
    })
    await act(async () => vi.runAllTimersAsync())

    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('does not duplicate a connection while one is active', async () => {
    await renderLiveProvider()

    act(() => {
      window.dispatchEvent(new Event('online'))
      window.dispatchEvent(new Event('online'))
    })

    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('schedules only one retry for repeated close callbacks', async () => {
    vi.useFakeTimers()
    await renderLiveProvider()
    const close = MockWebSocket.instances[0].onclose

    act(() => {
      close?.({ code: 1006 })
      close?.({ code: 1006 })
    })
    await act(async () => vi.advanceTimersByTimeAsync(500))

    expect(MockWebSocket.instances).toHaveLength(2)
  })

  it('blocks connections while offline', async () => {
    setOnline(false)
    getHealthMock.mockResolvedValue(liveHealth)
    renderProvider()
    await act(async () => {
      await Promise.resolve()
    })

    expect(MockWebSocket.instances).toHaveLength(0)
    expect(screen.getByTestId('connection').textContent).toBe('DISCONNECTED')
  })

  it('makes exactly one connection attempt when connectivity returns', async () => {
    setOnline(false)
    getHealthMock.mockResolvedValue(liveHealth)
    renderProvider()
    await act(async () => {
      await Promise.resolve()
    })

    setOnline(true)
    act(() => {
      window.dispatchEvent(new Event('online'))
      window.dispatchEvent(new Event('online'))
    })

    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it.each([1000, 1002, 1003, 1007, 1008, 1009, 1010])(
    'does not retry terminal close code %i',
    async (code) => {
      vi.useFakeTimers()
      await renderLiveProvider()

      act(() => MockWebSocket.instances[0].onclose?.({ code }))
      await act(async () => vi.runAllTimersAsync())
      act(() => window.dispatchEvent(new Event('online')))

      expect(MockWebSocket.instances).toHaveLength(1)
      expect(screen.getByTestId('connection').textContent).toBe(
        'DISCONNECTED',
      )
    },
  )

  it('uses bounded exponential backoff and stops after four retries', async () => {
    vi.useFakeTimers()
    await renderLiveProvider()
    const delays = [500, 1000, 2000, 4000]

    for (const [index, delay] of delays.entries()) {
      act(() =>
        MockWebSocket.instances.at(-1)?.onclose?.({ code: 1006 }),
      )
      await act(async () => vi.advanceTimersByTimeAsync(delay - 1))
      expect(MockWebSocket.instances).toHaveLength(index + 1)
      await act(async () => vi.advanceTimersByTimeAsync(1))
    }

    expect(MockWebSocket.instances).toHaveLength(5)
    act(() =>
      MockWebSocket.instances.at(-1)?.onclose?.({ code: 1013 }),
    )
    await act(async () => vi.runAllTimersAsync())

    expect(MockWebSocket.instances).toHaveLength(5)
    expect(screen.getByTestId('connection').textContent).toBe('DISCONNECTED')
    expect(screen.getByTestId('provider').textContent).toBe('none')
  })

  it('resets backoff after a successful reconnection', async () => {
    vi.useFakeTimers()
    await renderLiveProvider()

    act(() => MockWebSocket.instances[0].onclose?.({ code: 1006 }))
    await act(async () => vi.advanceTimersByTimeAsync(500))
    act(() => MockWebSocket.instances[1].onopen?.())
    act(() => MockWebSocket.instances[1].onclose?.({ code: 1006 }))
    await act(async () => vi.advanceTimersByTimeAsync(499))
    expect(MockWebSocket.instances).toHaveLength(2)
    await act(async () => vi.advanceTimersByTimeAsync(1))

    expect(MockWebSocket.instances).toHaveLength(3)
  })

  it('cancels a pending reconnect when unmounted', async () => {
    vi.useFakeTimers()
    const view = await renderLiveProvider()

    act(() => MockWebSocket.instances[0].onclose?.({ code: 1006 }))
    view.unmount()
    await act(async () => vi.runAllTimersAsync())

    expect(MockWebSocket.instances).toHaveLength(1)
  })
})
