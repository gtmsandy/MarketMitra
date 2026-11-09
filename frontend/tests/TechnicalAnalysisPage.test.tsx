import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import StockDetailPage from '../src/pages/StockDetailPage'
import { useAuth } from '../src/auth/useAuth'
import * as marketApi from '../src/api/market'
import { useLiveMarket } from '../src/live/useLiveMarket'

vi.mock('../src/auth/useAuth', () => ({ useAuth: vi.fn() }))
vi.mock('../src/live/useLiveMarket', () => ({ useLiveMarket: vi.fn() }))
vi.mock('../src/api/market')
vi.mock('../src/components/PriceChart', () => ({ default: () => <div>Price chart</div> }))

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({ status: 'anonymous', user: null, csrfToken: null, login: vi.fn(), register: vi.fn(), logout: vi.fn(), updateProfile: vi.fn() })
  vi.mocked(useLiveMarket).mockReturnValue({ state: null, connection: 'DISCONNECTED' })
  vi.mocked(marketApi.getStockDetail).mockResolvedValue({ symbol: 'SYNBANKA', company_name: 'Synthetic Bank A', ltp: 105, change: 5, change_percent: 5, open: 101, high: 106, low: 100, previous_close: 100, volume: 1000, last_updated: '2026-09-09T00:00:00Z', fifty_two_week_high: 106, fifty_two_week_low: 100 })
  vi.mocked(marketApi.getStockHistory).mockResolvedValue([
    { date: '2026-09-06', open: 100, high: 102, low: 99, close: 101, volume: 1000 },
    { date: '2026-09-07', open: 101, high: 103, low: 100, close: 102, volume: 1100 },
    { date: '2026-09-08', open: 102, high: 104, low: 101, close: 103, volume: 1200 },
    { date: '2026-09-09', open: 103, high: 105, low: 102, close: 104, volume: 1300 },
  ])
  vi.mocked(marketApi.getStockIntraday).mockResolvedValue([])
})

afterEach(() => cleanup())

function renderStock() {
  return render(<MemoryRouter initialEntries={['/stocks/SYNBANKA']}><Routes><Route path="/stocks/:symbol" element={<StockDetailPage />} /></Routes></MemoryRouter>)
}

describe('technical analysis controls', () => {
  it('explains insufficient history instead of rendering invented long-period values', async () => {
    renderStock()
    expect(await screen.findByText('Technical analysis')).toBeTruthy()
    fireEvent.click(screen.getByLabelText('Show SMA'))
    expect(screen.getByText(/SMA requires 20 consecutive valid observations; only 4 are available/)).toBeTruthy()
  })

  it('supports a shorter validated period on the existing history', async () => {
    renderStock()
    expect(await screen.findByText('Technical analysis')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('SMA period'), { target: { value: '2' } })
    fireEvent.click(screen.getByLabelText('Show SMA'))
    expect(screen.getByText('SMA has enough valid observations.')).toBeTruthy()
  })

  it('keeps the real empty intraday state for the 1D timeframe', async () => {
    renderStock()
    expect(await screen.findByText('Technical analysis')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '1D' }))
    expect(await screen.findByText(/No intraday trading records available/)).toBeTruthy()
  })
})
