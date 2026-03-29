import React from 'react'
import { formatKES } from '../../../lib/decimal'
import Card from '../../../components/ui/Card'

export default function TotalBalanceCard({ totalBalance, isLoading }) {
  return (
    <Card glow className="animate-fade-up" style={{
      background: 'linear-gradient(145deg, #1A2E24 0%, #0F1F18 100%)',
      border: '1px solid rgba(0,214,100,0.2)',
      minHeight: '180px',
      display: 'flex', flexDirection: 'column',
      justifyContent: 'space-between',
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute', top: -40, right: -40,
        width: 180, height: 180, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(0,214,100,0.1) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      <div>
        <p style={{
          fontSize: '11px', fontFamily: 'var(--font-mono)',
          letterSpacing: '0.1em', textTransform: 'uppercase',
          color: 'var(--color-green)', opacity: 0.8, marginBottom: '12px',
        }}>
          Total Float Balance
        </p>
        {isLoading ? (
          <div className="skeleton" style={{ width: '70%', height: '44px', borderRadius: '8px' }} />
        ) : (
          <div>
            <p style={{
              fontFamily: 'var(--font-mono)', fontWeight: 600,
              fontSize: '36px', letterSpacing: '-0.02em',
              color: 'var(--color-text-primary)', lineHeight: 1.1,
            }}>
              {formatKES(totalBalance, { showCents: false })}
            </p>
            <p style={{
              fontFamily: 'var(--font-mono)', fontSize: '13px',
              color: 'var(--color-text-muted)', marginTop: '4px',
            }}>
              {formatKES(totalBalance).replace('KES ', '')} KES
            </p>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '20px' }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          background: 'var(--color-green)',
          animation: 'pulse-green 2s infinite', flexShrink: 0,
        }} />
        <p style={{
          fontSize: '12px', color: 'var(--color-text-secondary)',
          fontFamily: 'var(--font-mono)',
        }}>
          Across all active tills
        </p>
      </div>
    </Card>
  )
}