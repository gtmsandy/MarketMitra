import { Link } from 'react-router-dom'

import type { MarketOverview } from '../types/market'
import { formatObservationDate } from '../utils/formatters'
import StockSearch from './StockSearch'

type AppHeaderProps = {
  overview: MarketOverview | null
}

function AppHeader({ overview }: AppHeaderProps) {
  const rawStatus = overview?.market_status.toUpperCase() || 'CLOSED'
  let statusClass = 'closed'
  if (rawStatus === 'OPEN') statusClass = 'open'
  else if (rawStatus === 'HALTED') statusClass = 'halted'
  else if (rawStatus === 'DATA_UNAVAILABLE') statusClass = 'unavailable'
  else if (rawStatus === 'STALE') statusClass = 'stale'

  // Determine data freshness badge
  const dataBadge = rawStatus === 'OPEN' ? 'LIVE' : 'HISTORICAL'
  const badgeClass = rawStatus === 'OPEN' ? 'market-badge--live' : 'market-badge--historical'
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
            <span className={`market-badge ${badgeClass}`}>{dataBadge}</span>
            <span>Last Updated {formatObservationDate(overview.last_updated)}</span>
            <span>Database records</span>
          </>
        ) : (
          <span>Database records</span>
        )}
      </div>
    </header>
  )
}

export default AppHeader
