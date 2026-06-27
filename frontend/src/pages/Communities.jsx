import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Users, Lock, Globe, Plus, Hash, Search, TrendingUp, Activity, Clock, Star } from 'lucide-react'

const SORT_TABS = [
  { key: 'trending', label: 'Trending',  icon: <TrendingUp size={13} />, hint: 'Most active in last 24h' },
  { key: 'active',   label: 'Active',    icon: <Activity size={13} />,   hint: 'Most active in last 48h' },
  { key: 'members',  label: 'Popular',   icon: <Star size={13} />,       hint: 'Most members' },
  { key: 'newest',   label: 'Newest',    icon: <Clock size={13} />,      hint: 'Recently created' },
]

export default function Communities() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [communities, setCommunities] = useState([])
  const [boards, setBoards] = useState([])
  const [filterBoard, setFilterBoard] = useState('')
  const [sort, setSort] = useState('trending')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', slug: '', description: '', board: '', is_private: false })
  const [createError, setCreateError] = useState('')

  const fetchCommunities = useCallback((overrides = {}) => {
    const params = new URLSearchParams()
    const board  = overrides.board  !== undefined ? overrides.board  : filterBoard
    const s      = overrides.sort   !== undefined ? overrides.sort   : sort
    const q      = overrides.search !== undefined ? overrides.search : search
    if (board)  params.set('board', board)
    if (s)      params.set('sort', s)
    if (q)      params.set('search', q)
    return api.get(`/communities/?${params}`).then(r => {
      setCommunities(r.data.results || r.data)
      setLoading(false)
    })
  }, [filterBoard, sort, search])

  useEffect(() => {
    api.get('/boards/').then(r => setBoards(r.data.results || r.data))
    fetchCommunities()
  }, [])  // eslint-disable-line

  const handleSort = s => {
    setSort(s)
    fetchCommunities({ sort: s })
  }

  const handleBoardFilter = b => {
    setFilterBoard(b)
    fetchCommunities({ board: b })
  }

  const handleSearch = e => {
    const q = e.target.value
    setSearch(q)
    fetchCommunities({ search: q })
  }

  const handleJoin = async (slug) => {
    if (!user) {
      navigate('/login', { state: { from: '/communities' } })
      return
    }
    await api.post(`/communities/${slug}/join/`)
    fetchCommunities()
  }

  const handleLeave = async (slug) => {
    await api.post(`/communities/${slug}/leave/`)
    fetchCommunities()
  }

  const handleCreate = async e => {
    e.preventDefault()
    setCreateError('')
    try {
      await api.post('/communities/', form)
      setShowCreate(false)
      setForm({ name: '', slug: '', description: '', board: '', is_private: false })
      fetchCommunities()
    } catch (err) {
      setCreateError(err.response?.data?.detail || 'Could not create community.')
    }
  }

  const autoSlug = name => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

  const activityLabel = (c) => {
    if (sort === 'trending' && c.trending_posts > 0)
      return `${c.trending_posts} post${c.trending_posts !== 1 ? 's' : ''} in 24h`
    if (sort === 'active' && c.active_posts > 0)
      return `${c.active_posts} post${c.active_posts !== 1 ? 's' : ''} in 48h`
    return null
  }

  return (
    <div className="page-layout">
      <div className="page-header">
        <Users size={20} className="accent" />
        <h1>Communities</h1>
        {user && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="community-limit-info">
              {user.is_premium
                ? `${user.communities_created || 0} / 10 communities (PRO)`
                : `${user.communities_created || 0} / 1 community`}
            </span>
            <button className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
              <Plus size={14} /> Create
            </button>
          </div>
        )}
      </div>

      {/* ── Create form ── */}
      {showCreate && (
        <form onSubmit={handleCreate} className="post-form">
          <input
            placeholder="Community name"
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value, slug: autoSlug(e.target.value) }))}
            required
          />
          <input
            placeholder="URL slug (auto-filled)"
            value={form.slug}
            onChange={e => setForm(f => ({ ...f, slug: e.target.value }))}
            required
          />
          <textarea
            placeholder="Description (optional)"
            value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
          />
          <select
            value={form.board}
            onChange={e => setForm(f => ({ ...f, board: e.target.value }))}
            required
          >
            <option value="">— Select a board —</option>
            {boards.map(b => (
              <option key={b.slug} value={b.slug}>{b.icon} /{b.slug}/ — {b.name}</option>
            ))}
          </select>
          <label className="sage-toggle">
            <input
              type="checkbox"
              checked={form.is_private}
              onChange={e => setForm(f => ({ ...f, is_private: e.target.checked }))}
            />
            <span className="sage-label">Private community (invite only)</span>
          </label>
          {createError && <div className="error-msg">{createError}</div>}
          <div className="form-actions">
            <button type="button" className="btn-ghost" onClick={() => setShowCreate(false)}>Cancel</button>
            <button type="submit" className="btn-primary">Create community</button>
          </div>
        </form>
      )}

      {/* ── Search bar ── */}
      <div className="discovery-search">
        <Search size={14} className="discovery-search-icon" />
        <input
          className="discovery-search-input"
          placeholder="Search communities…"
          value={search}
          onChange={handleSearch}
        />
      </div>

      {/* ── Sort tabs ── */}
      <div className="sort-tabs">
        {SORT_TABS.map(t => (
          <button
            key={t.key}
            className={`sort-tab${sort === t.key ? ' active' : ''}`}
            onClick={() => handleSort(t.key)}
            title={t.hint}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* ── Board filter ── */}
      <div className="board-filter">
        <button
          className={`filter-btn ${filterBoard === '' ? 'active' : ''}`}
          onClick={() => handleBoardFilter('')}
        >All</button>
        {boards.map(b => (
          <button
            key={b.slug}
            className={`filter-btn ${filterBoard === b.slug ? 'active' : ''}`}
            onClick={() => handleBoardFilter(b.slug)}
          >
            {b.icon} /{b.slug}/
          </button>
        ))}
      </div>

      {/* ── Community grid ── */}
      {loading ? (
        <div className="loader">Loading communities…</div>
      ) : (
        <div className="community-grid">
          {communities.map(c => {
            const activity = activityLabel(c)
            return (
              <div key={c.id} className="community-card">
                <div className="community-card-header">
                  <div className="community-icon">{c.board_icon || '👥'}</div>
                  <div className="community-privacy">
                    {c.is_private
                      ? <span className="privacy-tag private"><Lock size={10} /> Private</span>
                      : <span className="privacy-tag public"><Globe size={10} /> Public</span>
                    }
                  </div>
                </div>

                <Link to={`/c/${c.slug}`} className="community-name">{c.name}</Link>

                {c.board_slug && (
                  <Link to={`/boards/${c.board_slug}`} className="community-board-tag">
                    <Hash size={10} /> /{c.board_slug}/
                  </Link>
                )}

                {c.description && (
                  <p className="community-desc">{c.description.slice(0, 120)}{c.description.length > 120 ? '…' : ''}</p>
                )}

                <div className="community-stats">
                  <span className="community-members"><Users size={11} /> {c.member_count} members</span>
                  {activity && <span className="community-activity"><TrendingUp size={11} /> {activity}</span>}
                </div>

                <div className="community-footer">
                  {c.is_member ? (
                    <>
                      <Link to={`/c/${c.slug}`} className="btn-ghost btn-tiny">View</Link>
                      <button className="btn-ghost btn-tiny" onClick={() => handleLeave(c.slug)}>Leave</button>
                    </>
                  ) : c.is_private ? (
                    <span className="muted" style={{ fontSize: '11px' }}>Invite only</span>
                  ) : (
                    <button className="btn-primary btn-tiny" onClick={() => handleJoin(c.slug)}>
                      {user ? 'Join' : 'Join — log in'}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
          {communities.length === 0 && (
            <div className="empty-state" style={{ gridColumn: '1/-1' }}>
              {search ? `No communities matching "${search}".` : 'No communities yet.'}
              {!search && (user ? ' Create the first one!' : ' Log in to create one.')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
