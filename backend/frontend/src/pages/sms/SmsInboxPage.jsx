import React, { useCallback, useEffect, useState } from 'react'
import api from '../../lib/api'
import { format } from 'date-fns'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'

const STATUS_BADGE = { parsed: 'green', ambiguous: 'amber', failed: 'red', pending: 'muted' }
const SAMPLE_SMS = `RBA67XXXXX Confirmed. KES1,234.00 received from JOHN DOE 0712345678 on 1/3/25 at 10:30 AM. New M-PESA balance is KES12,340.00. Transaction cost, Ksh0.00.`

export default function SmsInboxPage() {
  const [smsText, setSmsText] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [lastResult, setLastResult] = useState(null)
  const [submitError, setSubmitError] = useState(null)
  const [inbox, setInbox] = useState([])
  const [isLoadingInbox, setIsLoadingInbox] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const PAGE_SIZE = 15

  const fetchInbox = useCallback(async () => {
    setIsLoadingInbox(true)
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE), ...(statusFilter && { parse_status: statusFilter }) })
      const { data } = await api.get(`/api/v1/sms/?${params}`)
      setInbox(data.items)
      setTotal(data.total)
    } catch { } finally {
      setIsLoadingInbox(false)
    }
  }, [page, statusFilter])

  useEffect(() => { fetchInbox() }, [fetchInbox])

  async function handleForward(e) {
    e.preventDefault()
    if (!smsText.trim()) return
    setIsSubmitting(true)
    setSubmitError(null)
    setLastResult(null)
    try {
      const { data } = await api.post('/api/v1/sms/forward', { raw_sms_text: smsText.trim(), received_at: new Date().toISOString() })
      setLastResult(data)
      setSmsText('')
      await fetchInbox()
    } catch (err) {
      setSubmitError(err?.response?.data?.detail ?? 'Failed to forward SMS. Try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="animate-fade-in">
      <div style={{ marginBottom: '32px' }}>
        <p style={metaLabel}>M-PESA MESSAGE PARSER</p>
        <h1 style={pageTitle}>SMS Inbox</h1>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px', marginTop: '4px' }}>Forward M-Pesa confirmation messages to auto-import transactions</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '24px', alignItems: 'flex-start' }}>
        {/* Left: Forward form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <Card className="animate-fade-up">
            <p style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '16px' }}>Forward SMS</p>
            <form onSubmit={handleForward} noValidate>
              <div style={{ marginBottom: '12px' }}>
                <label style={labelStyle}>M-Pesa SMS Text</label>
                <textarea value={smsText} onChange={(e) => { setSmsText(e.target.value); setSubmitError(null) }} placeholder={SAMPLE_SMS} rows={6}
                  style={{ width: '100%', padding: '12px 14px', background: 'var(--color-surface)', border: `1px solid ${submitError ? 'var(--color-red)' : 'var(--color-border)'}`, borderRadius: 'var(--radius-md)', color: 'var(--color-text-primary)', fontSize: '13px', fontFamily: 'var(--font-mono)', lineHeight: 1.6, resize: 'vertical', outline: 'none' }}
                />
              </div>
              {submitError && <div style={{ padding: '10px 12px', background: 'var(--color-red-dim)', border: '1px solid rgba(255,77,77,0.25)', borderRadius: 'var(--radius-md)', color: 'var(--color-red)', fontSize: '12px', marginBottom: '12px' }}>{submitError}</div>}
              <Button type="submit" fullWidth loading={isSubmitting} disabled={!smsText.trim()}>Parse & Import</Button>
            </form>
            <div style={{ marginTop: '16px', padding: '12px 14px', background: 'var(--color-green-muted)', border: '1px solid rgba(0,214,100,0.12)', borderRadius: 'var(--radius-md)', fontSize: '12px', color: 'var(--color-text-secondary)', lineHeight: 1.7 }}>
              <p style={{ fontWeight: 600, color: 'var(--color-green)', marginBottom: '4px' }}>How it works</p>
              1. Copy an M-Pesa SMS confirmation<br />2. Paste it above and click Parse<br />3. M-Okoa extracts the transaction data<br />4. It's added to your ledger automatically
            </div>
          </Card>

          <Card className="animate-fade-up delay-1" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border-dim)' }}>
            <p style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '6px' }}>⚡ Faster via Telegram</p>
            <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', lineHeight: 1.6, marginBottom: '12px' }}>Forward M-Pesa SMSes directly to the M-Okoa Telegram bot. No copy-paste needed.</p>
            <a href="https://t.me/MokoaAgentBot" target="_blank" rel="noopener noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '8px 14px', background: 'rgba(77,158,255,0.1)', border: '1px solid rgba(77,158,255,0.2)', borderRadius: 'var(--radius-md)', color: 'var(--color-blue)', fontSize: '12px', fontWeight: 500, textDecoration: 'none' }}>
              Open Telegram Bot →
            </a>
          </Card>
        </div>

        {/* Right: Result + Inbox */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {lastResult && <ParseResultCard result={lastResult} />}

          <Card className="animate-fade-up delay-1" padding="none">
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
              <p style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)' }}>Inbox · {total} messages</p>
              <div style={{ display: 'flex', gap: '6px' }}>
                {[['All',''],['✓ Parsed','parsed'],['⚠ Ambiguous','ambiguous'],['✕ Failed','failed']].map(([label, val]) => (
                  <button key={val} onClick={() => { setStatusFilter(val); setPage(1) }} style={{ padding: '4px 10px', background: statusFilter === val ? 'var(--color-green-muted)' : 'transparent', border: `1px solid ${statusFilter === val ? 'rgba(0,214,100,0.2)' : 'var(--color-border)'}`, borderRadius: 'var(--radius-full)', color: statusFilter === val ? 'var(--color-green)' : 'var(--color-text-muted)', fontSize: '11px', fontFamily: 'var(--font-body)', cursor: 'pointer' }}>
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {isLoadingInbox ? (
              <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {Array.from({ length: 5 }).map((_, i) => <div key={i} className="skeleton" style={{ height: '60px', borderRadius: '8px' }} />)}
              </div>
            ) : inbox.length === 0 ? (
              <div style={{ padding: '48px', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '14px' }}>No messages yet. Forward your first M-Pesa SMS above.</div>
            ) : (
              inbox.map((record, idx) => <SmsRow key={record.public_id} record={record} isLast={idx === inbox.length - 1} />)
            )}

            {totalPages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 20px', borderTop: '1px solid var(--color-border)' }}>
                <p style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}>Page {page} of {totalPages}</p>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <PagBtn label="← Prev" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} />
                  <PagBtn label="Next →" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} />
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}

function ParseResultCard({ result }) {
  const { inbox, parsed } = result
  const isSuccess = inbox.parse_status === 'parsed'
  const isAmbiguous = inbox.parse_status === 'ambiguous'
  return (
    <Card className="animate-fade-up" style={{ border: `1px solid ${isSuccess ? 'rgba(0,214,100,0.25)' : isAmbiguous ? 'rgba(245,166,35,0.25)' : 'rgba(255,77,77,0.25)'}`, background: isSuccess ? 'rgba(0,214,100,0.04)' : 'var(--color-card)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
        <p style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-primary)' }}>Parse Result</p>
        <Badge variant={STATUS_BADGE[inbox.parse_status]}>{inbox.parse_status}</Badge>
      </div>
      {parsed ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          {[
            ['Receipt', parsed.mpesa_receipt],
            ['Amount', parsed.amount_kes ? `KES ${parsed.amount_kes}` : null],
            ['Direction', parsed.direction],
            ['Counterparty', parsed.counterparty_name],
            ['Phone', parsed.counterparty_phone],
            ['Balance After', parsed.balance_after ? `KES ${parsed.balance_after}` : null],
          ].map(([label, value]) => (
            <div key={label} style={{ padding: '8px 10px', background: 'var(--color-surface)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border-dim)' }}>
              <p style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '3px' }}>{label}</p>
              <p style={{ fontSize: '13px', fontFamily: 'var(--font-mono)', color: value ? 'var(--color-text-primary)' : 'var(--color-text-muted)' }}>{value ?? '—'}</p>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ fontSize: '13px', color: 'var(--color-red)' }}>{inbox.parse_error ?? 'Could not parse this SMS.'}</p>
      )}
      {parsed && (
        <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}>Confidence:</span>
          <Badge variant={parsed.confidence === 'high' ? 'green' : parsed.confidence === 'medium' ? 'amber' : 'red'}>{parsed.confidence}</Badge>
        </div>
      )}
    </Card>
  )
}

function SmsRow({ record, isLast }) {
  const [expanded, setExpanded] = useState(false)
  const preview = record.raw_sms_text.slice(0, 80)
  return (
    <div onClick={() => setExpanded((v) => !v)} style={{ padding: '12px 20px', borderBottom: isLast ? 'none' : '1px solid var(--color-border-dim)', cursor: 'pointer' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ fontSize: '13px', fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: expanded ? 'normal' : 'nowrap', lineHeight: 1.5 }}>
            {expanded ? record.raw_sms_text : `${preview}${record.raw_sms_text.length > 80 ? '…' : ''}`}
          </p>
          {record.parse_error && expanded && <p style={{ fontSize: '11px', color: 'var(--color-red)', marginTop: '4px' }}>Error: {record.parse_error}</p>}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px', flexShrink: 0 }}>
          <Badge variant={STATUS_BADGE[record.parse_status]}>{record.parse_status}</Badge>
          <span style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}>{format(new Date(record.received_at), 'dd MMM HH:mm')}</span>
        </div>
      </div>
    </div>
  )
}

function PagBtn({ label, disabled, onClick }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{ padding: '5px 12px', background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: disabled ? 'var(--color-text-muted)' : 'var(--color-text-primary)', fontSize: '11px', fontFamily: 'var(--font-mono)', cursor: disabled ? 'not-allowed' : 'pointer' }}>
      {label}
    </button>
  )
}

const metaLabel = { fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', color: 'var(--color-text-muted)', textTransform: 'uppercase', marginBottom: '6px' }
const pageTitle = { fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: '28px', letterSpacing: '-0.02em', color: 'var(--color-text-primary)' }
const labelStyle = { display: 'block', fontSize: '11px', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '6px' }