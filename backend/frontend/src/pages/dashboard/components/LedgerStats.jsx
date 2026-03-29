import React from 'react'
import { formatKES } from '../../../lib/decimal'
import Card from '../../../components/ui/Card'

export default function LedgerStats({ summary, isLoading }) {
  return (
    <Card className="animate-fade-up delay-2">
      <p style={sectionLabel}>{summary?.period_label ?? 'This Month'}</p>
      {isLoading || !summary ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
          {[1,2,3].map((i) => (
            <div key={i} className="skeleton" style={{ height: '48px', borderRadius: '8px' }} />
          ))}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '16px' }}>
          <StatRow label="Money In"  value={summary.total_credits_kes} color="var(--color-green)" prefix="↑" />
          <StatRow label="Money Out" value={summary.total_debits_kes}  color="var(--color-red)"   prefix="↓" />
          <div style={{ height: '1px', background: 'var(--color-border)', margin: '4px 0' }} />
          <StatRow
            label="Net"
            value={summary.net_kes}
            color={parseFloat(summary.net_kes) >= 0 ? 'var(--color-green)' : 'var(--color-red)'}
            prefix="="
            bold
          />
          <p style={{
            fontSize: '11px', color: 'var(--color-text-muted)',
            fontFamily: 'var(--font-mono)', marginTop: '4px',
          }}>
            {summary.transaction_count} transactions
          </p>
        </div>
      )}
    </Card>
  )
}

function StatRow({ label, value, color, prefix, bold = false }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center',
      justifyContent: 'space-between',
      padding: '10px 12px',
      background: 'var(--color-surface)',
      borderRadius: 'var(--radius-md)',
      border: '1px solid var(--color-border-dim)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ color, fontSize: '14px', fontFamily: 'var(--font-mono)' }}>{prefix}</span>
        <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>{label}</span>
      </div>
      <span style={{
        fontFamily: 'var(--font-mono)', fontWeight: bold ? 700 : 500,
        fontSize: '14px', color,
      }}>
        {formatKES(value, { showCents: false })}
      </span>
    </div>
  )
}

const sectionLabel = {
  fontSize: '11px', fontFamily: 'var(--font-mono)',
  letterSpacing: '0.08em', textTransform: 'uppercase',
  color: 'var(--color-text-muted)',
}