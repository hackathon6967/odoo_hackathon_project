import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Layout from './components/Layout'
import LoginPage from './features/auth/LoginPage'
import Dashboard from './features/dashboard/Dashboard'
import EnvironmentalPage from './features/environmental/EnvironmentalPage'
import SocialPage from './features/social/SocialPage'
import GovernancePage from './features/governance/GovernancePage'
import GamificationPage from './features/gamification/GamificationPage'
import ScoringPage from './features/scoring/ScoringPage'
import SettingsPage from './features/settings/SettingsPage'
import AdminPage from './features/admin/AdminPage'
import { AuthProvider, useAuth } from './context/AuthContext'
import './index.css'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: '#ffffff', color: '#12344d', border: '1px solid #1599df',
              borderRadius: '0', fontFamily: 'Josefin Sans, sans-serif', letterSpacing: '.05em',
            },
          }}
        />
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="environmental/*" element={<EnvironmentalPage />} />
            <Route path="social/*" element={<SocialPage />} />
            <Route path="governance/*" element={<GovernancePage />} />
            <Route path="gamification/*" element={<GamificationPage />} />
            <Route path="scoring/*" element={<ScoringPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="accounts" element={<AdminPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
