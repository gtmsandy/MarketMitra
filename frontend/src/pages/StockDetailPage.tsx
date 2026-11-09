import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { getStockDetail, getStockHistory, getStockIntraday } from '../api/market'
import PriceChart, { type ChartDisplayOptions } from '../components/PriceChart'
import { calculateTechnicalIndicators, DEFAULT_INDICATOR_PERIODS, type TechnicalIndicators } from '../technical/indicators'
import type { IntradayPricePoint, PriceHistoryPoint, StockDetail } from '../types/market'
import {
  formatObservationDate,
  formatInteger,
  formatNpr,
  formatPercentage,
  formatSignedNumber,
  getChangeTone,
} from '../utils/formatters'
import { useLiveMarket } from '../live/useLiveMarket'
import { useAuth } from '../auth/useAuth'
import { addWatchlistItem, listWatchlists, type Watchlist } from '../api/watchlists'
import { AuthRequestError } from '../api/auth'

type Timeframe = '1D' | '1W' | '1M' | '1Y' | 'ALL'

function StockDetailPage() {
  const live = useLiveMarket()
  const auth = useAuth()
  const navigate = useNavigate()
  const { symbol } = useParams<{ symbol: string }>()
  const [detail, setDetail] = useState<StockDetail | null>(null)
  const [history, setHistory] = useState<PriceHistoryPoint[]>([])
  const [timeframe, setTimeframe] = useState<Timeframe>('ALL')
  const [intraday, setIntraday] = useState<IntradayPricePoint[] | null>(null)
  const [isIntradayLoading, setIsIntradayLoading] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [watchlists, setWatchlists] = useState<Watchlist[]>([])
  const [watchlistMessage, setWatchlistMessage] = useState('')
  const [chartOptions, setChartOptions] = useState<ChartDisplayOptions>({
    candleMode: false,
    showVolume: true,
    showSma: false,
    showEma: false,
    showBollinger: false,
    showRsi: false,
    showMacd: false,
  })
  const [periods, setPeriods] = useState(DEFAULT_INDICATOR_PERIODS)

  const loadStock = useCallback(async () => {
    if (!symbol) return
    setIsLoading(true)
    setError(null)
    setIntraday(null)
    setTimeframe('ALL')
    try {
      const [detailData, historyData] = await Promise.all([
        getStockDetail(symbol),
        getStockHistory(symbol),
      ])
      setDetail(detailData)
      setHistory(historyData)
    } catch {
      setError('Unable to load stock data.')
    } finally {
      setIsLoading(false)
    }
  }, [symbol])

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadStock() }, 0)
    return () => window.clearTimeout(timer)
  }, [loadStock])

  useEffect(() => {
    if (auth.status !== 'authenticated') return
    void listWatchlists().then(setWatchlists).catch(() => setWatchlists([]))
  }, [auth.status])

  async function addToWatchlist() {
    if (!symbol || !auth.csrfToken) { navigate('/login', { state: { from: `/stocks/${symbol}` } }); return }
    const target = watchlists[0]
    if (!target) { navigate('/watchlists'); return }
    try {
      const updated = await addWatchlistItem(target.id, symbol, auth.csrfToken)
      setWatchlists((current) => current.map((item) => item.id === updated.id ? updated : item))
      setWatchlistMessage(`${symbol.toUpperCase()} added to ${target.name}.`)
    } catch (caught) {
      setWatchlistMessage(caught instanceof AuthRequestError ? caught.message : 'Could not add this stock.')
    }
  }

  // Lazy-load intraday observations when 1D is selected
  useEffect(() => {
    if (timeframe === '1D' && symbol && intraday === null) {
      const timer = window.setTimeout(() => {
        setIsIntradayLoading(true)
        getStockIntraday(symbol)
          .then((data) => setIntraday(data))
          .catch(() => setIntraday([]))
          .finally(() => setIsIntradayLoading(false))
      }, 0)
      return () => window.clearTimeout(timer)
    }
    return undefined
  }, [timeframe, symbol, intraday])

  const chartData = useMemo(() => {
    if (timeframe === 'ALL' || history.length === 0) {
      return history
    }
    if (timeframe === '1D') {
      if (!intraday || intraday.length === 0) return []
      return intraday.map((p) => ({
        date: p.timestamp,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
        volume: p.volume,
      }))
    }
    const lastItem = history[history.length - 1]
    const lastDate = new Date(lastItem.date)
    const cutoff = new Date(lastDate)
    if (timeframe === '1W') {
      cutoff.setDate(cutoff.getDate() - 7)
    } else if (timeframe === '1M') {
      cutoff.setMonth(cutoff.getMonth() - 1)
    } else if (timeframe === '1Y') {
      cutoff.setFullYear(cutoff.getFullYear() - 1)
    }
    const filtered = history.filter((p) => new Date(p.date) >= cutoff)
    return filtered.length > 0 ? filtered : history.slice(-5)
  }, [timeframe, history, intraday])

  const indicators = useMemo<TechnicalIndicators | null>(() => {
    try {
      return calculateTechnicalIndicators(chartData, periods)
    } catch {
      return null
    }
  }, [chartData, periods])

  function updatePeriod(key: keyof typeof periods, value: string) {
    const parsed = Number(value)
    if (!Number.isFinite(parsed)) return
    setPeriods((current) => ({ ...current, [key]: Math.min(200, Math.max(2, Math.round(parsed))) }))
  }

  function toggleChartOption(key: keyof ChartDisplayOptions) {
    setChartOptions((current) => ({ ...current, [key]: !current[key] }))
  }
  if (isLoading) {
    return (
      <main className="stock-detail-page">
        <div className="stock-detail-page__content">
          <div className="loading-line loading-line--title" />
          <div className="loading-card" style={{ minHeight: 180 }} />
          <div className="loading-card" style={{ minHeight: 320 }} />
        </div>
      </main>
    )
  }

  if (error || !detail) {
    return (
      <main className="state-screen" aria-live="polite">
        <section className="state-panel">
          <p className="state-panel__label">Stock data unavailable</p>
          <h1>{error ?? 'Stock not found.'}</h1>
          <p>
            <Link to="/" className="back-link">← Back to dashboard</Link>
          </p>
          {error && (
            <button className="retry-button" type="button" onClick={() => void loadStock()}>
              Retry request
            </button>
          )}
        </section>
      </main>
    )
  }

  const liveQuote = symbol ? live.state?.quotes[symbol.toUpperCase()] : undefined
  const current = liveQuote ? { ...detail, ltp: liveQuote.ltp ?? detail.ltp, change_percent: liveQuote.change_percent ?? detail.change_percent, open: liveQuote.open ?? detail.open, high: liveQuote.high ?? detail.high, low: liveQuote.low ?? detail.low, volume: liveQuote.volume ?? detail.volume, last_updated: liveQuote.provider_timestamp ?? detail.last_updated } : detail
  const tone = getChangeTone(current.change)

  return (
    <main className="stock-detail-page">
      <div className="stock-detail-page__content">
        <Link to="/" className="back-link">← Dashboard</Link>

        <header className="stock-detail-header">
          <div>
            <h1 className="stock-detail-header__symbol">{current.symbol}</h1>
            <p className="stock-detail-header__name">{current.company_name}</p>
          </div>
          <div className="stock-detail-header__price">
              <span className="stock-detail-header__ltp">{formatNpr(current.ltp)}</span>
            <span className={`change change--${tone}`}>
              {formatSignedNumber(current.change)} ({formatPercentage(current.change_percent)})
            </span>
          </div>
          <div className="stock-detail-header__watchlist">
            <button type="button" className="secondary-button" onClick={() => void addToWatchlist()}>{auth.user ? 'Add to watchlist' : 'Sign in to watchlist'}</button>
            {watchlistMessage && <span role="status">{watchlistMessage}</span>}
          </div>
        </header>

        <section className="stock-detail-metrics" aria-label="Trading details">
          <dl className="stock-detail-dl">
            <div className="stock-detail-dl__item">
              <dt>Open</dt>
              <dd>{formatNpr(current.open)}</dd>
            </div>
            <div className="stock-detail-dl__item">
              <dt>High</dt>
              <dd>{formatNpr(current.high)}</dd>
            </div>
            <div className="stock-detail-dl__item">
              <dt>Low</dt>
              <dd>{formatNpr(current.low)}</dd>
            </div>
            <div className="stock-detail-dl__item">
              <dt>Prev. Close</dt>
              <dd>{formatNpr(detail.previous_close)}</dd>
            </div>
            <div className="stock-detail-dl__item">
              <dt>Volume</dt>
              <dd>{formatInteger(current.volume)}</dd>
            </div>
            <div className="stock-detail-dl__item">
              <dt>52W High</dt>
              <dd>{formatNpr(detail.fifty_two_week_high)}</dd>
            </div>
            <div className="stock-detail-dl__item">
              <dt>52W Low</dt>
              <dd>{formatNpr(detail.fifty_two_week_low)}</dd>
            </div>
          </dl>
        </section>

        <section className="stock-detail-chart" aria-label="Price history">
          <div className="stock-detail-chart__heading">
            <div>
              <h2>Price History</h2>
              <span>
                {timeframe === '1D'
                  ? 'Intraday Trading Observations'
                  : 'Historical closing prices'}
              </span>
            </div>
            <div className="timeframe-selector" role="group" aria-label="Chart timeframe">
              {(['1D', '1W', '1M', '1Y', 'ALL'] as const).map((tf) => (
                <button
                  key={tf}
                  type="button"
                  className={`timeframe-button ${timeframe === tf ? 'timeframe-button--active' : ''}`}
                  onClick={() => setTimeframe(tf)}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>
          {timeframe === '1D' && isIntradayLoading ? (
            <div className="chart-empty-state">
              <p>Loading intraday observations for {detail.symbol}…</p>
            </div>
          ) : timeframe === '1D' && (!intraday || intraday.length === 0) ? (
            <div className="chart-empty-state">
              <p>No intraday trading records available for {detail.symbol}.</p>
              <p className="chart-empty-state__hint">
                Live intraday observations are recorded during active market sessions. Select 1W, 1M,
                1Y, or ALL to view historical closing prices.
              </p>
            </div>
          ) : (
            <>
              <section className="technical-controls" aria-labelledby="technical-controls-heading">
                <div className="technical-controls__heading"><div><h2 id="technical-controls-heading">Technical analysis</h2><p>Indicators use only the observations visible in the selected timeframe.</p></div><span>Historical · no recommendations</span></div>
                <div className="technical-controls__grid">
                  <label><input aria-label="Show candlesticks" type="checkbox" checked={chartOptions.candleMode} onChange={() => toggleChartOption('candleMode')} /> Candlesticks</label>
                  <label><input aria-label="Show volume" type="checkbox" checked={chartOptions.showVolume} onChange={() => toggleChartOption('showVolume')} /> Volume</label>
                  <label><input aria-label="Show SMA" type="checkbox" checked={chartOptions.showSma} onChange={() => toggleChartOption('showSma')} /> SMA <input aria-label="SMA period" type="number" min="2" max="200" value={periods.sma} onChange={(event) => updatePeriod('sma', event.target.value)} /></label>
                  <label><input aria-label="Show EMA" type="checkbox" checked={chartOptions.showEma} onChange={() => toggleChartOption('showEma')} /> EMA <input aria-label="EMA period" type="number" min="2" max="200" value={periods.ema} onChange={(event) => updatePeriod('ema', event.target.value)} /></label>
                  <label><input aria-label="Show Bollinger Bands" type="checkbox" checked={chartOptions.showBollinger} onChange={() => toggleChartOption('showBollinger')} /> Bollinger Bands</label>
                  <label><input aria-label="Show RSI" type="checkbox" checked={chartOptions.showRsi} onChange={() => toggleChartOption('showRsi')} /> RSI <input aria-label="RSI period" type="number" min="2" max="200" value={periods.rsi} onChange={(event) => updatePeriod('rsi', event.target.value)} /></label>
                  <label><input aria-label="Show MACD" type="checkbox" checked={chartOptions.showMacd} onChange={() => toggleChartOption('showMacd')} /> MACD</label>
                </div>
              </section>
              {indicators && <div className="technical-status" aria-live="polite">{Object.entries(indicators.availability).filter(([key]) => chartOptions[`show${key.charAt(0).toUpperCase()}${key.slice(1)}` as keyof ChartDisplayOptions]).map(([key, status]) => <p key={key} className={status.available ? 'technical-status__item technical-status__item--available' : 'technical-status__item'}>{status.message}</p>)}</div>}
              <PriceChart data={chartData} indicators={indicators ?? undefined} options={chartOptions} />
            </>
          )}
        </section>

        <p className="stock-detail-footer">
          {liveQuote ? `${live.state?.provider ?? 'LIVE'} · Provider observation ` : 'Last Observation '}{formatObservationDate(current.last_updated)} · {liveQuote ? 'Current quote' : `${detail.data_freshness ?? 'HISTORICAL'} synthetic/historical · Historical records`}
        </p>
      </div>
    </main>
  )
}

export default StockDetailPage
