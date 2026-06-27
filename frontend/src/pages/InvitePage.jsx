import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Users, Lock } from 'lucide-react'

export default function InvitePage() {
  const { token } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [invite, setInvite] = useState(null)
  const [loading, setLoading] = useState(true)
  const [joining, setJoining] = useState(false)
  const [error, setError] = useState('')
  const [joined, setJoined] = useState(false)

  useEffect(() => {
    api.get(`/invites/${token}/`)
      .then(r => { setInvite(r.data); setLoading(false) })
      .catch(() => { setLoading(false) })
  }, [token])

  const handleJoin = async () => {
    if (!user) {
      navigate('/login', { state: { from: `/invite/${token}` } })
      return
    }
    setJoining(true)
    setError('')
    try {
      const { data } = await api.post(`/invites/${token}/join/`)
      if (data.already_member) {
        navigate(`/c/${data.community_slug}`)
      } else {
        setJoined(true)
        setTimeout(() => navigate(`/c/${data.community_slug}`), 1500)
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Could not join community.')
      setJoining(false)
    }
  }

  if (loading) return <div className="loader">Loading invite…</div>

  if (!invite) {
    return (
      <div className="page-layout">
        <div className="invite-card">
          <Lock size={40} className="accent" />
          <h2>Invite not found</h2>
          <p className="muted">This invite link is invalid or has been removed.</p>
          <Link to="/communities" className="btn-ghost">Browse communities</Link>
        </div>
      </div>
    )
  }

  if (!invite.is_valid) {
    return (
      <div className="page-layout">
        <div className="invite-card">
          <Lock size={40} className="accent" />
          <h2>Invite expired</h2>
          <p className="muted">This invite link has expired or reached its use limit.</p>
          <Link to="/communities" className="btn-ghost">Browse communities</Link>
        </div>
      </div>
    )
  }

  if (joined) {
    return (
      <div className="page-layout">
        <div className="invite-card">
          <div style={{ fontSize: '40px' }}>🎉</div>
          <h2>You're in!</h2>
          <p className="muted">Redirecting to {invite.community_name}…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page-layout">
      <div className="invite-card">
        <div className="invite-card-icon">{invite.community_icon}</div>
        <h2>{invite.community_name}</h2>
        {invite.community_description && (
          <p className="invite-card-desc">{invite.community_description}</p>
        )}
        <div className="invite-card-meta">
          <Users size={13} /> {invite.member_count} member{invite.member_count !== 1 ? 's' : ''}
        </div>
        {error && <div className="error-msg">{error}</div>}
        <button
          className="btn-primary"
          onClick={handleJoin}
          disabled={joining}
          style={{ minWidth: '160px' }}
        >
          {joining ? 'Joining…' : user ? 'Join community' : 'Log in to join'}
        </button>
        <Link to="/communities" className="muted" style={{ fontSize: '12px', marginTop: '8px' }}>
          Browse other communities
        </Link>
      </div>
    </div>
  )
}
