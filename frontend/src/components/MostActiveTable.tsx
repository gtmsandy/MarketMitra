import { Link } from 'react-router-dom'

import type { MostActiveStock } from '../types/market'
import { formatCompactNpr, formatInteger, formatNpr } from '../utils/formatters'

type MostActiveTableProps = {
  rows: MostActiveStock[]
  limit?: number
}

function MostActiveTable({ rows, limit = 15 }: MostActiveTableProps) {
  const sorted = [...rows].sort((a, b) => b.turnover - a.turnover)
  const displayRows = limit ? sorted.slice(0, limit) : sorted

  return (
    <section className="data-panel data-panel--wide" aria-labelledby="most-active-heading">
      <div className="data-panel__heading">
        <h2 id="most-active-heading">Most Active</h2>
        <span>{displayRows.length > 0 ? `Top ${displayRows.length} by turnover` : 'By turnover'}</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Stock</th>
              <th scope="col">LTP</th>
              <th scope="col">Volume</th>
              <th scope="col">Turnover</th>
            </tr>
          </thead>
          <tbody>
            {displayRows.length === 0 ? (
              <tr>
                <td colSpan={4} className="table-empty">
                  No active trading records.
                </td>
              </tr>
            ) : (
              displayRows.map((stock) => (
                <tr key={stock.symbol}>
                  <th scope="row">
                    <Link className="stock-link" to={`/stocks/${stock.symbol}`}>
                      <span className="stock-symbol">{stock.symbol}</span>
                      <span className="company-name">{stock.company_name}</span>
                    </Link>
                  </th>
                  <td>{formatNpr(stock.ltp)}</td>
                  <td>{formatInteger(stock.volume)}</td>
                  <td>{formatCompactNpr(stock.turnover)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default MostActiveTable

