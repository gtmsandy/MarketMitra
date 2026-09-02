export type HealthResponse = {
  status: string
  service: string
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/health`)

  if (!response.ok) {
    throw new Error(`Health request failed with status ${response.status}`)
  }

  return response.json() as Promise<HealthResponse>
}
