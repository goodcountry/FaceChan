import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import api from '../api/client'
import MarkdownBody from '../components/MarkdownBody'

export default function SitePage() {
  const { slug } = useParams()
  const [page, setPage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    setLoading(true)
    setNotFound(false)
    api.get(`/pages/${slug}/`)
      .then(r => { setPage(r.data); setLoading(false) })
      .catch(e => {
        setLoading(false)
        if (e.response?.status === 404) setNotFound(true)
      })
  }, [slug])

  if (loading) return <div className="loader">Loading…</div>

  if (notFound) return (
    <div className="page-layout">
      <div className="empty-state">
        <p>Page not found.</p>
        <Link to="/">← Home</Link>
      </div>
    </div>
  )

  return (
    <div className="page-layout">
      <article className="site-page-article">
        <h1 className="site-page-title">{page.title}</h1>
        <MarkdownBody text={page.content} className="site-page-body markdown-body" />
      </article>
    </div>
  )
}
