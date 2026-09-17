import { Link, NavLink } from 'react-router-dom'

import type { MarketOverview } from '../types/market'
import { formatObservationDate } from '../utils/formatters'
import StockSearch from './StockSearch'
import { useLiveMarket } from '../live/useLiveMarket'

type AppHeaderProps = {
  overview: MarketOverview | null
}

function AppHeader({ overview }: AppHeaderProps) {
  const live = useLiveMarket()
  const rawStatus = overview?.market_status.toUpperCase() || 'CLOSED'
  let statusClass = 'closed'
  if (rawStatus === 'OPEN') statusClass = 'open'
  else if (rawStatus === 'HALTED') statusClass = 'halted'
  else if (rawStatus === 'DATA_UNAVAILABLE') statusClass = 'unavailable'
  else if (rawStatus === 'STALE') statusClass = 'stale'

  const dataBadge = live.state?.provider === 'DEVELOPMENT_REPLAY' ? 'DEVELOPMENT REPLAY' : (overview?.data_freshness?.replace('_', ' ') ?? (rawStatus === 'OPEN' ? 'LIVE' : 'HISTORICAL'))
  const badgeClass = dataBadge === 'LIVE' ? 'market-badge--live' : 'market-badge--historical'
  return (
    <header className="app-header">
      <div className="app-header__identity">
        <Link className="app-header__brand" to="/" aria-label="MarketMitra dashboard">
          MarketMitra
        </Link>
        <span className="app-header__section">Market Dashboard</span>
      </div>
      <nav className="app-header__nav" aria-label="Primary navigation">
        <NavLink to="/" end>Dashboard</NavLink><NavLink to="/market/movers">Movers</NavLink><NavLink to="/market/sectors">Sectors</NavLink><NavLink to="/market/heatmap">Heatmap</NavLink>
      </nav>
      <StockSearch />
      <details className="app-header__mobile-nav"><summary>Menu</summary><nav aria-label="Mobile navigation"><NavLink to="/" end>Dashboard</NavLink><NavLink to="/market/movers">Movers</NavLink><NavLink to="/market/sectors">Sectors</NavLink><NavLink to="/market/heatmap">Heatmap</NavLink></nav></details>
      <div className="app-header__meta">
        {overview ? (
          <>
            <span className={`market-status market-status--${statusClass}`}>
              Market {overview.market_status}
            </span>
            <span className={`market-badge ${badgeClass}`}>{dataBadge}</span>
            <span>Last Updated {formatObservationDate(overview.last_updated)}</span>
            <span>Snapshot {overview.observation_date ?? '—'}</span>
          </>
        ) : (
          <span>Market data loading</span>
        )}
      </div>
    </header>
  )
}

export default AppHeader
