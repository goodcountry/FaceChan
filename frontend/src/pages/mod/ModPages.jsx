import { useState, useEffect } from 'react'
import api from '../../api/client'
import MarkdownBody from '../../components/MarkdownBody'

export default function ModPages() {
  const [pages, setPages] = useState([])
  const [selected, setSelected] = useState(null)
  const [body, setBody] = useState('')
  const [title, setTitle] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)
  const [preview, setPreview] = useState(false)

  useEffect(() => {
    // Fetch all footer pages
    api.get('/pages/').then(r => {
      setPages(r.data)
      if (r.data.length > 0) selectPage(r.data[0].slug)
    })
  }, [])

  const selectPage = slug => {
    api.get(`/pages/${slug}/`).then(r => {
      setSelected(r.data)
      setTitle(r.data.title)
      setBody(r.data.content)
      setSaved(false)
      setError(null)
      setPreview(false)
    })
  }

  const save = async () => {
    if (!selected) return
    setSaving(true)
    setSaved(false)
    setError(null)
    try {
      await api.patch(`/pages/${selected.slug}/edit/`, { title, content: body })
      setSaved(true)
      // Refresh page list in case title changed
      const r = await api.get('/pages/')
      setPages(r.data)
    } catch (e) {
      setError(e.response?.data?.error || 'Could not save.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mod-pages">
      <div className="mod-pages-sidebar">
        <h3>Site Pages</h3>
        {pages.map(p => (
          <button
            key={p.slug}
            className={`mod-pages-tab${selected?.slug === p.slug ? ' active' : ''}`}
            onClick={() => selectPage(p.slug)}
          >
            {p.title}
          </button>
        ))}
      </div>

      <div className="mod-pages-editor">
        {selected ? (
          <>
            <div className="mod-pages-toolbar">
              <input
                className="mod-pages-title-input"
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="Page title"
                autoComplete="off"
              />
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button
                  className={`btn-ghost btn-tiny${preview ? ' active' : ''}`}
                  onClick={() => setPreview(v => !v)}
                >
                  {preview ? 'Edit' : 'Preview'}
                </button>
                <button
                  className="btn-primary"
                  onClick={save}
                  disabled={saving}
                >
                  {saving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </div>
            {error && <div className="form-error" style={{ margin: '8px 0' }}>{error}</div>}
            {saved && <div style={{ color: 'var(--green)', fontSize: '13px', margin: '8px 0' }}>Saved.</div>}
            {preview ? (
              <div className="mod-pages-preview">
                <h2 style={{ marginBottom: '16px' }}>{title}</h2>
                <MarkdownBody text={body} />
              </div>
            ) : (
              <textarea
                className="mod-pages-textarea"
                value={body}
                onChange={e => setBody(e.target.value)}
                placeholder="Write your page content in markdown…"
                spellCheck
              />
            )}
            <div className="mod-pages-hint">
              Supports markdown — **bold**, *italic*, ## headings, {'>'} blockquotes, `code`, - lists, [links](url)
            </div>
          </>
        ) : (
          <div className="empty-state">Select a page to edit.</div>
        )}
      </div>
    </div>
  )
}
