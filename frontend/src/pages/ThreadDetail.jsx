import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import api from '../api/client'
import ReactionBar from '../components/ReactionBar'
import BadgeDisplay from '../components/BadgeDisplay'
import ReportButton from '../components/ReportButton'
import HiddenBadge from '../components/HiddenBadge'
import AgeGate from '../components/AgeGate'
import MarkdownBody from '../components/MarkdownBody'
import CaptchaField from '../components/CaptchaField'
import { useAuth } from '../context/AuthContext'
import { useSiteSettings } from '../context/SiteSettingsContext'
import UserLink from '../components/UserLink'
import { useNotifications } from '../context/NotificationContext'
import VideoPlayer from '../components/VideoPlayer'
import { MessageSquare, CornerDownRight, ChevronDown, ChevronUp, ArrowUp, Bell, BellOff, Pin, PinOff, MessageSquareOff, MessageSquareMore } from 'lucide-react'

// ── Reply composer ────────────────────────────────────────────────────────────
function ReplyComposer({ threadId, parentId, onPosted, onCancel, placeholder = 'Write a reply…', initialBody = '', showSage = false, allowImages = true, allowVideos = true }) {
  const [body, setBody] = useState(initialBody)
  const [sage, setSage] = useState(false)
  const [imageFile, setImageFile] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [videoFile, setVideoFile] = useState(null)
  const [videoPreview, setVideoPreview] = useState(null)
  const [mcaptchaToken, setMcaptchaToken] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const textareaRef = useRef(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.focus()
      const len = textareaRef.current.value.length
      textareaRef.current.setSelectionRange(len, len)
    }
  }, [])

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
    if (!body.trim()) return
    setSubmitting(true)
    setError('')
    try {
      const payload = new FormData()
      payload.append('body', body)
      payload.append('sage', showSage ? sage : false)
      payload.append('website', '')  // honeypot — always empty for humans
      if (mcaptchaToken) payload.append('mcaptcha_token', mcaptchaToken)
      if (parentId) payload.append('parent_id', parentId)
      if (imageFile) payload.append('image', imageFile)
      if (videoFile) payload.append('video', videoFile)
      const { data } = await api.post(`/threads/${threadId}/posts/`, payload, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      onPosted(data)
      setBody('')
      setSage(false)
      clearImage()
      clearVideo()
    } catch (err) {
      const d = err.response?.data
      const msg = d?.detail || d?.image || d?.video || d?.error ||
        (typeof d === 'string' ? d : 'Could not post reply.')
      setError(Array.isArray(msg) ? msg[0] : msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="reply-composer">
      <textarea
        ref={textareaRef}
        placeholder={placeholder}
        value={body}
        onChange={e => setBody(e.target.value)}
        rows={2}
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
      <CaptchaField onChange={setMcaptchaToken} />
      <div className="composer-footer">
        {showSage && (
          <label className="sage-toggle" title="Sage: reply without bumping thread to top">
            <input
              type="checkbox"
              checked={sage}
              onChange={e => setSage(e.target.checked)}
            />
            <span className={`sage-label ${sage ? 'sage-active' : ''}`}>
              sage {sage && '(won\'t bump)'}
            </span>
          </label>
        )}
        <label className="image-upload-label btn-ghost btn-tiny" title="Attach image" style={allowImages ? {} : { display: 'none' }}>
          🖼
          <input
            type="file"
            accept="image/*"
            onChange={handleImageChange}
            style={{ display: 'none' }}
          />
        </label>
        <label className="image-upload-label btn-ghost btn-tiny" title="Attach video (MP4/WebM)" style={allowVideos ? {} : { display: 'none' }}>
          🎬
          <input
            type="file"
            accept="video/mp4,video/webm"
            onChange={handleVideoChange}
            style={{ display: 'none' }}
          />
        </label>
        <div className="composer-actions">
          {onCancel && <button type="button" className="btn-ghost btn-tiny" onClick={onCancel}>Cancel</button>}
          <button type="submit" className={`btn-tiny ${sage ? 'btn-sage' : 'btn-primary'}`} disabled={submitting}>
            {submitting ? 'Posting…' : sage ? 'Post (sage)' : 'Reply ↑'}
          </button>
        </div>
      </div>
    </form>
  )
}

// ── Single reply (second level) ───────────────────────────────────────────────
function Reply({ reply, threadId, onReact, onReplyToReply }) {
  const { user } = useAuth()

  const handleReplyClick = () => {
    onReplyToReply(`@${reply.author?.username || 'Anonymous'} `)
  }

  return (
    <div className="fb-reply">
      <div className="fb-avatar fb-avatar-sm">
        {reply.author?.avatar
          ? <img src={reply.author.avatar} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
          : (reply.author?.display_name || reply.author?.username || '?')[0].toUpperCase()
        }
      </div>
      <div className="fb-reply-bubble">
        <div className="fb-reply-header">
          <UserLink author={reply.author} />
          <BadgeDisplay badge={reply.author?.display_badge} />
          {reply.author?.is_premium && !reply.author?.display_badge && <span className="premium-badge">PRO</span>}
          {reply.sage && <span className="sage-indicator">sage</span>}
          <span className="fb-time">{timeAgo(reply.created_at)}</span>
          {reply.is_hidden && user && reply.author?.id === user.id && <HiddenBadge />}
        </div>
        <MarkdownBody text={reply.body} />
        <div className="fb-actions">
          <ReactionBar reactions={reply.reactions || []} onReact={emoji => onReact(reply.id, emoji)} />
          {user && (
            <button className="fb-action-btn" onClick={handleReplyClick}>
              <CornerDownRight size={12} /> Reply
            </button>
          )}
          <ReportButton threadId={threadId} postId={reply.id} compact />
        </div>
      </div>
    </div>
  )
}

// ── Top-level comment ─────────────────────────────────────────────────────────
function Comment({ post, threadId, onReact, onNewReply, allowImages = true, allowVideos = true, allowVideoSound = true, commentsDisabled = false, isNew = false }) {
  const { user } = useAuth()
  const { allow_post_editing, post_edit_window_seconds } = useSiteSettings()
  const [currentPost, setCurrentPost] = useState(post)
  const [editing, setEditing] = useState(false)
  const [editBody, setEditBody] = useState('')
  const [editError, setEditError] = useState(null)
  const [editSaving, setEditSaving] = useState(false)
  const [secondsLeft, setSecondsLeft] = useState(null)
  const selfRef = useRef(null)

  useEffect(() => {
    if (isNew && selfRef.current) {
      selfRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [isNew])
  const [showReplies, setShowReplies] = useState(false)
  const [showComposer, setShowComposer] = useState(false)
  const [composerInitial, setComposerInitial] = useState('')
  const [replies, setReplies] = useState(post.replies || [])

  const handleNewReply = reply => {
    setReplies(r => [...r, reply])
    setShowReplies(true)
    setShowComposer(false)
    setComposerInitial('')
    onNewReply?.()
  }

  const handleReplyToReply = mention => {
    setComposerInitial(mention)
    setShowComposer(true)
  }

  const [editStart, setEditStart] = useState(null)

  // Countdown timer for edit window
  const isOwn = user && currentPost.author?.id === user.id
  const canEdit = allow_post_editing && isOwn

  useEffect(() => {
    if (!canEdit || post_edit_window_seconds === 0) return
    const updateTimer = () => {
      // If user has started editing, count from when they opened the editor
      const base = editStart || new Date(currentPost.created_at).getTime()
      const age = (Date.now() - base) / 1000
      const left = Math.max(0, post_edit_window_seconds - age)
      setSecondsLeft(Math.ceil(left))
    }
    updateTimer()
    const interval = setInterval(updateTimer, 1000)
    return () => clearInterval(interval)
  }, [canEdit, post_edit_window_seconds, currentPost.created_at, editStart])

  const withinWindow = post_edit_window_seconds === 0 || (secondsLeft !== null && secondsLeft > 0)

  const startEdit = () => {
    setEditBody(currentPost.body)
    setEditError(null)
    setEditing(true)
  }

  const handleEditChange = val => {
    // Restart the window from now whenever the user makes a change
    setEditStart(Date.now())
    setEditBody(val)
  }

  const cancelEdit = () => {
    setEditing(false)
    setEditError(null)
  }

  const saveEdit = async () => {
    if (!editBody.trim()) return
    setEditSaving(true)
    setEditError(null)
    try {
      const { data } = await api.patch(`/threads/${threadId}/posts/${currentPost.id}/edit/`, { body: editBody.trim() })
      setCurrentPost(data)
      setEditing(false)
    } catch (err) {
      setEditError(err.response?.data?.error || 'Could not save edit.')
    } finally {
      setEditSaving(false)
    }
  }

  return (
    <div className="fb-comment" ref={selfRef}>
      <div className="fb-avatar">
        {currentPost.author?.avatar
          ? <img src={currentPost.author.avatar} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
          : (currentPost.author?.display_name || currentPost.author?.username || '?')[0].toUpperCase()
        }
      </div>
      <div className="fb-comment-main">
        <div className="fb-comment-bubble">
          <div className="fb-comment-header">
            <UserLink author={currentPost.author} />
            <BadgeDisplay badge={currentPost.author?.display_badge} />
            {currentPost.author?.is_premium && !currentPost.author?.display_badge && <span className="premium-badge">PRO</span>}
            {currentPost.post_number && <span className="post-number">#{currentPost.post_number}</span>}
            {currentPost.sage && <span className="sage-indicator">sage</span>}
            <span className="fb-time">{timeAgo(currentPost.created_at)}</span>
            {currentPost.edited_at && (
              <span className="edited-badge" title={`Edited ${timeAgo(currentPost.edited_at)}`}>edited</span>
            )}
            {currentPost.is_hidden && user && currentPost.author?.id === user.id && <HiddenBadge />}
          </div>
          {currentPost.author?.tagline && (
            <div className="author-tagline">{currentPost.author.tagline}</div>
          )}
          {currentPost.image && <img src={currentPost.image} alt="" className="post-image" />}
          {currentPost.video && (
            <VideoPlayer
              src={currentPost.video}
              thumbnail={currentPost.video_thumbnail || undefined}
              duration={currentPost.video_duration}
              soundAllowed={allowVideoSound}
            />
          )}
          {editing ? (
            <div className="edit-composer">
              <textarea
                className="edit-textarea"
                value={editBody}
                onChange={e => handleEditChange(e.target.value)}
                autoFocus
                disabled={editSaving}
              />
              {editError && <div className="form-error">{editError}</div>}
              <div className="edit-actions">
                {post_edit_window_seconds > 0 && secondsLeft !== null && (
                  <span className="edit-timer" style={{ color: secondsLeft < 15 ? 'var(--danger)' : 'var(--muted)' }}>
                    {secondsLeft}s
                  </span>
                )}
                <button className="btn-ghost btn-tiny" onClick={cancelEdit} disabled={editSaving}>Cancel</button>
                <button className="btn-primary btn-tiny" onClick={saveEdit} disabled={editSaving || !editBody.trim()}>
                  {editSaving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </div>
          ) : (
            <MarkdownBody text={currentPost.body} />
          )}
        </div>

        <div className="fb-comment-footer">
          <ReactionBar reactions={currentPost.reactions || []} onReact={emoji => onReact(currentPost.id, emoji)} />
          {canEdit && withinWindow && !editing && (
            <button className="fb-action-btn" onClick={startEdit} title={post_edit_window_seconds > 0 ? `${secondsLeft}s to edit` : 'Edit post'}>
              ✏️ Edit{post_edit_window_seconds > 0 && secondsLeft !== null ? ` (${secondsLeft}s)` : ''}
            </button>
          )}
          {user && !commentsDisabled && (
            <button className="fb-action-btn" onClick={() => { setComposerInitial(''); setShowComposer(v => !v) }}>
              <CornerDownRight size={12} /> Reply
            </button>
          )}
          {replies.length > 0 && (
            <button className="fb-action-btn" onClick={() => setShowReplies(v => !v)}>
              {showReplies ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {replies.length} {replies.length === 1 ? 'reply' : 'replies'}
            </button>
          )}
          <ReportButton threadId={threadId} postId={currentPost.id} compact />
        </div>

        {showReplies && replies.length > 0 && (
          <div className="fb-replies">
            {replies.map(r => (
              <Reply
                key={r.id}
                reply={r}
                threadId={threadId}
                onReact={onReact}
                onReplyToReply={handleReplyToReply}
              />
            ))}
          </div>
        )}

        {showComposer && (
          <ReplyComposer
            threadId={threadId}
            parentId={post.id}
            onPosted={handleNewReply}
            onCancel={() => { setShowComposer(false); setComposerInitial('') }}
            initialBody={composerInitial}
            showSage={false}
            allowImages={allowImages}
            allowVideos={allowVideos}
            allowVideoSound={allowVideoSound}
          />
        )}
      </div>
    </div>
  )
}

// ── Thread Detail page ────────────────────────────────────────────────────────
export default function ThreadDetail() {
  const { id } = useParams()
  const { user, permissions } = useAuth()
  const { allow_image_uploads, allow_video_uploads } = useSiteSettings()
  const { refresh: refreshBell } = useNotifications()
  const [thread, setThread] = useState(null)
  const [posts, setPosts] = useState([])
  const [newPostId, setNewPostId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [nsfwGate, setNsfwGate] = useState(false)
  const [watching, setWatching] = useState(false)
  const [watcherCount, setWatcherCount] = useState(0)

  // canPin is computed once thread is loaded — needs board_slug and community info
  const canPin = (() => {
    if (!user || !thread) return false
    // Site role check
    if (permissions?.capabilities?.can_pin_threads) {
      if (permissions.is_admin_tier) return true
      if (permissions.assigned_boards?.includes(thread.board_slug)) return true
    }
    return false
  })()

  const handlePin = async () => {
    try {
      const { data } = await api.post(`/threads/${id}/pin/`)
      setThread(t => ({ ...t, is_pinned: data.is_pinned, comments_disabled: data.comments_disabled }))
    } catch { alert('Could not pin thread.') }
  }

  const handleUnpin = async () => {
    try {
      const { data } = await api.post(`/threads/${id}/unpin/`)
      setThread(t => ({ ...t, is_pinned: data.is_pinned, comments_disabled: data.comments_disabled }))
    } catch { alert('Could not unpin thread.') }
  }

  const handleToggleComments = async () => {
    try {
      const { data } = await api.post(`/threads/${id}/toggle-comments/`, {
        disabled: !thread.comments_disabled
      })
      setThread(t => ({ ...t, comments_disabled: data.comments_disabled }))
    } catch { alert('Could not toggle comments.') }
  }

  const loadThread = () => {
    setLoading(true)
    return api.get(`/threads/${id}/`).then(r => {
      setThread(r.data)
      setPosts(r.data.posts || [])
      setWatcherCount(r.data.watcher_count || 0)
      setNsfwGate(false)
      setLoading(false)
    }).catch(err => {
      if (err.response?.data?.nsfw_gate) {
        setNsfwGate(true)
      }
      setLoading(false)
    })
  }

  useEffect(() => { loadThread() }, [id])

  // Fetch watch state for authenticated users
  useEffect(() => {
    if (!user) return
    api.get(`/me/watched/`).then(r => {
      const watched = r.data.find(w => w.thread_id === id)
      setWatching(!!watched)
    }).catch(() => {})
  }, [id, user])

  // Mark thread as seen once it's loaded — clears unread count and refreshes bell
  useEffect(() => {
    if (!user || !thread) return
    api.post(`/threads/${id}/mark-seen/`)
      .then(() => refreshBell())
      .catch(() => {})
  }, [id, thread?.id, user?.id, refreshBell])

  const handleReact = async (postId, emoji) => {
    await api.post(`/threads/${id}/posts/${postId}/react/`, { emoji })
    api.get(`/threads/${id}/`).then(r => setPosts(r.data.posts || []))
  }

  const handleThreadReact = async emoji => {
    await api.post(`/threads/${id}/react/`, { emoji })
    api.get(`/threads/${id}/`).then(r => setThread(r.data))
  }

  const handleWatch = async () => {
    try {
      const r = await api.post(`/threads/${id}/watch/`)
      setWatching(r.data.watching)
      setWatcherCount(r.data.watcher_count)
    } catch {}
  }

  const handleNewPost = post => {
    setPosts(p => [...p, { ...post, replies: [] }])
    setThread(t => ({ ...t, reply_count: t.reply_count + 1 }))
    setNewPostId(post.id)
  }

  if (loading) return <div className="loader">Loading thread…</div>
  if (nsfwGate) {
    return (
      <div className="page-layout">
        <AgeGate onConfirm={loadThread} />
      </div>
    )
  }
  if (!thread) return <div className="loader">Thread not found.</div>

  return (
    <div className="page-layout">
      <article className="thread-op">
        <div className="thread-op-header">
          <Link to={`/boards/${thread.board_slug}`} className="board-tag">/{thread.board_slug}/</Link>
          {thread.is_pinned && <span className="pinned-badge">📌 Pinned</span>}
          {thread.author?.avatar && (
            <img src={thread.author.avatar} alt="" style={{ width: '24px', height: '24px', borderRadius: '50%', objectFit: 'cover', verticalAlign: 'middle' }} />
          )}
          <UserLink author={thread.author} />
          <BadgeDisplay badge={thread.author?.display_badge} />
          <span className="fb-time">{timeAgo(thread.created_at)}</span>
          {thread.is_hidden && user && thread.author?.id === user.id && <HiddenBadge />}
        </div>
        {thread.author?.tagline && (
          <div className="author-tagline">{thread.author.tagline}</div>
        )}
        <h1 className="thread-op-title">{thread.title}</h1>
        {thread.image && <img src={thread.image} alt="" className="thread-image-full" />}
        {thread.video && (
          <VideoPlayer
            src={thread.video}
            thumbnail={thread.video_thumbnail || undefined}
            duration={thread.video_duration}
            soundAllowed={thread.allow_video_sound !== false}
          />
        )}
        <MarkdownBody text={thread.body} className="fb-body markdown-body thread-op-body" />
        <div className="thread-op-footer">
          <ReactionBar reactions={thread.reactions || []} onReact={handleThreadReact} />
          <span className="thread-stats-inline">
            <MessageSquare size={13} /> {thread.reply_count} comments
          </span>
          {user && (
            <button
              className={`btn-ghost btn-tiny watch-btn${watching ? ' watching' : ''}`}
              onClick={handleWatch}
              title={watching ? 'Unwatch thread' : 'Watch thread — get notified of replies'}
            >
              {watching ? <BellOff size={13} /> : <Bell size={13} />}
              {watching ? 'Unwatch' : 'Watch'}
              {watcherCount > 0 && <span className="watch-count">{watcherCount}</span>}
            </button>
          )}
          {canPin && (
            <>
              {thread.is_pinned
                ? <button className="btn-ghost btn-tiny" onClick={handleUnpin} title="Unpin thread"><PinOff size={13} /> Unpin</button>
                : <button className="btn-ghost btn-tiny" onClick={handlePin} title="Pin thread"><Pin size={13} /> Pin</button>
              }
              <button
                className="btn-ghost btn-tiny"
                onClick={handleToggleComments}
                title={thread.comments_disabled ? 'Enable comments' : 'Disable comments'}
              >
                {thread.comments_disabled ? <MessageSquareMore size={13} /> : <MessageSquareOff size={13} />}
                {thread.comments_disabled ? 'Enable comments' : 'Disable comments'}
              </button>
            </>
          )}
          <ReportButton threadId={id} />
        </div>
      </article>

      {user && !thread.is_locked && !thread.comments_disabled && (
        <ReplyComposer
          threadId={id}
          parentId={null}
          onPosted={handleNewPost}
          placeholder="Write a comment…"
          showSage={true}
          allowImages={thread.allow_images !== false && (allow_image_uploads || !!user?.can_post_media)}
          allowVideos={thread.allow_videos !== false && (allow_video_uploads || !!user?.can_post_media)}
        />
      )}
      {thread.is_locked && <p className="muted text-center">🔒 This thread is locked — post limit reached.</p>}
      {thread.comments_disabled && <p className="muted text-center">💬 Comments are disabled on this thread.</p>}
      {!user && !thread.comments_disabled && <p className="muted text-center">Log in to comment.</p>}

      <div className="fb-comments-section">
        <h2 className="section-label">
          <MessageSquare size={14} /> {posts.length} comments
        </h2>
        {posts.map(p => (
          <Comment
            key={p.id}
            post={p}
            threadId={id}
            onReact={handleReact}
            onNewReply={() => setThread(t => ({ ...t, reply_count: t.reply_count + 1 }))}
            allowImages={thread.allow_images !== false && (allow_image_uploads || !!user?.can_post_media)}
            allowVideos={thread.allow_videos !== false && (allow_video_uploads || !!user?.can_post_media)}
            allowVideoSound={thread.allow_video_sound !== false}
            commentsDisabled={!!thread.comments_disabled}
            isNew={p.id === newPostId}
          />
        ))}
        {posts.length === 0 && <p className="empty-state">No comments yet. Be the first.</p>}
      </div>
    </div>
  )
}

function MentionText({ text }) {
  if (!text) return null
  const parts = text.split(/(@\w+)/g)
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith('@')
          ? <span key={i} className="mention">{part}</span>
          : part
      )}
    </>
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
