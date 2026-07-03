import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useSiteSettings } from '../context/SiteSettingsContext'
import CaptchaField from '../components/CaptchaField'

export default function Register() {
  const { register } = useAuth()
  const { registration_open, require_age_confirmation, minimum_age, settingsLoaded } = useSiteSettings()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', password: '', age_confirmed: false })
  const [mcaptchaToken, setMcaptchaToken] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  // Flips true if the backend itself reports registration is closed (e.g. it
  // was closed after this page loaded, or closed while settings were still
  // in flight). Once true, the form stays locked rather than re-showing a
  // dismissible error.
  const [closedByServer, setClosedByServer] = useState(false)

  const submit = async e => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await register(form.username, form.password, form.age_confirmed, mcaptchaToken)
      navigate('/')
    } catch (err) {
      const d = err.response?.data
      if (err.response?.status === 403 && d?.error) {
        setClosedByServer(true)
      } else {
        const msg = d?.username?.[0] || d?.age_confirmed?.[0] || d?.error || 'Something went wrong.'
        setError(msg)
      }
    } finally {
      setSubmitting(false)
    }
  }

  // Don't render the live form until we know for sure whether registration
  // is open — the context defaults to `true` while the settings fetch is
  // in flight, which previously let people fill in and submit a form that
  // was always going to be rejected, with no visible feedback.
  if (!settingsLoaded) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <h1>Create an account</h1>
          <p className="muted">Loading…</p>
        </div>
      </div>
    )
  }

  if (registration_open === false || closedByServer) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <h1>Registration closed</h1>
          <p className="muted">This instance isn't accepting new accounts right now.</p>
          <p className="muted text-center">Already have one? <Link to="/login">Log in</Link></p>
        </div>
      </div>
    )
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Create an account</h1>
        <p className="muted">Pick a username. No email required. No real name.</p>
        {error && <div className="error-msg">{error}</div>}
        <form onSubmit={submit}>
          <input placeholder="Username" value={form.username}
            onChange={e => setForm(f => ({ ...f, username: e.target.value }))} required
            autoComplete="username" disabled={submitting} />
          <input type="password" placeholder="Password (min 8 chars)" value={form.password}
            onChange={e => setForm(f => ({ ...f, password: e.target.value }))} required minLength={8}
            autoComplete="new-password" disabled={submitting} />
          {require_age_confirmation && (
            <label className="age-confirm-row">
              <input type="checkbox" checked={form.age_confirmed}
                onChange={e => setForm(f => ({ ...f, age_confirmed: e.target.checked }))} required
                disabled={submitting} />
              <span>I confirm I am at least {minimum_age || 18} years old.</span>
            </label>
          )}
          <CaptchaField onChange={setMcaptchaToken} />
          <button type="submit" className="btn-primary full-width" disabled={submitting}>
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>
        <p className="muted text-center">Already have one? <Link to="/login">Log in</Link></p>
      </div>
    </div>
  )
}
