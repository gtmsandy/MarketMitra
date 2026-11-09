import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { AuthRequestError } from '../api/auth'
import { useAuth } from '../auth/useAuth'

function RegisterPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (auth.status === 'authenticated') return <Navigate to="/profile" replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    const data = new FormData(event.currentTarget)
    const password = String(data.get('password'))
    if (password !== String(data.get('confirmPassword'))) {
      setError('Passwords do not match')
      return
    }
    setSubmitting(true)
    try {
      await auth.register(String(data.get('email')), String(data.get('displayName')), password)
      navigate('/profile', { replace: true })
    } catch (caught) {
      setError(caught instanceof AuthRequestError ? caught.message : 'Registration could not be completed')
    } finally {
      setSubmitting(false)
    }
  }

  return <main className="auth-screen"><section className="auth-card" aria-labelledby="register-title">
    <p className="state-panel__label">Investor account</p>
    <h1 id="register-title">Create your account</h1>
    <p>Use a unique password of at least 12 characters. Your password is never displayed or stored by the browser.</p>
    {error && <p className="form-error" role="alert">{error}</p>}
    <form className="auth-form" onSubmit={submit}>
      <label>Display name<input name="displayName" autoComplete="name" required maxLength={80} /></label>
      <label>Email<input name="email" type="email" autoComplete="email" required /></label>
      <label>Password<input name="password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} /></label>
      <label>Confirm password<input name="confirmPassword" type="password" autoComplete="new-password" required minLength={12} maxLength={128} /></label>
      <button className="primary-button" disabled={submitting}>{submitting ? 'Creating account…' : 'Create account'}</button>
    </form>
    <p className="auth-card__alternate">Already registered? <Link to="/login">Sign in</Link></p>
  </section></main>
}

export default RegisterPage
