import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuthStore } from './store/auth.store'
import AppLayout from './components/layout/AppLayout'
import AuthLayout from './components/layout/AuthLayout'
import LoginPage from './pages/auth/LoginPage'
import RegisterPage from './pages/auth/RegisterPage'
import DashboardPage from './pages/dashboard/DashboardPage'
import TillsPage from './pages/tills/TillsPage'
import AgentPage from './pages/agent/AgentPage'
import LedgerPage from './pages/ledger/LedgerPage'
import TaxVaultPage from './pages/tax/TaxVaultPage'
import SmsInboxPage from './pages/sms/SmsInboxPage'
import SettingsPage from './pages/settings/SettingsPage'
import DomainPage from './pages/domain/DomainPage'
import MiniAppDemoPage from './pages/miniapp/MiniAppDemoPage'

function RequireAuth({ children }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

function RequireGuest({ children }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : children
}

export default function App() {
  return (
    <Routes>
      <Route element={<RequireGuest><AuthLayout /></RequireGuest>}>
        <Route path="/login"    element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/tills"     element={<TillsPage />} />
        <Route path="/agent"     element={<AgentPage />} />
        <Route path="/ledger"    element={<LedgerPage />} />
        <Route path="/domain"    element={<DomainPage />} />
        <Route path="/miniapp"   element={<MiniAppDemoPage />} />
        <Route path="/tax"       element={<TaxVaultPage />} />
        <Route path="/sms"       element={<SmsInboxPage />} />
        <Route path="/settings"  element={<SettingsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}