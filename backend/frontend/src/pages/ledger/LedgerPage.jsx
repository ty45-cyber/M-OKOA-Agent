import React, { useCallback, useEffect, useState } from 'react'
import api from '../../lib/api'
import { formatKES } from '../../lib/decimal'
import { format } from 'date-fns'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'

const STATUS_BADGE = { completed: 'green', pending: 'amber', failed: 'red', reversed: 'muted' }
const TYPE_LABELS = { c2b_receive: 'Received', b2c_send: 'Sent', stk_push: 'STK Push', bill_payment: 'Bill', float_transfer: 'Float', tax_lock: 'Tax Lock', sms_import: 'SMS Import' }

export default function LedgerPage() {
  const [data, setData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [directionFilter, setDirectionFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [error, setError] = useState(null)

  const fetchTransactions = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ page: String(page), page_size: '20', ...(directionFilter && { direction: directionFilter }), ...(statusFilter && { status: statusFilter }) })
      const { data: res } = await api.get(`/api/v1/transactions/?${params}`)
      setData(res)
    } catch {
      setError('Failed to load transactions.')
    } finally {
      setIsLoading(false)
    }
  }, [page, directionFilter, statusFilter])

  useEffect(() => { fetchTransactions() }, [fetchTransactions])

  return (
    <div className="animate-fade-in">
      <div style={{ marginBottom: '28px' }}>
        <p style={metaLabel}>FINANCIAL RECORDS</p>
        <h1 style={pageTitle}>Transaction Ledger</h1>
        {data && <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px', marginTop: '4px' }}>{data.total.toLocaleString()} total transactions</p>}
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', flexWrap: 'wrap' }}>
        {[['All',''],['↑ Money In','credit'],['↓ Money Out','debit']].map(([label, val]) => (
          <FilterChip key={label} label={label} active={directionFilter === val} onClick={() => { setDirectionFilter(val); setPage(1) }} />
        ))}
        <div style={{ width: '1px', background: 'var(--color-border)', margin: '0 4px' }} />
        {[['All Status',''],['Completed','completed'],['Pending','pending'],['Failed','failed']].map(([label, val]) => (
          <FilterChip key={label} label={label} active={statusFilter === val} onClick={() => { setStatusFilter(val); setPage(1) }} />
        ))}
      </div>

      {error && <div style={{ padding: '12px 16px', background: 'var(--color-red-dim)', border: '1px solid rgba(255,77,77,0.25)', borderRadius: 'var(--radius-md)', color: 'var(--color-red)', fontSize: '13px', marginBottom: '20px' }}>{error}</div>}

      <Card padding="none" className="animate-fade-up">
        {/* Column headers */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.2fr 1fr 1fr 1fr', padding: '10px 24px', borderBottom: '1px solid var(--color-border)' }}>
          {['Transaction','Date','Type','Status','Amount'].map((h) => (
            <span key={h} style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', textAlign: h === 'Amount' ? 'right' : 'left' }}>{h}</span>
          ))}
        </div>

        {isLoading ? (
          <div style={{ padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {Array.from({ length: 8 }).map((_, i) => <div key={i} className="skeleton" style={{ height: '44px', borderRadius: '8px' }} />)}
          </div>
        ) : !data?.items.length ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '14px' }}>No transactions found.</div>
        ) : (
          data.items.map((txn, idx) => <LedgerRow key={txn.public_id} txn={txn} isLast={idx === data.items.length - 1} />)
        )}

        {data && data.total_pages > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 24px', borderTop: '1px solid var(--color-border)' }}>
            <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>Page {data.page} of {data.total_pages}</p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <PagBtn label="← Prev" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} />
              <PagBtn label="Next →" disabled={page >= data.total_pages} onClick={() => setPage((p) => p + 1)} />
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}

function LedgerRow({ txn, isLast }) {
  const isCredit = txn.direction === 'credit'
  const label = txn.counterparty_name ?? txn.description?.slice(0, 35) ?? TYPE_LABELS[txn.transaction_type] ?? txn.transaction_type

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.2fr 1fr 1fr 1fr', alignItems: 'center', padding: '12px 24px', borderBottom: isLast ? 'none' : '1px solid var(--color-border-dim)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
        <span style={{ width: 26, height: 26, borderRadius: '7px', flexShrink: 0, background: isCredit ? 'var(--color-green-muted)' : 'var(--color-red-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 700, color: isCredit ? 'var(--color-green)' : 'var(--color-red)' }}>
          {isCredit ? '↑' : '↓'}
        </span>
        <div style={{ minWidth: 0 }}>
          <p style={{ fontSize: '13px', color: 'var(--color-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</p>
          {txn.mpesa_receipt_number && <p style={{ fontSize: '10px', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>{txn.mpesa_receipt_number}</p>}
        </div>
      </div>
      <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}>{format(new Date(txn.transaction_date), 'dd MMM HH:mm')}</span>
      <Badge variant="muted">{TYPE_LABELS[txn.transaction_type] ?? txn.transaction_type}</Badge>
      <Badge variant={STATUS_BADGE[txn.status] ?? 'muted'}>{txn.status}</Badge>
      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '14px', textAlign: 'right', color: txn.status === 'failed' ? 'var(--color-text-muted)' : isCredit ? 'var(--color-green)' : 'var(--color-text-primary)' }}>
        {isCredit ? '+' : '-'}{formatKES(txn.amount_kes, { showCents: false })}
      </span>
    </div>
  )
}

function FilterChip({ label, active, onClick }) {
  return (
    <button onClick={onClick} style={{ padding: '6px 14px', background: active ? 'var(--color-green-muted)' : 'var(--color-card)', border: `1px solid ${active ? 'rgba(0,214,100,0.25)' : 'var(--color-border)'}`, borderRadius: 'var(--radius-full)', color: active ? 'var(--color-green)' : 'var(--color-text-secondary)', fontSize: '12px', fontFamily: 'var(--font-body)', cursor: 'pointer', fontWeight: active ? 600 : 400 }}>
      {label}
    </button>
  )
}

function PagBtn({ label, disabled, onClick }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{ padding: '6px 14px', background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: disabled ? 'var(--color-text-muted)' : 'var(--color-text-primary)', fontSize: '12px', fontFamily: 'var(--font-mono)', cursor: disabled ? 'not-allowed' : 'pointer' }}>
      {label}
    </button>
  )
}

const metaLabel = { fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', color: 'var(--color-text-muted)', textTransform: 'uppercase', marginBottom: '6px' }
const pageTitle = { fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: '28px', letterSpacing: '-0.02em', color: 'var(--color-text-primary)' }