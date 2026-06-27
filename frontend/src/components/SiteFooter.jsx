import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useSiteSettings } from '../context/SiteSettingsContext'
import api from '../api/client'

export default function SiteFooter() {
  const { site_name, publish_transparency_info } = useSiteSettings()
  const [pages, setPages] = useState([])

  useEffect(() => {
    api.get('/pages/').then(r => setPages(r.data)).catch(() => {})
  }, [])

  return (
    <footer className="site-footer">
      <div className="site-footer-links">
        {pages.map(p => (
          <Link key={p.slug} to={`/pages/${p.slug}/`} className="muted">{p.title}</Link>
        ))}
        {publish_transparency_info && (
          <Link to="/transparency" className="muted">Transparency</Link>
        )}
      </div>
      <span className="muted site-footer-copy">{site_name} · MIT licensed · No ads · No tracking</span>
    </footer>
  )
}
