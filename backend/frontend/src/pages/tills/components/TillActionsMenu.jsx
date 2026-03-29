import React, { useRef, useState, useEffect } from 'react'

export default function TillActionsMenu({ onRefresh, onConfigureFloat, onDeactivate }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const actions = [
    { label: '↻  Refresh Balance', onClick: onRefresh,       color: 'var(--color-text-primary)' },
    { label: '⚡  Smart Float',    onClick: onConfigureFloat,  color: 'var(--color-green)' },
    { label: '✕  Deactivate',      onClick: onDeactivate,      color: 'var(--color-red)' },
  ]

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{ width: 32, height: 32, borderRadius: 'var(--radius-md)', background: open ? 'var(--color-card)' : 'transparent', border: '1px solid ' + (open ? 'var(--color-border)' : 'transparent'), color: 'var(--color-text-muted)', fontSize: '16px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all var(--transition-fast)' }}
      >
        ⋯
      </button>
      {open && (
        <div style={{ position: 'absolute', top: '100%', right: 0, marginTop: '4px', background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-float)', zIndex: 50, minWidth: '180px', overflow: 'hidden', animation: 'fadeUp 150ms both' }}>
          {actions.map((action) => (
            <button key={action.label} onClick={() => { action.onClick(); setOpen(false) }} style={{ width: '100%', padding: '10px 16px', background: 'none', border: 'none', color: action.color, fontSize: '13px', fontFamily: 'var(--font-body)', cursor: 'pointer', textAlign: 'left', transition: 'background var(--transition-fast)' }}>
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}