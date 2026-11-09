import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { screenStocks, getSectorAnalytics, type StockScreenerParams } from '../api/market'
import { addWatchlistItem, listWatchlists } from '../api/watchlists'
import { AuthRequestError } from '../api/auth'
import { useAuth } from '../auth/useAuth'
import type { ScreenerSortBy, ScreenerSortOrder, StockScreenerResponse } from '../types/market'
import { formatCompactNpr, formatInteger, formatNpr, formatObservationDate, formatPercentage, getChangeTone } from '../utils/formatters'

const PAGE_SIZE = 25
const sortLabels: Record<ScreenerSortBy, string> = {
  symbol: 'Symbol',
  price: 'Price',
  change_percent: 'Change %',
  volume: 'Volume',
  turnover: 'Turnover',
}

function numberFromParams(value: string | null): number | undefined {
  if (value === null || value.trim() === '') return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function ScreenerPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const auth = useAuth()
  const [qDraft, setQDraft] = useState(searchParams.get('q') ?? '')
  const [sectors, setSectors] = useState<string[]>([])
  const [result, setResult] = useState<StockScreenerResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const requestId = useRef(0)

  const paramsKey = searchParams.toString()
  const filters = useMemo<StockScreenerParams>(() => {
    const current = new URLSearchParams(paramsKey)
    return {
    q: current.get('q') || undefined,
    sector: current.get('sector') || undefined,
    min_price: numberFromParams(current.get('min_price')),
    max_price: numberFromParams(current.get('max_price')),
    min_change_percent: numberFromParams(current.get('min_change_percent')),
    max_change_percent: numberFromParams(current.get('max_change_percent')),
    min_volume: numberFromParams(current.get('min_volume')),
    min_turnover: numberFromParams(current.get('min_turnover')),
    page: numberFromParams(current.get('page')) ?? 1,
    page_size: PAGE_SIZE,
    sort_by: (current.get('sort_by') as ScreenerSortBy | null) ?? 'symbol',
    sort_order: (current.get('sort_order') as ScreenerSortOrder | null) ?? 'asc',
    }
  }, [paramsKey])

  useEffect(() => {
    let cancelled = false
    void getSectorAnalytics().then((items) => {
      if (!cancelled) setSectors(items.map((item) => item.sector).filter(Boolean).sort())
    }).catch(() => undefined)
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => {
      const current = searchParams.get('q') ?? ''
      if (qDraft.trim() === current) return
      const next = new URLSearchParams(searchParams)
      if (qDraft.trim()) next.set('q', qDraft.trim())
      else next.delete('q')
      next.delete('page')
      setSearchParams(next, { replace: true })
    }, 350)
    return () => clearTimeout(timer)
  }, [qDraft, searchParams, setSearchParams])

  useEffect(() => {
    const id = ++requestId.current
    void screenStocks(filters).then((data) => {
      if (id === requestId.current) {
        setError('')
        setResult(data)
      }
    }).catch((caught: unknown) => {
      if (id === requestId.current) setError(caught instanceof Error ? caught.message : 'Unable to load screener results')
    }).finally(() => {
      if (id === requestId.current) setLoading(false)
    })
  }, [filters])

  const activeFilterCount = ['q', 'sector', 'min_price', 'max_price', 'min_change_percent', 'max_change_percent', 'min_volume', 'min_turnover']
    .filter((key) => searchParams.has(key)).length

  function updateFilter(key: string, value: string) {
    const next = new URLSearchParams(searchParams)
    if (value.trim()) next.set(key, value.trim())
    else next.delete(key)
    next.delete('page')
    setSearchParams(next)
  }

  function changeSort(sortBy: ScreenerSortBy) {
    const next = new URLSearchParams(searchParams)
    const current = next.get('sort_by') ?? 'symbol'
    next.set('sort_by', sortBy)
    next.set('sort_order', current === sortBy && next.get('sort_order') === 'asc' ? 'desc' : 'asc')
    next.delete('page')
    setSearchParams(next)
  }

  function reset() {
    setQDraft('')
    setSearchParams({})
  }

  async function addToWatchlist(symbol: string) {
    setNotice('')
    if (!auth.user) {
      navigate('/login', { state: { from: '/screener' } })
      return
    }
    try {
      const watchlists = await listWatchlists()
      if (!watchlists[0]) {
        navigate('/watchlists')
        return
      }
      await addWatchlistItem(watchlists[0].id, symbol, auth.csrfToken)
      setNotice(`${symbol} added to ${watchlists[0].name}.`)
    } catch (caught: unknown) {
      if (caught instanceof AuthRequestError && caught.status === 401) {
        navigate('/login', { state: { expired: true, from: '/screener' } })
      } else setError(caught instanceof Error ? caught.message : 'Unable to update watchlist')
    }
  }

  const page = result?.page ?? filters.page ?? 1
  const pageCount = result ? Math.max(1, Math.ceil(result.total / result.page_size)) : 1

  return <main className="dashboard-content screener-page">
    <section className="section-heading"><div><p className="state-panel__label">Research workspace</p><h1>Stock screener</h1></div><p>Filter the validated synthetic universe using one common historical market session.</p></section>
    <section className="data-panel screener-filters" aria-labelledby="screener-filters-heading">
      <div className="data-panel__heading"><div><h2 id="screener-filters-heading">Find instruments</h2><span>{activeFilterCount ? `${activeFilterCount} active filter${activeFilterCount === 1 ? '' : 's'}` : 'No filters applied'}</span></div><button className="secondary-button screener-reset" onClick={reset} disabled={!activeFilterCount && !qDraft}>Reset</button></div>
      <div className="screener-filter-grid">
        <label>Symbol or company<input value={qDraft} onChange={(event) => setQDraft(event.target.value)} placeholder="e.g. SYNBANK" maxLength={80} /></label>
        <label>Sector<select value={searchParams.get('sector') ?? ''} onChange={(event) => updateFilter('sector', event.target.value)}><option value="">All sectors</option>{sectors.map((sector) => <option key={sector} value={sector}>{sector}</option>)}</select></label>
        <label>Min price<input type="number" min="0" value={searchParams.get('min_price') ?? ''} onChange={(event) => updateFilter('min_price', event.target.value)} /></label>
        <label>Max price<input type="number" min="0" value={searchParams.get('max_price') ?? ''} onChange={(event) => updateFilter('max_price', event.target.value)} /></label>
        <label>Min change %<input type="number" min="-100" max="1000" step="0.01" value={searchParams.get('min_change_percent') ?? ''} onChange={(event) => updateFilter('min_change_percent', event.target.value)} /></label>
        <label>Max change %<input type="number" min="-100" max="1000" step="0.01" value={searchParams.get('max_change_percent') ?? ''} onChange={(event) => updateFilter('max_change_percent', event.target.value)} /></label>
        <label>Min volume<input type="number" min="0" value={searchParams.get('min_volume') ?? ''} onChange={(event) => updateFilter('min_volume', event.target.value)} /></label>
        <label>Min turnover<input type="number" min="0" value={searchParams.get('min_turnover') ?? ''} onChange={(event) => updateFilter('min_turnover', event.target.value)} /></label>
      </div>
    </section>
    {error && <p className="form-error" role="alert">{error}</p>}
    {notice && <p className="form-success" role="status">{notice}</p>}
    <section className="data-panel screener-results" aria-live="polite">
      <div className="data-panel__heading"><div><h2>Results</h2><span>{loading ? 'Refreshing…' : `${result?.total ?? 0} instruments`}</span></div><span>Sorted by {sortLabels[filters.sort_by ?? 'symbol']} ({filters.sort_order})</span></div>
      <p className="screener-provenance">Historical synthetic data · Common session {result?.observation_date ?? '—'} · {result?.data_freshness ?? 'HISTORICAL'}</p>
      {loading && !result ? <p className="empty-state">Loading screener results…</p> : result?.items.length === 0 ? <p className="empty-state">No instruments match these filters. Try widening the range.</p> : <div className="table-scroll"><table><caption className="sr-only">Stock screener results</caption><thead><tr>{(['symbol', 'price', 'change_percent', 'volume', 'turnover'] as ScreenerSortBy[]).map((column) => <th key={column}><button className="table-sort-button" onClick={() => changeSort(column)}>{sortLabels[column]} {filters.sort_by === column ? (filters.sort_order === 'asc' ? '↑' : '↓') : ''}</button></th>)}<th aria-label="Actions" /></tr></thead><tbody>{result?.items.map((item) => <tr key={item.symbol}><td><Link to={`/stocks/${item.symbol}`}><strong>{item.symbol}</strong><span className="table-subtitle">{item.company_name} · {item.sector ?? 'Unclassified'}</span></Link></td><td>{formatNpr(item.ltp)}</td><td className={`change-${getChangeTone(item.change_percent)}`}>{formatPercentage(item.change_percent)}</td><td>{formatInteger(item.volume)}</td><td>{item.turnover == null ? 'Unavailable' : formatCompactNpr(item.turnover)}</td><td><button className="text-button screener-watchlist-button" onClick={() => void addToWatchlist(item.symbol)}>Add to watchlist</button></td></tr>)}</tbody></table></div>}
      {result && result.total > 0 && <div className="screener-pagination"><span>Page {page} of {pageCount}</span><div><button className="secondary-button" disabled={page <= 1 || loading} onClick={() => updateFilter('page', String(page - 1))}>Previous</button><button className="secondary-button" disabled={page >= pageCount || loading} onClick={() => updateFilter('page', String(page + 1))}>Next</button></div></div>}
      {result && <p className="table-subtitle">Observation date {formatObservationDate(result.observation_date ?? '2026-01-01T00:00:00Z')} · Values are historical and not live market quotes.</p>}
    </section>
  </main>
}

export default ScreenerPage
