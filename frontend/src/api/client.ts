import { resolveApiBaseUrl } from '../config/runtime'

export const apiBaseUrl = resolveApiBaseUrl({
  mode: import.meta.env.MODE,
  configuredUrl: import.meta.env.VITE_API_BASE_URL,
})

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`)

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`)
  }

  return response.json() as Promise<T>
}
