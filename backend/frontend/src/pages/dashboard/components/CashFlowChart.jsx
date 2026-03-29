import React, { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { format, subDays } from 'date-fns'
import { formatKES } from '../../../lib/decimal'
import Card from '../../../components/ui/Card'

export default function CashFlowChart({ transactions, isLoading }) {
  const chartData = useMemo(() => {
    const days = Array.from({ length: 7 }, (_, i) => {
      const d = subDays(new Date(), 6 - i)
      return { day: format(d, 'EEE'), fullDate: format(d, 'yyyy-MM-dd'), credits: 0, debits: 0 }
    })
    transactions.forEach((txn) => {
      const txnDate = format(new Date(txn.transaction_date), 'yyyy-MM-dd')
      const day = days.find((d) => d.fullDate === txnDate)
      if (!day) return
      const amount = parseFloat(txn.amount_kes)
      if (txn.direction === 'credit') day.credits += amount
      else day.debits += amount
    })
    return days
  }, [transactions])

  return (
    <Card className="animate-fade-up delay-2">
      <div style={{
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', marginBottom: '20px',
      }}>
        <p style={sectionLabel}>Cash Flow — Last 7 Days</p>
        <div style={{ display: 'flex', gap: '16px' }}>
          <LegendDot color="var(--color-green)" label="In" />
          <LegendDot color="var(--color-red)" label="Out" />
        </div>
      </div>

      {isLoading ? (
        <div className="skeleton" style={{ height: '180px', borderRadius: '8px' }} />
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData} barGap={3} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(36,48,40,0.8)" vertical={false} />
            <XAxis
              dataKey="day"
              tick={{ fill: '#4A5E54', fontSize: 11, fontFamily: 'JetBrains Mono' }}
              axisLine={false} tickLine={false}
            />
            <YAxis
              tick={{ fill: '#4A5E54', fontSize: 10, fontFamily: 'JetBrains Mono' }}
              axisLine={false} tickLine={false}
              tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : String(v)}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="credits" fill="var(--color-green)" radius={[4,4,0,0]} maxBarSize={28} opacity={0.85} />
            <Bar dataKey="debits"  fill="var(--color-red)"   radius={[4,4,0,0]} maxBarSize={28} opacity={0.7} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  )
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--color-card)',
      border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-md)',
      padding: '10px 14px',
      boxShadow: 'var(--shadow-float)',
    }}>
      <p style={{
        fontSize: '11px', fontFamily: 'var(--font-mono)',
        color: 'var(--color-text-muted)', marginBottom: '6px', letterSpacing: '0.06em',
      }}>
        {label}
      </p>
      {payload.map((entry) => (
        <p key={entry.name} style={{
          fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 600,
          color: entry.name === 'credits' ? 'var(--color-green)' : 'var(--color-red)',
        }}>
          {entry.name === 'credits' ? '↑' : '↓'} {formatKES(entry.value, { showCents: false })}
        </p>
      ))}
    </div>
  )
}

function LegendDot({ color, label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
      <span style={{ width: 8, height: 8, borderRadius: '2px', background: color, flexShrink: 0 }} />
      <span style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>
        {label}
      </span>
    </div>
  )
}

const sectionLabel = {
  fontSize: '11px', fontFamily: 'var(--font-mono)',
  letterSpacing: '0.08em', textTransform: 'uppercase',
  color: 'var(--color-text-muted)',
}