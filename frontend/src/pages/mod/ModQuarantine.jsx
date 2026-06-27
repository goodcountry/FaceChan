import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import api from '../../api/client'
import { RotateCcw, Trash2, Check, AlertTriangle, LayoutGrid, Rows3 } from 'lucide-react'
import ModGrid from './ModGrid'

const REASON_LABEL = {
  spam: 'Spam or advertising',
  harassment: 'Harassment or bullying',
  illegal: 'Illegal content',
  csam: 'Child sexual abuse material',
  violence: 'Violence or graphic content',
  hate: 'Hate speech',
  other: 'Other',
}

export default function ModQuarantine() {
  const [view, setView] = useState('cards')
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busyKey, setBusyKey] = useState(null)
  const [confirmPurgeKey, setConfirmPurgeKey] = useState(null)
  const [gridReloadKey, setGridReloadKey] = useState(0)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    api.get('/mod/quarantine/')
      // Paginated response shape — see ModQueue.jsx for the same fix.
      .then(r => setReports(r.data.results ?? r.data))
      .catch(() => setError('Could not load the quarantine queue.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const act = async (report, action) => {
    setBusyKey(report.id)
    try {
      await api.post(`/mod/quarantine/${report.target_type}/${report.target_id}/action/`, { action })
      setReports(prev => prev.filter(r => r.id !== report.id))
      setConfirmPurgeKey(null)
      setGridReloadKey(k => k + 1)
    } catch (err) {
      setError(err.response?.data?.error || 'Action failed.')
    } finally {
      setBusyKey(null)
    }
  }

  if (loading) return <div className="loader">Loading quarantine queue…</div>

  return (
    <div className="page-layout">
      <div className="page-header">
        <h1>Quarantine <span className="accent">review</span></h1>
      </div>

      <div className="mod-info-note">
        <AlertTriangle size={13} />
        Quarantined content is invisible to everyone, including its author. Restore makes it
        fully visible again; purge permanently deletes it. See COMPLIANCE.md for why this is a
        separate step from a single delete action.
      </div>

      <div className="mod-toolbar">
        <div />
        <div className="mod-view-toggle">
          <button className={`mod-view-toggle-btn ${view === 'cards' ? 'active' : ''}`}
            onClick={() => setView('cards')} title="Card view">
            <Rows3 size={14} />
          </button>
          <button className={`mod-view-toggle-btn ${view === 'grid' ? 'active' : ''}`}
            onClick={() => setView('grid')} title="Grid view">
            <LayoutGrid size={14} />
          </button>
        </div>
      </div>

      {error && <div className="mod-error">{error}</div>}

      {view === 'cards' && (reports.length === 0 ? (
        <div className="empty-state">Nothing is currently quarantined.</div>
      ) : (
        <div className="mod-report-list">
          {reports.map(report => (
            <div key={report.id} className="mod-report-card">
              <div className="mod-report-meta">
                <span className="mod-reason-tag">{REASON_LABEL[report.reason] || report.reason}</span>
                {report.board_slug && <span className="mod-board-tag">/{report.board_slug}/</span>}
              </div>

              <div className="mod-report-target">
                <strong>{report.target_type === 'thread' ? 'Thread' : 'Post'}</strong> by{' '}
                {report.target_author || <em>(deleted)</em>}
                {report.thread_id && (
                  <Link to={`/thread/${report.thread_id}`} className="mod-view-link"> view →</Link>
                )}
                <p className="mod-report-preview">{report.target_preview}</p>
              </div>

              <div className="mod-action-buttons">
                <button className="btn-ghost btn-tiny" disabled={busyKey === report.id}
                  onClick={() => act(report, 'restore')}>
                  <RotateCcw size={12} /> Restore
                </button>
                {confirmPurgeKey !== report.id ? (
                  <button className="btn-ghost btn-tiny btn-danger" disabled={busyKey === report.id}
                    onClick={() => setConfirmPurgeKey(report.id)}>
                    <Trash2 size={12} /> Purge
                  </button>
                ) : (
                  <span className="mod-purge-confirm">
                    <AlertTriangle size={12} /> Irreversible.
                    <button className="btn-danger btn-tiny" disabled={busyKey === report.id}
                      onClick={() => act(report, 'purge')}>
                      <Check size={12} /> Confirm purge
                    </button>
                    <button className="btn-ghost btn-tiny" onClick={() => setConfirmPurgeKey(null)}>
                      Cancel
                    </button>
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      ))}

      {view === 'grid' && (
        <ModGrid
          endpoint="/mod/quarantine/"
          getRowId={r => r.id}
          reloadKey={gridReloadKey}
          columns={[
            { field: 'reason', headerName: 'Reason', width: 130,
              valueFormatter: v => REASON_LABEL[v] || v },
            { field: 'board_slug', headerName: 'Board', width: 100,
              valueFormatter: v => v ? `/${v}/` : '—' },
            { field: 'target_type', headerName: 'Type', width: 80 },
            { field: 'target_author', headerName: 'Author', width: 140,
              valueFormatter: v => v || '(unknown)' },
            { field: 'target_preview', headerName: 'Preview', flex: 1, minWidth: 200 },
            { field: 'created_at', headerName: 'Reported', width: 170,
              valueFormatter: v => v ? new Date(v).toLocaleString() : '' },
            {
              field: 'actions', headerName: 'Actions', width: 220, sortable: false,
              renderCell: ({ row: report }) => (
                <div className="mod-grid-actions">
                  <button className="btn-ghost btn-tiny" disabled={busyKey === report.id}
                    onClick={() => act(report, 'restore')} title="Restore">
                    <RotateCcw size={12} />
                  </button>
                  <button className="btn-ghost btn-tiny btn-danger" disabled={busyKey === report.id}
                    onClick={() => {
                      if (window.confirm('Purge this content permanently? This cannot be undone.')) {
                        act(report, 'purge')
                      }
                    }} title="Purge (irreversible)">
                    <Trash2 size={12} />
                  </button>
                </div>
              ),
            },
          ]}
        />
      )}
    </div>
  )
}
