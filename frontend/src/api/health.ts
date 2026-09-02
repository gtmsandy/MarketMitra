import { fetchJson } from './client'

export type HealthResponse = {
  status: string
  service: string
}

export async function getHealth(): Promise<HealthResponse> {
  return fetchJson('/api/v1/health')
}
