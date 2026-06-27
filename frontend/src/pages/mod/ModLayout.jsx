import { Link, useLocation, Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { ShieldCheck, Inbox, Archive, Users2, Crown, Wrench, Globe, FileText } from 'lucide-react'

export default function ModLayout({ children }) {
  const { user, permissions, isStaff } = useAuth()
  const location = useLocation()

  if (!user) return <Navigate to="/login" replace />

  // permissions === null can mean "still loading" OR "fetch failed/no role" —
  // isStaff being false after a load attempt is the real signal here.
  if (permissions === null) {
    return <div className="loader">Checking staff access…</div>
  }

  if (!isStaff) {
    return (
      <div className="mod-denied">
        <ShieldCheck size={32} />
        <h2>Staff access required</h2>
        <p>Your account doesn't hold a staff role on this instance.</p>
        <Link to="/" className="btn-ghost">Back to feed</Link>
      </div>
    )
  }

  const isAdmin = permissions.is_admin_tier

  const navItems = [
    { to: '/mod', label: 'Report queue', icon: Inbox, match: '/mod' },
    ...(isAdmin ? [{ to: '/mod/quarantine', label: 'Quarantine', icon: Archive, match: '/mod/quarantine' }] : []),
    ...(permissions.capabilities?.can_suspend || permissions.capabilities?.can_ban
      ? [{ to: '/mod/users', label: 'User actions', icon: Users2, match: '/mod/users' }]
      : []),
    ...(isAdmin ? [{ to: '/mod/federation', label: 'Federation', icon: Globe, match: '/mod/federation' }] : []),
    ...(permissions.capabilities?.can_manage_pages
      ? [{ to: '/mod/pages', label: 'Pages', icon: FileText, match: '/mod/pages' }]
      : []),
  ]

  return (
    <div className="mod-shell">
      <aside className="mod-sidebar">
        <div className="mod-sidebar-header">
          {isAdmin ? <Crown size={16} /> : <Wrench size={16} />}
          <span>{permissions.role}</span>
        </div>
        <nav className="mod-sidebar-nav">
          {navItems.map(item => (
            <Link
              key={item.to}
              to={item.to}
              className={`mod-nav-link ${location.pathname === item.match ? 'active' : ''}`}
            >
              <item.icon size={14} /> {item.label}
            </Link>
          ))}
        </nav>
        {!isAdmin && permissions.assigned_boards?.length > 0 && (
          <div className="mod-sidebar-boards">
            <span className="mod-sidebar-boards-label">Your boards</span>
            {permissions.assigned_boards.map(slug => (
              <span key={slug} className="mod-board-tag">/{slug}/</span>
            ))}
          </div>
        )}
      </aside>
      <div className="mod-content">{children}</div>
    </div>
  )
}
