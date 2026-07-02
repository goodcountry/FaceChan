import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import { MessageCircle, Plus, X } from 'lucide-react'

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const utcStr = /Z|[+-]\d{2}:\d{2}$/.test(dateStr) ? dateStr : dateStr + 'Z'
  const diff = (Date.now() - new Date(utcStr)) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

// Everyone except the current user — what a conversation row shows as "who this is with"
function otherParticipants(conversation, user) {
  return conversation.participants.filter(p => p.id !== user.id)
}

function NewConversationForm({ onCreated, onCancel }) {
  const [usernames, setUsernames] = useState('')
  const [body, setBody] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async e => {
    e.preventDefault()
    const participants = usernames.split(',').map(s => s.trim()).filter(Boolean)
    if (participants.length === 0) {
      setError('Enter at least one username.')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const { data } = await api.post('/conversations/', { participants, body })
      onCreated(data)
    } catch (err) {
      const d = err.response?.data
      const msg = d?.participants || d?.body || d?.detail || 'Could not start conversation.'
      setError(Array.isArray(msg) ? msg[0] : msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="post-form">
      <input
        placeholder="Usernames, comma-separated (e.g. alice, bob)"
        value={usernames}
        onChange={e => setUsernames(e.target.value)}
        required
      />
      <textarea
        placeholder="Your first message…"
        value={body}
        onChange={e => setBody(e.target.value)}
        rows={3}
        required
      />
      {error && <div className="error-msg">{error}</div>}
      <div className="form-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? 'Starting…' : 'Start conversation'}
        </button>
      </div>
    </form>
  )
}

export default function Conversations() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [conversations, setConversations] = useState([])
  const [loading, setLoading] = useState(true)
  const [showNew, setShowNew] = useState(false)

  const load = () => {
    setLoading(true)
    api.get('/conversations/').then(r => {
      setConversations(r.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }

  useEffect(() => { if (user) load() }, [user])

  const handleCreated = conversation => {
    setShowNew(false)
    navigate(`/messages/${conversation.id}`)
  }

  if (!user) return <div className="page-layout"><p className="muted text-center">Log in to view messages.</p></div>
  if (loading) return <div className="loader">Loading conversations…</div>

  return (
    <div className="page-layout">
      <div className="page-header">
        <MessageCircle size={20} className="accent" />
        <h1>Messages</h1>
        <div style={{ marginLeft: 'auto' }}>
          <button className="btn-primary" onClick={() => setShowNew(s => !s)}>
            {showNew ? <><X size={14} /> Cancel</> : <><Plus size={14} /> New message</>}
          </button>
        </div>
      </div>

      {showNew && <NewConversationForm onCreated={handleCreated} onCancel={() => setShowNew(false)} />}

      <div className="conversation-list">
        {conversations.map(c => {
          const others = otherParticipants(c, user)
          return (
            <Link key={c.id} to={`/messages/${c.id}`} className={`conversation-row${c.unread_count > 0 ? ' has-unread' : ''}`}>
              <div className="fb-avatar fb-avatar-sm">
                {(others[0]?.display_name || others[0]?.username || '?')[0].toUpperCase()}
              </div>
              <div className="conversation-row-body">
                <div className="conversation-row-top">
                  <span className="conversation-row-names">
                    {others.map(p => p.display_name || p.username).join(', ') || 'Just you'}
                  </span>
                  <span className="fb-time">{timeAgo(c.last_reply_at)}</span>
                </div>
                <div className="conversation-row-preview">
                  {c.last_message
                    ? <>{c.last_message.author && <strong>{c.last_message.author}: </strong>}{c.last_message.body}</>
                    : <span className="muted">No messages yet</span>}
                </div>
              </div>
              {c.unread_count > 0 && <span className="bell-badge conversation-unread-badge">{c.unread_count > 99 ? '99+' : c.unread_count}</span>}
            </Link>
          )
        })}
        {conversations.length === 0 && !showNew && (
          <p className="empty-state">No conversations yet. Start one above.</p>
        )}
      </div>
    </div>
  )
}
