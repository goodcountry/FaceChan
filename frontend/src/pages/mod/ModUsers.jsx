import { useState, useEffect, useCallback } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import api from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import { Ban, Clock, ShieldOff, RotateCcw, AlertTriangle, Check, LayoutGrid, Rows3, UserX } from 'lucide-react'
import ModGrid from './ModGrid'

export default function ModUsers() {
  const { permissions } = useAuth()
  const [searchParams] = useSearchParams()
  const userId = searchParams.get('id')
  const username = searchParams.get('username')

  const [hours, setHours] = useState('24')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [confirmBan, setConfirmBan] = useState(false)

  const [view, setView] = useState('cards')
  const [sanctioned, setSanctioned] = useState([])
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState(null)
  const [listBusyId, setListBusyId] = useState(null)
  const [gridReloadKey, setGridReloadKey] = useState(0)

  const canSuspend = !!permissions?.capabilities?.can_suspend
  const canBan = !!permissions?.capabilities?.can_ban

  const loadSanctioned = useCallback(() => {
    setListLoading(true)
    setListError(null)
    api.get('/mod/users/sanctioned/')
      .then(r => setSanctioned(r.data.results ?? r.data))
      .catch(() => setListError('Could not load the sanctioned-users list.'))
      .finally(() => setListLoading(false))
  }, [])

  useEffect(() => { loadSanctioned() }, [loadSanctioned, userId])

  const act = async (action, extra = {}) => {
    setBusy(true)
    setError(null)
    try {
      const { data } = await api.post(`/mod/users/${userId}/action/`, { action, ...extra })
      setResult(data)
      setConfirmBan(false)
      loadSanctioned()
      setGridReloadKey(k => k + 1)
    } catch (err) {
      setError(err.response?.data?.error || 'Action failed.')
    } finally {
      setBusy(false)
    }
  }

  // Quick unsuspend/unban directly from the list, without needing the
  // ?id=&username= deep link — same /mod/users/:id/action/ endpoint.
  const listAct = async (targetUser, action) => {
    setListBusyId(targetUser.id)
    try {
      await api.post(`/mod/users/${targetUser.id}/action/`, { action })
      loadSanctioned()
      setGridReloadKey(k => k + 1)
    } catch (err) {
      setListError(err.response?.data?.error || 'Action failed.')
    } finally {
      setListBusyId(null)
    }
  }

  return (
    <div className="page-layout">
      <div className="page-header">
        <h1>User <span className="accent">actions</span></h1>
      </div>

      {userId && (
        <div className="mod-report-card">
          <div className="mod-report-target">
            <strong>{username || 'User'}</strong>
            <span className="mod-board-tag">id: {userId}</span>
          </div>

          {error && <div className="mod-error">{error}</div>}

          {result && (
            <div className="mod-info-note">
              <Check size={13} />
              {result.is_banned !== undefined && (result.is_banned ? 'Banned.' : 'Ban lifted.')}
              {result.suspended_until && ` Suspended until ${new Date(result.suspended_until).toLocaleString()}.`}
              {result.suspended_until === null && result.is_banned === false && ' Suspension cleared.'}
            </div>
          )}

          {canSuspend && (
            <div className="mod-sanction-block">
              <span className="mod-sidebar-boards-label">Suspend</span>
              <div className="mod-action-buttons">
                <input
                  type="number"
                  min="1"
                  step="1"
                  className="mod-note-input mod-hours-input"
                  value={hours}
                  onChange={e => setHours(e.target.value)}
                />
                <span className="mod-report-date">hours</span>
                <button className="btn-ghost btn-tiny" disabled={busy}
                  onClick={() => act('suspend', { hours: Number(hours) })}>
                  <Clock size={12} /> Suspend
                </button>
                <button className="btn-ghost btn-tiny" disabled={busy}
                  onClick={() => act('unsuspend')}>
                  <RotateCcw size={12} /> Unsuspend
                </button>
              </div>
            </div>
          )}

          {canBan && (
            <div className="mod-sanction-block">
              <span className="mod-sidebar-boards-label">Ban</span>
              <div className="mod-action-buttons">
                {!confirmBan ? (
                  <button className="btn-ghost btn-tiny btn-danger" disabled={busy}
                    onClick={() => setConfirmBan(true)}>
                    <Ban size={12} /> Ban permanently
                  </button>
                ) : (
                  <span className="mod-purge-confirm">
                    <AlertTriangle size={12} /> This revokes their session immediately.
                    <button className="btn-danger btn-tiny" disabled={busy} onClick={() => act('ban')}>
                      <Check size={12} /> Confirm ban
                    </button>
                    <button className="btn-ghost btn-tiny" onClick={() => setConfirmBan(false)}>
                      Cancel
                    </button>
                  </span>
                )}
                <button className="btn-ghost btn-tiny" disabled={busy} onClick={() => act('unban')}>
                  <ShieldOff size={12} /> Unban
                </button>
              </div>
            </div>
          )}

          {!canSuspend && !canBan && (
            <p className="mod-report-details">Your role doesn't grant suspend or ban capabilities.</p>
          )}
        </div>
      )}

      <div className="mod-section-divider">
        <UserX size={14} /> Currently sanctioned users
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

      {listError && <div className="mod-error">{listError}</div>}

      {view === 'cards' && (
        listLoading ? <div className="loader">Loading sanctioned users…</div> :
        sanctioned.length === 0 ? (
          <div className="empty-state">No one is currently banned or suspended.</div>
        ) : (
          <div className="mod-report-list">
            {sanctioned.map(u => (
              <div key={u.id} className="mod-report-card">
                <div className="mod-report-meta">
                  <strong>{u.username}</strong>
                  {u.is_banned && <span className="mod-status-pill status-open">banned</span>}
                  {u.is_suspended && (
                    <span className="mod-status-pill" title={new Date(u.suspended_until).toLocaleString()}>
                      suspended until {new Date(u.suspended_until).toLocaleString()}
                    </span>
                  )}
                </div>
                <div className="mod-action-buttons">
                  {canSuspend && u.is_suspended && (
                    <button className="btn-ghost btn-tiny" disabled={listBusyId === u.id}
                      onClick={() => listAct(u, 'unsuspend')}>
                      <RotateCcw size={12} /> Unsuspend
                    </button>
                  )}
                  {canBan && u.is_banned && (
                    <button className="btn-ghost btn-tiny" disabled={listBusyId === u.id}
                      onClick={() => listAct(u, 'unban')}>
                      <ShieldOff size={12} /> Unban
                    </button>
                  )}
                  <Link to={`/mod/users?id=${u.id}&username=${encodeURIComponent(u.username)}`} className="btn-ghost btn-tiny">
                    Manage →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {view === 'grid' && (
        <ModGrid
          endpoint="/mod/users/sanctioned/"
          getRowId={r => r.id}
          reloadKey={gridReloadKey}
          columns={[
            { field: 'username', headerName: 'Username', width: 160 },
            { field: 'is_banned', headerName: 'Banned', width: 90,
              valueFormatter: v => v ? 'Yes' : 'No' },
            { field: 'suspended_until', headerName: 'Suspended until', width: 180,
              valueFormatter: v => v ? new Date(v).toLocaleString() : '—' },
            { field: 'created_at', headerName: 'Account created', width: 170,
              valueFormatter: v => v ? new Date(v).toLocaleString() : '' },
            {
              field: 'actions', headerName: 'Actions', width: 220, sortable: false,
              renderCell: ({ row: u }) => (
                <div className="mod-grid-actions">
                  {canSuspend && u.is_suspended && (
                    <button className="btn-ghost btn-tiny" disabled={listBusyId === u.id}
                      onClick={() => listAct(u, 'unsuspend')} title="Unsuspend">
                      <RotateCcw size={12} />
                    </button>
                  )}
                  {canBan && u.is_banned && (
                    <button className="btn-ghost btn-tiny" disabled={listBusyId === u.id}
                      onClick={() => listAct(u, 'unban')} title="Unban">
                      <ShieldOff size={12} />
                    </button>
                  )}
                  <Link to={`/mod/users?id=${u.id}&username=${encodeURIComponent(u.username)}`} className="btn-ghost btn-tiny">
                    Manage
                  </Link>
                </div>
              ),
            },
          ]}
        />
      )}
    </div>
  )
}
