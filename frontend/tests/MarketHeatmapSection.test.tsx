import { StrictMode } from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getMarketHeatmap } from '../src/api/market'
import MarketHeatmapSection from '../src/components/MarketHeatmapSection'
import { useLiveMarket } from '../src/live/useLiveMarket'
import MarketHeatmapPage from '../src/pages/MarketHeatmapPage'
import type { LiveState } from '../src/live/LiveMarketContext'
import type { HeatmapItem } from '../src/types/market'

vi.mock('../src/api/market', () => ({
  getMarketHeatmap: vi.fn(),
}))

vi.mock('../src/live/useLiveMarket', () => ({
  useLiveMarket: vi.fn(),
}))

const getMarketHeatmapMock = vi.mocked(getMarketHeatmap)
const useLiveMarketMock = vi.mocked(useLiveMarket)

const items: HeatmapItem[] = [
  {
    symbol: 'NABIL',
    company_name: 'Nabil Bank',
    sector: 'Commercial Banks',
    ltp: 1_000,
    change: 25,
    change_percent: 2.5,
    volume: 10_000,
    turnover: 2_000_000,
    observation_date: '2026-10-29',
    weight_metric: 'equal',
  },
  {
    symbol: 'NLIC',
    company_name: 'Nepal Life Insurance',
    sector: 'Life Insurance',
    ltp: 800,
    change: -16,
    change_percent: -2,
    volume: 8_000,
    turnover: 1_500_000,
    observation_date: '2026-10-29',
    weight_metric: 'equal',
  },
  {
    symbol: 'API',
    company_name: 'Api Power',
    sector: 'Hydropower',
    ltp: 300,
    change: 0,
    change_percent: 0,
    volume: 6_000,
    turnover: 900_000,
    observation_date: '2026-10-29',
    weight_metric: 'equal',
  },
]

let liveState: LiveState | null

function renderPage(node = <MarketHeatmapPage />) {
  return render(<MemoryRouter>{node}</MemoryRouter>)
}

beforeEach(() => {
  liveState = null
  getMarketHeatmapMock.mockReset()
  useLiveMarketMock.mockImplementation(() => ({
    state: liveState,
    connection: liveState ? 'CONNECTED' : 'DISCONNECTED',
  }))
})

afterEach(() => {
  cleanup()
})

describe('MarketHeatmapSection', () => {
  it('preserves sector filtering and heatmap categorization', () => {
    renderPage(<MarketHeatmapSection items={items} />)

    expect(screen.getByText('NABIL')).toBeTruthy()
    expect(screen.getByText('NLIC')).toBeTruthy()
    expect(screen.getByText('+2.50%').closest('a')?.style.backgroundColor).toBe(
      'rgb(5, 150, 105)',
    )
    expect(screen.getByText('-2.00%').closest('a')?.style.backgroundColor).toBe(
      'rgb(190, 18, 60)',
    )

    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by sector' }), {
      target: { value: 'Life Insurance' },
    })

    expect(screen.queryByText('NABIL')).toBeNull()
    expect(screen.getByText('NLIC')).toBeTruthy()
    expect(screen.queryByText('API')).toBeNull()
  })

  it('renders the section-level empty state with missing optional data', () => {
    renderPage(<MarketHeatmapSection items={[]} />)

    expect(screen.getByText('No active trading stocks in this view.')).toBeTruthy()
  })
})

describe('MarketHeatmapPage consumer integration', () => {
  it('loads and renders the complete historical REST heatmap while disconnected', async () => {
    getMarketHeatmapMock.mockResolvedValue(items)

    renderPage()

    expect(document.querySelector('[aria-busy="true"]')).not.toBeNull()
    expect(await screen.findByText('NABIL')).toBeTruthy()
    expect(screen.getByText('NLIC')).toBeTruthy()
    expect(screen.getByText('API')).toBeTruthy()
    expect(getMarketHeatmapMock).toHaveBeenCalledTimes(1)
  })

  it('overlays only known quoted symbols and retains REST values for missing quote fields', async () => {
    liveState = {
      provider: 'DEVELOPMENT_REPLAY',
      market_status: 'OPEN',
      data_freshness: 'LIVE',
      quotes: {
        NABIL: {
          ltp: null,
          change_percent: 4.25,
          provider_timestamp: '2026-10-31T10:00:00+05:45',
        },
        UNKNOWN: { ltp: 999, change_percent: 9.99 },
      },
    }
    getMarketHeatmapMock.mockResolvedValue(items)

    renderPage()

    expect(await screen.findByText('NABIL')).toBeTruthy()
    expect(screen.getByText('+4.25%')).toBeTruthy()
    expect(screen.getByText(/NPR\s*1,000/)).toBeTruthy()
    expect(screen.queryByText('NLIC')).toBeNull()
    expect(screen.queryByText('UNKNOWN')).toBeNull()
    expect(screen.getByText('DEVELOPMENT REPLAY · Current quotes')).toBeTruthy()
  })

  it('falls back on disconnect and reapplies current quotes on reconnect without refetching', async () => {
    liveState = {
      provider: 'authorized_provider',
      market_status: 'OPEN',
      data_freshness: 'LIVE',
      quotes: { NABIL: { ltp: 1_100, change_percent: 5 } },
    }
    getMarketHeatmapMock.mockResolvedValue(items)
    const view = renderPage()

    expect(await screen.findByText('+5.00%')).toBeTruthy()
    expect(screen.queryByText('NLIC')).toBeNull()

    liveState = null
    view.rerender(
      <MemoryRouter>
        <MarketHeatmapPage />
      </MemoryRouter>,
    )

    expect(screen.getByText('+2.50%')).toBeTruthy()
    expect(screen.getByText('NLIC')).toBeTruthy()

    liveState = {
      provider: 'authorized_provider',
      market_status: 'OPEN',
      data_freshness: 'LIVE',
      quotes: { NLIC: { ltp: 840, change_percent: 1.5 } },
    }
    view.rerender(
      <MemoryRouter>
        <MarketHeatmapPage />
      </MemoryRouter>,
    )

    expect(screen.getByText('NLIC')).toBeTruthy()
    expect(screen.getByText('+1.50%')).toBeTruthy()
    expect(screen.queryByText('NABIL')).toBeNull()
    expect(getMarketHeatmapMock).toHaveBeenCalledTimes(1)
  })

  it('uses the latest context update without duplicating a security', async () => {
    liveState = {
      provider: 'authorized_provider',
      market_status: 'OPEN',
      data_freshness: 'LIVE',
      quotes: {
        NABIL: {
          ltp: 1_100,
          change_percent: 5,
          provider_timestamp: '2026-10-31T10:01:00+05:45',
        },
      },
    }
    getMarketHeatmapMock.mockResolvedValue(items)
    const view = renderPage()
    expect(await screen.findByText('+5.00%')).toBeTruthy()

    liveState = {
      ...liveState,
      quotes: {
        NABIL: {
          ltp: 1_050,
          change_percent: 3,
          provider_timestamp: '2026-10-31T10:00:00+05:45',
        },
      },
    }
    view.rerender(
      <MemoryRouter>
        <MarketHeatmapPage />
      </MemoryRouter>,
    )

    expect(screen.queryByText('+5.00%')).toBeNull()
    expect(screen.getByText('+3.00%')).toBeTruthy()
    expect(screen.getAllByText('NABIL')).toHaveLength(1)
  })

  it('shows empty and retryable error states from the REST consumer', async () => {
    getMarketHeatmapMock.mockResolvedValueOnce([])
    const emptyView = renderPage()
    expect(await screen.findByText('No heatmap data is available.')).toBeTruthy()
    emptyView.unmount()

    getMarketHeatmapMock
      .mockRejectedValueOnce(new Error('unavailable'))
      .mockResolvedValueOnce(items)
    renderPage()
    expect(await screen.findByText('Unable to load the market dashboard.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Retry request' }))

    expect(await screen.findByText('NABIL')).toBeTruthy()
  })

  it('does not duplicate the REST request under React Strict Mode', async () => {
    getMarketHeatmapMock.mockResolvedValue(items)

    renderPage(
      <StrictMode>
        <MarketHeatmapPage />
      </StrictMode>,
    )

    expect(await screen.findByText('NABIL')).toBeTruthy()
    await waitFor(() => expect(getMarketHeatmapMock).toHaveBeenCalledTimes(1))
  })
})
