import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getStockDetail, getStockHistory, getStockIntraday } from '../api/market'
import PriceChart from '../components/PriceChart'
import type { IntradayPricePoint, PriceHistoryPoint, StockDetail } from '../types/market'
import {
  formatObservationDate,
  formatInteger,
  formatNpr,
  formatPercentage,
  formatSignedNumber,
  getChangeTone,
} from '../utils/formatters'

type Timeframe = '1D' | '1W' | '1M' | '1Y' | 'ALL'

function StockDetailPage() {
  const { symbol } = useParams<{ symbol: string }>()
  const [detail, setDetail] = useState<StockDetail | null>(null)
  const [history, setHistory] = useState<PriceHistoryPoint[]>([])
  const [timeframe, setTimeframe] = useState<Timeframe>('ALL')
  const [intraday, setIntraday] = useState<IntradayPricePoint[] | null>(null)
  const [isIntradayLoading, setIsIntradayLoading] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
    void loadStock()
  }, [loadStock])

  // Lazy-load intraday observations when 1D is selected
  useEffect(() => {
    if (timeframe === '1D' && symbol && intraday === null) {
      setIsIntradayLoading(true)
      getStockIntraday(symbol)
        .then((data) => setIntraday(data))
        .catch(() => setIntraday([]))
        .finally(() => setIsIntradayLoading(false))
    }
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

  const tone = getChangeTone(detail.change)

  return (
    <main className="stock-detail-page">
      <div className="stock-detail-page__content">
        <Link to="/" className="back-link">← Dashboard</Link>

        <header className="stock-detail-header">
          <div>
            <h1 className="stock-detail-header__symbol">{detail.symbol}</h1>
            <p className="stock-detail-header__name">{detail.company_name}</p>
          </div>
          <div className="stock-detail-header__price">
            <span className="stock-detail-header__ltp">{formatNpr(detail.ltp)}</span>
            <span className={`change change--${tone}`}>
              {formatSignedNumber(detail.change)} ({formatPercentage(detail.change_percent)})
            </span>
          </div>
        </header>

        <section className="stock-detail-metrics" aria-label="Trading details">
          <dl className="stock-detail-dl">
            <div className="stock-detail-dl__item">
              <dt>Open</dt>
              <dd>{formatNpr(detail.open)}</dd>
            </div>
            <div className="stock-detail-dl__item">
              <dt>High</dt>
              <dd>{formatNpr(detail.high)}</dd>
            </div>
            <div className="stock-detail-dl__item">
              <dt>Low</dt>
              <dd>{formatNpr(detail.low)}</dd>
            </div>
            <div className="stock-detail-dl__item">
              <dt>Prev. Close</dt>
              <dd>{formatNpr(detail.previous_close)}</dd>
            </div>
            <div className="stock-detail-dl__item">
              <dt>Volume</dt>
              <dd>{formatInteger(detail.volume)}</dd>
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
                  : 'Database records · Closing price'}
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
            <PriceChart data={chartData} />
          )}
        </section>

        <p className="stock-detail-footer">
          Last Observation {formatObservationDate(detail.last_updated)} · Database records
        </p>
      </div>
    </main>
  )
}

export default StockDetailPage
