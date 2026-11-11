import type { PortfolioSummary, PortfolioTransaction } from '../api/portfolios'
import { formatObservationDate } from '../utils/formatters'

type Props = {
  summary: PortfolioSummary
  transactions: PortfolioTransaction[]
}

function expandDecimal(value: string): string {
  if (!/[eE]/.test(value)) return value
  const [coefficient, exponentText] = value.toLowerCase().split('e')
  const exponent = Number(exponentText)
  const negative = coefficient.startsWith('-')
  const digits = coefficient.replace('-', '').replace('.', '')
  const decimalAt = coefficient.replace('-', '').indexOf('.') < 0
    ? coefficient.replace('-', '').length
    : coefficient.replace('-', '').indexOf('.')
  const nextDecimalAt = decimalAt + exponent
  const plain = nextDecimalAt <= 0
    ? `0.${'0'.repeat(-nextDecimalAt)}${digits}`
    : nextDecimalAt >= digits.length
      ? `${digits}${'0'.repeat(nextDecimalAt - digits.length)}`
      : `${digits.slice(0, nextDecimalAt)}.${digits.slice(nextDecimalAt)}`
  return negative ? `-${plain}` : plain
}

function formatDecimal(value: string, minimumFractionDigits = 0): string {
  const plain = expandDecimal(value)
  const negative = plain.startsWith('-')
  const [integer = '0', fraction = ''] = plain.replace('-', '').split('.')
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const trimmed = fraction.replace(/0+$/, '')
  const displayed = trimmed.padEnd(minimumFractionDigits, '0')
  return `${negative ? '-' : ''}${grouped}${displayed ? `.${displayed}` : ''}`
}

const formatMoney = (value: string) => `NPR ${formatDecimal(value, 2)}`
const pnlTone = (value: string | null) => value?.startsWith('-') ? 'change--negative' : value === null || Number(value) === 0 ? 'change--neutral' : 'change--positive'

function valuationStatus(summary: PortfolioSummary, symbol: string): string {
  if (summary.valuation.missing_symbols.includes(symbol)) return 'Price unavailable'
  if (summary.valuation.stale_symbols.includes(symbol)) return 'Stale historical price'
  return 'Historical price available'
}

export default function PortfolioDetails({ summary, transactions }: Props) {
  const orderedTransactions = [...transactions].sort((left, right) =>
    right.trade_date.localeCompare(left.trade_date) ||
    right.trade_sequence - left.trade_sequence ||
    right.created_at.localeCompare(left.created_at),
  )

  return <div className="portfolio-details">
    <section aria-labelledby="portfolio-summary-title">
      <div className="portfolio-section-heading">
        <div><h2 id="portfolio-summary-title">Portfolio summary</h2><p>Accounting values come from the immutable transaction ledger.</p></div>
        <span className={summary.valuation.complete ? 'status-chip status-chip--complete' : 'status-chip status-chip--warning'}>
          {summary.valuation.complete ? 'Valuation complete' : 'Valuation incomplete'}
        </span>
      </div>
      <div className="portfolio-summary-grid">
        <article><span>Total acquisition cost</span><strong>{formatMoney(summary.total_acquisition_cost)}</strong><small>All BUY costs, including fees.</small></article>
        <article><span>Remaining carrying cost</span><strong>{formatMoney(summary.cash_flow_cost)}</strong><small>Cost basis still held after sales.</small></article>
        <article><span>Realized P&amp;L</span><strong className={pnlTone(summary.realized_pnl)}>{formatMoney(summary.realized_pnl)}</strong><small>Profit or loss from completed sales.</small></article>
        <article><span>Unrealized P&amp;L</span><strong className={pnlTone(summary.unrealized_pnl)}>{summary.unrealized_pnl === null ? 'Unavailable until valuation is complete' : formatMoney(summary.unrealized_pnl)}</strong><small>Historical valuation less carrying cost.</small></article>
        <article><span>Total P&amp;L</span><strong className={pnlTone(summary.total_pnl)}>{summary.total_pnl === null ? 'Unavailable until valuation is complete' : formatMoney(summary.total_pnl)}</strong><small>Realized plus unrealized P&amp;L.</small></article>
        <article><span>Market value</span><strong>{summary.market_value === null ? 'Not shown — valuation incomplete' : formatMoney(summary.market_value)}</strong><small>Shown only when every holding has a valid, non-stale price.</small></article>
      </div>
      <p className="portfolio-provenance">
        {summary.valuation.source} · {summary.valuation.freshness} · requested {formatObservationDate(summary.valuation.as_of)}
      </p>
    </section>

    <section aria-labelledby="portfolio-holdings-title">
      <div className="portfolio-section-heading"><div><h2 id="portfolio-holdings-title">Holdings and cost basis</h2><p>Latest valid observations are labelled historical and never presented as live prices.</p></div></div>
      {summary.holdings.length === 0 ? <p className="empty-state">This portfolio has no open holdings.</p> : <div className="table-scroll portfolio-table">
        <table>
          <caption className="sr-only">Portfolio holdings and cost basis</caption>
          <thead><tr><th>Security</th><th>Quantity</th><th>Average cost</th><th>Carrying cost</th><th>Latest valid price</th><th>Observed</th><th>Unrealized P&amp;L</th><th>Status</th></tr></thead>
          <tbody>{summary.holdings.map((holding) => <tr key={holding.symbol}>
            <th scope="row" data-label="Security"><span className="stock-symbol">{holding.symbol}</span><span className="company-name">{holding.company_name}</span></th>
            <td data-label="Quantity">{formatDecimal(holding.quantity)}</td>
            <td data-label="Average cost">{formatMoney(holding.average_cost)}</td>
            <td data-label="Carrying cost">{formatMoney(holding.invested_cost)}</td>
            <td data-label="Latest valid price">{holding.valuation_price === null ? 'Unavailable' : formatMoney(holding.valuation_price)}</td>
            <td data-label="Observed">{holding.valuation_observed_on === null ? 'Unavailable' : formatObservationDate(holding.valuation_observed_on)}</td>
            <td data-label="Unrealized P&L" className={pnlTone(holding.unrealized_pnl)}>{holding.unrealized_pnl === null ? 'Unavailable' : formatMoney(holding.unrealized_pnl)}</td>
            <td data-label="Status"><span className="holding-status">{valuationStatus(summary, holding.symbol)}</span></td>
          </tr>)}</tbody>
        </table>
      </div>}
    </section>

    <section aria-labelledby="portfolio-transactions-title">
      <div className="portfolio-section-heading"><div><h2 id="portfolio-transactions-title">Transaction history</h2><p>Posted transactions are immutable and shown newest first.</p></div><span>{transactions.length} {transactions.length === 1 ? 'entry' : 'entries'}</span></div>
      {orderedTransactions.length === 0 ? <p className="empty-state">No transactions have been recorded for this portfolio.</p> : <div className="table-scroll portfolio-table">
        <table>
          <caption className="sr-only">Immutable portfolio transaction history</caption>
          <thead><tr><th>Date</th><th>Security</th><th>Side</th><th>Quantity</th><th>Unit price</th><th>Fees</th><th>Gross value</th><th>Sequence</th></tr></thead>
          <tbody>{orderedTransactions.map((transaction) => <tr key={transaction.id}>
            <td data-label="Date">{formatObservationDate(transaction.trade_date)}</td>
            <th scope="row" data-label="Security">{transaction.symbol}</th>
            <td data-label="Side"><span className={transaction.side === 'BUY' ? 'transaction-side transaction-side--buy' : 'transaction-side transaction-side--sell'}>{transaction.side}</span></td>
            <td data-label="Quantity">{formatDecimal(transaction.quantity)}</td>
            <td data-label="Unit price">{formatMoney(transaction.unit_price)}</td>
            <td data-label="Fees">{formatMoney(transaction.fees)}</td>
            <td data-label="Gross value">{formatMoney(transaction.gross_value)}</td>
            <td data-label="Sequence">{transaction.trade_sequence}</td>
          </tr>)}</tbody>
        </table>
      </div>}
    </section>
  </div>
}
