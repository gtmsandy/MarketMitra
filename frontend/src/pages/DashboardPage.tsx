import { useCallback, useEffect, useRef, useState } from 'react'

import {
  getMarketOverview,
  getMostActiveStocks,
  getTopGainers,
  getTopLosers,
} from '../api/market'
import ErrorState from '../components/ErrorState'
import LoadingState from '../components/LoadingState'
import MarketMetricCard from '../components/MarketMetricCard'
import MarketMoversTable from '../components/MarketMoversTable'
import MostActiveTable from '../components/MostActiveTable'
import type { MarketMover, MarketOverview, MostActiveStock } from '../types/market'
import {
  formatCompactNpr,
  formatInteger,
  formatNumber,
  formatPercentage,
  formatSignedNumber,
  getChangeTone,
} from '../utils/formatters'

type DashboardData = {
  overview: MarketOverview
  gainers: MarketMover[]
  losers: MarketMover[]
  mostActive: MostActiveStock[]
}

type DashboardPageProps = {
  onOverviewLoaded: (overview: MarketOverview) => void
}

function DashboardPage({ onOverviewLoaded }: DashboardPageProps) {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)
  const isRefreshingRef = useRef(false)

  const loadDashboard = useCallback(async () => {
    setIsLoading(true)
    setHasError(false)

    try {
      const [overview, gainers, losers, mostActive] = await Promise.all([
        getMarketOverview(),
        getTopGainers(),
        getTopLosers(),
        getMostActiveStocks(),
      ])

      setDashboardData({ overview, gainers, losers, mostActive })
      onOverviewLoaded(overview)
    } catch {
      setDashboardData(null)
      setHasError(true)
    } finally {
      setIsLoading(false)
    }
  }, [onOverviewLoaded])

  const refreshData = useCallback(async () => {
    if (isRefreshingRef.current) return
    isRefreshingRef.current = true
    try {
      const [overview, gainers, losers, mostActive] = await Promise.all([
        getMarketOverview(),
        getTopGainers(),
        getTopLosers(),
        getMostActiveStocks(),
      ])
      setDashboardData({ overview, gainers, losers, mostActive })
      onOverviewLoaded(overview)
    } catch {
      // Background poll failure: preserve existing dashboard state without disruption
    } finally {
      isRefreshingRef.current = false
    }
  }, [onOverviewLoaded])

  useEffect(() => {
    void loadDashboard()
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

  const { overview, gainers, losers, mostActive } = dashboardData
  const indexChange = `${formatSignedNumber(overview.index_change)} (${formatPercentage(overview.index_change_percent)})`

  return (
    <main className="dashboard-content">
      <section className="overview-section" aria-labelledby="market-overview-heading">
        <div className="section-heading">
          <div>
            <p className="section-heading__eyebrow">Market Overview</p>
            <h1 id="market-overview-heading">NEPSE Market Summary</h1>
          </div>
          <p>Current values reflect latest database-backed market records.</p>
        </div>
        <div className="metric-grid">
          <MarketMetricCard
            label="NEPSE Index"
            value={formatNumber(overview.nepse_index, 2)}
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

      <section className="market-tables" aria-label="Market activity">
        <MarketMoversTable title="Top Gainers" rows={gainers} limit={10} />
        <MarketMoversTable title="Top Losers" rows={losers} limit={10} />
        <MostActiveTable rows={mostActive} limit={15} />
      </section>
    </main>
  )
}

export default DashboardPage
