import { useState, useEffect, useCallback } from 'react'
import { ThemeProvider } from '@mui/material/styles'
import { DataGrid } from '@mui/x-data-grid'
import { modGridTheme } from './modGridTheme'
import api from '../../api/client'

// Wraps MUI's DataGrid with server-side pagination + sorting against a
// DRF ListAPIView using ModGridPagination (page/page_size) and
// _apply_safe_ordering (?ordering=field|-field). Column-hiding is purely
// client-side — DataGrid already does this via columnVisibilityModel,
// no backend support needed since we're not changing which fields are
// fetched, just which are displayed.
//
// `reloadKey` lets a parent force a refetch after a row action (dismiss/
// hide/purge/etc.) without ModGrid needing to know about individual
// actions — just change the key.
export default function ModGrid({ endpoint, columns, extraParams = {}, getRowId, reloadKey }) {
  const [rows, setRows] = useState([])
  const [rowCount, setRowCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 25 })
  const [sortModel, setSortModel] = useState([])
  const [columnVisibilityModel, setColumnVisibilityModel] = useState({})

  const extraParamsKey = JSON.stringify(extraParams)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    const params = {
      ...extraParams,
      page: paginationModel.page + 1, // DataGrid is 0-indexed, DRF's PageNumberPagination is 1-indexed
      page_size: paginationModel.pageSize,
    }
    if (sortModel.length > 0) {
      const { field, sort } = sortModel[0]
      params.ordering = sort === 'desc' ? `-${field}` : field
    }
    api.get(endpoint, { params })
      .then(r => {
        setRows(r.data.results ?? r.data)
        setRowCount(r.data.count ?? (r.data.results ?? r.data).length)
      })
      .catch(() => setError('Could not load this list.'))
      .finally(() => setLoading(false))
    // extraParamsKey (not extraParams) in deps deliberately — extraParams
    // is a fresh object every render from the caller, which would loop
    // this effect forever if used directly.
  }, [endpoint, paginationModel, sortModel, extraParamsKey, reloadKey])

  useEffect(() => { load() }, [load])

  return (
    <ThemeProvider theme={modGridTheme}>
      <div style={{ width: '100%' }}>
        {error && <div className="mod-error" style={{ marginBottom: 12 }}>{error}</div>}
        <DataGrid
          rows={rows}
          columns={columns}
          getRowId={getRowId}
          loading={loading}
          rowCount={rowCount}
          paginationMode="server"
          sortingMode="server"
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          sortModel={sortModel}
          onSortModelChange={setSortModel}
          columnVisibilityModel={columnVisibilityModel}
          onColumnVisibilityModelChange={setColumnVisibilityModel}
          pageSizeOptions={[10, 25, 50, 100]}
          disableRowSelectionOnClick
          density="compact"
          autoHeight
        />
      </div>
    </ThemeProvider>
  )
}
