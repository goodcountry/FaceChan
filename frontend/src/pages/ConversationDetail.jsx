import { useState, useEffect, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import api from '../api/client'
import MarkdownBody from '../components/MarkdownBody'
import UserLink from '../components/UserLink'
import { useAuth } from '../context/AuthContext'
import { useNotifications } from '../context/NotificationContext'
import { ArrowLeft, Users, UserPlus, UserMinus, LogOut, Send } from 'lucide-react'

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const utcStr = /Z|[+-]\d{2}:\d{2}$/.test(dateStr) ? dateStr : dateStr + 'Z'
  const diff = (Date.now() - new Date(utcStr)) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

// A single message. author=null is a system note (join/leave/add/remove) —
// same Post model as everything else in FaceChan, rendered plainly instead
// of as a chat bubble.
function Message({ post, isOwn }) {
  if (!post.author) {
    return <div className="conversation-system-note">{post.body}</div>
  }
  return (
    <div className={`fb-reply${isOwn ? ' conversation-message-own' : ''}`}>
      <div className="fb-avatar fb-avatar-sm">
        {post.author.avatar
          ? <img src={post.author.avatar} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
          : (post.author.display_name || post.author.username || '?')[0].toUpperCase()}
      </div>
      <div className="fb-reply-bubble">
        <div className="fb-reply-header">
          <UserLink author={post.author} />
          <span className="fb-time">{timeAgo(post.created_at)}</span>
        </div>
        <MarkdownBody text={post.body} />
      </div>
    </div>
  )
}

function ParticipantsPanel({ conversation, user, onChanged, onClose }) {
  const [username, setUsername] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const addParticipant = async e => {
    e.preventDefault()
    setError('')
    try {
      const { data } = await api.post(`/conversations/${conversation.id}/add-participant/`, { username })
      setUsername('')
      onChanged(data)
    } catch (err) {
      setError(err.response?.data?.username || 'Could not add participant.')
    }
  }

  const removeParticipant = async targetUsername => {
    if (!confirm(`Remove ${targetUsername} from this conversation?`)) return
    try {
      const { data } = await api.post(`/conversations/${conversation.id}/remove-participant/`, { username: targetUsername })
      onChanged(data)
    } catch (err) {
      alert(err.response?.data?.username || 'Could not remove participant.')
    }
  }

  const leave = async () => {
    if (!confirm('Leave this conversation? You can only rejoin if someone adds you back.')) return
    try {
      await api.post(`/conversations/${conversation.id}/leave/`)
      navigate('/messages')
    } catch {
      alert('Could not leave conversation.')
    }
  }

  return (
    <div className="conversation-participants-panel">
      <div className="conversation-participants-header">
        <Users size={14} /> <strong>Participants</strong>
        <button className="btn-ghost btn-tiny" style={{ marginLeft: 'auto' }} onClick={onClose}>Close</button>
      </div>
      <ul className="conversation-participants-list">
        {conversation.participants.map(p => (
          <li key={p.id}>
            <UserLink author={p} />
            {p.id !== user.id && (
              <button
                className="btn-ghost btn-tiny"
                title={`Remove ${p.username}`}
                onClick={() => removeParticipant(p.username)}
              >
                <UserMinus size={12} />
              </button>
            )}
          </li>
        ))}
      </ul>
      <form onSubmit={addParticipant} className="conversation-add-participant">
        <input
          placeholder="Add username…"
          value={username}
          onChange={e => setUsername(e.target.value)}
        />
        <button type="submit" className="btn-ghost btn-tiny" title="Add participant"><UserPlus size={14} /></button>
      </form>
      {error && <div className="error-msg">{error}</div>}
      <button className="btn-ghost btn-tiny conversation-leave-btn" onClick={leave}>
        <LogOut size={12} /> Leave conversation
      </button>
    </div>
  )
}

export default function ConversationDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const { refresh: refreshBell } = useNotifications()
  const [conversation, setConversation] = useState(null)
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [showParticipants, setShowParticipants] = useState(false)
  const [body, setBody] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef(null)

  const load = () => {
    setLoading(true)
    return api.get(`/conversations/${id}/`).then(r => {
      setConversation(r.data)
      setPosts(r.data.posts || [])
      setLoading(false)
    }).catch(() => {
      setNotFound(true)
      setLoading(false)
    })
  }

  useEffect(() => { load() }, [id])

  // Mark seen once loaded — same endpoint ordinary threads use, harmlessly
  // no-ops for anything the user isn't watching.
  useEffect(() => {
    if (!conversation) return
    api.post(`/threads/${id}/mark-seen/`).then(() => refreshBell()).catch(() => {})
  }, [id, conversation?.id, refreshBell])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [posts.length])

  const handleChanged = updated => {
    setConversation(updated)
    setPosts(updated.posts || [])
  }

  const send = async e => {
    e.preventDefault()
    if (!body.trim()) return
    setSubmitting(true)
    setError('')
    try {
      const { data } = await api.post(`/threads/${id}/posts/`, { body, website: '' })
      setPosts(p => [...p, data])
      setBody('')
    } catch (err) {
      setError(err.response?.data?.body || err.response?.data?.detail || 'Could not send message.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div className="loader">Loading conversation…</div>
  if (notFound || !conversation) {
    return (
      <div className="page-layout">
        <p className="muted text-center">Conversation not found.</p>
        <p className="text-center"><Link to="/messages">← Back to messages</Link></p>
      </div>
    )
  }

  const others = conversation.participants.filter(p => p.id !== user.id)

  return (
    <div className="page-layout conversation-detail">
      <div className="page-header">
        <Link to="/messages" className="btn-ghost btn-tiny"><ArrowLeft size={14} /></Link>
        <h1 style={{ fontSize: '16px' }}>
          {others.map(p => p.display_name || p.username).join(', ') || 'Conversation'}
        </h1>
        <button
          className="btn-ghost btn-tiny"
          style={{ marginLeft: 'auto' }}
          onClick={() => setShowParticipants(s => !s)}
        >
          <Users size={14} /> {conversation.participants.length}
        </button>
      </div>

      {showParticipants && (
        <ParticipantsPanel
          conversation={conversation}
          user={user}
          onChanged={handleChanged}
          onClose={() => setShowParticipants(false)}
        />
      )}

      <div className="conversation-messages">
        {posts.map(p => <Message key={p.id} post={p} isOwn={p.author?.id === user.id} />)}
        {posts.length === 0 && <p className="empty-state">No messages yet.</p>}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={send} className="reply-composer conversation-composer">
        <textarea
          placeholder="Write a message…"
          value={body}
          onChange={e => setBody(e.target.value)}
          rows={2}
          required
        />
        {error && <div className="error-msg">{error}</div>}
        <div className="composer-footer">
          <div className="composer-actions">
            <button type="submit" className="btn-primary btn-tiny" disabled={submitting}>
              <Send size={13} /> {submitting ? 'Sending…' : 'Send'}
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
