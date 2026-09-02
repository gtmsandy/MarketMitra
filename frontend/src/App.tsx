import { useCallback, useEffect, useState } from 'react'

import {
  getMarketOverview,
  getMostActiveStocks,
  getTopGainers,
  getTopLosers,
} from './api/market'
import AppHeader from './components/AppHeader'
import ErrorState from './components/ErrorState'
import LoadingState from './components/LoadingState'
import MarketMetricCard from './components/MarketMetricCard'
import MarketMoversTable from './components/MarketMoversTable'
import MostActiveTable from './components/MostActiveTable'
import type { MarketMover, MarketOverview, MostActiveStock } from './types/market'
import {
  formatCompactNpr,
  formatInteger,
  formatNumber,
  formatPercentage,
  formatSignedNumber,
  getChangeTone,
} from './utils/formatters'

type DashboardData = {
  overview: MarketOverview
  gainers: MarketMover[]
  losers: MarketMover[]
  mostActive: MostActiveStock[]
}

function App() {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)

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
    } catch {
      setDashboardData(null)
      setHasError(true)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadDashboard()
  }, [loadDashboard])

  if (isLoading) {
    return <LoadingState />
  }

  if (hasError || !dashboardData) {
    return <ErrorState onRetry={() => void loadDashboard()} />
  }

  const { overview, gainers, losers, mostActive } = dashboardData
  const indexChange = `${formatSignedNumber(overview.index_change)} (${formatPercentage(overview.index_change_percent)})`

  return (
    <div className="dashboard">
      <AppHeader overview={overview} />
      <main className="dashboard-content">
        <section className="overview-section" aria-labelledby="market-overview-heading">
          <div className="section-heading">
            <div>
              <p className="section-heading__eyebrow">Market Overview</p>
              <h1 id="market-overview-heading">NEPSE Market Summary</h1>
            </div>
            <p>Current values reflect the configured sample market provider.</p>
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
              value={formatCompactNpr(overview.turnover)}
              detail="Total traded value"
            />
            <MarketMetricCard
              label="Total Volume"
              value={formatInteger(overview.total_volume)}
              detail="Shares traded"
            />
            <MarketMetricCard
              label="Transactions"
              value={formatInteger(overview.total_transactions)}
              detail="Completed trades"
            />
          </div>
        </section>

        <section className="market-tables" aria-label="Market activity">
          <MarketMoversTable title="Top Gainers" rows={gainers} />
          <MarketMoversTable title="Top Losers" rows={losers} />
          <MostActiveTable rows={mostActive} />
        </section>
      </main>
    </div>
  )
}

export default App
