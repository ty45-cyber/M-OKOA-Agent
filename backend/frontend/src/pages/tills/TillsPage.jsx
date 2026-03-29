import React, { useState } from 'react'
import { useTills } from '../../hooks/useTills'
import { formatKES } from '../../lib/decimal'
import { formatDistanceToNow } from 'date-fns'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import AddTillDrawer from './components/AddTillDrawer'
import TillActionsMenu from './components/TillActionsMenu'
import SmartFloatDrawer from './components/SmartFloatDrawer'

export default function TillsPage() {
  const { tills, isLoading, error, fetchTills, createTill, deactivateTill, queryBalance } = useTills()
  const [showAddDrawer, setShowAddDrawer] = useState(false)
  const [selectedTill, setSelectedTill] = useState(null)
  const [showFloatDrawer, setShowFloatDrawer] = useState(false)
  const [refreshingId, setRefreshingId] = useState(null)

  async function handleRefreshBalance(till) {
    setRefreshingId(till.public_id)
    try {
      await queryBalance(till.public_id, true)
      await fetchTills()
    } finally {
      setRefreshingId(null)
    }
  }

  const tillTypeLabel = (t) =>
    t === 'till' ? 'Buy Goods' : t === 'paybill' ? 'Paybill' : 'Personal'

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'flex-start',
        justifyContent: 'space-between', marginBottom: '32px',
      }}>
        <div>
          <p style={metaLabel}>M-PESA ACCOUNTS</p>
          <h1 style={pageTitle}>Your Tills</h1>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px', marginTop: '4px' }}>
            {tills.length} registered till{tills.length !== 1 ? 's' : ''}
          </p>
        </div>
        <Button onClick={() => setShowAddDrawer(true)}>+ Add Till</Button>
      </div>

      {error && <ErrorBanner message={error} />}

      {/* Grid */}
      {isLoading ? (
        <div style={gridStyle}>
          {[1,2,3].map((i) => (
            <div key={i} className="skeleton" style={{ height: '220px', borderRadius: '16px' }} />
          ))}
        </div>
      ) : tills.length === 0 ? (
        <EmptyState onAdd={() => setShowAddDrawer(true)} />
      ) : (
        <div style={gridStyle}>
          {tills.map((till, idx) => (
            <TillCard
              key={till.public_id}
              till={till}
              animDelay={idx}
              isRefreshing={refreshingId === till.public_id}
              onRefresh={() => handleRefreshBalance(till)}
              onConfigureFloat={() => { setSelectedTill(till); setShowFloatDrawer(true) }}
              onDeactivate={() => deactivateTill(till.public_id)}
              tillTypeLabel={tillTypeLabel(till.till_type)}
            />
          ))}
        </div>
      )}

      <AddTillDrawer
        open={showAddDrawer}
        onClose={() => setShowAddDrawer(false)}
        onCreate={async (payload) => {
          await createTill(payload)
          setShowAddDrawer(false)
        }}
      />

      {selectedTill && (
        <SmartFloatDrawer
          open={showFloatDrawer}
          till={selectedTill}
          onClose={() => { setShowFloatDrawer(false); setSelectedTill(null) }}
        />
      )}
    </div>
  )
}

function TillCard({ till, animDelay, isRefreshing, onRefresh, onConfigureFloat, onDeactivate, tillTypeLabel }) {
  const hasBalance = till.last_known_balance_kes !== null
  const updatedLabel = till.balance_updated_at
    ? formatDistanceToNow(new Date(till.balance_updated_at), { addSuffix: true })
    : 'Never synced'
  const hasFloat = till.float_threshold_kes !== null

  return (
    <Card
      className={`animate-fade-up delay-${animDelay + 1}`}
      style={{ display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}
    >
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: '2px',
        background: till.is_active
          ? 'linear-gradient(90deg, var(--color-green), transparent)'
          : 'var(--color-border)',
      }} />

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div>
          <p style={{
            fontFamily: 'var(--font-display)', fontWeight: 700,
            fontSize: '16px', color: 'var(--color-text-primary)', marginBottom: '4px',
          }}>
            {till.display_name}
          </p>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--color-text-muted)', letterSpacing: '0.06em' }}>
            {till.till_number}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <Badge variant={till.is_active ? 'green' : 'muted'}>{tillTypeLabel}</Badge>
          <TillActionsMenu onRefresh={onRefresh} onConfigureFloat={onConfigureFloat} onDeactivate={onDeactivate} />
        </div>
      </div>

      <div style={{
        padding: '16px', background: 'var(--color-surface)',
        borderRadius: 'var(--radius-md)', marginBottom: '16px',
        border: '1px solid var(--color-border-dim)',
      }}>
        <p style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '6px' }}>
          Current Balance
        </p>
        {isRefreshing ? (
          <div className="skeleton" style={{ height: '28px', width: '60%', borderRadius: '6px' }} />
        ) : (
          <p style={{
            fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '24px',
            color: hasBalance ? 'var(--color-text-primary)' : 'var(--color-text-muted)',
            letterSpacing: '-0.01em',
          }}>
            {hasBalance ? formatKES(till.last_known_balance_kes, { showCents: false }) : '—'}
          </p>
        )}
        <p style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)', marginTop: '4px' }}>
          {updatedLabel}
        </p>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: hasFloat ? 'var(--color-green)' : 'var(--color-text-muted)',
            animation: hasFloat ? 'pulse-green 2s infinite' : 'none',
          }} />
          <p style={{ fontSize: '12px', color: hasFloat ? 'var(--color-text-secondary)' : 'var(--color-text-muted)' }}>
            {hasFloat ? `Auto-move at ${formatKES(till.float_threshold_kes, { showCents: false })}` : 'Smart Float off'}
          </p>
        </div>
        <button
          onClick={onRefresh} disabled={isRefreshing}
          style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', fontSize: '14px', cursor: 'pointer', padding: '4px' }}
          title="Refresh balance"
        >
          <span style={{ display: 'inline-block', animation: isRefreshing ? 'spin 1s linear infinite' : 'none' }}>↻</span>
        </button>
      </div>
    </Card>
  )
}

function EmptyState({ onAdd }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: '320px', gap: '16px',
      border: '1px dashed var(--color-border)', borderRadius: 'var(--radius-xl)',
    }}>
      <span style={{ fontSize: '40px', opacity: 0.3 }}>⬡</span>
      <p style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '18px', color: 'var(--color-text-primary)' }}>
        No tills registered
      </p>
      <p style={{ color: 'var(--color-text-muted)', fontSize: '14px', textAlign: 'center', maxWidth: '280px', lineHeight: 1.6 }}>
        Add your M-Pesa Till or Paybill to start tracking balances and automating transfers.
      </p>
      <Button onClick={onAdd}>+ Add Your First Till</Button>
    </div>
  )
}

function ErrorBanner({ message }) {
  return (
    <div style={{
      padding: '12px 16px', background: 'var(--color-red-dim)',
      border: '1px solid rgba(255,77,77,0.25)', borderRadius: 'var(--radius-md)',
      color: 'var(--color-red)', fontSize: '13px', marginBottom: '24px',
    }}>
      {message}
    </div>
  )
}

const gridStyle = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }
const metaLabel = { fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', color: 'var(--color-text-muted)', textTransform: 'uppercase', marginBottom: '6px' }
const pageTitle = { fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: '28px', letterSpacing: '-0.02em', color: 'var(--color-text-primary)' }