/**
 * Button — primary interactive element.
 */
import React from 'react'

export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  fullWidth = false,
  disabled,
  className,
  children,
  style,
  ...props
}) {
  const base = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    fontFamily: 'var(--font-body)',
    fontWeight: 500,
    borderRadius: 'var(--radius-md)',
    border: 'none',
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    transition: 'all var(--transition-fast)',
    position: 'relative',
    whiteSpace: 'nowrap',
    letterSpacing: '0.01em',
    width: fullWidth ? '100%' : undefined,
    opacity: disabled || loading ? 0.65 : 1,
  }

  const sizes = {
    sm: { height: '34px', padding: '0 12px', fontSize: '13px' },
    md: { height: '44px', padding: '0 18px', fontSize: '14px' },
    lg: { height: '52px', padding: '0 24px', fontSize: '16px' },
  }

  const variants = {
    primary: {
      background: 'var(--color-green)',
      color: 'var(--color-text-inverse)',
    },
    secondary: {
      background: 'var(--color-card)',
      color: 'var(--color-text-primary)',
      border: '1px solid var(--color-border)',
    },
    danger: {
      background: 'var(--color-red-dim)',
      color: 'var(--color-red)',
      border: '1px solid rgba(255,77,77,0.25)',
    },
    ghost: {
      background: 'transparent',
      color: 'var(--color-text-secondary)',
    },
  }

  return (
    <button
      disabled={disabled || loading}
      style={{ ...base, ...sizes[size], ...variants[variant], ...style }}
      {...props}
    >
      {loading && (
        <span style={{
          width: 14, height: 14,
          border: '2px solid currentColor',
          borderTopColor: 'transparent',
          borderRadius: '50%',
          display: 'inline-block',
          animation: 'spin 0.7s linear infinite',
        }} />
      )}
      <span style={{ opacity: loading ? 0.7 : 1 }}>{children}</span>
    </button>
  )
}