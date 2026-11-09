import { fetchJson } from './client'
import type {
  HeatmapItem,
  IntradayPricePoint,
  MarketBreadth,
  MarketMover,
  MarketOverview,
  MostActiveStock,
  PriceHistoryPoint,
  SectorPerformance,
  StockDetail,
  StockQuote,
  ScreenerSortBy,
  ScreenerSortOrder,
  StockScreenerResponse,
} from '../types/market'

export function getMarketOverview(): Promise<MarketOverview> {
  return fetchJson('/api/v1/market/overview')
}

export function getTopGainers(): Promise<MarketMover[]> {
  return fetchJson('/api/v1/market/gainers')
}

export function getTopLosers(): Promise<MarketMover[]> {
  return fetchJson('/api/v1/market/losers')
}

export function getMostActiveStocks(): Promise<MostActiveStock[]> {
  return fetchJson('/api/v1/market/most-active')
}

export function getStocks(): Promise<StockQuote[]> {
  return fetchJson('/api/v1/stocks')
}

export function searchStocks(query: string): Promise<StockQuote[]> {
  return fetchJson(`/api/v1/stocks?q=${encodeURIComponent(query)}`)
}

export type StockScreenerParams = {
  q?: string
  sector?: string
  min_price?: number
  max_price?: number
  min_change_percent?: number
  max_change_percent?: number
  min_volume?: number
  min_turnover?: number
  page?: number
  page_size?: number
  sort_by?: ScreenerSortBy
  sort_order?: ScreenerSortOrder
}

export function screenStocks(params: StockScreenerParams = {}): Promise<StockScreenerResponse> {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value))
  })
  const suffix = query.toString()
  return fetchJson(`/api/v1/stocks/screener${suffix ? `?${suffix}` : ''}`)
}

export function getStockDetail(symbol: string): Promise<StockDetail> {
  return fetchJson(`/api/v1/stocks/${encodeURIComponent(symbol)}`)
}

export function getStockHistory(symbol: string): Promise<PriceHistoryPoint[]> {
  return fetchJson(`/api/v1/stocks/${encodeURIComponent(symbol)}/history`)
}

export function getStockIntraday(symbol: string): Promise<IntradayPricePoint[]> {
  return fetchJson(`/api/v1/stocks/${encodeURIComponent(symbol)}/intraday`)
}

export function getMarketBreadth(): Promise<MarketBreadth> {
  return fetchJson('/api/v1/market/breadth')
}

export function getSectorAnalytics(): Promise<SectorPerformance[]> {
  return fetchJson('/api/v1/market/sectors')
}

export function getMarketHeatmap(): Promise<HeatmapItem[]> {
  return fetchJson('/api/v1/market/heatmap')
}

