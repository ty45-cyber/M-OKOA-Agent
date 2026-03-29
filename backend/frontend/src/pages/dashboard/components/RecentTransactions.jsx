import React from 'react'
import { formatKES } from '../../../lib/decimal'
import Card from '../../../components/ui/Card'
import Badge from '../../../components/ui/Badge'
import { format } from 'date-fns'

const TYPE_LABELS = {
  c2b_receive: 'Received', b2c_send: 'Sent', stk_push: 'STK Push',
  bill_payment: 'Bill', float_transfer: 'Float Move',
  tax_lock: 'Tax Lock', sms_import: 'SMS Import',
}

export default function RecentTransactions({ transactions, isLoading }) {
  return (
    <Card className="animate-fade-up delay-3" padding="none">
      <div style={{
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between',
        padding: '20px 24px 16px',
        borderBottom: '1px solid var(--color-border)',
      }}>
        <p style={sectionLabel}>Recent Transactions</p>
        <a href="/ledger" style={{ fontSize: '12px', color: 'var(--color-green)', fontWeight: 500 }}>
          View all →
        </a>
      </div>

      {isLoading ? (
        <div style={{ padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {[1,2,3,4,5].map((i) => (
            <div key={i} className="skeleton" style={{ height: '44px', borderRadius: '8px' }} />
          ))}
        </div>
      ) : transactions.length === 0 ? (
        <div style={{ padding: '48px', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '14px' }}>
          No transactions yet.
        </div>
      ) : (
        <div>
          <div style={{
            display: 'grid', gridTemplateColumns: '2fr 1.5fr 1fr 1fr',
            padding: '8px 24px',
            borderBottom: '1px solid var(--color-border-dim)',
          }}>
            {['Description','Date','Type','Amount'].map((h) => (
              <span key={h} style={{
                fontSize: '10px', fontFamily: 'var(--font-mono)',
                letterSpacing: '0.08em', textTransform: 'uppercase',
                color: 'var(--color-text-muted)',
                textAlign: h === 'Amount' ? 'right' : 'left',
              }}>
                {h}
              </span>
            ))}
          </div>
          {transactions.map((txn, idx) => (
            <TxnRow key={txn.public_id} txn={txn} isLast={idx === transactions.length - 1} />
          ))}
        </div>
      )}
    </Card>
  )
}

function TxnRow({ txn, isLast }) {
  const isCredit = txn.direction === 'credit'
  const isFailed = txn.status === 'failed'
  const label = txn.counterparty_name
    ?? txn.description?.slice(0, 30)
    ?? TYPE_LABELS[txn.transaction_type]
    ?? txn.transaction_type

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '2fr 1.5fr 1fr 1fr',
      alignItems: 'center', padding: '13px 24px',
      borderBottom: isLast ? 'none' : '1px solid var(--color-border-dim)',
      opacity: isFailed ? 0.55 : 1,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span style={{
          width: 28, height: 28, borderRadius: '8px',
          background: isCredit ? 'var(--color-green-muted)' : 'var(--color-red-dim)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '12px', fontWeight: 700, flexShrink: 0,
          color: isCredit ? 'var(--color-green)' : 'var(--color-red)',
        }}>
          {isCredit ? '↑' : '↓'}
        </span>
        <span style={{
          fontSize: '13px', color: 'var(--color-text-primary)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {label}
        </span>
      </div>
      <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}>
        {format(new Date(txn.transaction_date), 'dd MMM, HH:mm')}
      </span>
      <Badge variant={isFailed ? 'red' : isCredit ? 'green' : 'muted'}>
        {isFailed ? 'Failed' : TYPE_LABELS[txn.transaction_type] ?? txn.transaction_type}
      </Badge>
      <span style={{
        fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '14px',
        textAlign: 'right',
        color: isFailed ? 'var(--color-text-muted)' : isCredit ? 'var(--color-green)' : 'var(--color-text-primary)',
      }}>
        {isCredit ? '+' : '-'}{formatKES(txn.amount_kes, { showCents: false })}
      </span>
    </div>
  )
}

const sectionLabel = {
  fontSize: '11px', fontFamily: 'var(--font-mono)',
  letterSpacing: '0.08em', textTransform: 'uppercase',
  color: 'var(--color-text-muted)',
}