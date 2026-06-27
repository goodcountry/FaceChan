import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import { Hash } from 'lucide-react'

export default function Boards() {
  const [boards, setBoards] = useState([])

  useEffect(() => { api.get('/boards/').then(r => setBoards(r.data.results || r.data)) }, [])

  return (
    <div className="page-layout">
      <div className="page-header">
        <Hash size={20} className="accent" />
        <h1>Boards</h1>
      </div>
      <div className="board-grid">
        {boards.map(b => (
          <Link to={`/boards/${b.slug}`} key={b.slug} className="board-card">
            <span className="board-icon">{b.icon}</span>
            <div>
              <h3>/{b.slug}/</h3>
              <p>{b.name}</p>
              <small>{b.thread_count} threads</small>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-end' }}>
              {b.nsfw && <span className="nsfw-badge">18+</span>}
              {!b.allow_images && <span className="text-only-badge">Text only</span>}
            </div>
          </Link>
        ))}
        {boards.length === 0 && <p className="empty-state">No boards yet.</p>}
      </div>
    </div>
  )
}
