import { Link } from 'react-router-dom'

import type { MostActiveStock } from '../types/market'
import { formatCompactNpr, formatInteger, formatNpr } from '../utils/formatters'

type MostActiveTableProps = {
  rows: MostActiveStock[]
}

function MostActiveTable({ rows }: MostActiveTableProps) {
  return (
    <section className="data-panel data-panel--wide" aria-labelledby="most-active-heading">
      <div className="data-panel__heading">
        <h2 id="most-active-heading">Most Active</h2>
        <span>By turnover</span>
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
            {rows.map((stock) => (
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
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default MostActiveTable

