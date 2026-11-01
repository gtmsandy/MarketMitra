import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { AuthRequestError } from '../api/auth'
import { useAuth } from '../auth/useAuth'

function LoginPage() {
  const auth = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (auth.status === 'authenticated') return <Navigate to="/profile" replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    const data = new FormData(event.currentTarget)
    try {
      await auth.login(String(data.get('email')), String(data.get('password')))
      navigate('/profile', { replace: true })
    } catch (caught) {
      setError(caught instanceof AuthRequestError ? caught.message : 'Sign in could not be completed')
    } finally {
      setSubmitting(false)
    }
  }

  return <main className="auth-screen"><section className="auth-card" aria-labelledby="login-title">
    <p className="state-panel__label">Investor account</p>
    <h1 id="login-title">Sign in to MarketMitra</h1>
    <p>Access your account while public market research stays available without signing in.</p>
    {location.state?.expired && <p className="form-notice">Your session expired. Sign in again to continue.</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
    <form className="auth-form" onSubmit={submit}>
      <label>Email<input name="email" type="email" autoComplete="email" required /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required maxLength={128} /></label>
      <button className="primary-button" disabled={submitting}>{submitting ? 'Signing in…' : 'Sign in'}</button>
    </form>
    <p className="auth-card__alternate">New to MarketMitra? <Link to="/register">Create an account</Link></p>
  </section></main>
}

export default LoginPage
