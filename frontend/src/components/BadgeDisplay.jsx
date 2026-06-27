export default function BadgeDisplay({ badge }) {
  if (!badge) return null
  const badges = {
    founder: { label: '★ Founder', className: 'badge-founder' },
    mod:     { label: '⚑ Mod',     className: 'badge-mod' },
    premium: { label: '◆ PRO',     className: 'badge-premium' },
  }
  const b = badges[badge]
  if (!b) return null
  return <span className={`user-badge ${b.className}`}>{b.label}</span>
}
