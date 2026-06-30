import { ShieldAlert } from 'lucide-react'
import { useSiteSettings } from '../context/SiteSettingsContext'
import { useAuth } from '../context/AuthContext'
import api from '../api/client'

/**
 * Full-card age gate shown in place of NSFW board content until the viewer
 * confirms.
 *
 * Logged-in users: confirmation is saved server-side on the account via
 * POST /api/me/age-confirm/, so it carries across devices/browsers on any
 * future login — see User.age_verified.
 *
 * Logged-out users: no account exists to persist against, so confirmation
 * is stored in localStorage only and sent on every API request afterwards
 * via the X-Age-Verified header (see api/client.js). This resets on a fresh
 * browser/session by design — see COMPLIANCE.md.
 */
export default function AgeGate({ onConfirm }) {
  const { minimum_age } = useSiteSettings()
  const { user, updateUser } = useAuth()

  const confirm = async () => {
    if (user) {
      try {
        await api.post('/me/age-confirm/')
        updateUser({ age_verified: true })
      } catch {
        // If the request fails, don't claim success — leave the gate up
        // rather than silently falling through to an unconfirmed state.
        return
      }
    } else {
      localStorage.setItem('age_verified', 'true')
    }
    onConfirm?.()
  }

  return (
    <div className="age-gate">
      <ShieldAlert size={32} className="age-gate-icon" />
      <h2>Age-restricted board</h2>
      <p className="muted">
        This board is marked as adult content. You must be at least{' '}
        {minimum_age || 18} years old to view it.
      </p>
      <div className="age-gate-actions">
        <button className="btn-primary" onClick={confirm}>
          I am {minimum_age || 18} or older — continue
        </button>
      </div>
    </div>
  )
}

/**
 * Whether the viewer has already passed the gate.
 * Logged-in users: checked against the persisted account flag.
 * Logged-out users: checked against the client-side localStorage flag.
 */
export function isAgeVerified(user) {
  if (user) return !!user.age_verified
  return localStorage.getItem('age_verified') === 'true'
}
