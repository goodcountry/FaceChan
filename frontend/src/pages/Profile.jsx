import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useSiteSettings } from '../context/SiteSettingsContext'
import ThreadCard from '../components/ThreadCard'
import { MessageSquare, Hash, Calendar, Shield, Users, Lock, Globe, Crown, Wrench, ShieldCheck, Pencil, X, Check, AlertCircle, Camera } from 'lucide-react'

const ROLE_CONFIG = {
  admin: { label: 'Admin', icon: Crown, color: '#f59e0b' },
  mod:   { label: 'Janny', icon: Wrench, color: '#7c6aff' },
  member:{ label: 'Member', icon: Users, color: '#8888a0' },
}

function RoleBadge({ role }) {
  const config = ROLE_CONFIG[role] || ROLE_CONFIG.member
  const Icon = config.icon
  return (
    <span className="role-badge" style={{ color: config.color, borderColor: `${config.color}40`, background: `${config.color}15` }}>
      <Icon size={10} /> {config.label}
    </span>
  )
}

export default function Profile() {
  const { user, logout, isStaff, permissions, updateUser } = useAuth()
  const { allow_avatars, max_avatar_size_kb } = useSiteSettings()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [avatarError, setAvatarError] = useState(null)
  const [avatarUploading, setAvatarUploading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('communities')

  const [editingDisplayName, setEditingDisplayName] = useState(false)
  const [displayNameDraft, setDisplayNameDraft] = useState('')
  const [displayNameError, setDisplayNameError] = useState(null)
  const [displayNameSaving, setDisplayNameSaving] = useState(false)

  const [pwCurrent, setPwCurrent] = useState('')
  const [pwNew, setPwNew] = useState('')
  const [pwConfirm, setPwConfirm] = useState('')
  const [pwError, setPwError] = useState(null)
  const [pwSuccess, setPwSuccess] = useState(false)
  const [pwSaving, setPwSaving] = useState(false)

  const [taglineDraft, setTaglineDraft] = useState('')
  const [bioDraft, setBioDraft] = useState('')
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileSuccess, setProfileSuccess] = useState(false)
  const [profileError, setProfileError] = useState(null)

  const handleAvatarChange = async e => {
    const file = e.target.files?.[0]
    if (!file) return
    setAvatarError(null)
    const maxBytes = (max_avatar_size_kb || 512) * 1024
    if (file.size > maxBytes) {
      setAvatarError(`Avatar must be under ${max_avatar_size_kb || 512}KB.`)
      return
    }
    setAvatarUploading(true)
    try {
      const fd = new FormData()
      fd.append('avatar', file)
      const { data: updated } = await api.post('/me/avatar/', fd)
      updateUser({ avatar: updated.avatar })
    } catch (err) {
      setAvatarError(err.response?.data?.error || 'Could not upload avatar.')
    } finally {
      setAvatarUploading(false)
      e.target.value = ''
    }
  }

  const saveProfile = async () => {
    setProfileSaving(true)
    setProfileError(null)
    setProfileSuccess(false)
    try {
      const { data: updated } = await api.patch('/me/', {
        tagline: taglineDraft,
        bio: bioDraft,
      })
      updateUser({ tagline: updated.tagline, bio: updated.bio })
      setProfileSuccess(true)
    } catch (e) {
      setProfileError(e.response?.data?.error || 'Could not save.')
    } finally {
      setProfileSaving(false)
    }
  }

  const changePassword = async () => {
    setPwError(null)
    setPwSuccess(false)
    if (pwNew !== pwConfirm) { setPwError('New passwords do not match.'); return }
    if (pwNew.length < 8) { setPwError('New password must be at least 8 characters.'); return }
    setPwSaving(true)
    try {
      const { data } = await api.post('/me/password/', {
        current_password: pwCurrent,
        new_password: pwNew,
      })
      // Update stored token with reissued one
      localStorage.setItem('token', data.token)
      setPwCurrent(''); setPwNew(''); setPwConfirm('')
      setPwSuccess(true)
    } catch (e) {
      setPwError(e.response?.data?.error || 'Could not change password.')
    } finally {
      setPwSaving(false)
    }
  }

  useEffect(() => {
    if (!user) { navigate('/login'); return }
    api.get('/me/').then(r => {
      setData(r.data)
      setTaglineDraft(r.data.user?.tagline || '')
      setBioDraft(r.data.user?.bio || '')
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [user])

  const startEditingDisplayName = () => {
    setDisplayNameDraft(user.display_name || user.username)
    setDisplayNameError(null)
    setEditingDisplayName(true)
  }

  const cancelEditingDisplayName = () => {
    setEditingDisplayName(false)
    setDisplayNameError(null)
  }

  const saveDisplayName = async () => {
    const trimmed = displayNameDraft.trim()
    if (!trimmed || trimmed === (user.display_name || user.username)) {
      setEditingDisplayName(false)
      return
    }
    setDisplayNameSaving(true)
    setDisplayNameError(null)
    try {
      const { data: updated } = await api.patch('/me/', { display_name: trimmed })
      updateUser({ display_name: updated.display_name })
      setEditingDisplayName(false)
      api.get('/me/').then(r => setData(r.data))
    } catch (err) {
      const d = err.response?.data
      setDisplayNameError(d?.display_name?.[0] || d?.error || 'Could not change display name.')
    } finally {
      setDisplayNameSaving(false)
    }
  }

  if (loading) return <div className="loader">Loading profile…</div>
  if (!data) return <div className="loader">Could not load profile.</div>

  const threads = tab === 'op' ? data.op_threads : data.commented_threads

  return (
    <div className="page-layout">

      {/* ── Profile card ── */}
      <div className="profile-card">
        <div className="profile-avatar" style={{ position: 'relative' }}>
          {user.avatar
            ? <img src={user.avatar} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
            : (user.display_name || user.username)[0].toUpperCase()
          }
          {allow_avatars && (
            <label style={{
              position: 'absolute', bottom: 0, right: 0,
              background: 'var(--accent)', borderRadius: '50%',
              width: '22px', height: '22px', display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', opacity: avatarUploading ? 0.5 : 1,
            }} title={`Upload avatar (max ${max_avatar_size_kb || 512}KB)`}>
              <Camera size={12} color="white" />
              <input type="file" accept="image/*" style={{ display: 'none' }} onChange={handleAvatarChange} disabled={avatarUploading} />
            </label>
          )}
        </div>
        <div className="profile-info">
          {avatarError && <div className="form-error" style={{ marginBottom: '8px' }}>{avatarError}</div>}
          <div className="profile-username">
            {editingDisplayName ? (
              <div className="username-edit-form">
                <input
                  type="text"
                  className="username-edit-input"
                  value={displayNameDraft}
                  onChange={e => setDisplayNameDraft(e.target.value)}
                  maxLength={150}
                  autoFocus
                  autoComplete="off"
                  disabled={displayNameSaving}
                  onKeyDown={e => {
                    if (e.key === 'Enter') saveDisplayName()
                    if (e.key === 'Escape') cancelEditingDisplayName()
                  }}
                />
                <button className="btn-ghost btn-tiny" disabled={displayNameSaving} onClick={saveDisplayName} title="Save">
                  <Check size={13} />
                </button>
                <button className="btn-ghost btn-tiny" disabled={displayNameSaving} onClick={cancelEditingDisplayName} title="Cancel">
                  <X size={13} />
                </button>
              </div>
            ) : (
              <>
                {user.display_name || user.username}
                {user.is_premium && <span className="premium-badge">PRO</span>}
                {!data.display_name_eligible_at && (
                  <button className="username-edit-trigger" onClick={startEditingDisplayName} title="Change display name">
                    <Pencil size={12} />
                  </button>
                )}
              </>
            )}
          </div>
          {displayNameError && (
            <div className="username-edit-error"><AlertCircle size={12} /> {displayNameError}</div>
          )}
          {data.display_name_eligible_at && !editingDisplayName && (
            <div className="username-cooldown-note">
              You can change your display name again on {new Date(data.display_name_eligible_at).toLocaleDateString()}.
            </div>
          )}
          <div className="profile-meta">
            <span style={{ color: 'var(--muted)', fontSize: '12px' }}>Login: {user.username}</span>
            <span><Calendar size={12} /> Member since {new Date(data.stats.member_since).toLocaleDateString()}</span>
            <span><Shield size={12} /> Anonymous account</span>
            {isStaff && (
              <Link to="/mod" className="profile-mod-link">
                <ShieldCheck size={12} /> {permissions.role} — staff dashboard
              </Link>
            )}
          </div>
        </div>
        <button className="btn-ghost" onClick={() => { logout(); navigate('/') }}>
          Log out
        </button>
      </div>

      {/* ── Stats ── */}
      <div className="profile-stats">
        <div className="stat-box">
          <span className="stat-value">{data.stats.op_count}</span>
          <span className="stat-label">Threads started</span>
        </div>
        <div className="stat-box">
          <span className="stat-value">{data.stats.commented_count}</span>
          <span className="stat-label">Threads joined</span>
        </div>
        <div className="stat-box">
          <span className="stat-value">{data.stats.total_posts}</span>
          <span className="stat-label">Total posts</span>
        </div>
        <div className="stat-box">
          <span className="stat-value">{data.stats.communities_count}</span>
          <span className="stat-label">Communities</span>
        </div>
      </div>

      {/* ── Privacy notice ── */}
      <div className="privacy-notice">
        <Shield size={13} />
        Only you can see this page. Thread history vanishes when threads are culled.
      </div>

      {/* ── Tabs ── */}
      <div className="profile-tabs">
        <button className={`profile-tab ${tab === 'communities' ? 'active' : ''}`} onClick={() => setTab('communities')}>
          <Users size={13} /> Communities ({data.stats.communities_count})
        </button>
        <button className={`profile-tab ${tab === 'op' ? 'active' : ''}`} onClick={() => setTab('op')}>
          <Hash size={13} /> My threads ({data.stats.op_count})
        </button>
        <button className={`profile-tab ${tab === 'commented' ? 'active' : ''}`} onClick={() => setTab('commented')}>
          <MessageSquare size={13} /> Joined ({data.stats.commented_count})
        </button>
      </div>

      {/* ── Communities tab ── */}
      {tab === 'communities' && (
        <div className="profile-communities">
          {data.communities.length === 0 ? (
            <div className="empty-state">
              You haven't joined any communities yet. <Link to="/communities">Browse communities</Link>
            </div>
          ) : (
            data.communities.map(m => (
              <Link to={`/c/${m.slug}`} key={m.id} className="profile-community-row">
                <span className="profile-community-icon">{m.board_icon || '👥'}</span>
                <div className="profile-community-info">
                  <span className="profile-community-name">{m.name}</span>
                  {m.board_slug && (
                    <span className="profile-community-board">/{m.board_slug}/</span>
                  )}
                </div>
                <div className="profile-community-meta">
                  {m.is_private
                    ? <span className="privacy-tag private"><Lock size={9} /> Private</span>
                    : <span className="privacy-tag public"><Globe size={9} /> Public</span>
                  }
                  <RoleBadge role={m.role} />
                  <span className="profile-community-members">
                    <Users size={10} /> {m.member_count}
                  </span>
                </div>
              </Link>
            ))
          )}
          <div className="profile-communities-footer">
            <Link to="/communities" className="btn-ghost btn-tiny">
              <Users size={12} /> Browse all communities
            </Link>
          </div>
        </div>
      )}

      {/* ── Thread tabs ── */}
      {tab !== 'communities' && (
        <div className="thread-list">
          {threads.length === 0 ? (
            <div className="empty-state">
              {tab === 'op' ? "You haven't started any threads yet." : "You haven't commented in any threads yet."}
            </div>
          ) : (
            threads.map(t => <ThreadCard key={t.id} thread={t} />)
          )}
        </div>
      )}

      {/* ── Profile text ── */}
      <div className="profile-card" style={{ marginTop: '24px' }}>
        <h3 style={{ marginBottom: '16px', fontSize: '15px' }}>Profile</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxWidth: '400px' }}>
          <div>
            <label style={{ fontSize: '12px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>
              Strapline <span style={{ color: 'var(--muted)', fontWeight: 400 }}>(shown on your posts)</span>
            </label>
            <input
              className="form-input"
              type="text"
              placeholder="A short line about you…"
              value={taglineDraft}
              maxLength={100}
              autoComplete="off"
              onChange={e => setTaglineDraft(e.target.value)}
            />
          </div>
          <div>
            <label style={{ fontSize: '12px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>Bio</label>
            <textarea
              className="form-input"
              placeholder="A bit more about you…"
              value={bioDraft}
              maxLength={500}
              rows={3}
              onChange={e => setBioDraft(e.target.value)}
              style={{ resize: 'vertical' }}
            />
          </div>
          {profileError && <div className="form-error">{profileError}</div>}
          {profileSuccess && <div style={{ color: 'var(--green)', fontSize: '13px' }}>Saved.</div>}
          <button
            className="btn-primary"
            onClick={saveProfile}
            disabled={profileSaving}
            style={{ alignSelf: 'flex-start' }}
          >
            {profileSaving ? 'Saving…' : 'Save profile'}
          </button>
        </div>
      </div>

      {/* ── Change password ── */}
      <div className="profile-card" style={{ marginTop: '24px' }}>
        <h3 style={{ marginBottom: '16px', fontSize: '15px' }}>Change password</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxWidth: '320px' }}>
          <input
            className="form-input"
            type="password"
            placeholder="Current password"
            value={pwCurrent}
            onChange={e => setPwCurrent(e.target.value)}
          />
          <input
            className="form-input"
            type="password"
            placeholder="New password"
            value={pwNew}
            onChange={e => setPwNew(e.target.value)}
          />
          <input
            className="form-input"
            type="password"
            placeholder="Confirm new password"
            value={pwConfirm}
            onChange={e => setPwConfirm(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && changePassword()}
          />
          {pwError && <div className="form-error">{pwError}</div>}
          {pwSuccess && <div style={{ color: 'var(--green)', fontSize: '13px' }}>Password changed successfully.</div>}
          <button
            className="btn-primary"
            onClick={changePassword}
            disabled={pwSaving || !pwCurrent || !pwNew || !pwConfirm}
            style={{ alignSelf: 'flex-start' }}
          >
            {pwSaving ? 'Saving…' : 'Change password'}
          </button>
        </div>
      </div>

    </div>
  )
}
