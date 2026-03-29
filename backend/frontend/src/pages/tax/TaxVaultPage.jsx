import React, { useEffect, useState } from 'react'
import api from '../../lib/api'
import { formatKES } from '../../lib/decimal'
import { format } from 'date-fns'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'

const TAX_INFO = {
  dst: { label: 'Digital Services Tax', rate: '1.5%', desc: 'Applicable on digital service inflows per KRA guidelines.' },
  vat: { label: 'Value Added Tax',       rate: '16%',  desc: 'Applicable for VAT-registered enterprises.' },
  income_tax:  { label: 'Income Tax',       rate: 'Variable', desc: 'Annual income tax provisioning.' },
  presumptive: { label: 'Presumptive Tax',  rate: 'Variable', desc: 'Applicable for small businesses.' },
}

export default function TaxVaultPage() {
  const [summary, setSummary] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function fetchTaxSummary() {
      setIsLoading(true)
      try {
        const currentPeriod = format(new Date(), 'yyyy-MM')
        const { data } = await api.get(`/api/v1/transactions/summary/ledger?period_month=${currentPeriod}`)
        setSummary({
          period_month: currentPeriod,
          breakdown: { dst: String(parseFloat(data.total_credits_kes) * 0.015) },
          total_locked_kes: String(parseFloat(data.total_credits_kes) * 0.015),
        })
      } catch {
        setError('Failed to load tax summary.')
      } finally {
        setIsLoading(false)
      }
    }
    fetchTaxSummary()
  }, [])

  const currentMonth = format(new Date(), 'MMMM yyyy')
  const totalLocked = parseFloat(summary?.total_locked_kes ?? '0')

  return (
    <div className="animate-fade-in">
      <div style={{ marginBottom: '32px' }}>
        <p style={metaLabel}>KRA COMPLIANCE</p>
        <h1 style={pageTitle}>Tax Vault</h1>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px', marginTop: '4px' }}>{currentMonth} · Auto-locked from M-Pesa inflows</p>
      </div>

      {error && <div style={{ padding: '12px 16px', background: 'var(--color-red-dim)', border: '1px solid rgba(255,77,77,0.25)', borderRadius: 'var(--radius-md)', color: 'var(--color-red)', fontSize: '13px', marginBottom: '24px' }}>{error}</div>}

      {/* Hero row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
        <Card className="animate-fade-up" style={{ background: 'linear-gradient(145deg, #1A1F0F 0%, #111508 100%)', border: '1px solid rgba(245,166,35,0.2)', position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: -40, right: -40, width: 160, height: 160, borderRadius: '50%', background: 'radial-gradient(circle, rgba(245,166,35,0.1) 0%, transparent 70%)', pointerEvents: 'none' }} />
          <p style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-amber)', opacity: 0.8, marginBottom: '12px' }}>Total Locked — {currentMonth}</p>
          {isLoading ? (
            <div className="skeleton" style={{ height: '36px', width: '60%', borderRadius: '6px' }} />
          ) : (
            <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '32px', letterSpacing: '-0.02em', color: 'var(--color-text-primary)' }}>
              {formatKES(totalLocked, { showCents: false })}
            </p>
          )}
          <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '8px' }}>🔒 Reserved for KRA filing</p>
        </Card>

        <Card className="animate-fade-up delay-1">
          <p style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '16px' }}>Filing Status</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <StatusRow label="DST (1.5%)" status="locked" />
            <StatusRow label="VAT (16%)"  status="not_applicable" />
            <div style={{ padding: '10px 12px', background: 'var(--color-green-muted)', border: '1px solid rgba(0,214,100,0.15)', borderRadius: 'var(--radius-md)', fontSize: '12px', color: 'var(--color-green)' }}>
              ✓ Auto-locking is active. Tax is deducted on every inflow.
            </div>
          </div>
        </Card>
      </div>

      {/* Breakdown */}
      <Card className="animate-fade-up delay-2">
        <p style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '20px' }}>Tax Breakdown</p>
        {isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {[1,2].map((i) => <div key={i} className="skeleton" style={{ height: '80px', borderRadius: '10px' }} />)}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {summary && Object.entries(summary.breakdown).map(([taxType, amount]) => {
              const info = TAX_INFO[taxType]
              if (!info) return null
              return <TaxBreakdownCard key={taxType} label={info.label} rate={info.rate} desc={info.desc} amount={parseFloat(amount)} />
            })}
            {(!summary || Object.keys(summary.breakdown).length === 0) && (
              <p style={{ color: 'var(--color-text-muted)', fontSize: '14px', textAlign: 'center', padding: '24px' }}>
                No tax locked yet this month. Tax is calculated on your first inflow.
              </p>
            )}
          </div>
        )}
      </Card>

      {/* KRA reminders */}
      <Card className="animate-fade-up delay-3" style={{ marginTop: '20px', background: 'var(--color-surface)', border: '1px solid var(--color-border-dim)' }}>
        <p style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '16px' }}>KRA Filing Reminders</p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {[
            { label: 'DST Filing',     date: '20th of following month', desc: 'Digital Services Tax return via iTax' },
            { label: 'VAT Return',     date: '20th of following month', desc: 'If VAT-registered (enterprises only)' },
            { label: 'Monthly Rental', date: '20th of following month', desc: 'If applicable to your business' },
          ].map((item) => (
            <div key={item.label} style={{ display: 'flex', gap: '14px', alignItems: 'flex-start', padding: '12px', background: 'var(--color-card)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border-dim)' }}>
              <span style={{ color: 'var(--color-amber)', fontSize: '16px', flexShrink: 0 }}>⬗</span>
              <div>
                <p style={{ fontSize: '13px', fontWeight: 500, color: 'var(--color-text-primary)' }}>
                  {item.label}
                  <span style={{ marginLeft: '8px', fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-amber)' }}>Due: {item.date}</span>
                </p>
                <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '2px' }}>{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

function TaxBreakdownCard({ label, rate, desc, amount }) {
  return (
    <div style={{ padding: '16px', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <p style={{ fontSize: '14px', fontWeight: 500, color: 'var(--color-text-primary)' }}>{label}</p>
          <Badge variant="amber">{rate}</Badge>
        </div>
        <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', maxWidth: '320px' }}>{desc}</p>
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: '16px' }}>
        <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '18px', color: 'var(--color-amber)' }}>{formatKES(amount, { showCents: false })}</p>
        <p style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>🔒 locked</p>
      </div>
    </div>
  )
}

function StatusRow({ label, status }) {
  const variant = status === 'locked' ? 'amber' : status === 'filed' ? 'green' : 'muted'
  const statusLabel = status === 'locked' ? 'Locked' : status === 'filed' ? 'Filed' : 'N/A'
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', background: 'var(--color-surface)', border: '1px solid var(--color-border-dim)', borderRadius: 'var(--radius-md)' }}>
      <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>{label}</p>
      <Badge variant={variant}>{statusLabel}</Badge>
    </div>
  )
}

const metaLabel = { fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', color: 'var(--color-text-muted)', textTransform: 'uppercase', marginBottom: '6px' }
const pageTitle = { fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: '28px', letterSpacing: '-0.02em', color: 'var(--color-text-primary)' }