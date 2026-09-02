import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getStockDetail, getStockHistory } from '../api/market'
import PriceChart from '../components/PriceChart'
import type { PriceHistoryPoint, StockDetail } from '../types/market'
import {
  formatDateTime,
  formatInteger,
  formatNpr,
  formatPercentage,
  formatSignedNumber,
  getChangeTone,
} from '../utils/formatters'

function StockDetailPage() {
  const { symbol } = useParams<{ symbol: string }>()
  const [detail, setDetail] = useState<StockDetail | null>(null)
  const [history, setHistory] = useState<PriceHistoryPoint[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadStock = useCallback(async () => {
    if (!symbol) return
    setIsLoading(true)
    setError(null)

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
            <h2>Price History</h2>
            <span>Sample data · Closing price</span>
          </div>
          <PriceChart data={history} />
        </section>

        <p className="stock-detail-footer">
          Last Updated {formatDateTime(detail.last_updated)} · Sample data
        </p>
      </div>
    </main>
  )
}

export default StockDetailPage
