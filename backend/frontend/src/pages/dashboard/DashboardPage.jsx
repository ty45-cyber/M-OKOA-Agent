import React from 'react'
import { useAuthStore } from '../../store/auth.store'
import { useDashboard } from '../../hooks/useDashboard'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import TotalBalanceCard from './components/TotalBalanceCard'
import TillBalanceGrid from './components/TillBalanceGrid'
import CashFlowChart from './components/CashFlowChart'
import RecentTransactions from './components/RecentTransactions'
import LedgerStats from './components/LedgerStats'
import DomainModeSwitcher from './components/DomainModeSwitcher'

export default function DashboardPage() {
  const { user } = useAuthStore()
  const { data, isLoading, error, refetch } = useDashboard()

  const firstName = user?.full_name.split(' ')[0] ?? 'there'
  const hour = new Date().getHours()
  const greeting =
    hour < 12 ? 'Habari ya asubuhi'
    : hour < 17 ? 'Habari ya mchana'
    : 'Habari ya jioni'

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'flex-start',
        justifyContent: 'space-between', marginBottom: '24px',
      }}>
        <div>
          <p style={{
            fontSize: '12px', fontFamily: 'var(--font-mono)',
            letterSpacing: '0.08em', color: 'var(--color-text-muted)',
            textTransform: 'uppercase', marginBottom: '6px',
          }}>
            {greeting}
          </p>
          <h1 style={{
            fontFamily: 'var(--font-display)', fontWeight: 800,
            fontSize: '28px', letterSpacing: '-0.02em',
            color: 'var(--color-text-primary)',
          }}>
            {firstName} 👋
          </h1>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <Badge variant={user?.is_verified ? 'green' : 'amber'} dot>
            {user?.is_verified ? 'Verified' : 'Unverified'}
          </Badge>
          <Badge variant="muted">{user?.subscription_tier}</Badge>
          <button
            onClick={refetch} disabled={isLoading}
            style={{
              padding: '8px 16px',
              background: 'var(--color-card)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--color-text-secondary)',
              fontSize: '12px', fontFamily: 'var(--font-body)',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', gap: '6px',
            }}
          >
            <span style={{ display: 'inline-block', animation: isLoading ? 'spin 1s linear infinite' : 'none' }}>↻</span>
            Refresh
          </button>
        </div>
      </div>

      {/* Domain Mode Switcher */}
      <DomainModeSwitcher />

      {error && (
        <div style={{
          padding: '14px 18px',
          background: 'var(--color-red-dim)',
          border: '1px solid rgba(255,77,77,0.25)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--color-red)',
          fontSize: '13px', marginBottom: '24px',
        }}>
          {error}
        </div>
      )}

      {/* Row 1 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: '20px', marginBottom: '20px' }}>
        <TotalBalanceCard totalBalance={data.totalBalance} isLoading={isLoading} />
        <TillBalanceGrid balances={data.balances} isLoading={isLoading} />
      </div>

      {/* Row 2 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '20px', marginBottom: '20px' }}>
        <LedgerStats summary={data.ledgerSummary} isLoading={isLoading} />
        <CashFlowChart transactions={data.recentTransactions} isLoading={isLoading} />
      </div>

      {/* Row 3 */}
      <RecentTransactions transactions={data.recentTransactions} isLoading={isLoading} />
    </div>
  )
}