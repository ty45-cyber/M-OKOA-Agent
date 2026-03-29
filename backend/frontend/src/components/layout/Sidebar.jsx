import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/auth.store'

const NAV_ITEMS = [
  { path: '/dashboard', label: 'Dashboard',       icon: '◈' },
  { path: '/tills',     label: 'Tills',            icon: '⬡' },
  { path: '/ledger',    label: 'Ledger',           icon: '≡' },
  { path: '/agent',     label: 'Agent',            icon: '◎' },
  { path: '/domain',    label: 'Challenge Areas',  icon: '✦' },
  { path: '/miniapp',   label: 'Mini App Demo',    icon: '📱' },
  { path: '/tax',       label: 'Tax Vault',        icon: '⬗' },
  { path: '/sms',       label: 'SMS Inbox',        icon: '◻' },
  { path: '/settings',  label: 'Settings',         icon: '⊙' },
]

export default function Sidebar() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <aside style={{
      width: 'var(--sidebar-width)',
      height: '100vh',
      position: 'fixed',
      left: 0, top: 0,
      background: 'var(--color-surface)',
      borderRight: '1px solid var(--color-border)',
      display: 'flex',
      flexDirection: 'column',
      zIndex: 100,
    }}>
      {/* Logo */}
      <div style={{
        padding: '24px 20px 20px',
        borderBottom: '1px solid var(--color-border)',
      }}>
        <div style={{
          fontFamily: 'var(--font-display)',
          fontWeight: 800,
          fontSize: '18px',
          letterSpacing: '-0.02em',
          color: 'var(--color-text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
        }}>
          <span style={{
            width: 32, height: 32,
            background: 'var(--color-green)',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '14px',
            fontWeight: 800,
            color: '#0A0F0D',
            flexShrink: 0,
          }}>M</span>
          M-Okoa
        </div>
        <p style={{
          fontSize: '11px',
          color: 'var(--color-text-muted)',
          marginTop: '4px',
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.06em',
        }}>
          AGENT v1.0 · DARAJA 3.0
        </p>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '12px 10px', overflowY: 'auto' }}>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '9px 12px',
              borderRadius: 'var(--radius-md)',
              marginBottom: '2px',
              fontFamily: 'var(--font-body)',
              fontSize: '13px',
              fontWeight: isActive ? 500 : 400,
              color: isActive ? 'var(--color-green)' : 'var(--color-text-secondary)',
              background: isActive ? 'var(--color-green-muted)' : 'transparent',
              border: isActive
                ? '1px solid rgba(0,214,100,0.12)'
                : '1px solid transparent',
              transition: 'all var(--transition-fast)',
              textDecoration: 'none',
            })}
          >
            <span style={{ fontSize: '15px', width: 20, textAlign: 'center', flexShrink: 0 }}>
              {item.icon}
            </span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* User footer */}
      {user && (
        <div style={{ padding: '16px', borderTop: '1px solid var(--color-border)' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            marginBottom: '12px',
          }}>
            <div style={{
              width: 34, height: 34,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--color-green-dim), var(--color-green))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '13px',
              fontWeight: 700,
              color: '#0A0F0D',
              flexShrink: 0,
            }}>
              {user.full_name.charAt(0).toUpperCase()}
            </div>
            <div style={{ minWidth: 0 }}>
              <p style={{
                fontSize: '13px',
                fontWeight: 500,
                color: 'var(--color-text-primary)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
                {user.full_name.split(' ')[0]}
              </p>
              <p style={{
                fontSize: '11px',
                color: 'var(--color-text-muted)',
                fontFamily: 'var(--font-mono)',
              }}>
                {user.subscription_tier}
              </p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            style={{
              width: '100%',
              padding: '8px',
              background: 'transparent',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--color-text-muted)',
              fontSize: '12px',
              cursor: 'pointer',
              fontFamily: 'var(--font-body)',
              transition: 'all var(--transition-fast)',
            }}
          >
            Sign out
          </button>
        </div>
      )}
    </aside>
  )
}