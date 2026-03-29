import React, { useEffect, useState } from 'react'
import api from '../../../lib/api'

const MODES = [
  { mode: 'merchant',  label: 'Merchant', tagline: 'Auto-reconcile Lipa na M-Pesa', icon: '⬡', color: '#00D664' },
  { mode: 'farmer',   label: 'Farmer',   tagline: 'Instant crop payouts via B2C',   icon: '◈', color: '#F5A623' },
  { mode: 'student',  label: 'Student',  tagline: 'Fees direct to institution',      icon: '◻', color: '#4D9EFF' },
  { mode: 'community',label: 'Chama',    tagline: 'Group wallet transparency',       icon: '⬗', color: '#9B59B6' },
]

function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  if (!result) return '0,214,100'
  return `${parseInt(result[1], 16)},${parseInt(result[2], 16)},${parseInt(result[3], 16)}`
}

export default function DomainModeSwitcher() {
  const [activeMode, setActiveMode] = useState('general')
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    api.get('/api/v1/domain/current')
      .then(({ data }) => setActiveMode(data.current_mode))
      .catch(() => {})
  }, [])

  async function handleSwitch(mode) {
    if (mode === activeMode || isLoading) return
    setIsLoading(true)
    try {
      await api.post('/api/v1/domain/set', { mode })
      setActiveMode(mode)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div style={{ marginBottom: '24px' }}>
      <p style={{
        fontSize: '11px', fontFamily: 'var(--font-mono)',
        letterSpacing: '0.1em', textTransform: 'uppercase',
        color: 'var(--color-text-muted)', marginBottom: '10px',
      }}>
        Money in Motion — Challenge Area
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
        {MODES.map((m) => {
          const isActive = activeMode === m.mode
          return (
            <button
              key={m.mode}
              onClick={() => handleSwitch(m.mode)}
              disabled={isLoading}
              style={{
                padding: '14px 12px',
                background: isActive
                  ? `rgba(${hexToRgb(m.color)}, 0.08)`
                  : 'var(--color-card)',
                border: `1px solid ${isActive
                  ? `rgba(${hexToRgb(m.color)}, 0.3)`
                  : 'var(--color-border)'}`,
                borderRadius: 'var(--radius-lg)',
                cursor: isLoading ? 'not-allowed' : 'pointer',
                textAlign: 'left',
                transition: 'all var(--transition-normal)',
                position: 'relative', overflow: 'hidden',
              }}
            >
              {isActive && (
                <div style={{
                  position: 'absolute', top: 0, left: 0, right: 0,
                  height: '2px', background: m.color,
                }} />
              )}
              <div style={{ fontSize: '20px', marginBottom: '8px' }}>{m.icon}</div>
              <p style={{
                fontFamily: 'var(--font-display)', fontWeight: 700,
                fontSize: '13px',
                color: isActive ? m.color : 'var(--color-text-primary)',
                marginBottom: '3px',
              }}>
                {m.label}
              </p>
              <p style={{ fontSize: '11px', color: 'var(--color-text-muted)', lineHeight: 1.4 }}>
                {m.tagline}
              </p>
              {isActive && (
                <div style={{
                  marginTop: '8px', padding: '4px 8px',
                  background: `rgba(${hexToRgb(m.color)}, 0.12)`,
                  borderRadius: 'var(--radius-full)',
                  display: 'inline-flex', alignItems: 'center', gap: '4px',
                }}>
                  <span style={{ width: 5, height: 5, borderRadius: '50%', background: m.color }} />
                  <span style={{
                    fontSize: '10px', color: m.color,
                    fontFamily: 'var(--font-mono)', letterSpacing: '0.04em',
                  }}>ACTIVE</span>
                </div>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}