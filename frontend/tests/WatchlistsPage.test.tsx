import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import WatchlistsPage from '../src/pages/WatchlistsPage'
import { useAuth } from '../src/auth/useAuth'
import * as watchlistApi from '../src/api/watchlists'
import * as marketApi from '../src/api/market'

vi.mock('../src/auth/useAuth', () => ({ useAuth: vi.fn() }))
vi.mock('../src/api/watchlists')
vi.mock('../src/api/market')

const user = { id: 'user-1', email: 'investor@example.com', display_name: 'Investor', role: 'USER' as const, created_at: '2026-11-01T00:00:00Z' }

const emptyList = (id = 'list-1', name = 'research') => ({ id, name, created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z', items: [] })

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({ status: 'authenticated', user, csrfToken: 'csrf', login: vi.fn(), register: vi.fn(), logout: vi.fn(), updateProfile: vi.fn() })
  vi.mocked(watchlistApi.listWatchlists).mockResolvedValue([])
  vi.mocked(watchlistApi.createWatchlist).mockResolvedValue(emptyList())
  vi.mocked(watchlistApi.renameWatchlist).mockResolvedValue(emptyList())
  vi.mocked(watchlistApi.deleteWatchlist).mockResolvedValue(undefined)
  vi.mocked(watchlistApi.addWatchlistItem).mockResolvedValue(emptyList())
  vi.mocked(watchlistApi.removeWatchlistItem).mockResolvedValue(emptyList())
  vi.mocked(marketApi.searchStocks).mockResolvedValue([])
})

afterEach(() => cleanup())

describe('WatchlistsPage', () => {
  it('creates a watchlist from the empty state', async () => {
    render(<MemoryRouter><WatchlistsPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create' })).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Watchlist name'), { target: { value: 'Research' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'research' })).toBeTruthy())
    expect(watchlistApi.createWatchlist).toHaveBeenCalledWith('Research', 'csrf')
  })

  it('renders persisted items and removes them through the API', async () => {
    const persisted = { ...emptyList(), items: [{ symbol: 'SYNBANKA', company_name: 'Synthetic Bank', observation_date: '2026-09-09', latest_price: 105, change_percent: 5, created_at: '2026-11-01T00:00:00Z' }] }
    vi.mocked(watchlistApi.listWatchlists).mockResolvedValue([persisted])
    vi.mocked(watchlistApi.removeWatchlistItem).mockResolvedValue(emptyList())
    render(<MemoryRouter><WatchlistsPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('SYNBANKA')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(watchlistApi.removeWatchlistItem).toHaveBeenCalledWith('list-1', 'SYNBANKA', 'csrf'))
  })
})
