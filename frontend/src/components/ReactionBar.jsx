import { useState, useEffect, useRef } from 'react'
import { useAuth } from '../context/AuthContext'

const EMOJIS = ['👍','❤️','😂','😮','😢','😡','🔥']

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 600px)').matches)
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 600px)')
    const handler = e => setIsMobile(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])
  return isMobile
}

export default function ReactionBar({ reactions = [], onReact, readOnly = false }) {
  const { user } = useAuth()
  const isMobile = useIsMobile()
  const [pickerOpen, setPickerOpen] = useState(false)
  const wrapperRef = useRef(null)

  // Close picker on outside click (mobile tap-to-toggle)
  useEffect(() => {
    if (!isMobile || !pickerOpen) return
    const handler = e => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setPickerOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    document.addEventListener('touchstart', handler)
    return () => {
      document.removeEventListener('mousedown', handler)
      document.removeEventListener('touchstart', handler)
    }
  }, [isMobile, pickerOpen])

  const counts = reactions.reduce((acc, r) => {
    acc[r.emoji] = { count: r.count, reacted: r.reacted }
    return acc
  }, {})

  const activeEmojis = EMOJIS.filter(e => counts[e]?.count > 0)

  const handleReact = emoji => {
    if (user) onReact?.(emoji)
    setPickerOpen(false)
  }

  // Read-only mode — just show reaction counts, no picker
  if (readOnly) {
    return (
      <div className="reaction-bar reaction-bar-compact">
        {activeEmojis.map(emoji => {
          const info = counts[emoji]
          return (
            <span key={emoji} className="reaction-btn" style={{ cursor: 'default' }}>
              {emoji}
              <span className="reaction-count">{info.count}</span>
            </span>
          )
        })}
      </div>
    )
  }

  return (
    <div className="reaction-bar reaction-bar-compact">
      {activeEmojis.map(emoji => {
        const info = counts[emoji]
        return (
          <button
            key={emoji}
            className={`reaction-btn ${info?.reacted ? 'reacted' : ''}`}
            onClick={() => user && onReact?.(emoji)}
            title={user ? `React with ${emoji}` : 'Log in to react'}
          >
            {emoji}
            <span className="reaction-count">{info.count}</span>
          </button>
        )
      })}
      {/* + React picker — hover on desktop, tap to toggle on mobile */}
      <div className="reaction-picker-wrapper" ref={wrapperRef}>
        <button
          className="reaction-btn reaction-add-btn"
          onClick={() => isMobile && setPickerOpen(o => !o)}
          title="Add reaction"
        >
          + React
        </button>
        {(!isMobile || pickerOpen) && (
          <div className={`reaction-picker${isMobile ? ' reaction-picker-open' : ''}`}>
            {EMOJIS.map(emoji => (
              <button
                key={emoji}
                className="reaction-picker-btn"
                onClick={() => handleReact(emoji)}
              >
                {emoji}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
