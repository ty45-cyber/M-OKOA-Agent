import React from 'react'
import { formatKES } from '../../../lib/decimal'
import Card from '../../../components/ui/Card'
import { formatDistanceToNow } from 'date-fns'

export default function TillBalanceGrid({ balances, isLoading }) {
  if (isLoading) {
    return (
      <Card className="animate-fade-up delay-1">
        <p style={sectionLabel}>Your Tills</p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          {[1,2,3,4].map((i) => (
            <div key={i} className="skeleton" style={{ height: '72px', borderRadius: '10px' }} />
          ))}
        </div>
      </Card>
    )
  }

  if (!balances.length) {
    return (
      <Card className="animate-fade-up delay-1" style={{
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        minHeight: '180px', gap: '12px',
      }}>
        <p style={{ fontSize: '28px' }}>⬡</p>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px', textAlign: 'center' }}>
          No tills registered yet.
        </p>
        <a href="/tills" style={{ fontSize: '13px', color: 'var(--color-green)', fontWeight: 500 }}>
          Add your first till →
        </a>
      </Card>
    )
  }

  return (
    <Card className="animate-fade-up delay-1">
      <div style={{
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', marginBottom: '16px',
      }}>
        <p style={sectionLabel}>Your Tills</p>
        <a href="/tills" style={{ fontSize: '12px', color: 'var(--color-green)', fontWeight: 500 }}>
          Manage →
        </a>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
        gap: '12px',
      }}>
        {balances.map((b) => (
          <div key={b.till_public_id} style={{
            padding: '14px',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
          }}>
            <p style={{
              fontSize: '11px', color: 'var(--color-text-muted)',
              fontFamily: 'var(--font-mono)', letterSpacing: '0.04em',
              marginBottom: '6px', overflow: 'hidden',
              textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {b.display_name}
            </p>
            <p style={{
              fontFamily: 'var(--font-mono)', fontWeight: 600,
              fontSize: '18px', color: 'var(--color-text-primary)',
              letterSpacing: '-0.01em',
            }}>
              {formatKES(b.balance_kes, { showCents: false })}
            </p>
            <p style={{
              fontSize: '10px', color: 'var(--color-text-muted)',
              marginTop: '4px', fontFamily: 'var(--font-mono)',
            }}>
              {b.updated_at
                ? formatDistanceToNow(new Date(b.updated_at), { addSuffix: true })
                : 'Never synced'}
            </p>
          </div>
        ))}
      </div>
    </Card>
  )
}

const sectionLabel = {
  fontSize: '11px', fontFamily: 'var(--font-mono)',
  letterSpacing: '0.08em', textTransform: 'uppercase',
  color: 'var(--color-text-muted)',
}