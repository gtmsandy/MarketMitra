import { fetchJson } from './client'
import type {
  MarketMover,
  MarketOverview,
  MostActiveStock,
  StockQuote,
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
