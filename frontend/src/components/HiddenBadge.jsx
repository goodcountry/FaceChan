import { EyeOff } from 'lucide-react'

// Hide (tier 1) stays visible to its own author by design — see
// core/permissions.py and COMPLIANCE.md. This badge makes that visible
// rather than silent: the author should know their content is currently
// hidden from everyone else. Quarantine (tier 2) is excluded from the
// author too at the query level, so there's no equivalent case to show here.
export default function HiddenBadge() {
  return (
    <span className="hidden-by-mod-badge" title="Only visible to you — hidden from everyone else by moderation">
      <EyeOff size={11} /> Hidden by moderation
    </span>
  )
}
