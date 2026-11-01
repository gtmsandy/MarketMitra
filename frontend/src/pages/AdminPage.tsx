import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'

import { AuthRequestError, verifyAdminIdentity } from '../api/auth'
import { useAuth } from '../auth/useAuth'

function AdminPage() {
  const auth = useAuth()
  const [access, setAccess] = useState<'checking' | 'allowed' | 'denied'>('checking')

  useEffect(() => {
    if (auth.status !== 'authenticated') return
    let active = true
    void verifyAdminIdentity().then(() => { if (active) setAccess('allowed') }).catch((error) => {
      if (active) setAccess(error instanceof AuthRequestError ? 'denied' : 'denied')
    })
    return () => { active = false }
  }, [auth.status])

  if (auth.status === 'checking') return <main className="auth-screen"><p>Checking your session…</p></main>
  if (!auth.user) return <Navigate to="/login" replace state={{ expired: true }} />
  if (access === 'checking') return <main className="auth-screen"><p>Verifying administrator access…</p></main>
  if (access === 'denied') return <main className="state-screen"><section className="state-panel"><p className="state-panel__label">Access denied</p><h1>Administrator access required</h1><p>Your account does not have permission to view this area.</p></section></main>
  return <main className="auth-screen"><section className="auth-card"><p className="state-panel__label">Administration</p><h1>MarketMitra administration</h1><p>Administrative access was verified by the server.</p></section></main>
}

export default AdminPage
