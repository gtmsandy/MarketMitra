import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  AuthRequestError,
  getSession,
  loginIdentity,
  logoutIdentity,
  registerIdentity,
  updateIdentityProfile,
} from '../api/auth'
import { AuthContext, type AuthStatus } from './context'
import type { IdentityUser } from '../api/auth'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('checking')
  const [user, setUser] = useState<IdentityUser | null>(null)
  const [csrfToken, setCsrfToken] = useState<string | null>(null)

  const clearSession = useCallback(() => {
    setUser(null)
    setCsrfToken(null)
    setStatus('anonymous')
  }, [])

  useEffect(() => {
    let active = true
    void getSession().then((session) => {
      if (!active) return
      setUser(session.user)
      setCsrfToken(session.csrf_token)
      setStatus('authenticated')
    }).catch(() => {
      if (active) clearSession()
    })
    return () => { active = false }
  }, [clearSession])

  const applySession = useCallback((session: Awaited<ReturnType<typeof getSession>>) => {
    setUser(session.user)
    setCsrfToken(session.csrf_token)
    setStatus('authenticated')
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    applySession(await loginIdentity({ email, password }))
  }, [applySession])

  const register = useCallback(async (email: string, displayName: string, password: string) => {
    applySession(await registerIdentity({ email, display_name: displayName, password }))
  }, [applySession])

  const logout = useCallback(async () => {
    if (!csrfToken) {
      clearSession()
      return
    }
    try {
      await logoutIdentity(csrfToken)
    } finally {
      clearSession()
    }
  }, [clearSession, csrfToken])

  const updateProfile = useCallback(async (displayName: string) => {
    if (!csrfToken) throw new AuthRequestError(401, 'AUTHENTICATION_REQUIRED', 'Authentication is required')
    try {
      setUser(await updateIdentityProfile(displayName, csrfToken))
    } catch (error) {
      if (error instanceof AuthRequestError && error.status === 401) clearSession()
      throw error
    }
  }, [clearSession, csrfToken])

  const value = useMemo(() => ({ status, user, login, register, logout, updateProfile }), [status, user, login, register, logout, updateProfile])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
