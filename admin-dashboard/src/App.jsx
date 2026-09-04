import { Navigate, Route, Routes } from 'react-router-dom'
import { useEffect, useState } from 'react'
import Layout from './components/Layout.jsx'
import LoginPage from './pages/LoginPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import CrimeManagementPage from './pages/CrimeManagementPage.jsx'
import SafeZoneMapPage from './pages/SafeZoneMapPage.jsx'
import OptimizationPage from './pages/OptimizationPage.jsx'
import AssignmentsPage from './pages/AssignmentsPage.jsx'
import { api, clearSession, getStoredProfile, hasToken, storeProfile } from './services/apiClient.js'

function App() {
  const [profile, setProfile] = useState(getStoredProfile())
  const [checking, setChecking] = useState(hasToken())

  useEffect(() => {
    if (!hasToken()) return
    api.me().then((user) => {
      if (user.role !== 'ADMIN') throw new Error('This dashboard is restricted to administrators.')
      storeProfile(user); setProfile(user)
    }).catch(() => { clearSession(); setProfile(null) }).finally(() => setChecking(false))
  }, [])

  useEffect(() => {
    const expired = () => { clearSession(); setProfile(null) }
    window.addEventListener('safezone:auth-expired', expired)
    return () => window.removeEventListener('safezone:auth-expired', expired)
  }, [])

  if (checking) return <div className="center-screen"><div className="spinner" /><p>Verifying secure session…</p></div>
  const login = (user) => { storeProfile(user); setProfile(user) }
  const logout = () => { clearSession(); setProfile(null) }

  return <Routes>
    <Route path="/login" element={profile ? <Navigate to="/" replace /> : <LoginPage onLogin={login} />} />
    <Route element={profile ? <Layout profile={profile} onLogout={logout} /> : <Navigate to="/login" replace />}>
      <Route index element={<DashboardPage />} />
      <Route path="crimes" element={<CrimeManagementPage />} />
      <Route path="map" element={<SafeZoneMapPage />} />
      <Route path="optimization" element={<OptimizationPage />} />
      <Route path="assignments" element={<AssignmentsPage />} />
    </Route>
    <Route path="*" element={<Navigate to={profile ? '/' : '/login'} replace />} />
  </Routes>
}

export default App
