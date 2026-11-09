import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ScreenerPage from '../src/pages/ScreenerPage'
import { useAuth } from '../src/auth/useAuth'
import * as marketApi from '../src/api/market'
import * as watchlistApi from '../src/api/watchlists'

vi.mock('../src/auth/useAuth', () => ({ useAuth: vi.fn() }))
vi.mock('../src/api/market')
vi.mock('../src/api/watchlists')

const user = { id: 'user-1', email: 'investor@example.com', display_name: 'Investor', role: 'USER' as const, created_at: '2026-11-01T00:00:00Z' }
const result = {
  items: [{ symbol: 'SYNBANKA', company_name: 'Synthetic Bank A', sector: 'Synthetic Banking', ltp: 105, change_percent: 5, volume: 1000, turnover: 105000, observation_date: '2026-09-09', data_freshness: 'HISTORICAL' }],
  total: 1,
  page: 1,
  page_size: 25,
  observation_date: '2026-09-09',
  observation_policy: 'COMMON_MARKET_SESSION',
  data_freshness: 'HISTORICAL',
}

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({ status: 'authenticated', user, csrfToken: 'csrf', login: vi.fn(), register: vi.fn(), logout: vi.fn(), updateProfile: vi.fn() })
  vi.mocked(marketApi.getSectorAnalytics).mockResolvedValue([{ sector: 'Synthetic Banking', stock_count: 1, advancing_count: 1, declining_count: 0, unchanged_count: 0, average_change_percent: 5, total_volume: 1000, total_turnover: 105000, observation_date: '2026-09-09', methodology: 'test' }])
  vi.mocked(marketApi.screenStocks).mockResolvedValue(result)
  vi.mocked(watchlistApi.listWatchlists).mockResolvedValue([{ id: 'list-1', name: 'Research', created_at: '', updated_at: '', items: [] }])
  vi.mocked(watchlistApi.addWatchlistItem).mockResolvedValue({ id: 'list-1', name: 'Research', created_at: '', updated_at: '', items: [] })
})

afterEach(() => cleanup())

describe('ScreenerPage', () => {
  it('renders provenance, results and URL-backed filter controls', async () => {
    render(<MemoryRouter initialEntries={['/screener?sector=Synthetic%20Banking']}><ScreenerPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('SYNBANKA')).toBeTruthy())
    expect(screen.getByText(/Historical synthetic data/)).toBeTruthy()
    expect((screen.getByLabelText('Sector') as HTMLSelectElement).value).toBe('Synthetic Banking')
    expect(marketApi.screenStocks).toHaveBeenCalledWith(expect.objectContaining({ sector: 'Synthetic Banking', page: 1, page_size: 25 }))
  })

  it('sorts results and sends the selected column to the API', async () => {
    render(<MemoryRouter><ScreenerPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('SYNBANKA')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: /Change %/ }))
    await waitFor(() => expect(marketApi.screenStocks).toHaveBeenLastCalledWith(expect.objectContaining({ sort_by: 'change_percent', sort_order: 'asc' })))
  })

  it('adds a screened symbol to the first watchlist for an authenticated user', async () => {
    render(<MemoryRouter><ScreenerPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('SYNBANKA')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Add to watchlist' }))
    await waitFor(() => expect(watchlistApi.addWatchlistItem).toHaveBeenCalledWith('list-1', 'SYNBANKA', 'csrf'))
  })
})
