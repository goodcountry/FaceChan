import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import api from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const u = localStorage.getItem('user')
    return u ? JSON.parse(u) : null
  })
  // Mod/staff capabilities for the current user, from /api/me/permissions/.
  // Fetched globally (not just inside /mod) so the Navbar can decide whether
  // to show a "Mod" link at all. null = not loaded yet / no role.
  const [permissions, setPermissions] = useState(null)

  const refreshPermissions = useCallback(async () => {
    if (!localStorage.getItem('token')) {
      setPermissions(null)
      return
    }
    try {
      const { data } = await api.get('/me/permissions/')
      setPermissions(data)
    } catch {
      setPermissions(null)
    }
  }, [])

  useEffect(() => {
    if (user) refreshPermissions()
  }, [])

  const login = async (username, password) => {
    const { data } = await api.post('/auth/login/', { username, password })
    localStorage.setItem('token', data.token)
    localStorage.setItem('user', JSON.stringify(data.user))
    setUser(data.user)
    await refreshPermissions()
    return data.user
  }

  const register = async (username, password, age_confirmed, mcaptcha_token = '') => {
    const { data } = await api.post('/auth/register/', { username, password, age_confirmed, mcaptcha_token })
    localStorage.setItem('token', data.token)
    localStorage.setItem('user', JSON.stringify(data.user))
    setUser(data.user)
    await refreshPermissions()
    return data.user
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setUser(null)
    setPermissions(null)
  }

  // For profile edits (e.g. username change) that need the stored user
  // object updated immediately everywhere it's read (Navbar, etc.)
  // without a full re-login.
  const updateUser = (patch) => {
    setUser(prev => {
      const next = { ...prev, ...patch }
      localStorage.setItem('user', JSON.stringify(next))
      return next
    })
  }

  // Any staff role at all (board-scoped or admin-tier) gives the user
  // something to do in /mod — community-only moderation (Membership.role)
  // is handled within its own community pages, not the staff frontend.
  const isStaff = !!(permissions && permissions.role)

  return (
    <AuthContext.Provider value={{ user, login, register, logout, updateUser, permissions, isStaff, refreshPermissions }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
