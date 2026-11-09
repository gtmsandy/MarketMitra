import { apiBaseUrl } from './client'

export type IdentityRole = 'USER' | 'ADMIN'

export type IdentityUser = {
  id: string
  email: string
  display_name: string
  role: IdentityRole
  created_at: string
}

export type AuthSession = {
  user: IdentityUser
  csrf_token: string
  expires_at: string
}

export class AuthRequestError extends Error {
  readonly status: number
  readonly code: string

  constructor(
    status: number,
    code: string,
    message: string,
  ) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function authRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null) as {
      error?: { code?: string; message?: string }
    } | null
    throw new AuthRequestError(
      response.status,
      payload?.error?.code ?? 'REQUEST_FAILED',
      payload?.error?.message ?? 'Request could not be completed',
    )
  }

  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}

export function getSession() {
  return authRequest<AuthSession>('/api/v1/auth/session')
}

export function registerIdentity(input: {
  email: string
  display_name: string
  password: string
}) {
  return authRequest<AuthSession>('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function loginIdentity(input: { email: string; password: string }) {
  return authRequest<AuthSession>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function logoutIdentity(csrfToken: string) {
  return authRequest<void>('/api/v1/auth/logout', {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  })
}

export function updateIdentityProfile(displayName: string, csrfToken: string) {
  return authRequest<IdentityUser>('/api/v1/auth/profile', {
    method: 'PATCH',
    headers: { 'X-CSRF-Token': csrfToken },
    body: JSON.stringify({ display_name: displayName }),
  })
}

export function verifyAdminIdentity() {
  return authRequest<IdentityUser>('/api/v1/auth/admin')
}
