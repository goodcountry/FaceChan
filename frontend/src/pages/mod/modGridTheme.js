import { createTheme } from '@mui/material/styles'

// Mirrors the CSS variables in App.css (:root) so the DataGrid doesn't
// look like a foreign widget dropped into the dark terminal aesthetic.
// Deliberately hand-mapped rather than read from CSS vars at runtime —
// MUI's theme needs real values at creation time, not custom-property
// strings, and this only needs to track App.css if that palette changes.
export const modGridTheme = createTheme({
  palette: {
    mode: 'dark',
    background: {
      default: '#0d0d0f',
      paper: '#141418',
    },
    primary: {
      main: '#7c6aff',
    },
    error: {
      main: '#ff4d6d',
    },
    success: {
      main: '#4ade80',
    },
    text: {
      primary: '#e8e8f0',
      secondary: '#8888a0',
    },
    divider: '#2a2a35',
  },
  typography: {
    fontFamily: "'Inter', sans-serif",
  },
  shape: {
    borderRadius: 6,
  },
  components: {
    MuiDataGrid: {
      styleOverrides: {
        root: {
          border: '1px solid #2a2a35',
          backgroundColor: '#141418',
          fontFamily: "'Inter', sans-serif",
          fontSize: 13,
          color: '#e8e8f0',
        },
        columnHeaders: {
          backgroundColor: '#1e1e24',
          borderBottom: '1px solid #2a2a35',
        },
        row: {
          '&:hover': { backgroundColor: 'rgba(124,106,255,0.08)' },
        },
        cell: {
          borderBottom: '1px solid #2a2a35',
        },
        footerContainer: {
          borderTop: '1px solid #2a2a35',
        },
      },
    },
  },
})
