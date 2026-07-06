import { useState } from 'react'
import { Link } from 'react-router-dom'
import { MessageSquare, Eye, Pin, PinOff, MessageSquareOff, MessageSquareMore } from 'lucide-react'
import ReactionBar from './ReactionBar'
import BadgeDisplay from './BadgeDisplay'
import FederatedBadge from './FederatedBadge'
import ReportButton from './ReportButton'
import HiddenBadge from './HiddenBadge'
import VideoPlayer from './VideoPlayer'
import { useAuth } from '../context/AuthContext'
import api from '../api/client'
import { stripMarkdown } from '../utils/markdown'


export default function ThreadCard({ thread: initialThread, onReact, position, canPin = false }) {
  const [thread, setThread] = useState(initialThread)
  const isOwnHiddenThread = thread.is_hidden && user && thread.author?.id === user.id

  const handlePin = async () => {
    try {
      const { data } = await api.post(`/threads/${thread.id}/pin/`)
      setThread(t => ({ ...t, is_pinned: data.is_pinned, comments_disabled: data.comments_disabled }))
    } catch {
      alert('Could not pin thread.')
    }
  }

  const handleUnpin = async () => {
    try {
      const { data } = await api.post(`/threads/${thread.id}/unpin/`)
      setThread(t => ({ ...t, is_pinned: data.is_pinned, comments_disabled: data.comments_disabled }))
    } catch {
      alert('Could not unpin thread.')
    }
  }

  const handleToggleComments = async () => {
    try {
      const { data } = await api.post(`/threads/${thread.id}/toggle-comments/`, {
        disabled: !thread.comments_disabled
      })
      setThread(t => ({ ...t, comments_disabled: data.comments_disabled }))
    } catch {
      alert('Could not toggle comments.')
    }
  }

  return (
    <article className={`thread-card${thread.is_pinned ? ' thread-card--pinned' : ''}`}>
      <div className="thread-card-header">
        {position && <span className="thread-position">#{position}</span>}
        {thread.is_pinned && <span className="pinned-badge">📌 Pinned</span>}
        <Link to={`/boards/${thread.board_slug}`} className="board-tag">
          /{thread.board_slug}/
        </Link>
        <span className="thread-author">
          {thread.author ? (thread.author.display_name || thread.author.username) : 'Anonymous'}
          <FederatedBadge author={thread.author} />
          <BadgeDisplay badge={thread.author?.display_badge} />
          {thread.author?.is_premium && !thread.author?.display_badge && (
            <span className="premium-badge">PRO</span>
          )}
        </span>
        <span className="thread-time">{timeAgo(thread.last_reply_at)}</span>
        {isOwnHiddenThread && <HiddenBadge />}
      </div>

      <Link to={`/thread/${thread.id}`} className="thread-title">
        <h2>{thread.title}</h2>
      </Link>

      {(thread.thumbnail || thread.image) && (
        <Link to={`/thread/${thread.id}`}>
          <img
            src={thread.thumbnail || thread.image}
            alt=""
            className="thread-thumbnail"
            loading="lazy"
          />
        </Link>
      )}

      {thread.video && (
        <VideoPlayer
          src={thread.video}
          thumbnail={thread.video_thumbnail || undefined}
          duration={thread.video_duration}
          soundAllowed={thread.allow_video_sound !== false}
          compact
        />
      )}

      <p className="thread-body">
        {stripMarkdown(thread.body).slice(0, 280)}{stripMarkdown(thread.body).length > 280 ? '…' : ''}
      </p>

      {thread.comments_disabled && (
        <p className="comments-disabled-notice">💬 Comments are disabled on this thread.</p>
      )}

      <div className="thread-footer">
        <ReactionBar
          reactions={thread.reactions || []}
          onReact={emoji => onReact?.(thread.id, emoji)}
          readOnly
        />
        <div className="thread-stats">
          <span><MessageSquare size={13} /> {thread.reply_count}</span>
          <span><Eye size={13} /> {thread.view_count}</span>
        </div>
        {canPin && (
          <div className="pin-controls">
            {thread.is_pinned
              ? <button className="btn-ghost btn-tiny" onClick={handleUnpin} title="Unpin thread"><PinOff size={13} /></button>
              : <button className="btn-ghost btn-tiny" onClick={handlePin} title="Pin thread"><Pin size={13} /></button>
            }
            <button
              className="btn-ghost btn-tiny"
              onClick={handleToggleComments}
              title={thread.comments_disabled ? 'Enable comments' : 'Disable comments'}
            >
              {thread.comments_disabled
                ? <MessageSquareMore size={13} />
                : <MessageSquareOff size={13} />
              }
            </button>
          </div>
        )}
        <ReportButton threadId={thread.id} compact />
      </div>
    </article>
  )
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const utcStr = /Z|[+-]\d{2}:\d{2}$/.test(dateStr) ? dateStr : dateStr + 'Z'
  const diff = (Date.now() - new Date(utcStr)) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}
