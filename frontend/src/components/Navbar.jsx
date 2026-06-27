import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useSiteSettings } from '../context/SiteSettingsContext'
import { useNotifications } from '../context/NotificationContext'
import { useTheme } from '../context/ThemeContext'
import { Hash, Home, Users, ShieldCheck, Bell, Sun, Moon } from 'lucide-react'

export default function Navbar() {
  const { user, isStaff } = useAuth()
  const { site_name, registration_open, enable_communities } = useSiteSettings()
  const { unread: bellCount } = useNotifications()
  const { theme, toggle } = useTheme()

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">
        <Hash size={20} />
        <span>{site_name}</span>
      </Link>
      <div className="navbar-links">
        <Link to="/feed"><Home size={16} /><span className="nav-label"> Feed</span></Link>
        <Link to="/boards"><Hash size={16} /><span className="nav-label"> Boards</span></Link>
        {enable_communities !== false && (
          <Link to="/communities"><Users size={16} /><span className="nav-label"> Communities</span></Link>
        )}
        {user && (
          <Link to="/feed" state={{ tab: 'watched' }} className={`navbar-bell${bellCount > 0 ? ' has-unread' : ''}`} title="Watched threads">
            <Bell size={16} />
            {bellCount > 0 && <span className="bell-badge">{bellCount > 99 ? '99+' : bellCount}</span>}
          </Link>
        )}
        {isStaff && (
          <Link to="/mod" className="navbar-mod-link"><ShieldCheck size={16} /><span className="nav-label"> Mod</span></Link>
        )}
      </div>
      <div className="navbar-auth">
        <button
          className="theme-toggle"
          onClick={() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })}
          title="Jump to footer"
          aria-label="Jump to footer"
        >
          ↓
        </button>
        <button
          className="theme-toggle"
          onClick={toggle}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label="Toggle colour theme"
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        {user ? (
          <Link to="/profile" className="navbar-user">
            <div className="navbar-avatar">{(user.display_name || user.username)[0].toUpperCase()}</div>
            <span className="username-tag">{user.display_name || user.username}</span>
            {user.is_premium && <span className="premium-badge">PRO</span>}
          </Link>
        ) : (
          <>
            <Link to="/login" className="btn-ghost">Log in</Link>
            {registration_open !== false && (
              <Link to="/register" className="btn-primary">Sign up</Link>
            )}
          </>
        )}
      </div>
    </nav>
  )
}
