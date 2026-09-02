type MarketMetricCardProps = {
  label: string
  value: string
  detail?: string
  change?: string
  tone?: 'positive' | 'negative' | 'neutral'
}

function MarketMetricCard({
  label,
  value,
  detail,
  change,
  tone = 'neutral',
}: MarketMetricCardProps) {
  return (
    <article className="metric-card">
      <p className="metric-card__label">{label}</p>
      <p className="metric-card__value">{value}</p>
      {(change || detail) && (
        <div className="metric-card__meta">
          {change && <span className={`change change--${tone}`}>{change}</span>}
          {detail && <span>{detail}</span>}
        </div>
      )}
    </article>
  )
}

export default MarketMetricCard
