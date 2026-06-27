import { useState, useEffect, useCallback } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import ThreadCard from '../components/ThreadCard'
import CaptchaField from '../components/CaptchaField'
import { Users, Lock, Globe, Hash, Plus, RefreshCw, Star, Shield, ChevronDown, ChevronUp, UserPlus, X, ChevronRight, Link as LinkIcon, Trash2 } from 'lucide-react'

const ROLE_ICON  = { admin: <Star size={11} />, mod: <Shield size={11} />, member: null }
const ROLE_LABEL = { admin: 'Admin', mod: 'Mod', member: 'Member' }

export default function CommunityDetail() {
  const { slug } = useParams()
  const { user, permissions } = useAuth()
  const navigate = useNavigate()

  const [community, setCommunity]   = useState(null)
  const [threads, setThreads]       = useState([])
  const [loading, setLoading]       = useState(true)
  const [isMember, setIsMember]     = useState(false)
  const [userRole, setUserRole]     = useState(null)
  const [showForm, setShowForm]     = useState(false)
  const [form, setForm]             = useState({ title: '', body: '' })
  const [mcaptchaToken, setMcaptchaToken] = useState('')
  const [error, setError]           = useState('')

  // Members panel
  const [showMembers, setShowMembers]     = useState(false)
  const [members, setMembers]             = useState([])
  const [membersLoading, setMembersLoading] = useState(false)
  const [addUsername, setAddUsername]     = useState('')
  const [addError, setAddError]           = useState('')
  const [addSuccess, setAddSuccess]       = useState('')
  const [showAddForm, setShowAddForm]     = useState(false)

  // Invite panel
  const [showInvites, setShowInvites]     = useState(false)
  const [invites, setInvites]             = useState([])
  const [inviteLoading, setInviteLoading] = useState(false)
  const [inviteForm, setInviteForm]       = useState({ expires_in_days: '', max_uses: '' })
  const [inviteError, setInviteError]     = useState('')
  const [copiedToken, setCopiedToken]     = useState(null)

  // Leave / delete confirmation
  const [showLeaveConfirm, setShowLeaveConfirm] = useState(false)

  const fetchCommunity = useCallback(() =>
    api.get(`/communities/${slug}/`).then(r => {
      setCommunity(r.data)
      setIsMember(r.data.is_member)
      setUserRole(r.data.user_role)
    }), [slug])

  const fetchThreads = useCallback(() =>
    api.get(`/communities/${slug}/threads/`).then(r => {
      setThreads(r.data)
    }).catch(err => {
      if (err.response?.status === 403) setError('members only')
    }), [slug])

  const fetchMembers = useCallback(async () => {
    setMembersLoading(true)
    try {
      const res = await api.get(`/communities/${slug}/members/`)
      setMembers(res.data)
    } catch { setMembers([]) }
    setMembersLoading(false)
  }, [slug])

  useEffect(() => {
    Promise.all([fetchCommunity(), fetchThreads()]).finally(() => setLoading(false))
  }, [fetchCommunity, fetchThreads])

  useEffect(() => {
    const onFocus = () => fetchThreads()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [fetchThreads])

  const handleToggleMembers = () => {
    if (!showMembers && members.length === 0) fetchMembers()
    setShowMembers(v => !v)
  }

  const handleJoin = async () => {
    await api.post(`/communities/${slug}/join/`)
    setIsMember(true)
    fetchCommunity()
    fetchThreads()
    if (showMembers) fetchMembers()
  }

  // Called when Leave is clicked
  const handleLeaveClick = async () => {
    try {
      const res = await api.post(`/communities/${slug}/leave/`)
      // Non-admin successful leave
      setIsMember(false)
      setUserRole(null)
      fetchCommunity()
      setThreads([])
      setError('members only')
      if (showMembers) fetchMembers()
    } catch (err) {
      const data = err.response?.data || {}
      if (data.must_confirm_delete) {
        setShowLeaveConfirm(true)
      } else if (data.must_demote_first) {
        alert('You are an admin with other admins in this community. Use the role dropdown in the members panel to demote yourself to member before leaving.')
      } else {
        alert(data.error || 'Could not leave community.')
      }
    }
  }

  // Last-admin confirmed they want to delete
  const handleLeaveAndDelete = async () => {
    try {
      await api.post(`/communities/${slug}/leave-and-delete/`)
      navigate('/communities')
    } catch (err) {
      alert(err.response?.data?.error || 'Could not delete community.')
    }
  }

  const handlePost = async e => {
    e.preventDefault()
    await api.post('/threads/', {
      ...form,
      board: community.board_slug,
      community: slug,
      website: '',  // honeypot
      ...(mcaptchaToken ? { mcaptcha_token: mcaptchaToken } : {}),
    })
    setForm({ title: '', body: '' })
    setMcaptchaToken('')
    setShowForm(false)
    fetchThreads()
  }

  const handleAddMember = async e => {
    e.preventDefault()
    setAddError('')
    setAddSuccess('')
    try {
      await api.post(`/communities/${slug}/add-member/`, { username: addUsername })
      setAddSuccess(`${addUsername} added successfully.`)
      setAddUsername('')
      fetchMembers()
      fetchCommunity()
    } catch (err) {
      setAddError(err.response?.data?.error || 'Could not add member.')
    }
  }

  const handleRemoveMember = async (username) => {
    if (!window.confirm(`Remove ${username} from this community?`)) return
    try {
      await api.post(`/communities/${slug}/remove-member/`, { username })
      fetchMembers()
      fetchCommunity()
    } catch (err) {
      alert(err.response?.data?.error || 'Could not remove member.')
    }
  }

  const handleSetRole = async (username, newRole) => {
    try {
      await api.post(`/communities/${slug}/set-role/`, { username, role: newRole })
      fetchMembers()
    } catch (err) {
      alert(err.response?.data?.error || 'Could not change role.')
    }
  }

  const fetchInvites = async () => {
    setInviteLoading(true)
    try {
      const r = await api.get(`/communities/${slug}/invites/`)
      setInvites(r.data)
    } catch {}
    setInviteLoading(false)
  }

  const handleShowInvites = () => {
    const next = !showInvites
    setShowInvites(next)
    if (next && invites.length === 0) fetchInvites()
  }

  const handleCreateInvite = async e => {
    e.preventDefault()
    setInviteError('')
    try {
      const payload = {}
      if (inviteForm.expires_in_days) payload.expires_in_days = inviteForm.expires_in_days
      if (inviteForm.max_uses) payload.max_uses = inviteForm.max_uses
      await api.post(`/communities/${slug}/invites/`, payload)
      setInviteForm({ expires_in_days: '', max_uses: '' })
      fetchInvites()
    } catch (err) {
      setInviteError(err.response?.data?.error || 'Could not create invite.')
    }
  }

  const handleRevokeInvite = async (token) => {
    if (!window.confirm('Revoke this invite link? Anyone with it will no longer be able to join.')) return
    try {
      await api.delete(`/communities/${slug}/invites/${token}/`)
      fetchInvites()
    } catch (err) {
      alert(err.response?.data?.error || 'Could not revoke invite.')
    }
  }

  const handleCopyInvite = (url, token) => {
    navigator.clipboard.writeText(url).then(() => {
      setCopiedToken(token)
      setTimeout(() => setCopiedToken(null), 2000)
    })
  }

  if (loading) return <div className="loader">Loading community…</div>
  if (!community) return <div className="loader">Community not found.</div>

  const canPost       = user && isMember
  const canView       = !community.is_private || isMember
  const isAdminOrMod  = userRole === 'admin' || userRole === 'mod'
  const isAdmin       = userRole === 'admin'
  // Can pin if: community admin/mod, OR community creator, OR site role with can_pin_threads on this board
  const isCreator     = user && community.created_by_id && user.id === community.created_by_id
  const hasSitePin    = !!(permissions?.capabilities?.can_pin_threads && (
    permissions.is_admin_tier || permissions.assigned_boards?.includes(community.board_slug)
  ))
  const canPin        = !!(user && (userRole === 'admin' || isCreator || hasSitePin))

  return (
    <div className="page-layout">

      {/* ── Community header ── */}
      <div className="community-header">
        <div className="community-header-top">
          <div className="community-header-icon">{community.board_icon || '👥'}</div>
          <div className="community-header-info">
            <h1>{community.name}</h1>
            <div className="community-header-meta">
              {community.board_slug && (
                <Link to={`/boards/${community.board_slug}`} className="board-tag">
                  <Hash size={10} /> /{community.board_slug}/
                </Link>
              )}
              {community.is_private
                ? <span className="privacy-tag private"><Lock size={10} /> Private</span>
                : <span className="privacy-tag public"><Globe size={10} /> Public</span>
              }
              <button className="members-count-btn" onClick={handleToggleMembers}>
                <Users size={11} /> {community.member_count} member{community.member_count !== 1 ? 's' : ''}
                {showMembers ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
              </button>
              {userRole && (
                <span className={`role-badge role-badge--${userRole}`}>
                  {ROLE_ICON[userRole]} {ROLE_LABEL[userRole]}
                </span>
              )}
            </div>
          </div>
          <div className="community-header-actions">
            <button className="btn-ghost btn-tiny" onClick={fetchThreads}>
              <RefreshCw size={13} />
            </button>
            {/* Join shown to non-members of public communities */}
            {user && !isMember && !community.is_private && (
              <button className="btn-primary" onClick={handleJoin}>Join</button>
            )}
            {/* Leave shown to all members */}
            {user && isMember && (
              <button className="btn-ghost" onClick={handleLeaveClick}>Leave</button>
            )}
            {canPost && (
              <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
                <Plus size={14} /> New Thread
              </button>
            )}
          </div>
        </div>
        {community.description && (
          <p className="community-description">{community.description}</p>
        )}
      </div>

      {/* ── Last-admin leave confirmation ── */}
      {showLeaveConfirm && (
        <div className="danger-banner">
          <strong>⚠ You are the last admin.</strong>
          <p>Leaving will permanently delete <strong>{community.name}</strong> and all its threads. There is no undo.</p>
          <div className="danger-banner-actions">
            <button className="btn-ghost" onClick={() => setShowLeaveConfirm(false)}>Cancel</button>
            <button className="btn-danger" onClick={handleLeaveAndDelete}>Delete community &amp; leave</button>
          </div>
        </div>
      )}

      {/* ── Members panel ── */}
      {showMembers && (
        <div className="members-panel">
          <div className="members-panel-header">
            <h3><Users size={14} /> Members ({community.member_count})</h3>
            {isAdminOrMod && (
              <button
                className="btn-ghost btn-tiny"
                onClick={() => { setShowAddForm(v => !v); setAddError(''); setAddSuccess('') }}
              >
                <UserPlus size={13} /> Add member
              </button>
            )}
          </div>

          {showAddForm && isAdminOrMod && (
            <form className="add-member-form" onSubmit={handleAddMember}>
              <input
                type="text"
                placeholder="Username to add…"
                value={addUsername}
                onChange={e => setAddUsername(e.target.value)}
                required
                autoFocus
              />
              <button type="submit" className="btn-primary btn-tiny">Add</button>
              <button type="button" className="btn-ghost btn-tiny" onClick={() => setShowAddForm(false)}>Cancel</button>
              {addError   && <span className="error-msg">{addError}</span>}
              {addSuccess && <span className="success-msg">{addSuccess}</span>}
            </form>
          )}

          {membersLoading ? (
            <p className="muted-text">Loading members…</p>
          ) : members.length === 0 ? (
            <p className="muted-text">No members yet.</p>
          ) : (
            <div className="members-list">
              {members.map(m => (
                <div key={m.user.id} className="member-row">
                  <span className="member-username">{m.user.username}</span>

                  {/* Role badge / dropdown for admins */}
                  {isAdmin && m.user.username !== user?.username ? (
                    <select
                      className="role-select"
                      value={m.role}
                      onChange={e => handleSetRole(m.user.username, e.target.value)}
                    >
                      <option value="member">Member</option>
                      <option value="mod">Mod</option>
                      <option value="admin">Admin</option>
                    </select>
                  ) : (
                    m.role !== 'member' && (
                      <span className={`role-badge role-badge--${m.role}`}>
                        {ROLE_ICON[m.role]} {ROLE_LABEL[m.role]}
                      </span>
                    )
                  )}

                  <span className="member-joined">
                    joined {new Date(m.joined_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                  </span>

                  {/* Remove button — admins/mods can remove non-admins (not themselves) */}
                  {isAdminOrMod && m.role !== 'admin' && m.user.username !== user?.username && (
                    <button
                      className="remove-member-btn"
                      title={`Remove ${m.user.username}`}
                      onClick={() => handleRemoveMember(m.user.username)}
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Invite links panel (admin/mod only) ── */}
      {isAdminOrMod && (
        <div className="members-panel">
          <div className="members-panel-header">
            <h3><LinkIcon size={14} /> Invite Links</h3>
            <button className="btn-ghost btn-tiny" onClick={handleShowInvites}>
              {showInvites ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              {showInvites ? 'Hide' : 'Manage'}
            </button>
          </div>

          {showInvites && (
            <>
              <form className="add-member-form" onSubmit={handleCreateInvite} style={{ gap: '6px' }}>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <input
                    type="number"
                    min="1"
                    placeholder="Expires in days (optional)"
                    value={inviteForm.expires_in_days}
                    onChange={e => setInviteForm(f => ({ ...f, expires_in_days: e.target.value }))}
                    style={{ width: '190px' }}
                  />
                  <input
                    type="number"
                    min="1"
                    placeholder="Max uses (optional)"
                    value={inviteForm.max_uses}
                    onChange={e => setInviteForm(f => ({ ...f, max_uses: e.target.value }))}
                    style={{ width: '160px' }}
                  />
                  <button type="submit" className="btn-primary btn-tiny">Generate link</button>
                </div>
                {inviteError && <span className="error-msg">{inviteError}</span>}
              </form>

              {inviteLoading ? (
                <p className="muted-text">Loading invites…</p>
              ) : invites.length === 0 ? (
                <p className="muted-text">No active invite links.</p>
              ) : (
                <div className="invite-list">
                  {invites.map(inv => (
                    <div key={inv.token} className="invite-row">
                      <div className="invite-url">{inv.invite_url}</div>
                      <div className="invite-meta">
                        {inv.expires_at
                          ? <span>Expires {new Date(inv.expires_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                          : <span>No expiry</span>
                        }
                        {inv.max_uses != null
                          ? <span>{inv.use_count} / {inv.max_uses} uses</span>
                          : <span>{inv.use_count} uses</span>
                        }
                        {!inv.is_valid && <span className="invite-expired">Expired</span>}
                      </div>
                      <div className="invite-actions">
                        <button
                          className="btn-ghost btn-tiny"
                          onClick={() => handleCopyInvite(inv.invite_url, inv.token)}
                        >
                          {copiedToken === inv.token ? '✓ Copied' : 'Copy'}
                        </button>
                        <button
                          className="btn-ghost btn-tiny"
                          onClick={() => handleRevokeInvite(inv.token)}
                          title="Revoke this link"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── New thread form ── */}
      {showForm && (
        <form onSubmit={handlePost} className="post-form">
          <input
            placeholder="Thread title"
            value={form.title}
            onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
            required
          />
          <textarea
            placeholder="What's on your mind?"
            value={form.body}
            onChange={e => setForm(f => ({ ...f, body: e.target.value }))}
            required
          />
          <div className="form-actions">
            <CaptchaField onChange={setMcaptchaToken} />
            <button type="button" className="btn-ghost" onClick={() => setShowForm(false)}>Cancel</button>
            <button type="submit" className="btn-primary">Post to community</button>
          </div>
        </form>
      )}

      {/* ── Thread list or gate ── */}
      {!canView ? (
        <div className="private-gate">
          <Lock size={32} />
          <h2>Private Community</h2>
          <p>This community's posts are only visible to members.</p>
          {!user && <Link to="/login" className="btn-primary">Log in to request access</Link>}
        </div>
      ) : (
        <div className="thread-list">
          {threads.length === 0 ? (
            <div className="empty-state">
              No threads yet.{canPost ? ' Be the first to post.' : ''}
            </div>
          ) : (
            threads.map((t, i) => <ThreadCard key={t.id} thread={t} position={i + 1} canPin={canPin} />)
          )}
        </div>
      )}
    </div>
  )
}
