import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { createPortfolio, getPortfolioSummary, listPortfolios, type Portfolio, type PortfolioSummary } from '../api/portfolios'

function PortfolioPage() {
  const auth = useAuth()
  const [portfolios, setPortfolios] = useState<Portfolio[]>([])
  const [active, setActive] = useState<Portfolio | null>(null)
  const [summary, setSummary] = useState<PortfolioSummary | null>(null)
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (auth.status !== 'authenticated') return
    void listPortfolios().then((items) => { setPortfolios(items); setActive(items.find((item) => !item.archived_at) ?? null) }).catch((caught) => setError(caught instanceof Error ? caught.message : 'Portfolio request failed'))
  }, [auth.status])
  useEffect(() => {
    if (!active) return
    void getPortfolioSummary(active.id).then(setSummary).catch((caught) => setError(caught instanceof Error ? caught.message : 'Portfolio request failed'))
  }, [active])

  if (auth.status === 'checking') return <main className="auth-screen"><p>Checking your session…</p></main>
  if (!auth.user) return <Navigate to="/login" replace />

  async function create() {
    if (!name.trim()) return
    try { const created = await createPortfolio(name, auth.csrfToken); setPortfolios((items) => [...items, created]); setActive(created); setName('') } catch (caught) { setError(caught instanceof Error ? caught.message : 'Portfolio request failed') }
  }

  return <main className="dashboard-content">
    <section className="section-heading"><div><p className="state-panel__label">Private research</p><h1>Portfolio</h1></div><p>NPR ledger with weighted-average cost and synthetic historical valuation.</p></section>
    {error && <p className="form-error" role="alert">{error}</p>}
    <section className="data-panel">
      <div className="data-panel__heading"><h2>Your portfolios</h2><div><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Portfolio name" aria-label="Portfolio name" /><button className="primary-button" onClick={() => void create()}>Create</button></div></div>
      {portfolios.length === 0 ? <p className="empty-state">Create a portfolio to begin.</p> : <div className="watchlist-tabs">{portfolios.map((item) => <button key={item.id} className={active?.id === item.id ? 'watchlist-tab watchlist-tab--active' : 'watchlist-tab'} onClick={() => setActive(item)}>{item.name}{item.archived_at ? ' (archived)' : ''}</button>)}</div>}
      {active && summary && <div className="table-scroll"><table><caption className="sr-only">Portfolio holdings</caption><thead><tr><th>Symbol</th><th>Quantity</th><th>Average cost</th><th>Valuation</th></tr></thead><tbody>{summary.holdings.map((holding) => <tr key={holding.symbol}><td><strong>{holding.symbol}</strong></td><td>{holding.quantity}</td><td>NPR {holding.average_cost}</td><td>{summary.market_value == null ? 'Incomplete' : `NPR ${summary.market_value}`}</td></tr>)}</tbody></table><p className="table-subtitle">{summary.valuation.complete ? 'Synthetic historical valuation complete.' : `Valuation incomplete: ${[...summary.valuation.missing_symbols, ...summary.valuation.stale_symbols].join(', ') || 'no current price'}`}</p></div>}
    </section>
  </main>
}

export default PortfolioPage
