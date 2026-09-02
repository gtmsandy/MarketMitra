import { Link } from 'react-router-dom'

import type { MarketOverview } from '../types/market'
import { formatDateTime } from '../utils/formatters'
import StockSearch from './StockSearch'

type AppHeaderProps = {
  overview: MarketOverview | null
}

function AppHeader({ overview }: AppHeaderProps) {
  const statusClass = overview
    ? overview.market_status.toLowerCase() === 'open' ? 'open' : 'closed'
    : ''

  return (
    <header className="app-header">
      <div className="app-header__identity">
        <Link className="app-header__brand" to="/" aria-label="MarketMitra dashboard">
          MarketMitra
        </Link>
        <span className="app-header__section">Market Dashboard</span>
      </div>
      <StockSearch />
      <div className="app-header__meta">
        {overview ? (
          <>
            <span className={`market-status market-status--${statusClass}`}>
              Market {overview.market_status}
            </span>
            <span>Last Updated {formatDateTime(overview.last_updated)}</span>
            <span>Sample data</span>
          </>
        ) : (
          <span>Sample data</span>
        )}
      </div>
    </header>
  )
}

export default AppHeader
