/**
 * VideoPlayer — HTML5 video player for short user-uploaded clips.
 *
 * Behaviour:
 *   - Shows thumbnail as poster until the user interacts
 *   - Autoplay muted on hover, unmute on click (standard imageboard UX)
 *   - Loop enabled — short clips look better looping
 *   - Controls always visible
 *   - Duration badge in bottom-right of thumbnail
 *   - Lazy: video src not loaded until the component is visible (IntersectionObserver)
 *
 * Props:
 *   src           string   — URL to the video file (MP4 or WebM)
 *   thumbnail     string   — URL to the WebP thumbnail (optional)
 *   duration      number   — seconds (optional, shown as badge)
 *   compact       bool     — true = thumbnail-only in catalog/card view, click to expand
 */
import { useRef, useState, useEffect } from 'react'

function formatDuration(seconds) {
  if (!seconds) return ''
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function VideoPlayer({ src, thumbnail, duration, compact = false, soundAllowed = true }) {
  const videoRef  = useRef(null)
  const wrapRef   = useRef(null)
  const [expanded, setExpanded] = useState(!compact)
  const [loaded,   setLoaded]   = useState(!compact)

  // Lazy-load: only set src when the element enters the viewport
  useEffect(() => {
    if (!expanded || !wrapRef.current) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setLoaded(true) },
      { threshold: 0.1 }
    )
    observer.observe(wrapRef.current)
    return () => observer.disconnect()
  }, [expanded])

  const handleMouseEnter = () => {
    if (videoRef.current) {
      videoRef.current.muted = true
      videoRef.current.play().catch(() => {})
    }
  }

  const handleMouseLeave = () => {
    if (videoRef.current) {
      videoRef.current.pause()
      videoRef.current.currentTime = 0
    }
  }

  const handleClick = () => {
    if (compact && !expanded) {
      setExpanded(true)
      setLoaded(true)
      return
    }
    // Only toggle mute if sound is permitted on this board
    if (soundAllowed && videoRef.current) {
      videoRef.current.muted = !videoRef.current.muted
    }
  }

  // Compact mode: show thumbnail with play icon, expand on click
  if (compact && !expanded) {
    return (
      <div
        onClick={handleClick}
        style={{
          position: 'relative',
          display: 'inline-block',
          cursor: 'pointer',
          borderRadius: 4,
          overflow: 'hidden',
          maxWidth: 320,
        }}
      >
        {thumbnail ? (
          <img src={thumbnail} alt="Video thumbnail" style={{ display: 'block', maxWidth: '100%' }} />
        ) : (
          <div style={{
            width: 320, height: 180,
            background: '#111',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <span style={{ color: '#888', fontSize: 48 }}>▶</span>
          </div>
        )}
        {/* Play icon overlay */}
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(0,0,0,0.3)',
        }}>
          <span style={{ fontSize: 40, color: 'white', textShadow: '0 1px 4px rgba(0,0,0,0.8)' }}>▶</span>
        </div>
        {/* Duration badge */}
        {duration && (
          <div style={{
            position: 'absolute', bottom: 6, right: 6,
            background: 'rgba(0,0,0,0.75)',
            color: 'white', fontSize: 11, padding: '1px 5px',
            borderRadius: 3, fontFamily: 'monospace',
          }}>
            {formatDuration(duration)}
          </div>
        )}
      </div>
    )
  }

  return (
    <div
      ref={wrapRef}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
      style={{ display: 'inline-block', maxWidth: '100%', cursor: 'pointer' }}
    >
      <video
        ref={videoRef}
        src={loaded ? src : undefined}
        poster={thumbnail || undefined}
        loop
        muted
        controls={soundAllowed}  // hide controls entirely when no sound — just play/pause via hover
        playsInline
        style={{
          display: 'block',
          maxWidth: '100%',
          maxHeight: 480,
          borderRadius: 4,
          background: '#111',
        }}
      />
      {!soundAllowed && (
        <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>🔇 Silent</div>
      )}
      {duration && (
        <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>
          {formatDuration(duration)}
        </div>
      )}
    </div>
  )
}
