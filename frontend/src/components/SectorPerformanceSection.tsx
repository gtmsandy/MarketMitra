import type { SectorPerformance } from '../types/market'
import { formatCompactNpr, formatInteger, formatPercentage, getChangeTone } from '../utils/formatters'

type SectorPerformanceSectionProps = {
  sectors: SectorPerformance[]
}

function SectorPerformanceSection({ sectors }: SectorPerformanceSectionProps) {
  return (
    <section className="data-panel data-panel--wide" aria-labelledby="sector-performance-heading">
      <div className="data-panel__heading">
        <div>
          <h2 id="sector-performance-heading">Equity Sector Performance</h2>
          <span>Equal-weighted constituent average · Ranked by daily % change</span>
        </div>
        <span className="methodology-tag">Methodology: Constituent % Average</span>
      </div>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Sector</th>
              <th scope="col">Avg Change</th>
              <th scope="col">Constituents</th>
              <th scope="col">Breadth (Adv / Dec / Unch)</th>
              <th scope="col">Volume</th>
              <th scope="col">Turnover</th>
            </tr>
          </thead>
          <tbody>
            {sectors.length === 0 ? (
              <tr>
                <td colSpan={6} className="table-empty">
                  No sector performance data available.
                </td>
              </tr>
            ) : (
              sectors.map((s) => {
                const tone = getChangeTone(s.average_change_percent)

                return (
                  <tr key={s.sector}>
                    <th scope="row">
                      <span className="sector-name">{s.sector}</span>
                    </th>
                    <td className={`change change--${tone} change--strong`}>
                      {formatPercentage(s.average_change_percent)}
                    </td>
                    <td>{formatInteger(s.stock_count)} stocks</td>
                    <td>
                      <span className="sector-breadth">
                        <span className="text-adv">+{s.advancing_count}</span> /{' '}
                        <span className="text-dec">-{s.declining_count}</span> /{' '}
                        <span className="text-unc">{s.unchanged_count}</span>
                      </span>
                    </td>
                    <td>{formatInteger(s.total_volume)}</td>
                    <td>{formatCompactNpr(s.total_turnover)}</td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default SectorPerformanceSection
