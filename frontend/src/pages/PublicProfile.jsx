import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import api from '../api/client'
import BadgeDisplay from '../components/BadgeDisplay'
import { Calendar, ShieldCheck } from 'lucide-react'

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-GB', { year: 'numeric', month: 'long' })
}

export default function PublicProfile() {
  const { username } = useParams()
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    api.get(`/users/${username}/`)
      .then(r => { setProfile(r.data); setLoading(false) })
      .catch(err => {
        setLoading(false)
        if (err.response?.status === 404) setNotFound(true)
      })
  }, [username])

  if (loading) return <div className="loader">Loading…</div>
  if (notFound) return (
    <div className="page-layout">
      <div className="empty-state">User not found.</div>
    </div>
  )

  return (
    <div className="page-layout">
      <div className="profile-card">
        <div className="profile-header">
          <div className="profile-avatar-lg">
            {profile.avatar
              ? <img src={profile.avatar} alt="" className="profile-avatar-img" />
              : <span>{(profile.display_name || profile.username)[0].toUpperCase()}</span>
            }
          </div>
          <div className="profile-header-info">
            <div className="profile-username-row">
              <h1 className="profile-username">{profile.display_name || profile.username}</h1>
              <BadgeDisplay badge={profile.display_badge} />
              {profile.is_premium && !profile.display_badge && (
                <span className="premium-badge">PRO</span>
              )}
            </div>
            <div className="profile-meta">
              <span><Calendar size={13} /> Member since {timeAgo(profile.member_since)}</span>
              <span><ShieldCheck size={13} /> Anonymous account</span>
            </div>
            <div className="activity-tier-badge">{profile.activity_tier}</div>
          </div>
        </div>
      </div>
    </div>
  )
}
