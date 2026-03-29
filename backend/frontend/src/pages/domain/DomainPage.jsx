/**
 * Domain Mode page — dedicated view for Money in Motion challenge areas.
 * Shows the active persona, its demo prompt, APIs used,
 * and a direct link to the Agent pre-filled with the demo prompt.
 */
import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'

const DOMAIN_ICONS = { merchant: '⬡', farmer: '◈', student: '◻', community: '⬗', general: '◎' }
const DOMAIN_COLORS = { merchant: '#00D664', farmer: '#F5A623', student: '#4D9EFF', community: '#9B59B6', general: '#00D664' }

const DOMAIN_DETAIL = {
  merchant: {
    headline: 'Automated Merchant Reconciliation',
    problem: 'Kamau spends 2 hours every night matching M-Pesa SMS receipts to his hardware shop invoices. Missed payments mean lost revenue.',
    solution: 'M-Okoa Agent monitors your till via the Transaction Status API, auto-matches C2B payments to open invoices, and flags unmatched payments for review.',
    impact: '2 hours of manual work → 0 minutes',
    apis: ['Transaction Status API', 'C2B Callback', 'Account Balance API'],
    prompts: [
      'Nionyeshe malipo ya leo na ile ambayo haijafanana na invoice',
      'How many payments did I receive today?',
      'Which transactions are unreconciled?',
    ],
  },
  farmer: {
    headline: 'Instant Crop Payout Disbursements',
    problem: 'Wanjiku delivers 200kg of maize to a cooperative. She waits 2 weeks for a cheque. Middlemen take 15–20% in "fees."',
    solution: 'Cooperatives disburse B2C payments instantly on crop delivery confirmation. Full audit trail visible to both farmer and cooperative.',
    impact: '14 days to payment → 14 seconds',
    apis: ['B2C API', 'Account Balance API', 'Transaction Status API'],
    prompts: [
      'Lipa Wanjiku KES 8,400 kwa mahindi 120kg @ 70 per kg',
      'Show me all farmer payouts this week',
      'Check cooperative balance before next payout',
    ],
  },
  student: {
    headline: 'Direct Institution Fee Payments',
    problem: 'Amina sends KES 35,000 fees via an intermediary. The school says fees not received. Dispute takes weeks. 12% of fees are misdirected nationally.',
    solution: 'M-Okoa Agent pays fees directly to verified institution Paybills, with the correct admission number. Zero intermediaries.',
    impact: 'Fee misdirection rate: 12% → 0%',
    apis: ['STK Push', 'Bill Pay API', 'Transaction Status API'],
    prompts: [
      'Lipa fees KES 35,000 kwa University of Nairobi admission A001/2024',
      'What are my saved school payees?',
      'Verify my last fee payment reached the school',
    ],
  },
  community: {
    headline: 'Chama Wallet Transparency',
    problem: 'A Chama of 20 members pools KES 200,000 monthly. Only the treasurer has M-Pesa access. 3 members quit after suspecting embezzlement.',
    solution: 'Every member can view real-time balance, contribution status, and monthly collection rate via the Account Balance API. The treasurer has nowhere to hide.',
    impact: 'Chama trust disputes: eliminated',
    apis: ['Account Balance API', 'C2B Tracking', 'B2C Dividends'],
    prompts: [
      'Taarifa ya Chama yetu — Bidii Women Group, wanachama 20, kila mmoja KES 5,000',
      'Wangapi wamechanga mwezi huu?',
      'Show Chama balance and collection rate',
    ],
  },
  general: {
    headline: 'Full M-Pesa Financial Co-pilot',
    problem: 'Managing money across multiple M-Pesa tills, paying bills, tracking expenses, and staying KRA-compliant is a full-time job.',
    solution: 'M-Okoa Agent handles all of it — balance aggregation, conditional payments, smart float automation, and automatic tax locking.',
    impact: 'All Daraja APIs in one agentic interface',
    apis: ['All Daraja 3.0 APIs'],
    prompts: [
      'Uko na pesa ngapi kwa till zote?',
      'Lipa KPLC 1000 kama balance iko juu ya 5k',
      'Nionyeshe kodi yangu ya KRA mwezi huu',
    ],
  },
}

export default function DomainPage() {
  const navigate = useNavigate()
  const [modes, setModes] = useState([])
  const [activeMode, setActiveMode] = useState('general')
  const [isLoading, setIsLoading] = useState(true)
  const [isSwitching, setIsSwitching] = useState(false)

  useEffect(() => {
    async function load() {
      try {
        const [currentRes, allRes] = await Promise.all([
          api.get('/api/v1/domain/current'),
          api.get('/api/v1/domain/all'),
        ])
        setActiveMode(currentRes.data.current_mode)
        setModes(allRes.data)
      } catch { } finally {
        setIsLoading(false)
      }
    }
    load()
  }, [])

  async function handleSwitch(mode) {
    if (mode === activeMode || isSwitching) return
    setIsSwitching(true)
    try {
      await api.post('/api/v1/domain/set', { mode })
      setActiveMode(mode)
    } finally {
      setIsSwitching(false)
    }
  }

  function handleTryPrompt(prompt) {
    sessionStorage.setItem('mokoa_agent_prefill', prompt)
    navigate('/agent')
  }

  const detail = DOMAIN_DETAIL[activeMode] || DOMAIN_DETAIL.general
  const color = DOMAIN_COLORS[activeMode] || '#00D664'
  const icon = DOMAIN_ICONS[activeMode] || '◎'

  return (
    <div className="animate-fade-in">
      <div style={{ marginBottom: '32px' }}>
        <p style={metaLabel}>MONEY IN MOTION</p>
        <h1 style={pageTitle}>Challenge Areas</h1>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px', marginTop: '4px' }}>
          Switch between M-Okoa Agent personas for each hackathon challenge area
        </p>
      </div>

      {/* Mode selector */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '28px' }}>
        {[...modes, { mode: 'general', label: 'General', tagline: 'Full co-pilot', icon: '◎', color: '#00D664' }].map((m) => {
          const isActive = activeMode === m.mode
          const mColor = DOMAIN_COLORS[m.mode] || '#00D664'
          return (
            <button key={m.mode} onClick={() => handleSwitch(m.mode)} disabled={isSwitching} style={{ padding: '16px 14px', background: isActive ? `rgba(${hexToRgb(mColor)}, 0.08)` : 'var(--color-card)', border: `1px solid ${isActive ? `rgba(${hexToRgb(mColor)}, 0.3)` : 'var(--color-border)'}`, borderRadius: 'var(--radius-lg)', cursor: isSwitching ? 'not-allowed' : 'pointer', textAlign: 'left', transition: 'all var(--transition-normal)', position: 'relative', overflow: 'hidden' }}>
              {isActive && <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '2px', background: mColor }} />}
              <div style={{ fontSize: '22px', marginBottom: '8px' }}>{DOMAIN_ICONS[m.mode]}</div>
              <p style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '13px', color: isActive ? mColor : 'var(--color-text-primary)', marginBottom: '3px' }}>{m.label}</p>
              <p style={{ fontSize: '11px', color: 'var(--color-text-muted)', lineHeight: 1.4 }}>{m.tagline}</p>
            </button>
          )
        })}
      </div>

      {/* Active mode detail */}
      {isLoading ? (
        <div className="skeleton" style={{ height: '300px', borderRadius: '16px' }} />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          {/* Left: problem + solution */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <Card className="animate-fade-up" style={{ border: `1px solid rgba(${hexToRgb(color)}, 0.2)`, background: `rgba(${hexToRgb(color)}, 0.03)` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
                <span style={{ fontSize: '28px' }}>{icon}</span>
                <div>
                  <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '18px', color, marginBottom: '2px' }}>{detail.headline}</h2>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    {detail.apis.map((api_) => <Badge key={api_} variant="muted">{api_}</Badge>)}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ padding: '14px', background: 'var(--color-red-dim)', border: '1px solid rgba(255,77,77,0.15)', borderRadius: 'var(--radius-md)' }}>
                  <p style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--color-red)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '6px' }}>The Problem</p>
                  <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>{detail.problem}</p>
                </div>
                <div style={{ padding: '14px', background: 'var(--color-green-muted)', border: '1px solid rgba(0,214,100,0.15)', borderRadius: 'var(--radius-md)' }}>
                  <p style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--color-green)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '6px' }}>The Solution</p>
                  <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>{detail.solution}</p>
                </div>
                <div style={{ padding: '12px 14px', background: `rgba(${hexToRgb(color)}, 0.08)`, border: `1px solid rgba(${hexToRgb(color)}, 0.2)`, borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '16px' }}>📊</span>
                  <p style={{ fontSize: '13px', fontWeight: 600, color }}>{detail.impact}</p>
                </div>
              </div>
            </Card>
          </div>

          {/* Right: demo prompts */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <Card className="animate-fade-up delay-1">
              <p style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
                Demo Prompts — Try These
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {detail.prompts.map((prompt, idx) => (
                  <div key={idx} style={{ padding: '14px 16px', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
                    <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)', lineHeight: 1.5, flex: 1 }}>
                      "{prompt}"
                    </p>
                    <button onClick={() => handleTryPrompt(prompt)} style={{ padding: '6px 12px', background: `rgba(${hexToRgb(color)}, 0.1)`, border: `1px solid rgba(${hexToRgb(color)}, 0.25)`, borderRadius: 'var(--radius-md)', color, fontSize: '11px', fontFamily: 'var(--font-body)', fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0 }}>
                      Try →
                    </button>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: '20px' }}>
                <Button fullWidth onClick={() => navigate('/agent')} style={{ background: color, color: '#0A0F0D' }}>
                  Open Agent Chat
                </Button>
              </div>
            </Card>

            {/* Daraja 3.0 badge */}
            <Card className="animate-fade-up delay-2" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border-dim)' }}>
              <p style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '12px' }}>Daraja 3.0 Stack</p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {['Daraja 3.0', 'Security API', 'Mini App SDK', 'LangGraph Agent', 'Swahili NLP', 'KRA Tax Lock', 'Smart Float'].map((tag) => (
                  <span key={tag} style={{ padding: '4px 10px', background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-full)', fontSize: '11px', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)' }}>
                    {tag}
                  </span>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}

function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  if (!result) return '0,214,100'
  return `${parseInt(result[1], 16)},${parseInt(result[2], 16)},${parseInt(result[3], 16)}`
}

const metaLabel = { fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', color: 'var(--color-text-muted)', textTransform: 'uppercase', marginBottom: '6px' }
const pageTitle = { fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: '28px', letterSpacing: '-0.02em', color: 'var(--color-text-primary)' }