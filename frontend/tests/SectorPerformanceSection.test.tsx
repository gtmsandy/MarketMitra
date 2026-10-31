import { StrictMode } from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getSectorAnalytics } from '../src/api/market'
import SectorPerformanceSection from '../src/components/SectorPerformanceSection'
import { useLiveMarket } from '../src/live/useLiveMarket'
import SectorPerformancePage from '../src/pages/SectorPerformancePage'
import type { SectorPerformance } from '../src/types/market'

vi.mock('../src/api/market', () => ({
  getSectorAnalytics: vi.fn(),
}))

vi.mock('../src/live/useLiveMarket', () => ({
  useLiveMarket: vi.fn(),
}))

const getSectorAnalyticsMock = vi.mocked(getSectorAnalytics)
const useLiveMarketMock = vi.mocked(useLiveMarket)

const sectors: SectorPerformance[] = [
  {
    sector: 'Commercial Banks',
    stock_count: 2,
    advancing_count: 1,
    declining_count: 1,
    unchanged_count: 0,
    average_change_percent: 1.25,
    total_volume: 12_500,
    total_turnover: 2_500_000,
    observation_date: '2026-10-29',
    methodology: 'constituent_percent_average',
  },
  {
    sector: 'Hydropower',
    stock_count: 1,
    advancing_count: 0,
    declining_count: 0,
    unchanged_count: 1,
    average_change_percent: 0,
    total_volume: 4_000,
    total_turnover: 750_000,
    observation_date: '2026-10-29',
    methodology: 'constituent_percent_average',
  },
]

beforeEach(() => {
  getSectorAnalyticsMock.mockReset()
  useLiveMarketMock.mockReturnValue({
    state: null,
    connection: 'DISCONNECTED',
  })
})

afterEach(() => {
  cleanup()
})

describe('SectorPerformanceSection', () => {
  it('renders the historical sector calculation and its methodology', () => {
    render(<SectorPerformanceSection sectors={sectors} />)

    expect(screen.getByText('Commercial Banks')).toBeTruthy()
    expect(screen.getByText('+1.25%')).toBeTruthy()
    expect(screen.getByText('2 stocks')).toBeTruthy()
    expect(screen.getByText('12,500')).toBeTruthy()
    expect(screen.getByText('Methodology: Constituent % Average')).toBeTruthy()
  })

  it('renders the section-level empty state', () => {
    render(<SectorPerformanceSection sectors={[]} />)

    expect(screen.getByText('No sector performance data available.')).toBeTruthy()
  })
})

describe('SectorPerformancePage consumer integration', () => {
  it('loads and renders REST-backed sectors while disconnected', async () => {
    getSectorAnalyticsMock.mockResolvedValue(sectors)

    render(<SectorPerformancePage />)

    expect(document.querySelector('[aria-busy="true"]')).not.toBeNull()
    expect(await screen.findByText('Commercial Banks')).toBeTruthy()
    expect(getSectorAnalyticsMock).toHaveBeenCalledTimes(1)
    expect(screen.queryByText(/Live values use/)).toBeNull()
  })

  it('keeps server-calculated sector values intact when live quotes exist', async () => {
    useLiveMarketMock.mockReturnValue({
      connection: 'CONNECTED',
      state: {
        provider: 'authorized_provider',
        market_status: 'OPEN',
        data_freshness: 'LIVE',
        quotes: {
          NABIL: { ltp: 1_100, change_percent: 9.75 },
          API: { ltp: 320, change_percent: -4.5 },
        },
      },
    })
    getSectorAnalyticsMock.mockResolvedValue(sectors)

    render(<SectorPerformancePage />)

    expect(await screen.findByText('+1.25%')).toBeTruthy()
    expect(screen.getByText('0.00%')).toBeTruthy()
    expect(
      screen.getByText('Live values use current quoted equity constituents only.'),
    ).toBeTruthy()
  })

  it('shows the page empty state for an empty REST response', async () => {
    getSectorAnalyticsMock.mockResolvedValue([])

    render(<SectorPerformancePage />)

    expect(await screen.findByText('No sector data is available.')).toBeTruthy()
  })

  it('shows an error and retries the REST fallback', async () => {
    getSectorAnalyticsMock
      .mockRejectedValueOnce(new Error('unavailable'))
      .mockResolvedValueOnce(sectors)

    render(<SectorPerformancePage />)

    expect(await screen.findByText('Unable to load the market dashboard.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Retry request' }))

    expect(await screen.findByText('Commercial Banks')).toBeTruthy()
    expect(getSectorAnalyticsMock).toHaveBeenCalledTimes(2)
  })

  it('does not duplicate the REST request under React Strict Mode', async () => {
    getSectorAnalyticsMock.mockResolvedValue(sectors)

    render(
      <StrictMode>
        <SectorPerformancePage />
      </StrictMode>,
    )

    expect(await screen.findByText('Commercial Banks')).toBeTruthy()
    await waitFor(() => expect(getSectorAnalyticsMock).toHaveBeenCalledTimes(1))
  })
})
