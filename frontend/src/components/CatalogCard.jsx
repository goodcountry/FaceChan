import { Link } from 'react-router-dom'
import { MessageSquare } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export default function CatalogCard({ thread }) {
  const { user } = useAuth()
  const isOwnHidden = thread.is_hidden && user && thread.author?.id === user.id

  return (
    <Link to={`/thread/${thread.id}`} className={`catalog-card${isOwnHidden ? ' catalog-card--hidden' : ''}`}>
      {(thread.thumbnail || thread.image) ? (
        <div className="catalog-card-img">
          <img src={thread.thumbnail || thread.image} alt="" loading="lazy" />
        </div>
      ) : (
        <div className="catalog-card-img catalog-card-img--placeholder">
          <span>no image</span>
        </div>
      )}
      <div className="catalog-card-body">
        <div className="catalog-card-title">{thread.title}</div>
        <div className="catalog-card-meta">
          <span><MessageSquare size={11} /> {thread.reply_count}</span>
          <span className="catalog-card-time">{timeAgo(thread.last_reply_at)}</span>
        </div>
        <p className="catalog-card-excerpt">
          {thread.body.slice(0, 120)}{thread.body.length > 120 ? '…' : ''}
        </p>
      </div>
    </Link>
  )
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const utcStr = /Z|[+-]\d{2}:\d{2}$/.test(dateStr) ? dateStr : dateStr + 'Z'
  const diff = (Date.now() - new Date(utcStr)) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`
  return `${Math.floor(diff / 86400)}d`
}
