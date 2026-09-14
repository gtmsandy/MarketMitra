import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'

import type { HeatmapItem } from '../types/market'
import { formatCompactNpr, formatNpr, formatPercentage } from '../utils/formatters'

type MarketHeatmapSectionProps = {
  items: HeatmapItem[]
}

function getHeatmapColor(pct: number): string {
  if (pct >= 6.0) return '#065f46'    // Strong positive (emerald-800)
  if (pct >= 3.0) return '#047857'    // Positive (emerald-700)
  if (pct >= 1.0) return '#059669'    // Mild positive (emerald-600)
  if (pct > 0.0) return '#10b981'     // Slight positive (emerald-500)
  if (pct === 0.0) return '#334155'   // Neutral (slate-700)
  if (pct <= -6.0) return '#881337'   // Strong negative (rose-900)
  if (pct <= -3.0) return '#9f1239'   // Negative (rose-800)
  if (pct <= -1.0) return '#be123c'   // Mild negative (rose-700)
  return '#e11d48'                    // Slight negative (rose-600)
}

function MarketHeatmapSection({ items }: MarketHeatmapSectionProps) {
  const [selectedSector, setSelectedSector] = useState<string>('ALL')

  // Extract unique sector list
  const sectors = useMemo(() => {
    const set = new Set<string>()
    for (const item of items) {
      if (item.sector) set.add(item.sector)
    }
    return ['ALL', ...Array.from(set).sort()]
  }, [items])

  // Filter items by sector for the complete common-equity session
  const filteredItems = useMemo(() => {
    let list = items
    if (selectedSector !== 'ALL') {
      list = list.filter((i) => i.sector === selectedSector)
    }
    // Display up to 60 prominent stocks
    return list
  }, [items, selectedSector])

  return (
    <section className="data-panel data-panel--wide" aria-labelledby="heatmap-heading">
      <div className="data-panel__heading">
        <div>
          <h2 id="heatmap-heading">Equity Market Heatmap</h2>
          <span>Color intensity by daily % change · Equal-weight tiles</span>
        </div>
        <div className="heatmap-controls">
          <label htmlFor="heatmap-sector-select" className="sr-only">
            Filter by sector
          </label>
          <select
            id="heatmap-sector-select"
            className="heatmap-select"
            value={selectedSector}
            onChange={(e) => setSelectedSector(e.target.value)}
          >
            {sectors.map((sec) => (
              <option key={sec} value={sec}>
                {sec === 'ALL' ? 'All Sectors' : sec}
              </option>
            ))}
          </select>
          <span className="methodology-tag">Tile Sizing: Neutral Grid</span>
        </div>
      </div>

      <div className="heatmap-container">
        {filteredItems.length === 0 ? (
          <div className="table-empty">No active trading stocks in this view.</div>
        ) : (
          <div className="heatmap-grid" role="region" aria-label="Stock heatmap grid">
            {filteredItems.map((stock) => {
              const bgColor = getHeatmapColor(stock.change_percent)

              return (
                <Link
                  key={stock.symbol}
                  to={`/stocks/${stock.symbol}`}
                  className="heatmap-tile"
                  style={{ backgroundColor: bgColor }}
                  title={`${stock.symbol}: ${stock.company_name} | LTP: ${formatNpr(stock.ltp)} | Turnover: ${formatCompactNpr(stock.turnover)}`}
                >
                  <span className="heatmap-tile__symbol">{stock.symbol}</span>
                  <span className="heatmap-tile__change">{formatPercentage(stock.change_percent)}</span>
                  <span className="heatmap-tile__price">{formatNpr(stock.ltp, 0)}</span>
                </Link>
              )
            })}
          </div>
        )}
      </div>

      <div className="heatmap-legend" aria-hidden="true">
        <span className="legend-item"><span className="legend-swatch" style={{ background: '#065f46' }} /> &gt; +6%</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: '#059669' }} /> +1% to +6%</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: '#334155' }} /> 0%</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: '#be123c' }} /> -1% to -6%</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: '#881337' }} /> &lt; -6%</span>
      </div>
    </section>
  )
}

export default MarketHeatmapSection
