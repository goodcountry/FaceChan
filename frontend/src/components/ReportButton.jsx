import { useState } from 'react'
import { Flag } from 'lucide-react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useSiteSettings } from '../context/SiteSettingsContext'

const REASONS = [
  { value: 'spam', label: 'Spam or advertising' },
  { value: 'harassment', label: 'Harassment or bullying' },
  { value: 'illegal', label: 'Illegal content' },
  { value: 'csam', label: 'Child sexual abuse material' },
  { value: 'violence', label: 'Violence or graphic content' },
  { value: 'hate', label: 'Hate speech' },
  { value: 'other', label: 'Other' },
]

/**
 * Report control for a thread or a post. Pass exactly one of `threadId` or
 * `postId` (+ its parent `threadId` for posts, since the API nests posts
 * under threads).
 */
export default function ReportButton({ threadId, postId, compact = false }) {
  const { user } = useAuth()
  const settings = useSiteSettings()
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [details, setDetails] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null) // { ok: bool, message: string }

  if (!user || !settings.enable_content_reporting) return null

  const endpoint = postId
    ? `/threads/${threadId}/posts/${postId}/report/`
    : `/threads/${threadId}/report/`

  const submit = async e => {
    e.preventDefault()
    if (!reason) return
    setSubmitting(true)
    try {
      await api.post(endpoint, { reason, details })
      setResult({ ok: true, message: 'Report submitted. A moderator will review it.' })
    } catch (err) {
      const msg = err.response?.data?.error || 'Could not submit report.'
      setResult({ ok: false, message: msg })
    } finally {
      setSubmitting(false)
    }
  }

  const close = () => {
    setOpen(false)
    setReason('')
    setDetails('')
    setResult(null)
  }

  return (
    <div className="report-control">
      <button
        type="button"
        className={compact ? 'fb-action-btn' : 'btn-ghost btn-tiny'}
        onClick={() => setOpen(v => !v)}
        title="Report this content"
      >
        <Flag size={compact ? 12 : 13} /> Report
      </button>

      {open && (
        <div className="report-popover">
          {result ? (
            <div className={`report-result ${result.ok ? 'report-result-ok' : 'report-result-error'}`}>
              <p>{result.message}</p>
              <button type="button" className="btn-ghost btn-tiny" onClick={close}>Close</button>
            </div>
          ) : (
            <form onSubmit={submit} className="report-form">
              <label className="report-form-label">Why are you reporting this?</label>
              <select value={reason} onChange={e => setReason(e.target.value)} required>
                <option value="" disabled>Select a reason…</option>
                {REASONS.map(r => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
              <textarea
                placeholder="Additional details (optional)"
                value={details}
                onChange={e => setDetails(e.target.value)}
                rows={2}
                maxLength={1000}
              />
              <div className="report-form-actions">
                <button type="button" className="btn-ghost btn-tiny" onClick={close}>Cancel</button>
                <button type="submit" className="btn-tiny btn-primary" disabled={submitting || !reason}>
                  {submitting ? 'Submitting…' : 'Submit report'}
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  )
}
