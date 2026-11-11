import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { AuthRequestError } from '../api/auth'
import {
  addPortfolioTransaction,
  createPortfolio,
  getPortfolioSummary,
  listPortfolios,
  listPortfolioTransactions,
  type Portfolio,
  type PortfolioSummary,
  type PortfolioTransaction,
} from '../api/portfolios'
import { useAuth } from '../auth/useAuth'
import PortfolioDetails from '../components/PortfolioDetails'

function PortfolioPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const detailRequest = useRef(0)
  const [portfolios, setPortfolios] = useState<Portfolio[]>([])
  const [portfoliosLoading, setPortfoliosLoading] = useState(true)
  const [active, setActive] = useState<Portfolio | null>(null)
  const [summary, setSummary] = useState<PortfolioSummary | null>(null)
  const [transactions, setTransactions] = useState<PortfolioTransaction[]>([])
  const [detailsState, setDetailsState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const [detailsError, setDetailsError] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [symbol, setSymbol] = useState('')
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY')
  const [tradeDate, setTradeDate] = useState(new Date().toISOString().slice(0, 10))
  const [quantity, setQuantity] = useState('')
  const [unitPrice, setUnitPrice] = useState('')
  const [fees, setFees] = useState('0')
  const [submitting, setSubmitting] = useState(false)

  const handleError = useCallback((caught: unknown, fallback: string, setMessage = setError) => {
    if (caught instanceof AuthRequestError && caught.status === 401) {
      navigate('/login', { replace: true, state: { expired: true } })
      return
    }
    setMessage(caught instanceof Error ? caught.message : fallback)
  }, [navigate])

  const loadDetails = useCallback(async (portfolioId: string) => {
    const request = ++detailRequest.current
    setDetailsState('loading')
    setDetailsError('')
    setSummary(null)
    setTransactions([])
    try {
      const [nextSummary, nextTransactions] = await Promise.all([
        getPortfolioSummary(portfolioId),
        listPortfolioTransactions(portfolioId),
      ])
      if (request !== detailRequest.current) return
      setSummary(nextSummary)
      setTransactions(nextTransactions)
      setDetailsState('ready')
    } catch (caught) {
      if (request !== detailRequest.current) return
      setDetailsState('error')
      handleError(caught, 'Portfolio details could not be loaded', setDetailsError)
    }
  }, [handleError])

  useEffect(() => {
    if (auth.status !== 'authenticated') return
    let current = true
    void listPortfolios().then((items) => {
      if (!current) return
      setPortfolios(items)
      setPortfoliosLoading(false)
      const selected = items.find((item) => !item.archived_at) ?? null
      setActive(selected)
      if (selected) void loadDetails(selected.id)
    }).catch((caught) => { setPortfoliosLoading(false); handleError(caught, 'Portfolio request failed') })
    return () => { current = false }
  }, [auth.status, handleError, loadDetails])

  if (auth.status === 'checking') return <main className="auth-screen"><p>Checking your session…</p></main>
  if (!auth.user) return <Navigate to="/login" replace />

  async function create() {
    if (!name.trim()) return
    try {
      const created = await createPortfolio(name, auth.csrfToken)
      setPortfolios((items) => [...items, created])
      setActive(created)
      void loadDetails(created.id)
      setName('')
    } catch (caught) {
      handleError(caught, 'Portfolio request failed')
    }
  }

  async function addTransaction() {
    if (!active || !symbol || !quantity || !unitPrice || submitting) return
    setSubmitting(true)
    try {
      await addPortfolioTransaction(active.id, { idempotency_key: crypto.randomUUID(), symbol, side, trade_date: tradeDate, quantity, unit_price: unitPrice, fees, notes: null }, auth.csrfToken)
      await loadDetails(active.id)
      setSymbol('')
      setQuantity('')
      setUnitPrice('')
      setFees('0')
    } catch (caught) {
      handleError(caught, 'Transaction request failed')
    } finally {
      setSubmitting(false)
    }
  }

  return <main className="dashboard-content portfolio-page">
    <section className="section-heading">
      <div><p className="state-panel__label">Private research</p><h1>Portfolio</h1></div>
      <p>NPR ledger with weighted-average cost and synthetic historical valuation.</p>
    </section>
    {error && <p className="form-error" role="alert">{error}</p>}
    <section className="data-panel portfolio-workspace">
      <div className="data-panel__heading portfolio-picker">
        <div><h2>Your portfolios</h2><span>Select a portfolio to inspect its immutable ledger.</span></div>
        <div className="portfolio-create">
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Portfolio name" aria-label="Portfolio name" />
          <button className="primary-button" onClick={() => void create()}>Create</button>
        </div>
      </div>
      {portfoliosLoading
        ? <p className="portfolio-loading" role="status">Loading portfolios…</p>
        : portfolios.length === 0
        ? <p className="empty-state portfolio-empty">Create a portfolio to begin.</p>
        : <div className="portfolio-tabs" aria-label="Portfolio selection">{portfolios.map((item) =>
          <button key={item.id} className={active?.id === item.id ? 'watchlist-tab watchlist-tab--active' : 'watchlist-tab'} aria-pressed={active?.id === item.id} onClick={() => { setActive(item); void loadDetails(item.id) }}>
            {item.name}{item.archived_at ? ' (archived)' : ''}
          </button>)}</div>}

      {active && !active.archived_at && <form className="portfolio-transaction-form" onSubmit={(event) => { event.preventDefault(); void addTransaction() }}>
        <div className="portfolio-form-heading"><h2>Record transaction</h2><p>Transactions are permanent ledger entries and cannot be edited or deleted.</p></div>
        <label>Symbol<input value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="SYNBANKA" aria-label="Transaction symbol" /></label>
        <label>Side<select value={side} onChange={(event) => setSide(event.target.value as 'BUY' | 'SELL')} aria-label="Transaction side"><option value="BUY">Buy</option><option value="SELL">Sell</option></select></label>
        <label>Trade date<input type="date" value={tradeDate} onChange={(event) => setTradeDate(event.target.value)} aria-label="Trade date" /></label>
        <label>Quantity<input type="number" min="0.00000001" step="0.00000001" value={quantity} onChange={(event) => setQuantity(event.target.value)} placeholder="0" aria-label="Quantity" /></label>
        <label>Unit price<input type="number" min="0.00000001" step="0.00000001" value={unitPrice} onChange={(event) => setUnitPrice(event.target.value)} placeholder="NPR" aria-label="Unit price" /></label>
        <label>Fees<input type="number" min="0" step="0.00000001" value={fees} onChange={(event) => setFees(event.target.value)} placeholder="0" aria-label="Fees" /></label>
        <button className="primary-button" type="submit" disabled={submitting}>{submitting ? 'Recording…' : 'Record transaction'}</button>
      </form>}

      {active && detailsState === 'loading' && <div className="portfolio-loading" role="status" aria-live="polite">Loading portfolio details…</div>}
      {active && detailsState === 'error' && <div className="portfolio-error">
        <p className="form-error" role="alert">{detailsError}</p>
        <button className="retry-button" onClick={() => void loadDetails(active.id)}>Retry portfolio details</button>
      </div>}
      {active && detailsState === 'ready' && summary && <PortfolioDetails summary={summary} transactions={transactions} />}
    </section>
  </main>
}

export default PortfolioPage
