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
  onclose: (() => void) | null = null
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

beforeEach(() => {
  getHealthMock.mockReset()
  MockWebSocket.instances = []
  vi.stubGlobal('WebSocket', MockWebSocket)
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
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
    getHealthMock.mockResolvedValue(
      health({
        provider: 'authorized_provider',
        enabled: true,
        configured: true,
        connection_status: 'CONNECTED',
        data_freshness: 'LIVE',
      }),
    )

    renderProvider()

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1))
    expect(MockWebSocket.instances[0].url).toBe('ws://127.0.0.1:8000/api/v1/ws/market')
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
      health({ enabled: false, configured: true, provider: 'authorized_provider' }),
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
      resolveHealth?.(
        health({
          provider: 'authorized_provider',
          enabled: true,
          configured: true,
          connection_status: 'CONNECTED',
          data_freshness: 'LIVE',
        }),
      )
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

  it('keeps the existing snapshot handling contract', async () => {
    getHealthMock.mockResolvedValue(
      health({
        provider: 'authorized_provider',
        enabled: true,
        configured: true,
        connection_status: 'CONNECTED',
        data_freshness: 'LIVE',
      }),
    )
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
    })

    expect(screen.getByTestId('connection').textContent).toBe('CONNECTED')
    expect(screen.getByTestId('provider').textContent).toBe('authorized_provider')
    expect(screen.getByTestId('quote').textContent).toBe('105')
  })
})
