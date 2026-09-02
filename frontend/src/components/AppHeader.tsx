import type { MarketOverview } from '../types/market'
import { formatDateTime } from '../utils/formatters'

type AppHeaderProps = {
  overview: MarketOverview
}

function AppHeader({ overview }: AppHeaderProps) {
  const statusClass = overview.market_status.toLowerCase() === 'open' ? 'open' : 'closed'

  return (
    <header className="app-header">
      <div className="app-header__identity">
        <a className="app-header__brand" href="/" aria-label="MarketMitra dashboard">
          MarketMitra
        </a>
        <span className="app-header__section">Market Dashboard</span>
      </div>
      <div className="app-header__meta">
        <span className={`market-status market-status--${statusClass}`}>
          Market {overview.market_status}
        </span>
        <span>Last Updated {formatDateTime(overview.last_updated)}</span>
        <span>Sample data</span>
      </div>
    </header>
  )
}

export default AppHeader
