import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import api from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import { Check, EyeOff, Archive, Trash2, X, AlertTriangle, Users2, LayoutGrid, Rows3 } from 'lucide-react'
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

const STATUS_TABS = [
  { value: 'open', label: 'Open' },
  { value: 'reviewing', label: 'Reviewing' },
  { value: 'actioned', label: 'Actioned' },
  { value: 'dismissed', label: 'Dismissed' },
  { value: 'all', label: 'All' },
]

export default function ModQueue() {
  const { permissions } = useAuth()
  const [status, setStatus] = useState('open')
  const [view, setView] = useState('cards') // 'cards' | 'grid'
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [confirmPurge, setConfirmPurge] = useState(null) // report id pending purge confirmation
  const [noteDraft, setNoteDraft] = useState({}) // report id -> resolution note text
  const [gridReloadKey, setGridReloadKey] = useState(0)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    api.get('/mod/queue/', { params: { status } })
      // ModQueueView is paginated (DEFAULT_PAGINATION_CLASS in settings.py) —
      // the response is {count, next, previous, results}, not a bare array.
      .then(r => setReports(r.data.results ?? r.data))
      .catch(() => setError('Could not load the report queue.'))
      .finally(() => setLoading(false))
  }, [status])

  useEffect(() => { load() }, [load])

  // Mirrors core/permissions.py's can_moderate() scoping using only
  // /api/me/permissions/ data — this is a UI convenience so we don't show
  // buttons that would 403; the server re-checks every action regardless.
  const canActOnReport = (report, capability) => {
    if (!permissions || !permissions.capabilities?.[capability]) return false
    if (permissions.is_admin_tier) return true
    if (report.board_slug && permissions.assigned_boards?.includes(report.board_slug)) return true
    // ModQueueView already scopes which reports the caller sees server-side
    // (board assignment OR community staff) — if a report shows up here at
    // all and board-assignment didn't explain why, it's in scope via
    // community staff, for which only these capabilities apply (see
    // can_moderate: purge is never community-grantable).
    if (['can_hide', 'can_resolve_reports', 'can_quarantine', 'can_lock_threads'].includes(capability)) {
      return true
    }
    return false
  }

  const canPurge = permissions?.is_admin_tier && permissions.capabilities?.can_purge

  const resolve = async (report, action) => {
    setBusyId(report.id)
    try {
      const { data } = await api.post(`/mod/reports/${report.id}/resolve/`, {
        action,
        resolution_note: noteDraft[report.id] || '',
      })
      setReports(prev => prev.map(r => (r.id === report.id ? data : r)))
      setConfirmPurge(null)
      setGridReloadKey(k => k + 1)
    } catch (err) {
      setError(err.response?.data?.error || 'Action failed.')
    } finally {
      setBusyId(null)
    }
  }

  if (loading) return <div className="loader">Loading report queue…</div>

  const missingResolveCapability = permissions && !permissions.capabilities?.can_resolve_reports

  return (
    <div className="page-layout">
      <div className="page-header">
        <h1>Report <span className="accent">queue</span></h1>
      </div>

      {missingResolveCapability && (
        <div className="mod-info-note mod-config-hint">
          <AlertTriangle size={13} />
          Your role ({permissions.role}) doesn't have <code>can_resolve_reports</code> enabled,
          so this queue will always be empty for you — even if reports exist and even if you're
          admin-tier. Admin-tier only grants unscoped <em>reach</em>; the capability flags on the
          Role itself (Django admin → Core → Roles) still need to be ticked for each action.
        </div>
      )}

      <div className="mod-toolbar">
        <div className="mod-status-tabs">
          {STATUS_TABS.map(t => (
            <button
              key={t.value}
              className={`mod-status-tab ${status === t.value ? 'active' : ''}`}
              onClick={() => setStatus(t.value)}
            >
              {t.label}
            </button>
          ))}
        </div>
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
        <div className="empty-state">No reports in this view.</div>
      ) : (
        <div className="mod-report-list">
          {reports.map(report => (
            <div key={report.id} className="mod-report-card">
              <div className="mod-report-meta">
                <span className="mod-reason-tag">{REASON_LABEL[report.reason] || report.reason}</span>
                <span className={`mod-status-pill status-${report.status}`}>{report.status}</span>
                {report.board_slug && <span className="mod-board-tag">/{report.board_slug}/</span>}
                {!report.target_id && (
                  <span className="mod-purged-marker" title="The reported content has been purged — this is a frozen historical record, not live data.">
                    <AlertTriangle size={11} /> Purged — historical record
                  </span>
                )}
                <span className="mod-report-date">{new Date(report.created_at).toLocaleString()}</span>
              </div>

              <div className="mod-report-target">
                <strong>{report.target_type === 'thread' ? 'Thread' : 'Post'}</strong> by{' '}
                {report.target_author || <em>(unknown)</em>}
                {report.thread_id && (
                  <Link to={`/thread/${report.thread_id}`} className="mod-view-link"> view →</Link>
                )}
                <p className="mod-report-preview">{report.target_preview}</p>
              </div>

              {report.details && <p className="mod-report-details">Reporter note: {report.details}</p>}

              <div className="mod-report-reporter">
                Reported by {report.reporter?.username || <em>anon</em>}
                {report.resolved_by && <> · resolved by {report.resolved_by.username}</>}
              </div>

              {report.target_id && (
                <div className="mod-report-actions">
                  <input
                    type="text"
                    className="mod-note-input"
                    placeholder="Resolution note (optional)"
                    value={noteDraft[report.id] || ''}
                    onChange={e => setNoteDraft(prev => ({ ...prev, [report.id]: e.target.value }))}
                  />
                  <div className="mod-action-buttons">
                    {report.status === 'open' && canActOnReport(report, 'can_resolve_reports') && (
                      <button className="btn-ghost btn-tiny" disabled={busyId === report.id}
                        onClick={() => resolve(report, 'dismiss')}>
                        <X size={12} /> Dismiss
                      </button>
                    )}
                    {!report.target_is_hidden && !report.target_is_quarantined && canActOnReport(report, 'can_hide') && (
                      <button className="btn-ghost btn-tiny" disabled={busyId === report.id}
                        onClick={() => resolve(report, 'hide')}>
                        <EyeOff size={12} /> Hide
                      </button>
                    )}
                    {report.target_is_hidden && canActOnReport(report, 'can_hide') && (
                      <button className="btn-ghost btn-tiny" disabled={busyId === report.id}
                        onClick={() => resolve(report, 'unhide')}>
                        <Check size={12} /> Unhide
                      </button>
                    )}
                    {!report.target_is_quarantined && canActOnReport(report, 'can_quarantine') && (
                      <button className="btn-ghost btn-tiny" disabled={busyId === report.id}
                        onClick={() => resolve(report, 'quarantine')}>
                        <Archive size={12} /> Quarantine
                      </button>
                    )}
                    {report.target_is_quarantined && permissions?.is_admin_tier && (
                      <Link to="/mod/quarantine" className="btn-ghost btn-tiny">
                        <Archive size={12} /> Review in quarantine
                      </Link>
                    )}
                    {canPurge && confirmPurge !== report.id && (
                      <button className="btn-ghost btn-tiny btn-danger" disabled={busyId === report.id}
                        onClick={() => setConfirmPurge(report.id)}>
                        <Trash2 size={12} /> Purge
                      </button>
                    )}
                    {canPurge && confirmPurge === report.id && (
                      <span className="mod-purge-confirm">
                        <AlertTriangle size={12} /> Irreversible.
                        <button className="btn-danger btn-tiny" disabled={busyId === report.id}
                          onClick={() => resolve(report, 'purge')}>
                          <Check size={12} /> Confirm purge
                        </button>
                        <button className="btn-ghost btn-tiny" onClick={() => setConfirmPurge(null)}>
                          Cancel
                        </button>
                      </span>
                    )}
                    {report.target_author_id && (permissions?.capabilities?.can_suspend || permissions?.capabilities?.can_ban) && (
                      <Link
                        to={`/mod/users?id=${report.target_author_id}&username=${encodeURIComponent(report.target_author || '')}`}
                        className="btn-ghost btn-tiny"
                      >
                        <Users2 size={12} /> Sanction user
                      </Link>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      ))}

      {view === 'grid' && (
        <ModGrid
          endpoint="/mod/queue/"
          extraParams={{ status }}
          getRowId={r => r.id}
          reloadKey={gridReloadKey}
          columns={[
            { field: 'reason', headerName: 'Reason', width: 130,
              valueFormatter: v => REASON_LABEL[v] || v },
            { field: 'status', headerName: 'Status', width: 100 },
            { field: 'board_slug', headerName: 'Board', width: 100,
              valueFormatter: v => v ? `/${v}/` : '—' },
            { field: 'target_type', headerName: 'Type', width: 80 },
            { field: 'target_author', headerName: 'Reported user', width: 140,
              valueFormatter: v => v || '(unknown)' },
            { field: 'target_preview', headerName: 'Preview', flex: 1, minWidth: 200 },
            { field: 'reporter', headerName: 'Reporter', width: 130,
              valueGetter: (v, row) => row.reporter?.username || 'anon' },
            { field: 'created_at', headerName: 'Reported', width: 170,
              valueFormatter: v => v ? new Date(v).toLocaleString() : '' },
            {
              field: 'actions', headerName: 'Actions', width: 280, sortable: false,
              renderCell: ({ row: report }) => (
                <div className="mod-grid-actions">
                  {!report.target_id ? (
                    <span className="mod-purged-marker" title="Content purged — historical record">
                      <AlertTriangle size={11} /> Purged
                    </span>
                  ) : (
                    <>
                      {report.status === 'open' && canActOnReport(report, 'can_resolve_reports') && (
                        <button className="btn-ghost btn-tiny" disabled={busyId === report.id}
                          onClick={() => resolve(report, 'dismiss')} title="Dismiss">
                          <X size={12} />
                        </button>
                      )}
                      {!report.target_is_hidden && !report.target_is_quarantined && canActOnReport(report, 'can_hide') && (
                        <button className="btn-ghost btn-tiny" disabled={busyId === report.id}
                          onClick={() => resolve(report, 'hide')} title="Hide">
                          <EyeOff size={12} />
                        </button>
                      )}
                      {report.target_is_hidden && canActOnReport(report, 'can_hide') && (
                        <button className="btn-ghost btn-tiny" disabled={busyId === report.id}
                          onClick={() => resolve(report, 'unhide')} title="Unhide">
                          <Check size={12} />
                        </button>
                      )}
                      {!report.target_is_quarantined && canActOnReport(report, 'can_quarantine') && (
                        <button className="btn-ghost btn-tiny" disabled={busyId === report.id}
                          onClick={() => resolve(report, 'quarantine')} title="Quarantine">
                          <Archive size={12} />
                        </button>
                      )}
                      {canPurge && (
                        <button className="btn-ghost btn-tiny btn-danger" disabled={busyId === report.id}
                          onClick={() => {
                            if (window.confirm('Purge this content permanently? This cannot be undone.')) {
                              resolve(report, 'purge')
                            }
                          }} title="Purge (irreversible)">
                          <Trash2 size={12} />
                        </button>
                      )}
                      {report.target_author_id && (permissions?.capabilities?.can_suspend || permissions?.capabilities?.can_ban) && (
                        <Link
                          to={`/mod/users?id=${report.target_author_id}&username=${encodeURIComponent(report.target_author || '')}`}
                          className="btn-ghost btn-tiny" title="Sanction user"
                        >
                          <Users2 size={12} />
                        </Link>
                      )}
                    </>
                  )}
                </div>
              ),
            },
          ]}
        />
      )}
    </div>
  )
}
