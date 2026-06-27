import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { SiteSettingsProvider } from './context/SiteSettingsContext'
import { NotificationProvider } from './context/NotificationContext'
import { ThemeProvider } from './context/ThemeContext'
import Navbar from './components/Navbar'
import SiteFooter from './components/SiteFooter'
import Feed from './pages/Feed'
import Boards from './pages/Boards'
import BoardDetail from './pages/BoardDetail'
import ThreadDetail from './pages/ThreadDetail'
import Communities from './pages/Communities'
import CommunityDetail from './pages/CommunityDetail'
import Login from './pages/Login'
import Register from './pages/Register'
import Profile from './pages/Profile'
import Transparency from './pages/Transparency'
import PublicProfile from './pages/PublicProfile'
import InvitePage from './pages/InvitePage'
import SitePageView from './pages/SitePage'
import './App.css'

// Lazy-loaded: pulls in MUI + DataGrid (~700KB before gzip), which would
// otherwise ship to every visitor on first load even though only staff
// ever reach /mod/*. Split here keeps the main bundle at its previous
// size for everyone else.
const ModLayout = lazy(() => import('./pages/mod/ModLayout'))
const ModQueue = lazy(() => import('./pages/mod/ModQueue'))
const ModQuarantine = lazy(() => import('./pages/mod/ModQuarantine'))
const ModUsers = lazy(() => import('./pages/mod/ModUsers'))
const FederationDashboard = lazy(() => import('./pages/mod/FederationDashboard'))
const ModPages = lazy(() => import('./pages/mod/ModPages'))

function ModRoute({ children }) {
  return (
    <Suspense fallback={<div className="loader">Loading staff tools…</div>}>
      {children}
    </Suspense>
  )
}

export default function App() {
  return (
    <ThemeProvider>
    <SiteSettingsProvider>
      <AuthProvider>
        <BrowserRouter>
          <NotificationProvider>
          <Navbar />
          <main className="main-content">
            <Routes>
              <Route path="/" element={<Feed />} />
              <Route path="/feed" element={<Feed />} />
              <Route path="/boards" element={<Boards />} />
              <Route path="/boards/:slug" element={<BoardDetail />} />
              <Route path="/thread/:id" element={<ThreadDetail />} />
              <Route path="/communities" element={<Communities />} />
              <Route path="/c/:slug" element={<CommunityDetail />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/user/:username" element={<PublicProfile />} />
              <Route path="/transparency" element={<Transparency />} />
              <Route path="/invite/:token" element={<InvitePage />} />
              <Route path="/pages/:slug" element={<SitePageView />} />
              <Route path="/mod" element={<ModRoute><ModLayout><ModQueue /></ModLayout></ModRoute>} />
              <Route path="/mod/quarantine" element={<ModRoute><ModLayout><ModQuarantine /></ModLayout></ModRoute>} />
              <Route path="/mod/users" element={<ModRoute><ModLayout><ModUsers /></ModLayout></ModRoute>} />
              <Route path="/mod/federation" element={<ModRoute><ModLayout><FederationDashboard /></ModLayout></ModRoute>} />
              <Route path="/mod/pages" element={<ModRoute><ModLayout><ModPages /></ModLayout></ModRoute>} />
            </Routes>
          </main>
          <SiteFooter />
          </NotificationProvider>
        </BrowserRouter>
      </AuthProvider>
    </SiteSettingsProvider>
    </ThemeProvider>
  )
}
