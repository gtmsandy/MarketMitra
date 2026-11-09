import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { AuthRequestError } from '../api/auth'
import { useAuth } from '../auth/useAuth'

function ProfilePage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  if (auth.status === 'checking') return <main className="auth-screen"><p>Checking your session…</p></main>
  if (!auth.user) return <Navigate to="/login" replace state={{ expired: true }} />

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSaved(false)
    const displayName = String(new FormData(event.currentTarget).get('displayName'))
    try {
      await auth.updateProfile(displayName)
      setSaved(true)
    } catch (caught) {
      if (caught instanceof AuthRequestError && caught.status === 401) {
        navigate('/login', { replace: true, state: { expired: true } })
        return
      }
      setError(caught instanceof AuthRequestError ? caught.message : 'Profile could not be updated')
    }
  }

  return <main className="auth-screen"><section className="auth-card" aria-labelledby="profile-title">
    <p className="state-panel__label">Account</p><h1 id="profile-title">Your profile</h1>
    <dl className="profile-details"><div><dt>Email</dt><dd>{auth.user.email}</dd></div><div><dt>Role</dt><dd>{auth.user.role}</dd></div></dl>
    {error && <p className="form-error" role="alert">{error}</p>}
    {saved && <p className="form-success" role="status">Profile saved.</p>}
    <form className="auth-form" onSubmit={save}><label>Display name<input name="displayName" defaultValue={auth.user.display_name} required maxLength={80} /></label><button className="primary-button">Save profile</button></form>
    <button className="secondary-button" onClick={() => void auth.logout()}>Sign out</button>
  </section></main>
}

export default ProfilePage
