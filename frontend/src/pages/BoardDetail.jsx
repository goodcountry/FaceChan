import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import api from '../api/client'
import ThreadCard from '../components/ThreadCard'
import CatalogCard from '../components/CatalogCard'
import AgeGate, { isAgeVerified } from '../components/AgeGate'
import CaptchaField from '../components/CaptchaField'
import { useAuth } from '../context/AuthContext'
import { useSiteSettings } from '../context/SiteSettingsContext'
import { Plus, RefreshCw, LayoutList, LayoutGrid, Search, X } from 'lucide-react'

export default function BoardDetail() {
  const { slug } = useParams()
  const { user, permissions } = useAuth()
  const { enable_nsfw_boards, block_nsfw_without_age_gate, allow_image_uploads, allow_video_uploads } = useSiteSettings()
  const [threads, setThreads] = useState([])
  const [board, setBoard] = useState(null)
  const [gateNeeded, setGateNeeded] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ title: '', body: '' })
  const [mcaptchaToken, setMcaptchaToken] = useState('')
  const [imageFile, setImageFile] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [videoFile, setVideoFile] = useState(null)
  const [videoPreview, setVideoPreview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [view, setView] = useState(() => localStorage.getItem('boardView') || 'list')
  const [search, setSearch] = useState('')
  const debounceRef = useRef(null)

  // User can pin on this board if they have can_pin_threads and are either
  // admin-tier (unscoped) or explicitly assigned to this board.
  const canPin = !!(
    user &&
    permissions?.capabilities?.can_pin_threads &&
    (permissions.is_admin_tier || permissions.assigned_boards?.includes(slug))
  )

  const setViewMode = mode => {
    setView(mode)
    localStorage.setItem('boardView', mode)
  }

  const gateActive = enable_nsfw_boards && block_nsfw_without_age_gate

  const fetchThreads = useCallback((q = search) => {
    const params = new URLSearchParams({ board: slug })
    if (q) params.set('search', q)
    return api.get(`/threads/?${params}`)
      .then(r => setThreads(r.data.results || r.data))
  }, [slug, search])

  const handleSearchChange = e => {
    const q = e.target.value
    setSearch(q)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => fetchThreads(q), 300)
  }

  const clearSearch = () => {
    setSearch('')
    fetchThreads('')
  }

  useEffect(() => {
    setLoading(true)
    api.get(`/boards/${slug}/`).then(r => {
      setBoard(r.data)
      const needsGate = r.data.nsfw && gateActive && !isAgeVerified()
      setGateNeeded(needsGate)
      if (needsGate) {
        setLoading(false)
      } else {
        fetchThreads().finally(() => setLoading(false))
      }
    })
  }, [slug, fetchThreads, gateActive])

  // Re-fetch when tab regains focus — catches bumps from thread replies
  useEffect(() => {
    if (gateNeeded) return
    const onFocus = () => fetchThreads()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [fetchThreads, gateNeeded])

  // ── Board WebSocket ────────────────────────────────────────────────────────
  // Listens for new_thread events pushed by BoardConsumer (federated threads
  // and any future real-time thread creation). Prepends the new thread card
  // without a page refresh. No auth required — board feeds are public.
  useEffect(() => {
    if (gateNeeded || loading) return

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${proto}://${window.location.host}/ws/boards/${slug}/`
    const ws = new WebSocket(url)

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'new_thread' && data.thread) {
          setThreads(prev => {
            // Deduplicate — ignore if we already have this thread
            if (prev.some(t => t.id === data.thread.id)) return prev
            return [data.thread, ...prev]
          })
        }
      } catch (_) {}
    }

    // onerror fires before onclose — no action needed here
    ws.onerror = () => {}

    return () => {
      ws.onmessage = null
      ws.close()
    }
  }, [slug, gateNeeded, loading])

  const handleImageChange = e => {
    const file = e.target.files[0]
    if (!file) return
    setVideoFile(null); setVideoPreview(null)  // mutually exclusive
    setImageFile(file)
    setImagePreview(URL.createObjectURL(file))
  }

  const clearImage = () => {
    setImageFile(null)
    setImagePreview(null)
  }

  const handleVideoChange = e => {
    const file = e.target.files[0]
    if (!file) return
    setImageFile(null); setImagePreview(null)  // mutually exclusive
    setVideoFile(file)
    setVideoPreview(URL.createObjectURL(file))
  }

  const clearVideo = () => {
    setVideoFile(null)
    setVideoPreview(null)
  }

  const submit = async e => {
    e.preventDefault()
    setError('')
    const payload = new FormData()
    payload.append('title', form.title)
    payload.append('body', form.body)
    payload.append('board', slug)
    payload.append('website', '')  // honeypot — always empty for humans
    if (mcaptchaToken) payload.append('mcaptcha_token', mcaptchaToken)
    if (imageFile) payload.append('image', imageFile)
    if (videoFile) payload.append('video', videoFile)
    try {
      await api.post('/threads/', payload, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setForm({ title: '', body: '' })
      setImageFile(null); setImagePreview(null)
      setVideoFile(null); setVideoPreview(null)
      setShowForm(false)
      fetchThreads()
    } catch (err) {
      const data = err.response?.data
      const msg = data?.detail || data?.image || data?.video || data?.error ||
        (typeof data === 'string' ? data : 'Could not post thread.')
      setError(Array.isArray(msg) ? msg[0] : msg)
    }
  }

  if (loading) return <div className="loader">Loading /{slug}/…</div>

  if (gateNeeded) {
    return (
      <div className="page-layout">
        <AgeGate onConfirm={() => {
          setGateNeeded(false)
          setLoading(true)
          fetchThreads().finally(() => setLoading(false))
        }} />
      </div>
    )
  }

  return (
    <div className="page-layout">
      {board && (
        <div className="page-header">
          <span className="board-icon-lg">{board.icon}</span>
          <div>
            <h1>/{board.slug}/</h1>
            <p className="muted">{board.description || board.name}</p>
            {!board.allow_images && (
              <span className="text-only-badge" style={{ marginTop: '4px', display: 'inline-block' }}>Text only</span>
            )}
          </div>
          <div className="header-actions">
            <div className="board-search">
              <Search size={13} className="board-search-icon" />
              <input
                className="board-search-input"
                placeholder="Search threads…"
                value={search}
                onChange={handleSearchChange}
              />
              {search && (
                <button className="board-search-clear" onClick={clearSearch} title="Clear search">
                  <X size={12} />
                </button>
              )}
            </div>
            <div className="view-toggle">
              <button
                className={`view-toggle-btn${view === 'list' ? ' active' : ''}`}
                onClick={() => setViewMode('list')}
                title="List view"
              ><LayoutList size={15} /></button>
              <button
                className={`view-toggle-btn${view === 'catalog' ? ' active' : ''}`}
                onClick={() => setViewMode('catalog')}
                title="Catalog view"
              ><LayoutGrid size={15} /></button>
            </div>
            <button className="btn-ghost" onClick={fetchThreads} title="Refresh">
              <RefreshCw size={14} />
            </button>
            {user && (
              <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
                <Plus size={14} /> New Thread
              </button>
            )}
          </div>
        </div>
      )}

      {showForm && (
        <form onSubmit={submit} className="post-form">
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
          {imagePreview && (
            <div className="image-preview">
              <img src={imagePreview} alt="preview" />
              <button type="button" className="image-remove" onClick={clearImage}>✕</button>
            </div>
          )}
          {videoPreview && (
            <div className="image-preview">
              <video src={videoPreview} controls muted style={{ maxWidth: '100%', maxHeight: 180 }} />
              <button type="button" className="image-remove" onClick={clearVideo}>✕</button>
            </div>
          )}
          {error && <div className="error-msg">{error}</div>}
          <div className="form-actions">
            {board?.allow_images && (allow_image_uploads || user?.can_post_media) && (
              <label className="btn-ghost image-upload-label" title="Attach image">
                🖼 Image
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleImageChange}
                  style={{ display: 'none' }}
                />
              </label>
            )}
            {board?.allow_videos && (allow_video_uploads || user?.can_post_media) && (
              <label className="btn-ghost image-upload-label" title="Attach video (MP4/WebM)">
                🎬 Video
                <input
                  type="file"
                  accept="video/mp4,video/webm"
                  onChange={handleVideoChange}
                  style={{ display: 'none' }}
                />
              </label>
            )}
            <CaptchaField onChange={setMcaptchaToken} />
            <div style={{ flex: 1 }} />
            <button type="button" className="btn-ghost" onClick={() => { setShowForm(false); clearImage(); clearVideo() }}>Cancel</button>
            <button type="submit" className="btn-primary">Post</button>
          </div>
        </form>
      )}

      {/* Thread position indicator */}
      <div className="board-meta">
        <span className="muted" style={{fontSize: '12px'}}>
          {search
            ? `${threads.length} result${threads.length !== 1 ? 's' : ''} for "${search}"`
            : `${threads.length} / 100 threads — sorted by last bump`
          }
        </span>
      </div>

      {view === 'catalog' ? (
        <div className="catalog-grid">
          {threads.map(t => (
            <CatalogCard key={t.id} thread={t} />
          ))}
          {threads.length === 0 && (
            <div className="empty-state">
              {search ? `No threads matching "${search}".` : 'No threads yet. Start one.'}
            </div>
          )}
        </div>
      ) : (
        <div className="thread-list">
          {threads.map((t, i) => (
            <ThreadCard key={t.id} thread={t} position={i + 1} onReact={() => {}} canPin={canPin} />
          ))}
          {threads.length === 0 && (
            <div className="empty-state">
              {search ? `No threads matching "${search}".` : 'No threads yet. Start one.'}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
