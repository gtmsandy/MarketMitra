import { fetchJson } from './client'

export type IngestionSummary = {
  source: string
  status: string
  finished_at: string
  prices_accepted: number
  prices_rejected: number
}

export type HealthResponse = {
  status: 'ok' | 'degraded'
  service: 'marketmitra-api'
  market_data_source: string
  database_status: 'connected' | 'disconnected' | 'not_configured'
  market_status: 'OPEN' | 'CLOSED' | 'HALTED' | 'DATA_UNAVAILABLE' | 'STALE'
  data_freshness:
    | 'FRESH'
    | 'STALE'
    | 'UNKNOWN'
    | 'LIVE'
    | 'DELAYED'
    | 'HISTORICAL'
    | 'DATA_UNAVAILABLE'
  market_snapshot_date: string | null
  last_ingestion: IngestionSummary | null
  provider: string
  enabled: boolean
  configured: boolean
  connection_status: string
  failure_count: number
  circuit_state: string
}

export async function getHealth(): Promise<HealthResponse> {
  return fetchJson('/api/v1/health')
}
