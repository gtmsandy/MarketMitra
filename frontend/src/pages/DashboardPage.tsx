import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  getMarketBreadth,
  getMarketOverview,
  getTopGainers,
  getTopLosers,
} from '../api/market'
import ErrorState from '../components/ErrorState'
import LoadingState from '../components/LoadingState'
import MarketBreadthCard from '../components/MarketBreadthCard'
import MarketMetricCard from '../components/MarketMetricCard'
import MarketMoversTable from '../components/MarketMoversTable'
import type {
  MarketBreadth,
  MarketMover,
  MarketOverview,
} from '../types/market'
import {
  formatCompactNpr,
  formatInteger,
  formatNumber,
  formatPercentage,
  formatSignedNumber,
  getChangeTone,
} from '../utils/formatters'
import { useLiveMarket } from '../live/useLiveMarket'

type DashboardData = {
  overview: MarketOverview
  gainers: MarketMover[]
  losers: MarketMover[]
  breadth: MarketBreadth | null
}

function DashboardPage() {
  const live = useLiveMarket()
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)
  const isRefreshingRef = useRef(false)

  const loadDashboard = useCallback(async () => {
    setIsLoading(true)
    setHasError(false)

    try {
      const [overview, gainers, losers, breadth] =
        await Promise.all([
          getMarketOverview(),
          getTopGainers(),
          getTopLosers(),
          getMarketBreadth().catch(() => null),
        ])

      setDashboardData({ overview, gainers, losers, breadth })
    } catch {
      setDashboardData(null)
      setHasError(true)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const refreshData = useCallback(async () => {
    if (isRefreshingRef.current) return
    isRefreshingRef.current = true
    try {
      const [overview, gainers, losers, breadth] =
        await Promise.all([
          getMarketOverview(),
          getTopGainers(),
          getTopLosers(),
          getMarketBreadth().catch(() => null),
        ])

      setDashboardData({ overview, gainers, losers, breadth })
    } catch {
      // Background poll failure: preserve existing dashboard state without disruption
    } finally {
      isRefreshingRef.current = false
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadDashboard() }, 0)
    return () => window.clearTimeout(timer)
  }, [loadDashboard])

  // Auto-refresh: 30s polling only when market status is OPEN
  useEffect(() => {
    if (!dashboardData || dashboardData.overview.market_status.toUpperCase() !== 'OPEN') {
      return
    }
    const timer = setInterval(() => {
      void refreshData()
    }, 30000)
    return () => clearInterval(timer)
  }, [dashboardData, refreshData])
  if (isLoading) {
    return <LoadingState />
  }

  if (hasError || !dashboardData) {
    return <ErrorState onRetry={() => void loadDashboard()} />
  }

  const { overview, gainers, losers, breadth } = dashboardData
  const liveIndex = live.state?.index ?? overview.nepse_index
  const liveBreadth = live.state && Object.keys(live.state.quotes).length ? (() => { const qs=Object.values(live.state!.quotes); const a=qs.filter(q=>(q.change_percent??0)>0).length; const d=qs.filter(q=>(q.change_percent??0)<0).length; const u=qs.length-a-d; const t=qs.length; return {observation_date:'CURRENT', advancing_count:a, declining_count:d, unchanged_count:u, total_count:t, advance_decline_ratio:d?a/d:null, advancing_percent:t?a*100/t:0, declining_percent:t?d*100/t:0, unchanged_percent:t?u*100/t:0} })() : breadth
  const indexChange = `${formatSignedNumber(overview.index_change)} (${formatPercentage(overview.index_change_percent)})`

  return (
    <main className="dashboard-content">
      <section className="overview-section" aria-labelledby="market-overview-heading">
        <div className="section-heading">
          <div>
            <p className="section-heading__eyebrow">Market Overview</p>
            <h1 id="market-overview-heading">NEPSE Market Summary</h1>
          </div>
          <p>
            {overview.data_freshness === 'LIVE'
              ? 'Current values reflect the latest authorized market feed.'
              : 'Historical snapshot for the observation date shown.'}
          </p>
        </div>
        <div className="metric-grid">
          <MarketMetricCard
            label="NEPSE Index"
            value={formatNumber(liveIndex, 2)}
            change={indexChange}
            detail="Index movement"
            tone={getChangeTone(overview.index_change)}
          />
          <MarketMetricCard
            label="Turnover"
            value={overview.turnover !== null ? formatCompactNpr(overview.turnover) : "—"}
            detail="Total traded value"
          />
          <MarketMetricCard
            label="Total Volume"
            value={overview.total_volume !== null ? formatInteger(overview.total_volume) : "—"}
            detail="Shares traded"
          />
          <MarketMetricCard
            label="Transactions"
            value={overview.total_transactions !== null ? formatInteger(overview.total_transactions) : "—"}
            detail="Completed trades"
          />
        </div>
      </section>

      <div className="dashboard-analytics-grid">
        <MarketBreadthCard breadth={liveBreadth} />
      </div>

      <section className="market-tables" aria-label="Market activity">
        <MarketMoversTable title="Top Equity Gainers" rows={gainers} limit={10} />
        <MarketMoversTable title="Top Equity Losers" rows={losers} limit={10} />
      </section>
      <section className="dashboard-action-grid" aria-label="More market analytics">
        <Link className="dashboard-action-card" to="/market/movers"><strong>All market movers</strong><span>Gainers, losers and most active equities</span></Link>
        <Link className="dashboard-action-card" to="/market/sectors"><strong>Sector performance</strong><span>Compare common equity sectors</span></Link>
        <Link className="dashboard-action-card" to="/market/heatmap"><strong>Market heatmap</strong><span>Scan performance across the session</span></Link>
      </section>
    </main>
  )
}

export default DashboardPage
