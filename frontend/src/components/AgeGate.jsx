import { ShieldAlert } from 'lucide-react'
import { useSiteSettings } from '../context/SiteSettingsContext'

/**
 * Full-card age gate shown in place of NSFW board content until the viewer
 * confirms. Confirmation is stored in localStorage (no server-side session
 * for logged-out users on this anonymous-first platform) and sent on every
 * API request afterwards via the X-Age-Verified header — see api/client.js.
 */
export default function AgeGate({ onConfirm }) {
  const { minimum_age } = useSiteSettings()

  const confirm = () => {
    localStorage.setItem('age_verified', 'true')
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

/** Whether the viewer has already passed the gate in this browser. */
export function isAgeVerified() {
  return localStorage.getItem('age_verified') === 'true'
}
