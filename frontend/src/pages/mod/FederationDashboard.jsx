import { useState, useEffect, useCallback } from 'react'
import { Globe, Plus, RefreshCw, Trash2, Check, X, ChevronDown, ChevronRight, AlertTriangle, Link2, Unlink, ToggleLeft, ToggleRight } from 'lucide-react'
import api from '../../api/client'
import './FederationDashboard.css'

// ─── Status badge ────────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  return <span className={`fed-badge fed-badge--${status}`}>{status}</span>
}

// ─── Master switch ────────────────────────────────────────────────────────────

function MasterSwitch({ enabled, onToggle, busy }) {
  return (
    <div className="fed-master">
      <div className="fed-master-info">
        <h2>Federation</h2>
        <p>
          {enabled
            ? 'Federation is active. Your boards are discoverable and activities are being exchanged.'
            : 'Federation is paused. No inbound or outbound activities are processed. Instance mappings and board configurations are preserved.'}
        </p>
      </div>
      <button
        className={`fed-toggle ${enabled ? 'fed-toggle--on' : 'fed-toggle--off'}`}
        onClick={onToggle}
        disabled={busy}
      >
        {enabled ? <ToggleRight size={28} /> : <ToggleLeft size={28} />}
        <span>{enabled ? 'Enabled' : 'Paused'}</span>
      </button>
    </div>
  )
}

// ─── Add instance panel ───────────────────────────────────────────────────────

function AddInstancePanel({ onAdded }) {
  const [domain, setDomain] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)

  const handleSubmit = async () => {
    const clean = domain.trim().replace(/^https?:\/\//, '').replace(/\/$/, '')
    if (!clean) { setError('Enter a domain.'); return }
    setBusy(true); setError('')
    try {
      await api.post('/federation/instances/', { domain: clean, status: 'pending', notes })
      setDomain(''); setNotes(''); setOpen(false)
      onAdded()
    } catch (e) {
      setError(e.response?.data?.domain?.[0] || e.response?.data?.detail || 'Failed to add instance.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fed-add-panel">
      <button className="fed-add-toggle" onClick={() => setOpen(o => !o)}>
        <Plus size={14} /> Add instance
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      {open && (
        <div className="fed-add-form">
          <input
            className="fed-input"
            placeholder="other.facechan.example or abc123.onion"
            value={domain}
            onChange={e => setDomain(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSubmit()}
          />
          <textarea
            className="fed-input fed-input--notes"
            placeholder="Notes (optional) — why you're adding this instance"
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={2}
          />
          {error && <p className="fed-error">{error}</p>}
          <div className="fed-add-actions">
            <button className="fed-btn fed-btn--primary" onClick={handleSubmit} disabled={busy}>
              {busy ? 'Adding…' : 'Add (pending)'}
            </button>
            <button className="fed-btn fed-btn--ghost" onClick={() => setOpen(false)}>Cancel</button>
          </div>
          <p className="fed-hint">
            Instance is added as <strong>pending</strong>. Approve it below to start exchanging
            activities and to fetch its board list.
          </p>
        </div>
      )}
    </div>
  )
}

// ─── Board mapping row ────────────────────────────────────────────────────────

function BoardMappingRow({ remoteBoard, localBoards, instanceId, onMappingChange }) {
  const [localSlug, setLocalSlug] = useState(remoteBoard.mapped_to?.slug || '')
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const handleSave = async () => {
    if (!localSlug) return
    setSaving(true)
    try {
      if (remoteBoard.is_mapped) {
        // Find mapping id to update — re-fetch mappings for this instance
        const r = await api.get('/federation/mappings/', { params: { instance: instanceId } })
        const rows = Array.isArray(r.data) ? r.data : (r.data?.results ?? [])
        const existing = rows.find(m => m.remote_slug === remoteBoard.remote_slug)
        if (existing) {
          await api.patch(`/federation/mappings/${existing.id}/`, { local_board: localSlug })
        }
      } else {
        await api.post('/federation/mappings/', {
          instance: instanceId,
          remote_slug: remoteBoard.remote_slug,
          local_board: localSlug,
        })
      }
      onMappingChange()
    } catch (e) {
      console.error('Mapping save failed', e)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      const r = await api.get('/federation/mappings/', { params: { instance: instanceId } })
      const rows = Array.isArray(r.data) ? r.data : (r.data?.results ?? [])
      const existing = rows.find(m => m.remote_slug === remoteBoard.remote_slug)
      if (existing) {
        await api.delete(`/federation/mappings/${existing.id}/`)
        setLocalSlug('')
        onMappingChange()
      }
    } catch (e) {
      console.error('Mapping delete failed', e)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className={`fed-board-row ${remoteBoard.is_mapped ? 'fed-board-row--mapped' : ''}`}>
      <div className="fed-board-remote">
        <span className="fed-board-slug">/{remoteBoard.remote_slug}/</span>
        <span className="fed-board-name">{remoteBoard.name}</span>
        {remoteBoard.nsfw && <span className="fed-nsfw-tag">NSFW</span>}
        {remoteBoard.is_mapped && (
          remoteBoard.follow_accepted === true
            ? <span className="fed-follow-status fed-follow-status--accepted">✓ Following</span>
            : remoteBoard.follow_accepted === false
              ? <span className="fed-follow-status fed-follow-status--pending">⏳ Pending</span>
              : null
        )}
      </div>
      <div className="fed-board-arrow">
        {remoteBoard.is_mapped ? <Link2 size={14} /> : <Unlink size={14} className="fed-unmapped-icon" />}
      </div>
      <div className="fed-board-local">
        <select
          className="fed-select"
          value={localSlug}
          onChange={e => setLocalSlug(e.target.value)}
        >
          <option value="">— no mapping —</option>
          {localBoards.map(b => (
            <option key={b.slug} value={b.slug}>
              /{b.slug}/ — {b.name}
              {!b.allow_federation ? ' (federation off)' : ''}
            </option>
          ))}
        </select>
        <div className="fed-board-actions">
          {localSlug && localSlug !== (remoteBoard.mapped_to?.slug || '') && (
            <button className="fed-btn fed-btn--primary fed-btn--sm" onClick={handleSave} disabled={saving}>
              {saving ? '…' : 'Save'}
            </button>
          )}
          {remoteBoard.is_mapped && (
            <button className="fed-btn fed-btn--danger fed-btn--sm" onClick={handleDelete} disabled={deleting}>
              {deleting ? '…' : 'Remove'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Instance card ────────────────────────────────────────────────────────────

function InstanceCard({ instance, localBoards, onUpdate }) {
  const [expanded, setExpanded] = useState(false)
  const [remoteBoards, setRemoteBoards] = useState([])
  const [loadingBoards, setLoadingBoards] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [busy, setBusy] = useState(false)

  const loadBoards = useCallback(async () => {
    setLoadingBoards(true)
    try {
      const r = await api.get(`/federation/instances/${instance.id}/boards/`)
      setRemoteBoards(Array.isArray(r.data) ? r.data : (r.data?.results ?? []))
    } catch { }
    finally { setLoadingBoards(false) }
  }, [instance.id])

  useEffect(() => {
    if (expanded && instance.status === 'approved') loadBoards()
  }, [expanded, instance.status, loadBoards])

  const handleStatus = async (newStatus) => {
    setBusy(true)
    try {
      await api.patch(`/federation/instances/${instance.id}/`, { status: newStatus })
      onUpdate()
    } catch { }
    finally { setBusy(false) }
  }

  const handleDelete = async () => {
    if (!window.confirm(`Remove ${instance.domain}? This will also delete all board mappings for this instance.`)) return
    setBusy(true)
    try {
      await api.delete(`/federation/instances/${instance.id}/`)
      onUpdate()
    } catch { }
    finally { setBusy(false) }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await api.post(`/federation/instances/${instance.id}/refresh/`)
      setTimeout(() => { loadBoards(); setRefreshing(false) }, 2000)
    } catch { setRefreshing(false) }
  }

  return (
    <div className={`fed-instance-card fed-instance-card--${instance.status}`}>
      <div className="fed-instance-header" onClick={() => setExpanded(e => !e)}>
        <div className="fed-instance-title">
          <Globe size={14} />
          <span className="fed-instance-domain">{instance.domain}</span>
          <StatusBadge status={instance.status} />
          {instance.mapping_count > 0 && (
            <span className="fed-mapping-count">{instance.mapping_count} mapping{instance.mapping_count !== 1 ? 's' : ''}</span>
          )}
          {instance.pending_follows > 0 && (
            <span className="fed-pending-follows">
              <AlertTriangle size={11} /> {instance.pending_follows} pending follow{instance.pending_follows !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <div className="fed-instance-meta">
          {instance.board_count > 0 && (
            <span className="fed-board-count">{instance.board_count} board{instance.board_count !== 1 ? 's' : ''}</span>
          )}
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </div>

      {expanded && (
        <div className="fed-instance-body">
          {instance.notes && (
            <p className="fed-instance-notes">{instance.notes}</p>
          )}

          <div className="fed-instance-actions">
            {instance.status === 'pending' && (
              <>
                <button className="fed-btn fed-btn--approve" onClick={() => handleStatus('approved')} disabled={busy}>
                  <Check size={13} /> Approve
                </button>
                <button className="fed-btn fed-btn--danger" onClick={() => handleStatus('blocked')} disabled={busy}>
                  <X size={13} /> Block
                </button>
              </>
            )}
            {instance.status === 'approved' && (
              <>
                <button className="fed-btn fed-btn--ghost" onClick={handleRefresh} disabled={refreshing}>
                  <RefreshCw size={13} className={refreshing ? 'fed-spin' : ''} /> Refresh boards
                </button>
                <button className="fed-btn fed-btn--danger" onClick={() => handleStatus('blocked')} disabled={busy}>
                  <X size={13} /> Block
                </button>
              </>
            )}
            {instance.status === 'blocked' && (
              <button className="fed-btn fed-btn--ghost" onClick={() => handleStatus('approved')} disabled={busy}>
                <Check size={13} /> Unblock
              </button>
            )}
            <button className="fed-btn fed-btn--danger fed-btn--ghost" onClick={handleDelete} disabled={busy}>
              <Trash2 size={13} /> Remove
            </button>
          </div>

          {instance.status === 'approved' && (
            <div className="fed-boards-section">
              <div className="fed-boards-header">
                <span>Board mappings</span>
                <span className="fed-boards-hint">Map their boards to yours</span>
              </div>
              {loadingBoards && <p className="fed-loading">Loading boards…</p>}
              {!loadingBoards && remoteBoards.length === 0 && (
                <p className="fed-empty">
                  No boards fetched yet.{' '}
                  <button className="fed-link" onClick={handleRefresh}>Refresh now</button>
                </p>
              )}
              {remoteBoards.map(rb => (
                <BoardMappingRow
                  key={rb.remote_slug}
                  remoteBoard={rb}
                  localBoards={localBoards}
                  instanceId={instance.id}
                  onMappingChange={loadBoards}
                />
              ))}
            </div>
          )}

          {instance.status === 'pending' && (
            <p className="fed-hint fed-hint--approve">
              Approve this instance to fetch its board list and start exchanging activities.
            </p>
          )}
          {instance.status === 'blocked' && (
            <p className="fed-hint fed-hint--blocked">
              This instance is blocked. All inbound activities from it are rejected.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Main dashboard ───────────────────────────────────────────────────────────

export default function FederationDashboard() {
  const [status, setStatus] = useState(null)
  const [instances, setInstances] = useState([])
  const [localBoards, setLocalBoards] = useState([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [togglingMaster, setTogglingMaster] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [statusR, instancesR, boardsR] = await Promise.all([
        api.get('/federation/status/'),
        api.get('/federation/instances/'),
        api.get('/federation/local-boards/'),
      ])
      // Tolerate either a bare array or a paginated {results: [...]} object
      const asArray = (d) => (Array.isArray(d) ? d : (d?.results ?? []))
      setStatus(statusR.data)
      setInstances(asArray(instancesR.data))
      setLocalBoards(asArray(boardsR.data))
    } catch { }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const toggleMaster = async () => {
    if (!status) return
    setTogglingMaster(true)
    try {
      const r = await api.patch('/federation/status/', {
        federation_enabled: !status.federation_enabled
      })
      setStatus(s => ({ ...s, federation_enabled: r.data.federation_enabled }))
    } catch { }
    finally { setTogglingMaster(false) }
  }

  const filtered = filter === 'all' ? instances : instances.filter(i => i.status === filter)
  const pendingCount = instances.filter(i => i.status === 'pending').length

  if (loading) return <div className="fed-loader">Loading federation status…</div>

  return (
    <div className="fed-dashboard">
      <div className="fed-dashboard-header">
        <h1>Federation</h1>
        {status && (
          <div className="fed-stats">
            <span>{status.instance_count} approved</span>
            {status.pending_count > 0 && (
              <span className="fed-stat--pending">
                <AlertTriangle size={12} /> {status.pending_count} pending
              </span>
            )}
            <span>{status.total_mappings} mapping{status.total_mappings !== 1 ? 's' : ''}</span>
          </div>
        )}
      </div>

      {status && !status.federation_configured && (
        <div className="fed-unconfigured">
          <AlertTriangle size={16} />
          <div>
            <strong>FEDERATION_BASE_URL is not set</strong>
            <p>
              Federation is running but this instance has no public address configured.
              Remote servers cannot discover or contact you, and no activities will be delivered.
            </p>
            {status.base_url?.includes('localhost') && (
              <p className="fed-unconfigured-steps">
                <strong>Tor instance?</strong> First boot generates your onion address.
                Check it with:<br />
                <code>docker compose -f docker-compose.prod.yml -p facechan-prod logs tor</code><br />
                Then add <code>FEDERATION_BASE_URL=http://youraddress.onion</code> to your <code>.env</code> and restart.
              </p>
            )}
            <p className="fed-unconfigured-steps">
              <strong>Clearnet instance?</strong> Add <code>FEDERATION_BASE_URL=https://yourdomain.tld</code> to your <code>.env</code> and restart.
            </p>
            <p>Federation will activate automatically once this is set. Everything else is preserved.</p>
          </div>
        </div>
      )}

      {status && (
        <MasterSwitch
          enabled={status.federation_enabled}
          onToggle={toggleMaster}
          busy={togglingMaster}
        />
      )}

      <div className="fed-section">
        <div className="fed-section-header">
          <h2>Remote instances</h2>
          <div className="fed-filter-tabs">
            {['all', 'pending', 'approved', 'blocked'].map(f => (
              <button
                key={f}
                className={`fed-filter-tab ${filter === f ? 'active' : ''}`}
                onClick={() => setFilter(f)}
              >
                {f === 'pending' && pendingCount > 0
                  ? <><AlertTriangle size={11} /> {f} ({pendingCount})</>
                  : f}
              </button>
            ))}
          </div>
        </div>

        <AddInstancePanel onAdded={load} />

        {filtered.length === 0 && (
          <p className="fed-empty fed-empty--section">
            {filter === 'all'
              ? 'No remote instances yet. Add one above to get started.'
              : `No ${filter} instances.`}
          </p>
        )}

        {filtered.map(instance => (
          <InstanceCard
            key={instance.id}
            instance={instance}
            localBoards={localBoards}
            onUpdate={load}
          />
        ))}
      </div>

      {localBoards.length > 0 && (
        <div className="fed-section fed-section--local">
          <h2>Local boards</h2>
          <p className="fed-section-hint">
            Boards with federation disabled do not appear in the instance discovery endpoint
            and their threads are not delivered to remote instances.
          </p>
          <div className="fed-local-boards">
            {localBoards.map(b => (
              <div key={b.slug} className={`fed-local-board ${!b.allow_federation ? 'fed-local-board--off' : ''}`}>
                <span className="fed-board-slug">/{b.slug}/</span>
                <span className="fed-board-name">{b.name}</span>
                {b.nsfw && <span className="fed-nsfw-tag">NSFW</span>}
                <span className={`fed-fed-status ${b.allow_federation ? 'fed-fed-status--on' : 'fed-fed-status--off'}`}>
                  {b.allow_federation ? 'Federated' : 'Local only'}
                </span>
              </div>
            ))}
          </div>
          <p className="fed-hint">To change a board's federation setting, use the Django admin board editor.</p>
        </div>
      )}
    </div>
  )
}
