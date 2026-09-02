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
}

function MarketMoversTable({ title, rows }: MarketMoversTableProps) {
  return (
    <section className="data-panel" aria-labelledby={`${title}-heading`}>
      <div className="data-panel__heading">
        <h2 id={`${title}-heading`}>{title}</h2>
        <span>Change %</span>
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
            {rows.map((stock) => {
              const tone = getChangeTone(stock.change_percent)

              return (
                <tr key={stock.symbol}>
                  <th scope="row">
                    <span className="stock-symbol">{stock.symbol}</span>
                    <span className="company-name">{stock.company_name}</span>
                  </th>
                  <td>{formatNpr(stock.ltp)}</td>
                  <td className={`change change--${tone}`}>
                    {formatPercentage(stock.change_percent)}
                  </td>
                  <td>{formatInteger(stock.volume)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default MarketMoversTable
