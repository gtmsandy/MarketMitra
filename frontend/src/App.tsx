import { useCallback, useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import AppHeader from './components/AppHeader'
import DashboardPage from './pages/DashboardPage'
import StockDetailPage from './pages/StockDetailPage'
import type { MarketOverview } from './types/market'

function App() {
  const [overview, setOverview] = useState<MarketOverview | null>(null)

  const handleOverviewLoaded = useCallback((data: MarketOverview) => {
    setOverview(data)
  }, [])

  return (
    <BrowserRouter>
      <div className="dashboard">
        <AppHeader overview={overview} />
        <Routes>
          <Route path="/" element={<DashboardPage onOverviewLoaded={handleOverviewLoaded} />} />
          <Route path="/stocks/:symbol" element={<StockDetailPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
