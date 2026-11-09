import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getMarketBreadth,
  getMarketOverview,
  getStockDetail,
  getStockHistory,
  getTopGainers,
  getTopLosers,
} from '../src/api/market'
import AppHeader from '../src/components/AppHeader'
import { useLiveMarket } from '../src/live/useLiveMarket'
import DashboardPage from '../src/pages/DashboardPage'
import StockDetailPage from '../src/pages/StockDetailPage'
import type { MarketOverview } from '../src/types/market'

vi.mock('../src/api/market', () => ({
  getMarketBreadth: vi.fn(),
  getMarketOverview: vi.fn(),
  getStockDetail: vi.fn(),
  getStockHistory: vi.fn(),
  getStockIntraday: vi.fn(),
  getTopGainers: vi.fn(),
  getTopLosers: vi.fn(),
}))

vi.mock('../src/components/PriceChart', () => ({
  default: () => <div>Price chart</div>,
}))

vi.mock('../src/live/useLiveMarket', () => ({
  useLiveMarket: vi.fn(),
}))

const overview: MarketOverview = {
  nepse_index: 2_786.42,
  index_change: 21.35,
  index_change_percent: 0.77,
  turnover: 552_907_933,
  total_volume: 1_241_890,
  total_transactions: 38_640,
  market_status: 'Open',
  last_updated: '2026-09-03T11:30:00+05:45',
  observation_date: '2026-09-03',
  data_freshness: 'HISTORICAL',
}

beforeEach(() => {
  vi.mocked(useLiveMarket).mockReturnValue({
    state: null,
    connection: 'DISCONNECTED',
  })
  vi.mocked(getMarketOverview).mockResolvedValue(overview)
  vi.mocked(getTopGainers).mockResolvedValue([])
  vi.mocked(getTopLosers).mockResolvedValue([])
  vi.mocked(getMarketBreadth).mockResolvedValue({
    observation_date: '2026-09-03',
    advancing_count: 0,
    declining_count: 0,
    unchanged_count: 0,
    total_count: 0,
    advance_decline_ratio: null,
    advancing_percent: 0,
    declining_percent: 0,
    unchanged_percent: 0,
  })
  vi.mocked(getStockDetail).mockResolvedValue({
    symbol: 'NABIL',
    company_name: 'Nabil Bank Limited',
    ltp: 515,
    change: 13,
    change_percent: 2.59,
    open: 504,
    high: 520,
    low: 502,
    previous_close: 502,
    volume: 182_450,
    last_updated: '2026-09-03T11:30:00+05:45',
    fifty_two_week_high: 523.48,
    fifty_two_week_low: 325.81,
  })
  vi.mocked(getStockHistory).mockResolvedValue([])
})

afterEach(() => cleanup())

describe('historical market presentation', () => {
  it('labels an open historical session as snapshot context, not current market state', () => {
    render(
      <MemoryRouter>
        <AppHeader overview={overview} />
      </MemoryRouter>,
    )

    expect(screen.getByText('Snapshot status Open')).toBeTruthy()
    expect(screen.queryByText('Market Open')).toBeNull()
    expect(screen.getByText('HISTORICAL')).toBeTruthy()
  })

  it('describes historical records without claiming they are database-backed', async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    )

    expect(
      await screen.findByText('Historical snapshot for the observation date shown.'),
    ).toBeTruthy()
    expect(
      screen.queryByText('Current values reflect latest database-backed market records.'),
    ).toBeNull()
  })

  it('labels stock history by time context instead of storage implementation', async () => {
    render(
      <MemoryRouter initialEntries={['/stocks/NABIL']}>
        <Routes>
          <Route path="/stocks/:symbol" element={<StockDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByText('Historical closing prices')).toBeTruthy()
    expect(screen.getByText(/Historical records$/)).toBeTruthy()
    expect(screen.queryByText(/Database records/)).toBeNull()
  })
})
