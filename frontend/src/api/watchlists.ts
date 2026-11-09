import { apiBaseUrl } from './client'
import { AuthRequestError } from './auth'

export type WatchlistItem = {
  symbol: string
  company_name: string
  observation_date: string | null
  latest_price: number | null
  change_percent: number | null
  created_at: string
}

export type Watchlist = {
  id: string
  name: string
  created_at: string
  updated_at: string
  items: WatchlistItem[]
}

async function request<T>(path: string, csrfToken: string | null, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
      ...init.headers,
    },
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string; error?: { code?: string; message?: string } } | null
    throw new AuthRequestError(response.status, payload?.error?.code ?? 'REQUEST_FAILED', payload?.error?.message ?? payload?.detail ?? 'Watchlist request failed')
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}

export const listWatchlists = () => request<Watchlist[]>('/api/v1/watchlists', null)
export const createWatchlist = (name: string, csrfToken: string | null) => request<Watchlist>('/api/v1/watchlists', csrfToken, { method: 'POST', body: JSON.stringify({ name }) })
export const renameWatchlist = (id: string, name: string, csrfToken: string | null) => request<Watchlist>(`/api/v1/watchlists/${id}`, csrfToken, { method: 'PATCH', body: JSON.stringify({ name }) })
export const deleteWatchlist = (id: string, csrfToken: string | null) => request<void>(`/api/v1/watchlists/${id}`, csrfToken, { method: 'DELETE' })
export const addWatchlistItem = (id: string, symbol: string, csrfToken: string | null) => request<Watchlist>(`/api/v1/watchlists/${id}/items`, csrfToken, { method: 'POST', body: JSON.stringify({ symbol }) })
export const removeWatchlistItem = (id: string, symbol: string, csrfToken: string | null) => request<Watchlist>(`/api/v1/watchlists/${id}/items/${encodeURIComponent(symbol)}`, csrfToken, { method: 'DELETE' })
