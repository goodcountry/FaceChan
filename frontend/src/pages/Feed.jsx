import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import api from '../api/client'
import ThreadCard from '../components/ThreadCard'
import { Flame, Bell } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export default function Feed() {
  const { user } = useAuth()
  const location = useLocation()
  const [threads, setThreads] = useState([])
  const [watched, setWatched] = useState([])
  const [tab, setTab] = useState(location.state?.tab || 'feed')

  // If the bell navigates to /feed with state.tab='watched' while already
  // on /feed, the component doesn't remount — watch for state changes.
  useEffect(() => {
    if (location.state?.tab) setTab(location.state.tab)
  }, [location.state])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/feed/').then(r => { setThreads(r.data.results || r.data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!user) return
    api.get('/me/watched/').then(r => setWatched(r.data)).catch(() => {})
  }, [user])

  const handleReact = async (threadId, emoji) => {
    await api.post(`/threads/${threadId}/react/`, { emoji })
    setThreads(ts => ts.map(t => t.id === threadId ? { ...t, _reactKey: Date.now() } : t))
  }

  const unreadTotal = watched.reduce((sum, w) => sum + (w.unread || 0), 0)

  if (loading) return <div className="loader">Loading feed…</div>

  return (
    <div className="page-layout">
      <div className="page-header">
        <Flame size={20} className="accent" />
        <h1>Feed</h1>
        {user && (
          <div className="feed-tabs">
            <button
              className={`feed-tab${tab === 'feed' ? ' active' : ''}`}
              onClick={() => setTab('feed')}
            >Feed</button>
            <button
              className={`feed-tab${tab === 'watched' ? ' active' : ''}`}
              onClick={() => setTab('watched')}
            >
              <Bell size={13} /> Watched
              {unreadTotal > 0 && <span className="feed-unread-badge">{unreadTotal}</span>}
            </button>
          </div>
        )}
      </div>

      {tab === 'feed' && (
        threads.length === 0 ? (
          <div className="empty-state">
            <p>No threads yet. Join some communities or browse a board.</p>
          </div>
        ) : (
          <div className="thread-list">
            {threads.map(t => <ThreadCard key={t.id} thread={t} onReact={handleReact} />)}
          </div>
        )
      )}

      {tab === 'watched' && (
        <div className="watched-list">
          {watched.length === 0 ? (
            <div className="empty-state">
              <p>You're not watching any threads yet.</p>
              <p className="muted">Open a thread and click <Bell size={12} style={{display:'inline',verticalAlign:'middle'}} /> Watch to get notified of replies.</p>
            </div>
          ) : (
            watched.map(w => (
              <Link key={w.thread_id} to={`/thread/${w.thread_id}`} className="watched-item">
                <div className="watched-item-title">
                  <span className="board-tag">/{w.board_slug}/</span>
                  {w.title}
                </div>
                <div className="watched-item-meta">
                  <span className="muted">{w.reply_count} replies</span>
                  {w.unread > 0 && (
                    <span className="watched-unread">{w.unread} new</span>
                  )}
                </div>
              </Link>
            ))
          )}
        </div>
      )}
    </div>
  )
}
