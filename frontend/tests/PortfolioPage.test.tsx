import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthRequestError } from '../src/api/auth'
import { addPortfolioTransaction, getPortfolioSummary, listPortfolios, listPortfolioTransactions } from '../src/api/portfolios'
import { useAuth } from '../src/auth/useAuth'
import PortfolioPage from '../src/pages/PortfolioPage'

vi.mock('../src/auth/useAuth', () => ({ useAuth: vi.fn() }))
vi.mock('../src/api/portfolios', () => ({
  listPortfolios: vi.fn(), createPortfolio: vi.fn(), addPortfolioTransaction: vi.fn(),
  getPortfolioSummary: vi.fn(), listPortfolioTransactions: vi.fn(),
}))

const portfolio = { id: 'portfolio-1', name: 'Research', base_currency: 'NPR', archived_at: null, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }
const summary = {
  holdings: [{ symbol: 'SYNBANKA', company_name: 'Synthetic Bank A', quantity: '3.00000000', average_cost: '112.60000000', invested_cost: '337.80000000', realized_pnl: '31.80000000', valuation_price: '105.00000000', valuation_observed_on: '2026-09-09', unrealized_pnl: '-22.80000000' }],
  total_acquisition_cost: '450.40000000', cash_flow_cost: '337.80000000', market_value: '315.00000000', unrealized_pnl: '-22.80000000', realized_pnl: '31.80000000', total_pnl: '9.00000000', return_percent: '1.99822380',
  valuation: { as_of: '2026-09-09', source: 'synthetic', freshness: 'historical', observed_on_by_symbol: { SYNBANKA: '2026-09-09' }, complete: true, missing_symbols: [], stale_symbols: [] },
}
const transactions = [
  { id: 'buy-1', portfolio_id: portfolio.id, symbol: 'SYNBANKA', side: 'BUY' as const, trade_date: '2026-09-06', trade_sequence: 0, quantity: '10.00000000', unit_price: '100.12345678', fees: '5.00000000', gross_value: '1001.23456780', idempotency_key: 'key-1', notes: null, created_at: '2026-09-06T09:00:00Z' },
  { id: 'sell-1', portfolio_id: portfolio.id, symbol: 'SYNBANKA', side: 'SELL' as const, trade_date: '2026-09-08', trade_sequence: 0, quantity: '4.00000000', unit_price: '120.00000000', fees: '2.00000000', gross_value: '480.00000000', idempotency_key: 'key-2', notes: null, created_at: '2026-09-08T09:00:00Z' },
]

function renderPage() {
  return render(<MemoryRouter initialEntries={['/portfolio']}><Routes><Route path="/portfolio" element={<PortfolioPage />} /><Route path="/login" element={<p>Login page</p>} /></Routes></MemoryRouter>)
}

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({ status: 'authenticated', user: { id: 'user-1', email: 'investor@example.test', display_name: 'Investor', role: 'USER', created_at: '2026-01-01T00:00:00Z' }, csrfToken: 'csrf', login: vi.fn(), register: vi.fn(), logout: vi.fn(), updateProfile: vi.fn() })
  vi.mocked(listPortfolios).mockResolvedValue([portfolio])
  vi.mocked(getPortfolioSummary).mockResolvedValue(summary)
  vi.mocked(listPortfolioTransactions).mockResolvedValue(transactions)
})

afterEach(() => cleanup())

describe('PortfolioPage', () => {
  it('renders the immutable transaction ledger newest first with precise monetary values', async () => {
    renderPage()
    const rows = await screen.findAllByRole('row')
    expect(screen.getByRole('heading', { name: 'Transaction history' })).toBeTruthy()
    expect(screen.getByText('BUY')).toBeTruthy()
    expect(screen.getByText('SELL')).toBeTruthy()
    expect(screen.getByText('NPR 1,001.2345678')).toBeTruthy()
    expect(screen.getByText('NPR 100.12345678')).toBeTruthy()
    expect(screen.getByText('NPR 480.00')).toBeTruthy()
    expect(rows.findIndex((row) => row.textContent?.includes('SELL'))).toBeLessThan(rows.findIndex((row) => row.textContent?.includes('BUY')))
  })

  it('shows cost basis, company, valuation observation, and distinct P&L metrics', async () => {
    renderPage()
    expect(await screen.findByText('Synthetic Bank A')).toBeTruthy()
    expect(screen.getByText('NPR 450.40')).toBeTruthy()
    expect(screen.getAllByText('NPR 337.80')).toHaveLength(2)
    expect(screen.getByText('NPR 31.80')).toBeTruthy()
    expect(screen.getAllByText('NPR -22.80')).toHaveLength(2)
    expect(screen.getByText('NPR 112.60')).toBeTruthy()
    expect(screen.getByText('NPR 105.00')).toBeTruthy()
    expect(screen.getAllByText('Sep 9, 2026').length).toBeGreaterThan(0)
  })

  it('does not present stale or incomplete valuation as current market value', async () => {
    vi.mocked(getPortfolioSummary).mockResolvedValueOnce({ ...summary, market_value: null, unrealized_pnl: null, total_pnl: null, return_percent: null, valuation: { ...summary.valuation, complete: false, stale_symbols: ['SYNBANKA'] } })
    renderPage()
    expect(await screen.findByText('Not shown — valuation incomplete')).toBeTruthy()
    expect(screen.getByText('Stale historical price')).toBeTruthy()
    expect(screen.getAllByText('Unavailable until valuation is complete')).toHaveLength(2)
  })

  it('shows an explicit empty transaction history', async () => {
    vi.mocked(listPortfolioTransactions).mockResolvedValueOnce([])
    renderPage()
    expect(await screen.findByText('No transactions have been recorded for this portfolio.')).toBeTruthy()
  })

  it('shows a retry state when portfolio details fail', async () => {
    vi.mocked(getPortfolioSummary).mockRejectedValueOnce(new Error('Summary unavailable'))
    renderPage()
    expect((await screen.findByRole('alert')).textContent).toBe('Summary unavailable')
    vi.mocked(getPortfolioSummary).mockResolvedValueOnce(summary)
    fireEvent.click(screen.getByRole('button', { name: 'Retry portfolio details' }))
    expect(await screen.findByText('Synthetic Bank A')).toBeTruthy()
  })

  it('ignores a stale response after switching portfolios', async () => {
    const second = { ...portfolio, id: 'portfolio-2', name: 'Second portfolio' }
    let resolveFirst: ((value: typeof summary) => void) | undefined
    vi.mocked(listPortfolios).mockResolvedValueOnce([portfolio, second])
    vi.mocked(getPortfolioSummary).mockReturnValueOnce(new Promise((resolve) => { resolveFirst = resolve })).mockResolvedValueOnce({ ...summary, holdings: [{ ...summary.holdings[0], symbol: 'SYNHYDRO', company_name: 'Synthetic Hydro' }] })
    vi.mocked(listPortfolioTransactions).mockResolvedValue([])
    renderPage()
    await screen.findByRole('button', { name: 'Second portfolio' })
    fireEvent.click(screen.getByRole('button', { name: 'Second portfolio' }))
    expect(await screen.findByText('Synthetic Hydro')).toBeTruthy()
    resolveFirst?.(summary)
    await waitFor(() => expect(screen.queryByText('Synthetic Bank A')).toBeNull())
  })

  it('redirects to login when a detail request reports an expired session', async () => {
    vi.mocked(getPortfolioSummary).mockRejectedValueOnce(new AuthRequestError(401, 'AUTHENTICATION_REQUIRED', 'Authentication is required'))
    renderPage()
    expect(await screen.findByText('Login page')).toBeTruthy()
  })

  it('refreshes summary and transaction history after a successful transaction', async () => {
    vi.mocked(addPortfolioTransaction).mockResolvedValue(transactions[0])
    renderPage()
    await screen.findByText('Synthetic Bank A')
    fireEvent.change(screen.getByLabelText('Transaction symbol'), { target: { value: 'SYNBANKA' } })
    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Unit price'), { target: { value: '100' } })
    fireEvent.click(screen.getByRole('button', { name: 'Record transaction' }))
    await waitFor(() => expect(getPortfolioSummary).toHaveBeenCalledTimes(2))
    expect(listPortfolioTransactions).toHaveBeenCalledTimes(2)
  })

  it('prevents a second transaction submission while the first is in flight', async () => {
    vi.mocked(addPortfolioTransaction).mockReturnValue(new Promise(() => undefined) as never)
    renderPage()
    await screen.findByText('Synthetic Bank A')
    fireEvent.change(screen.getByLabelText('Transaction symbol'), { target: { value: 'SYNBANKA' } })
    fireEvent.change(screen.getByLabelText('Quantity'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Unit price'), { target: { value: '100' } })
    fireEvent.click(screen.getByRole('button', { name: 'Record transaction' }))
    fireEvent.submit(screen.getByRole('button', { name: 'Recording…' }).closest('form')!)
    expect(addPortfolioTransaction).toHaveBeenCalledTimes(1)
  })
})
