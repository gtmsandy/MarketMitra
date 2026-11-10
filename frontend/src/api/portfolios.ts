import { apiBaseUrl } from './client'
import { AuthRequestError } from './auth'

export type Portfolio = { id: string; name: string; base_currency: string; archived_at: string | null; created_at: string; updated_at: string }
export type PortfolioTransaction = { id: string; portfolio_id: string; symbol: string; side: 'BUY' | 'SELL'; trade_date: string; trade_sequence: number; quantity: string; unit_price: string; fees: string; idempotency_key: string; notes: string | null; created_at: string }
export type PortfolioSummary = { holdings: { symbol: string; quantity: string; average_cost: string; invested_cost: string; realized_pnl: string }[]; cash_flow_cost: string; market_value: string | null; unrealized_pnl: string | null; realized_pnl: string; total_pnl: string | null; return_percent: string | null; valuation: { as_of: string; source: string; freshness: string; complete: boolean; missing_symbols: string[]; stale_symbols: string[] } }

async function request<T>(path: string, csrfToken: string | null, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, { ...init, credentials: 'include', headers: { ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}), ...init.headers } })
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string; error?: { message?: string; code?: string } } | null
    throw new AuthRequestError(response.status, payload?.error?.code ?? 'REQUEST_FAILED', payload?.error?.message ?? payload?.detail ?? 'Portfolio request failed')
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}

export const listPortfolios = () => request<Portfolio[]>('/api/v1/portfolios', null)
export const createPortfolio = (name: string, csrf: string | null) => request<Portfolio>('/api/v1/portfolios', csrf, { method: 'POST', body: JSON.stringify({ name, base_currency: 'NPR' }) })
export const addPortfolioTransaction = (id: string, input: Omit<PortfolioTransaction, 'id' | 'portfolio_id' | 'trade_sequence' | 'created_at'>, csrf: string | null) => request<PortfolioTransaction>(`/api/v1/portfolios/${id}/transactions`, csrf, { method: 'POST', body: JSON.stringify(input) })
export const getPortfolioSummary = (id: string) => request<PortfolioSummary>(`/api/v1/portfolios/${id}/summary`, null)
