import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { verifyAdminIdentity } from '../src/api/auth'
import { useAuth } from '../src/auth/useAuth'
import AdminPage from '../src/pages/AdminPage'
import RegisterPage from '../src/pages/RegisterPage'

vi.mock('../src/auth/useAuth', () => ({ useAuth: vi.fn() }))
vi.mock('../src/api/auth', async (importOriginal) => {
  const original = await importOriginal<typeof import('../src/api/auth')>()
  return { ...original, verifyAdminIdentity: vi.fn() }
})

const user = { id: 'user-1', email: 'investor@example.com', display_name: 'Investor', role: 'USER' as const, created_at: '2026-11-01T00:00:00Z' }

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({ status: 'anonymous', user: null, csrfToken: null, login: vi.fn(), register: vi.fn(), logout: vi.fn(), updateProfile: vi.fn() })
  vi.mocked(verifyAdminIdentity).mockReset()
})

afterEach(() => cleanup())

describe('identity pages', () => {
  it('rejects mismatched registration passwords before any request', () => {
    const register = vi.fn()
    vi.mocked(useAuth).mockReturnValue({ status: 'anonymous', user: null, csrfToken: null, login: vi.fn(), register, logout: vi.fn(), updateProfile: vi.fn() })
    render(<MemoryRouter><RegisterPage /></MemoryRouter>)

    fireEvent.change(screen.getByLabelText('Display name'), { target: { value: 'Investor' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'investor@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a-secure-password' } })
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'a-different-password' } })
    fireEvent.submit(screen.getByRole('button', { name: 'Create account' }).closest('form')!)

    expect(screen.getByRole('alert').textContent).toBe('Passwords do not match')
    expect(register).not.toHaveBeenCalled()
  })

  it('requires backend confirmation before rendering the admin area', async () => {
    vi.mocked(useAuth).mockReturnValue({ status: 'authenticated', user, csrfToken: 'csrf', login: vi.fn(), register: vi.fn(), logout: vi.fn(), updateProfile: vi.fn() })
    vi.mocked(verifyAdminIdentity).mockRejectedValue(new Error('403'))
    render(<MemoryRouter><AdminPage /></MemoryRouter>)

    expect(screen.getByText('Verifying administrator access…')).toBeTruthy()
    expect(await screen.findByText('Administrator access required')).toBeTruthy()
    expect(verifyAdminIdentity).toHaveBeenCalledTimes(1)
  })

  it('redirects an anonymous admin visit to the expired-session login state', async () => {
    render(<MemoryRouter initialEntries={['/admin']}><Routes><Route path="/admin" element={<AdminPage />} /><Route path="/login" element={<p>Session expired login</p>} /></Routes></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Session expired login')).toBeTruthy())
    expect(verifyAdminIdentity).not.toHaveBeenCalled()
  })
})
