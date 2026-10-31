const DEVELOPMENT_API_BASE_URL = 'http://127.0.0.1:8000'

type ApiBaseUrlOptions = {
  mode: string
  configuredUrl?: string
}

export function resolveApiBaseUrl({
  mode,
  configuredUrl,
}: ApiBaseUrlOptions): string {
  const raw = configuredUrl?.trim()
  if (!raw) {
    if (mode === 'production') {
      throw new Error('VITE_API_BASE_URL is required for production builds')
    }
    return DEVELOPMENT_API_BASE_URL
  }

  let parsed: URL
  try {
    parsed = new URL(raw)
  } catch {
    throw new Error('VITE_API_BASE_URL must be a valid API origin')
  }

  if (
    !['http:', 'https:'].includes(parsed.protocol) ||
    parsed.username !== '' ||
    parsed.password !== '' ||
    parsed.search !== '' ||
    parsed.hash !== '' ||
    !['', '/'].includes(parsed.pathname)
  ) {
    throw new Error('VITE_API_BASE_URL must be a valid API origin')
  }
  if (mode === 'production' && parsed.protocol !== 'https:') {
    throw new Error('VITE_API_BASE_URL must use HTTPS in production')
  }
  if (
    mode === 'production' &&
    ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname)
  ) {
    throw new Error('VITE_API_BASE_URL must use a public host in production')
  }

  return parsed.origin
}

export function toWebSocketUrl(apiBaseUrl: string): string {
  const parsed = new URL(apiBaseUrl)
  parsed.protocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:'
  parsed.pathname = '/api/v1/ws/market'
  return parsed.toString()
}
