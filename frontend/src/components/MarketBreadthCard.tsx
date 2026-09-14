import type { MarketBreadth } from '../types/market'
import { formatInteger } from '../utils/formatters'

type MarketBreadthCardProps = {
  breadth: MarketBreadth | null
}

function MarketBreadthCard({ breadth }: MarketBreadthCardProps) {
  if (!breadth) {
    return (
      <section className="data-panel" aria-label="Equity Market Breadth">
        <div className="data-panel__heading">
          <h2>Equity Market Breadth</h2>
          <span>Advance · Decline metrics</span>
        </div>
        <div className="table-empty">No breadth data available.</div>
      </section>
    )
  }

  const {
    advancing_count,
    declining_count,
    unchanged_count,
    total_count,
    advance_decline_ratio,
    advancing_percent,
    declining_percent,
    unchanged_percent,
    observation_date,
  } = breadth

  const ratioLabel = advance_decline_ratio !== null ? advance_decline_ratio.toFixed(2) : '—'
  const ratioTone =
    advance_decline_ratio !== null
      ? advance_decline_ratio >= 1.0
        ? 'positive'
        : 'negative'
      : 'neutral'

  return (
    <section className="data-panel" aria-label="Equity Market Breadth">
      <div className="data-panel__heading">
        <h2>Equity Market Breadth</h2>
        <span>Traded Equities · Advances vs Declines · {observation_date}</span>
      </div>

      <div className="breadth-summary">
        <div className="breadth-stat breadth-stat--advancing">
          <span className="breadth-stat__label">Advancing</span>
          <span className="breadth-stat__value">{formatInteger(advancing_count)}</span>
          <span className="breadth-stat__pct">+{advancing_percent.toFixed(1)}%</span>
        </div>
        <div className="breadth-stat breadth-stat--declining">
          <span className="breadth-stat__label">Declining</span>
          <span className="breadth-stat__value">{formatInteger(declining_count)}</span>
          <span className="breadth-stat__pct">-{declining_percent.toFixed(1)}%</span>
        </div>
        <div className="breadth-stat breadth-stat--unchanged">
          <span className="breadth-stat__label">Unchanged</span>
          <span className="breadth-stat__value">{formatInteger(unchanged_count)}</span>
          <span className="breadth-stat__pct">{unchanged_percent.toFixed(1)}%</span>
        </div>
        <div className="breadth-stat breadth-stat--ratio">
          <span className="breadth-stat__label">A/D Ratio</span>
          <span className={`breadth-stat__value breadth-stat__value--${ratioTone}`}>{ratioLabel}</span>
          <span className="breadth-stat__pct">{formatInteger(total_count)} Total Traded</span>
        </div>
      </div>

      {/* Visual proportional ratio bar */}
      <div className="breadth-bar" role="progressbar" aria-label="Advance decline ratio bar">
        <div
          className="breadth-bar__segment breadth-bar__segment--adv"
          style={{ width: `${advancing_percent}%` }}
          title={`Advancing: ${advancing_percent}%`}
        />
        <div
          className="breadth-bar__segment breadth-bar__segment--dec"
          style={{ width: `${declining_percent}%` }}
          title={`Declining: ${declining_percent}%`}
        />
        <div
          className="breadth-bar__segment breadth-bar__segment--unc"
          style={{ width: `${unchanged_percent}%` }}
          title={`Unchanged: ${unchanged_percent}%`}
        />
      </div>
    </section>
  )
}

export default MarketBreadthCard
