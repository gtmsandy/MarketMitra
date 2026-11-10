import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuth } from '../src/auth/useAuth'
import { addPortfolioTransaction, getPortfolioSummary, listPortfolios } from '../src/api/portfolios'
import PortfolioPage from '../src/pages/PortfolioPage'

vi.mock('../src/auth/useAuth', () => ({ useAuth: vi.fn() }))
vi.mock('../src/api/portfolios', () => ({
  listPortfolios: vi.fn(), createPortfolio: vi.fn(), addPortfolioTransaction: vi.fn(), getPortfolioSummary: vi.fn(),
}))

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({ status: 'authenticated', user: { id: 'user-1', email: 'investor@example.test', display_name: 'Investor', role: 'USER', created_at: '2026-01-01T00:00:00Z' }, csrfToken: 'csrf', login: vi.fn(), register: vi.fn(), logout: vi.fn(), updateProfile: vi.fn() })
  vi.mocked(listPortfolios).mockResolvedValue([{ id: 'portfolio-1', name: 'Research', base_currency: 'NPR', archived_at: null, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }])
  vi.mocked(getPortfolioSummary).mockResolvedValue({
    holdings: [{ symbol: 'SYNBANKA', quantity: '3.00000000', average_cost: '112.60000000', invested_cost: '337.80000000', realized_pnl: '31.80000000' }],
    cash_flow_cost: '337.80000000', market_value: '315.00000000', unrealized_pnl: '-22.80000000', realized_pnl: '31.80000000', total_pnl: '9.00000000', return_percent: '1.59857904',
    valuation: { as_of: '2026-09-09', source: 'synthetic', freshness: 'historical', observed_on_by_symbol: { SYNBANKA: '2026-09-09' }, complete: true, missing_symbols: [], stale_symbols: [] },
  })
})

afterEach(() => cleanup())

describe('PortfolioPage', () => {
  it('shows calculated P&L and provenance-labelled valuation details', async () => {
    render(<MemoryRouter><PortfolioPage /></MemoryRouter>)

    await waitFor(() => expect(screen.getByText('NPR 31.80000000')).toBeTruthy())
    expect(screen.getByText('NPR -22.80000000')).toBeTruthy()
    expect(screen.getByText('synthetic · historical · 2026-09-09')).toBeTruthy()
    expect(screen.getByText('SYNBANKA 2026-09-09')).toBeTruthy()
    expect(screen.getByText('NPR 112.60000000')).toBeTruthy()
  })

  it('keeps the workspace usable when an older API response lacks observation dates', async () => {
    vi.mocked(getPortfolioSummary).mockResolvedValueOnce({
      holdings: [], cash_flow_cost: '0', market_value: null, unrealized_pnl: null, realized_pnl: '0', total_pnl: null, return_percent: null,
      valuation: { as_of: '2026-09-09', source: 'synthetic', freshness: 'historical', complete: false, missing_symbols: ['SYNBANKA'], stale_symbols: [] },
    } as never)
    render(<MemoryRouter><PortfolioPage /></MemoryRouter>)

    expect(await screen.findByText('No observation available')).toBeTruthy()
  })

  it('prevents a second transaction submission while the first is in flight', async () => {
    vi.mocked(addPortfolioTransaction).mockReturnValue(new Promise(() => undefined) as never)
    render(<MemoryRouter><PortfolioPage /></MemoryRouter>)

    await screen.findByText('NPR 31.80000000')
    fireEvent.change(screen.getByLabelText('Transaction symbol'), { target: { value: 'SYNBANKA' } })
    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Unit price'), { target: { value: '100' } })
    fireEvent.click(screen.getByRole('button', { name: 'Record transaction' }))

    const submit = screen.getByRole('button', { name: 'Recording…' })
    expect(submit.getAttribute('disabled')).not.toBeNull()
    fireEvent.click(submit)
    fireEvent.submit(submit.closest('form')!)
    expect(addPortfolioTransaction).toHaveBeenCalledTimes(1)
  })
})
