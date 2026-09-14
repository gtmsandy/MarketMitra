export type MarketOverview = {
  nepse_index: number
  index_change: number
  index_change_percent: number
  turnover: number | null
  total_volume: number | null
  total_transactions: number | null
  market_status: string
  last_updated: string
  observation_date?: string | null
  data_freshness?: string
}

export type MarketMover = {
  symbol: string
  company_name: string
  ltp: number
  change_percent: number
  volume: number
  observation_date?: string | null
}

export type MostActiveStock = {
  symbol: string
  company_name: string
  ltp: number
  volume: number
  turnover: number
  observation_date?: string | null
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
  stock_observation_date?: string | null
  market_snapshot_date?: string | null
}

export type PriceHistoryPoint = {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}


export type IntradayPricePoint = {
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  turnover: number
  provider: string
  source_timestamp: string | null
}
export type StockDetail = {
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
  fifty_two_week_high: number
  fifty_two_week_low: number
  stock_observation_date?: string | null
  market_snapshot_date?: string | null
}

export type MarketBreadth = {
  observation_date: string
  advancing_count: number
  declining_count: number
  unchanged_count: number
  total_count: number
  advance_decline_ratio: number | null
  advancing_percent: number
  declining_percent: number
  unchanged_percent: number
}

export type SectorPerformance = {
  sector: string
  stock_count: number
  advancing_count: number
  declining_count: number
  unchanged_count: number
  average_change_percent: number
  total_volume: number
  total_turnover: number
  observation_date: string
  methodology: string
}

export type HeatmapItem = {
  symbol: string
  company_name: string
  sector: string | null
  ltp: number
  change: number
  change_percent: number
  volume: number
  turnover: number
  observation_date: string
  weight_metric: string
}
