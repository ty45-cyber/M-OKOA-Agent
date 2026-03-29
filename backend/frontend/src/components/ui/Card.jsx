import React from 'react'

export default function Card({
  children,
  className,
  style,
  onClick,
  glow = false,
  padding = 'md',
}) {
  const paddingMap = { none: '0', sm: '16px', md: '24px', lg: '32px' }

  return (
    <div
      onClick={onClick}
      className={className}
      style={{
        background: 'var(--color-card)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        padding: paddingMap[padding],
        boxShadow: glow
          ? 'var(--shadow-card), var(--shadow-green)'
          : 'var(--shadow-card)',
        transition: 'all var(--transition-normal)',
        cursor: onClick ? 'pointer' : undefined,
        ...style,
      }}
    >
      {children}
    </div>
  )
}