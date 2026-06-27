import { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from || '/'
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')

  const submit = async e => {
    e.preventDefault()
    setError('')
    try {
      await login(form.username, form.password)
      navigate(from, { replace: true })
    } catch {
      setError('Wrong username or password.')
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Log in</h1>
        <p className="muted">No real name needed. Just your username.</p>
        {error && <div className="error-msg">{error}</div>}
        <form onSubmit={submit}>
          <input placeholder="Username" value={form.username}
            onChange={e => setForm(f => ({ ...f, username: e.target.value }))} required
            autoComplete="username" />
          <input type="password" placeholder="Password" value={form.password}
            onChange={e => setForm(f => ({ ...f, password: e.target.value }))} required
            autoComplete="current-password" />
          <button type="submit" className="btn-primary full-width">Log in</button>
        </form>
        <p className="muted text-center">No account? <Link to="/register">Sign up</Link></p>
      </div>
    </div>
  )
}
