import React from 'react'
import { Outlet } from 'react-router-dom'

export default function AuthLayout() {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      minHeight: '100vh',
    }}>
      {/* Left brand panel */}
      <div style={{
        background: 'var(--color-surface)',
        borderRight: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        padding: '64px',
        position: 'relative',
        overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: `
            linear-gradient(var(--color-border) 1px, transparent 1px),
            linear-gradient(90deg, var(--color-border) 1px, transparent 1px)
          `,
          backgroundSize: '48px 48px',
          opacity: 0.4,
        }} />
        <div style={{
          position: 'absolute',
          bottom: -80, left: -80,
          width: 320, height: 320,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(0,214,100,0.15) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        <div style={{ position: 'relative', zIndex: 1 }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            marginBottom: '48px',
          }}>
            <div style={{
              width: 44, height: 44,
              background: 'var(--color-green)',
              borderRadius: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: 'var(--font-display)',
              fontWeight: 800,
              fontSize: '18px',
              color: '#0A0F0D',
            }}>M</div>
            <span style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 800,
              fontSize: '22px',
              letterSpacing: '-0.02em',
            }}>M-Okoa Agent</span>
          </div>

          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 800,
            fontSize: '40px',
            lineHeight: 1.1,
            letterSpacing: '-0.03em',
            marginBottom: '20px',
            color: 'var(--color-text-primary)',
          }}>
            Your M-Pesa<br />
            <span style={{ color: 'var(--color-green)' }}>Co-pilot.</span>
          </h1>

          <p style={{
            color: 'var(--color-text-secondary)',
            fontSize: '16px',
            lineHeight: 1.7,
            maxWidth: '360px',
          }}>
            Manage tills, pay bills, move float, and stay KRA-compliant — all from one intelligent dashboard.
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '40px' }}>
            {['Smart Float', 'Auto Tax', 'Bill Pay', 'SMS Import', 'Telegram Bot'].map((f) => (
              <span key={f} style={{
                padding: '6px 14px',
                background: 'var(--color-green-muted)',
                border: '1px solid rgba(0,214,100,0.15)',
                borderRadius: 'var(--radius-full)',
                fontSize: '12px',
                color: 'var(--color-green)',
                fontWeight: 500,
              }}>{f}</span>
            ))}
          </div>
        </div>
      </div>

      {/* Right form panel */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px',
        background: 'var(--color-base)',
      }}>
        <div style={{ width: '100%', maxWidth: '400px' }}>
          <Outlet />
        </div>
      </div>
    </div>
  )
}