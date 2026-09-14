import { useEffect, useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import AppHeader from './components/AppHeader'
import DashboardPage from './pages/DashboardPage'
import StockDetailPage from './pages/StockDetailPage'
import MarketMoversPage from './pages/MarketMoversPage'
import SectorPerformancePage from './pages/SectorPerformancePage'
import MarketHeatmapPage from './pages/MarketHeatmapPage'
import NotFoundPage from './pages/NotFoundPage'
import { getMarketOverview } from './api/market'
import type { MarketOverview } from './types/market'

function App() {
  const [overview, setOverview] = useState<MarketOverview | null>(null)

  useEffect(() => {
    let cancelled = false
    void getMarketOverview().then((data) => { if (!cancelled) setOverview(data) }).catch(() => undefined)
    return () => { cancelled = true }
  }, [])

  return (
    <BrowserRouter>
      <div className="dashboard">
        <AppHeader overview={overview} />
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/market/movers" element={<MarketMoversPage />} />
          <Route path="/market/sectors" element={<SectorPerformancePage />} />
          <Route path="/market/heatmap" element={<MarketHeatmapPage />} />
          <Route path="/stocks/:symbol" element={<StockDetailPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
