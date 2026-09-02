export type MarketOverview = {
  nepse_index: number
  index_change: number
  index_change_percent: number
  turnover: number
  total_volume: number
  total_transactions: number
  market_status: string
  last_updated: string
}

export type MarketMover = {
  symbol: string
  company_name: string
  ltp: number
  change_percent: number
  volume: number
}

export type MostActiveStock = {
  symbol: string
  company_name: string
  ltp: number
  volume: number
  turnover: number
}

export type StockQuote = {
  symbol: string
  company_name: string
  ltp: number
  change: number
  change_percent: number
  open: number
  high: number
  low: number
  previous_close: number
  volume: number
  last_updated: string
}
