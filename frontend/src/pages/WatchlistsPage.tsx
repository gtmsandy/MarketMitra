import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { AuthRequestError } from '../api/auth'
import { addWatchlistItem, createWatchlist, deleteWatchlist, listWatchlists, removeWatchlistItem, renameWatchlist, type Watchlist } from '../api/watchlists'
import { searchStocks } from '../api/market'
import type { StockQuote } from '../types/market'
import { useAuth } from '../auth/useAuth'

function WatchlistsPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [watchlists, setWatchlists] = useState<Watchlist[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<StockQuote[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const active = useMemo(() => watchlists.find((watchlist) => watchlist.id === activeId) ?? null, [activeId, watchlists])

  const handleError = useCallback((caught: unknown) => {
    if (caught instanceof AuthRequestError && caught.status === 401) {
      navigate('/login', { replace: true, state: { expired: true } })
      return
    }
    setError(caught instanceof Error ? caught.message : 'Watchlist request failed')
  }, [navigate])

  useEffect(() => {
    if (auth.status !== 'authenticated') return
    void listWatchlists().then((data) => {
      setWatchlists(data)
      setActiveId(data[0]?.id ?? null)
    }).catch((caught) => handleError(caught)).finally(() => setLoading(false))
  }, [auth.status, handleError])

  useEffect(() => {
    if (!query.trim()) return
    let cancelled = false
    void searchStocks(query).then((data) => { if (!cancelled) setResults(data.slice(0, 8)) }).catch(() => { if (!cancelled) setResults([]) })
    return () => { cancelled = true }
  }, [query])

  if (auth.status === 'checking') return <main className="auth-screen"><p>Checking your session…</p></main>
  if (!auth.user) return <Navigate to="/login" replace state={{ expired: true }} />

  async function create() {
    if (!name.trim()) return
    setError('')
    try {
      const created = await createWatchlist(name, auth.csrfToken)
      setWatchlists((current) => [...current, created])
      setActiveId(created.id)
      setName('')
    } catch (caught) { handleError(caught) }
  }

  async function rename() {
    if (!active || !name.trim()) return
    setError('')
    try {
      const updated = await renameWatchlist(active.id, name, auth.csrfToken)
      setWatchlists((current) => current.map((item) => item.id === updated.id ? updated : item))
      setName('')
    } catch (caught) { handleError(caught) }
  }

  async function removeList() {
    if (!active || !window.confirm(`Delete ${active.name}?`)) return
    try {
      await deleteWatchlist(active.id, auth.csrfToken)
      const remaining = watchlists.filter((item) => item.id !== active.id)
      setWatchlists(remaining)
      setActiveId(remaining[0]?.id ?? null)
    } catch (caught) { handleError(caught) }
  }

  async function add(symbol: string) {
    if (!active) return
    setError('')
    try {
      const updated = await addWatchlistItem(active.id, symbol, auth.csrfToken)
      setWatchlists((current) => current.map((item) => item.id === updated.id ? updated : item))
      setQuery('')
    } catch (caught) { handleError(caught) }
  }

  async function remove(symbol: string) {
    if (!active) return
    try {
      const updated = await removeWatchlistItem(active.id, symbol, auth.csrfToken)
      setWatchlists((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch (caught) { handleError(caught) }
  }

  return <main className="dashboard-content watchlists-page">
    <section className="section-heading"><div><p className="state-panel__label">Private research</p><h1>Watchlists</h1></div><p>Track synthetic historical observations without changing public market access.</p></section>
    {error && <p className="form-error" role="alert">{error}</p>}
    <div className="watchlists-layout">
      <aside className="data-panel watchlists-sidebar" aria-label="Your watchlists">
        <div className="data-panel__heading"><h2>Collections</h2></div>
        {loading ? <p>Loading watchlists…</p> : watchlists.length === 0 ? <p className="empty-state">No watchlists yet.</p> : <div className="watchlist-tabs">{watchlists.map((item) => <button key={item.id} className={item.id === activeId ? 'watchlist-tab watchlist-tab--active' : 'watchlist-tab'} onClick={() => setActiveId(item.id)}>{item.name}</button>)}</div>}
        <div className="watchlist-create"><input value={name} onChange={(event) => setName(event.target.value)} maxLength={80} placeholder={active ? 'New name' : 'Watchlist name'} aria-label={active ? 'New watchlist name' : 'Watchlist name'} /><button className="primary-button" onClick={() => void (active ? rename() : create())}>{active ? 'Rename' : 'Create'}</button></div>
      </aside>
      <section className="data-panel watchlist-detail" aria-live="polite">
        {!active ? <div className="empty-state"><h2>Start a watchlist</h2><p>Create a private collection, then add instruments from search.</p></div> : <>
          <div className="data-panel__heading"><div><p className="state-panel__label">{active.name}</p><h2>Add instruments</h2></div><button className="secondary-button watchlist-delete" onClick={() => void removeList()}>Delete list</button></div>
          <input className="watchlist-search" value={query} onChange={(event) => { const value = event.target.value; setQuery(value); if (!value.trim()) setResults([]) }} placeholder="Search synthetic stocks by symbol or company" aria-label="Search stocks to add" />
          {results.length > 0 && <ul className="watchlist-search-results">{results.map((stock) => <li key={stock.symbol}><span><strong>{stock.symbol}</strong> {stock.company_name}</span><button className="secondary-button" onClick={() => void add(stock.symbol)}>Add</button></li>)}</ul>}
          {active.items.length === 0 ? <p className="empty-state">No instruments in this watchlist.</p> : <div className="table-scroll"><table><caption className="sr-only">Instruments in {active.name}</caption><thead><tr><th>Instrument</th><th>Latest observation</th><th>Change</th><th aria-label="Actions" /></tr></thead><tbody>{active.items.map((item) => <tr key={item.symbol}><td><Link to={`/stocks/${item.symbol}`}><strong>{item.symbol}</strong><span className="table-subtitle">{item.company_name}</span></Link></td><td>{item.latest_price == null ? 'Unavailable' : `NPR ${item.latest_price.toLocaleString()}`}<span className="table-subtitle">{item.observation_date ?? 'No valid observation'}</span></td><td>{item.change_percent == null ? '—' : `${item.change_percent.toFixed(2)}%`}</td><td><button className="text-button" onClick={() => void remove(item.symbol)}>Remove</button></td></tr>)}</tbody></table></div>}
        </>}
      </section>
    </div>
  </main>
}

export default WatchlistsPage
