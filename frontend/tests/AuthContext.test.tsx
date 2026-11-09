import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getSession, loginIdentity } from '../src/api/auth'
import { AuthProvider } from '../src/auth/AuthContext'
import { useAuth } from '../src/auth/useAuth'

vi.mock('../src/api/auth', async (importOriginal) => {
  const original = await importOriginal<typeof import('../src/api/auth')>()
  return { ...original, getSession: vi.fn(), loginIdentity: vi.fn(), logoutIdentity: vi.fn(), registerIdentity: vi.fn(), updateIdentityProfile: vi.fn() }
})

const session = {
  user: { id: 'user-1', email: 'investor@example.com', display_name: 'Investor', role: 'USER' as const, created_at: '2026-11-01T00:00:00Z' },
  csrf_token: 'csrf-value',
  expires_at: '2026-11-01T12:00:00Z',
}

function Observer() {
  const auth = useAuth()
  return <><span data-testid="status">{auth.status}</span><span>{auth.user?.display_name ?? 'Public visitor'}</span><button onClick={() => void auth.login('investor@example.com', 'long-password')}>Login</button></>
}

beforeEach(() => {
  vi.mocked(getSession).mockReset()
  vi.mocked(loginIdentity).mockReset()
})

afterEach(() => cleanup())

describe('AuthProvider', () => {
  it('keeps public children rendered while session bootstrap is pending', () => {
    vi.mocked(getSession).mockReturnValue(new Promise(() => undefined))
    render(<AuthProvider><main>Public market analytics</main></AuthProvider>)
    expect(screen.getByText('Public market analytics')).toBeTruthy()
  })

  it('restores a server-validated session without browser storage', async () => {
    vi.mocked(getSession).mockResolvedValue(session)
    render(<AuthProvider><Observer /></AuthProvider>)
    expect(await screen.findByText('Investor')).toBeTruthy()
    expect(screen.getByTestId('status').textContent).toBe('authenticated')
  })

  it('shares bootstrap across Strict Mode effect replay so rotation does not revoke the live session', async () => {
    vi.mocked(getSession).mockResolvedValue(session)
    render(<StrictMode><AuthProvider><Observer /></AuthProvider></StrictMode>)
    expect(await screen.findByText('Investor')).toBeTruthy()
    expect(getSession).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('status').textContent).toBe('authenticated')
  })

  it('waits for bootstrap before login so an anonymous response cannot clear the new session', async () => {
    let settleBootstrap!: (value: never) => void
    vi.mocked(getSession).mockReturnValueOnce(new Promise((resolve) => { settleBootstrap = resolve }))
    vi.mocked(loginIdentity).mockResolvedValueOnce(session)

    render(<AuthProvider><Observer /></AuthProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Login' }))
    expect(loginIdentity).not.toHaveBeenCalled()
    settleBootstrap(undefined as never)
    await waitFor(() => expect(loginIdentity).toHaveBeenCalledWith({ email: 'investor@example.com', password: 'long-password' }))
    expect(screen.getByTestId('status').textContent).toBe('authenticated')
  })

  it('settles as anonymous when no session cookie is valid', async () => {
    vi.mocked(getSession).mockRejectedValue(new Error('401'))
    render(<AuthProvider><Observer /></AuthProvider>)
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('anonymous'))
    expect(screen.getByText('Public visitor')).toBeTruthy()
  })
})
