import { Link } from 'react-router-dom'

import type { MarketMover } from '../types/market'
import {
  formatInteger,
  formatNpr,
  formatPercentage,
  getChangeTone,
} from '../utils/formatters'

type MarketMoversTableProps = {
  title: string
  rows: MarketMover[]
  limit?: number
}

function MarketMoversTable({ title, rows, limit = 10 }: MarketMoversTableProps) {
  const isGainers = title.toLowerCase().includes('gainer')
  const sorted = [...rows].sort((a, b) =>
    isGainers
      ? b.change_percent - a.change_percent
      : a.change_percent - b.change_percent
  )
  const displayRows = limit ? sorted.slice(0, limit) : sorted

  return (
    <section className="data-panel" aria-labelledby={`${title}-heading`}>
      <div className="data-panel__heading">
        <h2 id={`${title}-heading`}>{title}</h2>
        <span>{displayRows.length > 0 ? `Top ${displayRows.length} · Change %` : 'Change %'}</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Stock</th>
              <th scope="col">LTP</th>
              <th scope="col">Change</th>
              <th scope="col">Volume</th>
            </tr>
          </thead>
          <tbody>
            {displayRows.length === 0 ? (
              <tr>
                <td colSpan={4} className="table-empty">
                  No records available.
                </td>
              </tr>
            ) : (
              displayRows.map((stock) => {
                const tone = getChangeTone(stock.change_percent)

                return (
                  <tr key={stock.symbol}>
                    <th scope="row">
                      <Link className="stock-link" to={`/stocks/${stock.symbol}`}>
                        <span className="stock-symbol">{stock.symbol}</span>
                        <span className="company-name">{stock.company_name}</span>
                      </Link>
                    </th>
                    <td>{formatNpr(stock.ltp)}</td>
                    <td className={`change change--${tone}`}>
                      {formatPercentage(stock.change_percent)}
                    </td>
                    <td>{formatInteger(stock.volume)}</td>
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

export default MarketMoversTable

