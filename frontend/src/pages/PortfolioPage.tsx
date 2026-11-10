import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { addPortfolioTransaction, createPortfolio, getPortfolioSummary, listPortfolios, type Portfolio, type PortfolioSummary } from '../api/portfolios'

function PortfolioPage() {
  const auth = useAuth()
  const [portfolios, setPortfolios] = useState<Portfolio[]>([])
  const [active, setActive] = useState<Portfolio | null>(null)
  const [summary, setSummary] = useState<PortfolioSummary | null>(null)
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [symbol, setSymbol] = useState('')
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY')
  const [tradeDate, setTradeDate] = useState(new Date().toISOString().slice(0, 10))
  const [quantity, setQuantity] = useState('')
  const [unitPrice, setUnitPrice] = useState('')
  const [fees, setFees] = useState('0')

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

  async function addTransaction() {
    if (!active || !symbol || !quantity || !unitPrice) return
    try {
      await addPortfolioTransaction(active.id, { idempotency_key: crypto.randomUUID(), symbol, side, trade_date: tradeDate, quantity, unit_price: unitPrice, fees, notes: null }, auth.csrfToken)
      setSummary(await getPortfolioSummary(active.id))
      setSymbol(''); setQuantity(''); setUnitPrice(''); setFees('0')
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Transaction request failed') }
  }

  return <main className="dashboard-content">
    <section className="section-heading"><div><p className="state-panel__label">Private research</p><h1>Portfolio</h1></div><p>NPR ledger with weighted-average cost and synthetic historical valuation.</p></section>
    {error && <p className="form-error" role="alert">{error}</p>}
    <section className="data-panel">
      <div className="data-panel__heading"><h2>Your portfolios</h2><div><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Portfolio name" aria-label="Portfolio name" /><button className="primary-button" onClick={() => void create()}>Create</button></div></div>
      {portfolios.length === 0 ? <p className="empty-state">Create a portfolio to begin.</p> : <div className="watchlist-tabs">{portfolios.map((item) => <button key={item.id} className={active?.id === item.id ? 'watchlist-tab watchlist-tab--active' : 'watchlist-tab'} onClick={() => setActive(item)}>{item.name}{item.archived_at ? ' (archived)' : ''}</button>)}</div>}
      {active && !active.archived_at && <form className="watchlist-create" onSubmit={(event) => { event.preventDefault(); void addTransaction() }}><input value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="Symbol" aria-label="Transaction symbol" /><select value={side} onChange={(event) => setSide(event.target.value as 'BUY' | 'SELL')} aria-label="Transaction side"><option value="BUY">Buy</option><option value="SELL">Sell</option></select><input type="date" value={tradeDate} onChange={(event) => setTradeDate(event.target.value)} aria-label="Trade date" /><input type="number" min="0.00000001" step="0.00000001" value={quantity} onChange={(event) => setQuantity(event.target.value)} placeholder="Quantity" aria-label="Quantity" /><input type="number" min="0.00000001" step="0.00000001" value={unitPrice} onChange={(event) => setUnitPrice(event.target.value)} placeholder="Unit price" aria-label="Unit price" /><input type="number" min="0" step="0.00000001" value={fees} onChange={(event) => setFees(event.target.value)} placeholder="Fees" aria-label="Fees" /><button className="primary-button" type="submit">Record transaction</button></form>}
      {active && summary && <div className="table-scroll"><table><caption className="sr-only">Portfolio holdings</caption><thead><tr><th>Symbol</th><th>Quantity</th><th>Average cost</th><th>Valuation</th></tr></thead><tbody>{summary.holdings.map((holding) => <tr key={holding.symbol}><td><strong>{holding.symbol}</strong></td><td>{holding.quantity}</td><td>NPR {holding.average_cost}</td><td>{summary.market_value == null ? 'Incomplete' : `NPR ${summary.market_value}`}</td></tr>)}</tbody></table><p className="table-subtitle">{summary.valuation.complete ? 'Synthetic historical valuation complete.' : `Valuation incomplete: ${[...summary.valuation.missing_symbols, ...summary.valuation.stale_symbols].join(', ') || 'no current price'}`}</p></div>}
    </section>
  </main>
}

export default PortfolioPage
