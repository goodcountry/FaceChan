import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useSiteSettings } from '../context/SiteSettingsContext'
import CaptchaField from '../components/CaptchaField'

export default function Register() {
  const { register } = useAuth()
  const { registration_open, require_age_confirmation, minimum_age } = useSiteSettings()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', password: '', age_confirmed: false })
  const [mcaptchaToken, setMcaptchaToken] = useState('')
  const [error, setError] = useState('')

  const submit = async e => {
    e.preventDefault()
    setError('')
    try {
      await register(form.username, form.password, form.age_confirmed, mcaptchaToken)
      navigate('/')
    } catch (err) {
      const d = err.response?.data
      const msg = d?.username?.[0] || d?.age_confirmed?.[0] || d?.error || 'Something went wrong.'
      setError(msg)
    }
  }

  if (registration_open === false) {
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
            autoComplete="username" />
          <input type="password" placeholder="Password (min 8 chars)" value={form.password}
            onChange={e => setForm(f => ({ ...f, password: e.target.value }))} required minLength={8}
            autoComplete="new-password" />
          {require_age_confirmation && (
            <label className="age-confirm-row">
              <input type="checkbox" checked={form.age_confirmed}
                onChange={e => setForm(f => ({ ...f, age_confirmed: e.target.checked }))} required />
              <span>I confirm I am at least {minimum_age || 18} years old.</span>
            </label>
          )}
          <CaptchaField onChange={setMcaptchaToken} />
          <button type="submit" className="btn-primary full-width">Create account</button>
        </form>
        <p className="muted text-center">Already have one? <Link to="/login">Log in</Link></p>
      </div>
    </div>
  )
}
