import React from 'react'

const variantStyles = {
  green: { background: 'var(--color-green-muted)', color: 'var(--color-green)', border: '1px solid rgba(0,214,100,0.2)' },
  amber: { background: 'var(--color-amber-dim)', color: 'var(--color-amber)', border: '1px solid rgba(245,166,35,0.25)' },
  red:   { background: 'var(--color-red-dim)',   color: 'var(--color-red)',   border: '1px solid rgba(255,77,77,0.25)' },
  blue:  { background: 'rgba(77,158,255,0.1)',   color: 'var(--color-blue)', border: '1px solid rgba(77,158,255,0.2)' },
  muted: { background: 'var(--color-surface)',   color: 'var(--color-text-muted)', border: '1px solid var(--color-border)' },
}

export default function Badge({ variant = 'muted', children, dot = false }) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '5px',
      padding: '2px 10px',
      borderRadius: 'var(--radius-full)',
      fontSize: '11px',
      fontWeight: 600,
      fontFamily: 'var(--font-body)',
      letterSpacing: '0.04em',
      textTransform: 'uppercase',
      ...variantStyles[variant],
    }}>
      {dot && (
        <span style={{
          width: 5, height: 5,
          borderRadius: '50%',
          background: 'currentColor',
          animation: variant === 'green' ? 'pulse-green 2s infinite' : undefined,
        }} />
      )}
      {children}
    </span>
  )
}