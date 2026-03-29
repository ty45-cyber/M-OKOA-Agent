/**
 * Mini App Demo Page — the most important page for the hackathon.
 *
 * Design concept: "Phone Inside A Page"
 * A live M-Pesa phone simulator embedded in the dashboard.
 * Judges can interact with the Mini App interface without a physical phone.
 * Three screens: Home (balances), Agent (chat), Pay (STK Push demo).
 *
 * The phone frame on the left mirrors exactly what a real
 * M-Pesa Super App user would see.
 * The right panel explains the Daraja 3.0 APIs being called in real time.
 */
import React, { useState, useRef, useEffect } from 'react'
import api from '../../lib/api'
import { formatKES } from '../../lib/decimal'
import { useTillStore } from '../../store/till.store'

// ── Screens ───────────────────────────────────────────────────
const SCREENS = {
  home:  'home',
  agent: 'agent',
  pay:   'pay',
}

// ── Demo data (used when live API unavailable) ────────────────
const DEMO_TILLS = [
  { display_name: 'Mama Mboga Till', balance: 12340 },
  { display_name: 'Delivery Till',   balance: 5820 },
  { display_name: 'Hardware Shop',   balance: 38100 },
]

const DEMO_AGENT_RESPONSES = {
  'pesa': 'Jumla ya balance zako zote:\n\n• Mama Mboga Till: KES 12,340\n• Delivery Till: KES 5,820\n• Hardware Shop: KES 38,100\n\nJumla yote: KES 56,260 💰\n\nNapendekeza uhamishie KES 20,000 kwenye KCB ili kupata riba. Unataka nifanye hivyo?',
  'lipa': '✅ STK Push imetumwa!\n\nKiasi: KES 1,000\nKwa: KPLC Prepaid (247247)\nMeter: 12345678\n\nIngiza PIN yako ya M-Pesa kukamilisha. Utapata ujumbe wa uthibitisho. 🔋',
  'kodi': '📊 Tax iliyohifadhiwa — Machi 2026:\n\n• DST (1.5%): KES 844\n\nJumla: KES 844\n(Pesa hii imehifadhiwa kwa KRA — usitumie) ⚠️',
  'hamisha': '✅ Uhamisho umeanzishwa!\n\nKES 5,000 → KCB Bank (0712345678)\nSababu: Smart Float auto-transfer\n\nUtapata ujumbe wa uthibitisho hivi karibuni. 🏦',
  'chama': '📊 Bidii Women Group — Machi 2026\n\n💰 Balance: KES 98,500\n📈 Imekusanywa: KES 85,000 (85% ya lengo)\n⏳ Hawajachanga: wanachama 3\n\nVilipwa hivi karibuni:\n  ✓ Wanjiku — KES 5,000 (Leo 09:30)\n  ✓ Akinyi — KES 5,000 (Jana 16:45)\n  ✓ Nafula — KES 5,000 (Jana 14:20)',
  'default': 'Habari! Ninaweza kukusaidia na:\n\n• Kuangalia balance za tills zako\n• Kulipa bili (KPLC, maji, kodi)\n• Kuhamisha pesa kwa SACCO au benki\n• Kuonyesha hali ya kodi ya KRA\n• Taarifa ya Chama\n\nUnataka kufanya nini? 😊',
}

function getDemoResponse(text) {
  const lower = text.toLowerCase()
  if (lower.includes('pesa') || lower.includes('balance') || lower.includes('ngapi')) return DEMO_AGENT_RESPONSES.pesa
  if (lower.includes('lipa') || lower.includes('kplc') || lower.includes('bill')) return DEMO_AGENT_RESPONSES.lipa
  if (lower.includes('kodi') || lower.includes('kra') || lower.includes('tax')) return DEMO_AGENT_RESPONSES.kodi
  if (lower.includes('hamisha') || lower.includes('transfer') || lower.includes('move')) return DEMO_AGENT_RESPONSES.hamisha
  if (lower.includes('chama') || lower.includes('group') || lower.includes('wanachama')) return DEMO_AGENT_RESPONSES.chama
  return DEMO_AGENT_RESPONSES.default
}

// ── API log entry builder ──────────────────────────────────────
function makeApiLog(action, api, status = 'success') {
  return {
    id: Date.now(),
    timestamp: new Date().toLocaleTimeString('en-KE', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    action,
    api,
    status,
  }
}

// ── Main component ─────────────────────────────────────────────
export default function MiniAppDemoPage() {
  const [screen, setScreen] = useState(SCREENS.home)
  const [tills, setTills] = useState(DEMO_TILLS)
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Habari! Mimi ni M-Okoa Agent. Niambie unataka kufanya nini leo? 👋',
    },
  ])
  const [chatInput, setChatInput] = useState('')
  const [isChatLoading, setIsChatLoading] = useState(false)
  const [apiLogs, setApiLogs] = useState([
    makeApiLog('App launched', 'Mini App SDK → Auth Code'),
    makeApiLog('Identity resolved', 'Security API → Masked MSISDN'),
    makeApiLog('Balances fetched', 'Account Balance API'),
  ])
  const [stkPhone, setStkPhone] = useState('0712345678')
  const [stkAmount, setStkAmount] = useState('1000')
  const [stkStatus, setStkStatus] = useState(null) // null | 'pending' | 'success' | 'failed'
  const [totalBalance, setTotalBalance] = useState(56260)
  const chatBottomRef = useRef(null)
  const { balances } = useTillStore()

  // Load live balances if available
  useEffect(() => {
    if (balances.length > 0) {
      const liveTills = balances.map((b) => ({
        display_name: b.display_name,
        balance: parseFloat(b.balance_kes || '0'),
      }))
      setTills(liveTills)
      setTotalBalance(liveTills.reduce((s, t) => s + t.balance, 0))
    }
  }, [balances])

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function addApiLog(action, apiName, status = 'success') {
    setApiLogs((prev) => [makeApiLog(action, apiName, status), ...prev].slice(0, 8))
  }

  async function handleChatSend() {
    if (!chatInput.trim() || isChatLoading) return
    const text = chatInput.trim()
    setChatInput('')

    const userMsg = { id: String(Date.now()), role: 'user', content: text }
    const loadingMsg = { id: 'loading', role: 'assistant', content: '', loading: true }
    setMessages((prev) => [...prev, userMsg, loadingMsg])
    setIsChatLoading(true)

    addApiLog('Intent parsed', 'Claude claude-sonnet-4-20250514 → LangGraph')

    try {
      const { data } = await api.post('/api/v1/agent/message', {
        message: text,
        conversation_history: messages
          .filter((m) => !m.loading && m.id !== 'welcome')
          .map((m) => ({ role: m.role, content: m.content })),
      })
      const reply = data.response

      // Log which Daraja API was likely called
      const lower = text.toLowerCase()
      if (lower.includes('balance') || lower.includes('pesa'))
        addApiLog('Balance queried', 'Account Balance API')
      else if (lower.includes('lipa') || lower.includes('bill'))
        addApiLog('STK Push initiated', 'Lipa na M-Pesa API')
      else if (lower.includes('hamisha') || lower.includes('transfer'))
        addApiLog('B2C initiated', 'B2C Disbursement API')
      else if (lower.includes('kodi') || lower.includes('kra'))
        addApiLog('Tax calculated', 'Internal Tax Engine')
      else if (lower.includes('chama'))
        addApiLog('Group balance', 'Account Balance API')
      else
        addApiLog('Response generated', 'LangGraph → Claude')

      setMessages((prev) => [
        ...prev.filter((m) => m.id !== 'loading'),
        { id: String(Date.now()) + '_a', role: 'assistant', content: reply },
      ])
    } catch {
      // Use demo response when backend unavailable
      addApiLog('Offline mode', 'Demo Data', 'warning')
      const demoReply = getDemoResponse(text)
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== 'loading'),
        { id: String(Date.now()) + '_a', role: 'assistant', content: demoReply },
      ])
    } finally {
      setIsChatLoading(false)
    }
  }

  async function handleStkPush() {
    if (stkStatus === 'pending') return
    setStkStatus('pending')
    addApiLog('STK Push initiated', 'Lipa na M-Pesa API')

    // Simulate 3-second M-Pesa callback
    await new Promise((r) => setTimeout(r, 3000))

    setStkStatus('success')
    addApiLog('Payment confirmed', 'Daraja Callback → Ledger')
    addApiLog('Tax locked (1.5%)', 'Internal Tax Engine')
  }

  return (
    <div className="animate-fade-in">
      {/* ── Page header ────────────────────────────────── */}
      <div style={{ marginBottom: '32px' }}>
        <p style={metaLabel}>SAFARICOM DARAJA 3.0</p>
        <h1 style={pageTitle}>M-Pesa Mini App Demo</h1>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px', marginTop: '4px' }}>
          Interactive simulator — exactly what judges see inside the M-Pesa Super App
        </p>
      </div>

      {/* ── Main layout: Phone + Right panel ───────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '360px 1fr',
        gap: '32px',
        alignItems: 'flex-start',
      }}>

        {/* ── PHONE SIMULATOR ──────────────────────────── */}
        <div style={{ position: 'sticky', top: '24px' }}>
          <PhoneFrame>
            {/* M-Pesa status bar */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '8px 16px 4px',
              background: '#006400',
            }}>
              <span style={{ color: 'white', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>9:41</span>
              <span style={{ color: '#00D664', fontSize: '10px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>M-PESA</span>
              <span style={{ color: 'white', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>▋▋▋▋ 5G</span>
            </div>

            {/* Mini App header */}
            <div style={{
              background: 'linear-gradient(180deg, #006400 0%, #004d00 100%)',
              padding: '10px 16px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}>
              <div style={{
                width: 28, height: 28,
                background: '#00D664',
                borderRadius: '7px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '12px',
                fontWeight: 800,
                color: '#0A0F0D',
                flexShrink: 0,
              }}>M</div>
              <div>
                <p style={{ color: 'white', fontSize: '13px', fontWeight: 600, lineHeight: 1 }}>M-Okoa Agent</p>
                <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '10px', marginTop: '2px' }}>Mini App · Daraja 3.0</p>
              </div>
              <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#00D664', animation: 'pulse-green 2s infinite' }} />
                <span style={{ color: '#00D664', fontSize: '9px', fontFamily: 'var(--font-mono)' }}>LIVE</span>
              </div>
            </div>

            {/* Screen content */}
            <div style={{
              flex: 1,
              background: '#0A0F0D',
              overflowY: 'auto',
              overflowX: 'hidden',
            }}>
              {screen === SCREENS.home && (
                <HomeScreen
                  tills={tills}
                  totalBalance={totalBalance}
                  onNavigate={setScreen}
                  addApiLog={addApiLog}
                />
              )}
              {screen === SCREENS.agent && (
                <AgentScreen
                  messages={messages}
                  input={chatInput}
                  isLoading={isChatLoading}
                  onInputChange={setChatInput}
                  onSend={handleChatSend}
                  bottomRef={chatBottomRef}
                  onBack={() => setScreen(SCREENS.home)}
                />
              )}
              {screen === SCREENS.pay && (
                <PayScreen
                  phone={stkPhone}
                  amount={stkAmount}
                  status={stkStatus}
                  onPhoneChange={setStkPhone}
                  onAmountChange={setStkAmount}
                  onPay={handleStkPush}
                  onBack={() => setScreen(SCREENS.home)}
                />
              )}
            </div>

            {/* Bottom tab bar */}
            <div style={{
              display: 'flex',
              background: '#111916',
              borderTop: '1px solid #243028',
              flexShrink: 0,
            }}>
              {[
                { key: SCREENS.home,  icon: '◈', label: 'Float' },
                { key: SCREENS.agent, icon: '◎', label: 'Agent' },
                { key: SCREENS.pay,   icon: '⬡', label: 'Pay' },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setScreen(tab.key)}
                  style={{
                    flex: 1,
                    padding: '10px 0 8px',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '3px',
                    borderTop: screen === tab.key
                      ? '2px solid #00D664'
                      : '2px solid transparent',
                    marginTop: '-1px',
                  }}
                >
                  <span style={{
                    fontSize: '16px',
                    color: screen === tab.key ? '#00D664' : '#4A5E54',
                  }}>
                    {tab.icon}
                  </span>
                  <span style={{
                    fontSize: '9px',
                    fontFamily: 'var(--font-mono)',
                    color: screen === tab.key ? '#00D664' : '#4A5E54',
                    letterSpacing: '0.04em',
                  }}>
                    {tab.label}
                  </span>
                </button>
              ))}
            </div>
          </PhoneFrame>

          {/* Daraja 3.0 badge below phone */}
          <div style={{
            marginTop: '16px',
            padding: '12px 16px',
            background: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}>
            <div style={{
              width: 32, height: 32,
              background: 'rgba(0,214,100,0.1)',
              border: '1px solid rgba(0,214,100,0.2)',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '14px',
              flexShrink: 0,
            }}>
              🔒
            </div>
            <div>
              <p style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                Privacy-First Identity
              </p>
              <p style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '1px' }}>
                Raw MSISDN never stored · Daraja 3.0 Security API
              </p>
            </div>
          </div>
        </div>

        {/* ── RIGHT PANEL ───────────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

          {/* Live API activity log */}
          <div style={{
            background: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
          }}>
            <div style={{
              padding: '14px 20px',
              borderBottom: '1px solid var(--color-border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--color-green)', animation: 'pulse-green 2s infinite' }} />
                <p style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-text-muted)' }}>
                  Live API Activity
                </p>
              </div>
              <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}>
                Daraja 3.0
              </span>
            </div>

            <div style={{ padding: '8px', display: 'flex', flexDirection: 'column', gap: '4px', minHeight: '180px' }}>
              {apiLogs.map((log) => (
                <div key={log.id} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '8px 12px',
                  background: 'var(--color-surface)',
                  borderRadius: 'var(--radius-md)',
                  animation: 'fadeIn 300ms both',
                }}>
                  <span style={{
                    fontSize: '11px',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--color-text-muted)',
                    flexShrink: 0,
                    width: '56px',
                  }}>
                    {log.timestamp}
                  </span>
                  <div style={{
                    width: 6, height: 6,
                    borderRadius: '50%',
                    background: log.status === 'warning' ? 'var(--color-amber)' : 'var(--color-green)',
                    flexShrink: 0,
                  }} />
                  <p style={{ fontSize: '12px', color: 'var(--color-text-primary)', flex: 1, minWidth: 0 }}>
                    {log.action}
                  </p>
                  <span style={{
                    fontSize: '10px',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--color-green)',
                    background: 'var(--color-green-muted)',
                    padding: '2px 7px',
                    borderRadius: 'var(--radius-full)',
                    whiteSpace: 'nowrap',
                    flexShrink: 0,
                  }}>
                    {log.api}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Architecture diagram */}
          <div style={{
            background: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            padding: '20px',
          }}>
            <p style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
              System Architecture
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {[
                { layer: 'M-Pesa Super App', tech: 'Mini App SDK · .axml + .js', color: '#006400', icon: '📱' },
                { layer: 'Daraja 3.0 Security',  tech: 'Identity · Fraud · Privacy', color: '#F5A623', icon: '🔒' },
                { layer: 'M-Okoa Agent API', tech: 'FastAPI · LangGraph · Claude', color: '#00D664', icon: '🧠' },
                { layer: 'Daraja APIs',       tech: 'STK Push · B2C · Balance · C2B', color: '#4D9EFF', icon: '💸' },
                { layer: 'Tax Engine',        tech: 'DST 1.5% · VAT 16% · KRA', color: '#9B59B6', icon: '⬗' },
              ].map((item, idx) => (
                <React.Fragment key={item.layer}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '10px 14px',
                    background: 'var(--color-surface)',
                    border: `1px solid ${item.color}22`,
                    borderLeft: `3px solid ${item.color}`,
                    borderRadius: 'var(--radius-md)',
                  }}>
                    <span style={{ fontSize: '16px', flexShrink: 0 }}>{item.icon}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p style={{ fontSize: '13px', fontWeight: 500, color: 'var(--color-text-primary)' }}>{item.layer}</p>
                      <p style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>{item.tech}</p>
                    </div>
                  </div>
                  {idx < 4 && (
                    <div style={{ display: 'flex', justifyContent: 'center' }}>
                      <span style={{ color: 'var(--color-text-muted)', fontSize: '12px' }}>↓</span>
                    </div>
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Money in Motion challenge coverage */}
          <div style={{
            background: 'var(--color-card)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            padding: '20px',
          }}>
            <p style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
              Money in Motion — Coverage
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              {[
                { area: 'Merchant',  api: 'Transaction Status API', icon: '⬡', color: '#00D664', demo: 'Auto-reconciliation' },
                { area: 'Farmer',    api: 'B2C Disbursement API',   icon: '◈', color: '#F5A623', demo: '14-second payouts' },
                { area: 'Student',   api: 'Bill Pay / STK Push',    icon: '◻', color: '#4D9EFF', demo: 'Direct institution pay' },
                { area: 'Community', api: 'Account Balance API',    icon: '⬗', color: '#9B59B6', demo: 'Chama transparency' },
              ].map((item) => (
                <div key={item.area} style={{
                  padding: '12px',
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border-dim)',
                  borderRadius: 'var(--radius-md)',
                  borderTop: `2px solid ${item.color}`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                    <span style={{ fontSize: '14px', color: item.color }}>{item.icon}</span>
                    <p style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-primary)' }}>{item.area}</p>
                    <span style={{
                      marginLeft: 'auto',
                      width: 14, height: 14,
                      borderRadius: '50%',
                      background: 'var(--color-green-muted)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '8px',
                      color: 'var(--color-green)',
                      flexShrink: 0,
                    }}>✓</span>
                  </div>
                  <p style={{ fontSize: '10px', color: item.color, fontFamily: 'var(--font-mono)', marginBottom: '3px' }}>{item.api}</p>
                  <p style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>{item.demo}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Demo script */}
          <div style={{
            background: 'linear-gradient(145deg, #1A2E24, #0F1F18)',
            border: '1px solid rgba(0,214,100,0.2)',
            borderRadius: 'var(--radius-lg)',
            padding: '20px',
          }}>
            <p style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-green)', marginBottom: '16px', opacity: 0.8 }}>
              5-Minute Demo Script
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {[
                { time: '0:00', action: 'Open Mini App', detail: 'Show identity resolution — no raw phone stored' },
                { time: '1:00', action: 'Home screen', detail: '"Uko na pesa ngapi?" → 3 till balances aggregate live' },
                { time: '2:00', action: 'Agent tab', detail: 'Type the demo prompt → watch API log update in real time' },
                { time: '3:00', action: 'STK Push', detail: 'Tap Pay → enter amount → 3-second M-Pesa simulation' },
                { time: '4:00', action: 'Close', detail: '"One backend. 3 interfaces. 40M users. Money in Motion."' },
              ].map((step) => (
                <div key={step.time} style={{
                  display: 'flex',
                  gap: '12px',
                  alignItems: 'flex-start',
                }}>
                  <span style={{
                    fontSize: '11px',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--color-green)',
                    flexShrink: 0,
                    width: '36px',
                    paddingTop: '1px',
                  }}>
                    {step.time}
                  </span>
                  <div>
                    <p style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)' }}>{step.action}</p>
                    <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '1px' }}>{step.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Phone frame wrapper ───────────────────────────────────────
function PhoneFrame({ children }) {
  return (
    <div style={{
      width: '320px',
      height: '640px',
      background: '#1a1a1a',
      borderRadius: '40px',
      padding: '12px',
      boxShadow: '0 0 0 1px #333, 0 24px 64px rgba(0,0,0,0.8), 0 0 40px rgba(0,214,100,0.08)',
      position: 'relative',
      margin: '0 auto',
    }}>
      {/* Notch */}
      <div style={{
        position: 'absolute',
        top: '12px',
        left: '50%',
        transform: 'translateX(-50%)',
        width: '80px',
        height: '20px',
        background: '#1a1a1a',
        borderRadius: '0 0 12px 12px',
        zIndex: 10,
      }} />

      <div style={{
        width: '100%',
        height: '100%',
        background: '#0A0F0D',
        borderRadius: '30px',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {children}
      </div>
    </div>
  )
}

// ── Home screen ───────────────────────────────────────────────
function HomeScreen({ tills, totalBalance, onNavigate, addApiLog }) {
  function handleRefresh() {
    addApiLog('Balance refreshed', 'Account Balance API')
  }

  return (
    <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
      {/* Total balance */}
      <div style={{
        background: 'linear-gradient(145deg, #1A2E24, #0F1F18)',
        border: '1px solid rgba(0,214,100,0.2)',
        borderRadius: '16px',
        padding: '16px',
        position: 'relative',
        overflow: 'hidden',
      }}>
        <div style={{ position: 'absolute', top: -20, right: -20, width: 100, height: 100, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,214,100,0.1) 0%, transparent 70%)', pointerEvents: 'none' }} />
        <p style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#00D664', opacity: 0.8, marginBottom: '6px' }}>TOTAL FLOAT</p>
        <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '24px', color: '#E8F0EC', letterSpacing: '-0.02em' }}>
          {formatKES(totalBalance, { showCents: false })}
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px' }}>
          <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#00D664', animation: 'pulse-green 2s infinite' }} />
          <p style={{ fontSize: '10px', color: '#8A9E94', fontFamily: 'var(--font-mono)' }}>Verified · Masked MSISDN</p>
        </div>
      </div>

      {/* Till list */}
      <p style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: '#4A5E54' }}>YOUR TILLS</p>
      {tills.map((till) => (
        <div key={till.display_name} style={{
          background: '#1A2420',
          border: '1px solid #243028',
          borderRadius: '12px',
          padding: '12px 14px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <p style={{ fontSize: '13px', color: '#E8F0EC', fontWeight: 500 }}>{till.display_name}</p>
          <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '14px', color: '#E8F0EC' }}>
            {formatKES(till.balance, { showCents: false })}
          </p>
        </div>
      ))}

      {/* Quick actions */}
      <p style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: '#4A5E54', marginTop: '4px' }}>QUICK ACTIONS</p>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
        {[
          { label: 'Ask Agent',     icon: '◎', onClick: () => onNavigate(SCREENS.agent) },
          { label: 'Pay Bill',      icon: '⬡', onClick: () => onNavigate(SCREENS.pay) },
          { label: 'Refresh',       icon: '↻', onClick: handleRefresh },
          { label: 'Tax Vault',     icon: '⬗', onClick: () => {} },
        ].map((action) => (
          <button key={action.label} onClick={action.onClick} style={{
            background: '#1A2420',
            border: '1px solid #243028',
            borderRadius: '12px',
            padding: '12px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '6px',
            cursor: 'pointer',
          }}>
            <span style={{ fontSize: '18px', color: '#00D664' }}>{action.icon}</span>
            <span style={{ fontSize: '10px', color: '#8A9E94' }}>{action.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Agent screen ──────────────────────────────────────────────
function AgentScreen({ messages, input, isLoading, onInputChange, onSend, bottomRef, onBack }) {
  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  const quickPrompts = [
    'Pesa ngapi zote?',
    'Lipa KPLC 1000',
    'Kodi ya KRA?',
    'Taarifa ya Chama',
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Back header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '10px 14px',
        borderBottom: '1px solid #243028',
        flexShrink: 0,
      }}>
        <button onClick={onBack} style={{ background: 'none', border: 'none', color: '#8A9E94', fontSize: '16px', cursor: 'pointer', padding: '2px' }}>←</button>
        <div style={{ width: 22, height: 22, borderRadius: '6px', background: 'linear-gradient(135deg, #00A84F, #00D664)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 800, color: '#0A0F0D' }}>M</div>
        <p style={{ fontSize: '13px', fontWeight: 600, color: '#E8F0EC' }}>M-Okoa Agent</p>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#00D664', animation: 'pulse-green 2s infinite' }} />
          <span style={{ fontSize: '9px', color: '#00D664', fontFamily: 'var(--font-mono)' }}>ONLINE</span>
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {messages.map((msg) => (
          <div key={msg.id} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
            {msg.loading ? (
              <div style={{ background: '#1A2420', border: '1px solid #243028', borderRadius: '12px 12px 12px 3px', padding: '10px 14px', display: 'flex', gap: '4px', alignItems: 'center' }}>
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </div>
            ) : (
              <div style={{
                maxWidth: '82%',
                padding: '9px 12px',
                background: msg.role === 'user' ? '#00D664' : '#1A2420',
                border: '1px solid ' + (msg.role === 'user' ? 'transparent' : '#243028'),
                borderRadius: msg.role === 'user' ? '12px 12px 3px 12px' : '12px 12px 12px 3px',
                color: msg.role === 'user' ? '#0A0F0D' : '#E8F0EC',
                fontSize: '12px',
                lineHeight: 1.55,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}>
                {msg.content}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Quick prompts */}
      {messages.length <= 1 && (
        <div style={{ padding: '6px 10px', display: 'flex', flexWrap: 'wrap', gap: '5px', flexShrink: 0 }}>
          {quickPrompts.map((p) => (
            <button key={p} onClick={() => { onInputChange(p); onSend() }} style={{ padding: '5px 10px', background: '#1A2420', border: '1px solid #243028', borderRadius: '20px', color: '#8A9E94', fontSize: '10px', cursor: 'pointer', whiteSpace: 'nowrap' }}>
              {p}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div style={{ padding: '8px 10px', borderTop: '1px solid #243028', display: 'flex', gap: '8px', alignItems: 'flex-end', flexShrink: 0 }}>
        <input
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Andika hapa..."
          style={{ flex: 1, background: '#1A2420', border: '1px solid #243028', borderRadius: '20px', padding: '8px 12px', color: '#E8F0EC', fontSize: '12px', outline: 'none', fontFamily: 'var(--font-body)' }}
        />
        <button onClick={onSend} disabled={!input.trim() || isLoading} style={{ width: 32, height: 32, borderRadius: '50%', background: input.trim() && !isLoading ? '#00D664' : '#243028', border: 'none', color: input.trim() && !isLoading ? '#0A0F0D' : '#4A5E54', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px', cursor: input.trim() && !isLoading ? 'pointer' : 'not-allowed', flexShrink: 0 }}>
          ↑
        </button>
      </div>
    </div>
  )
}

// ── Pay screen (STK Push demo) ────────────────────────────────
function PayScreen({ phone, amount, status, onPhoneChange, onAmountChange, onPay, onBack }) {
  return (
    <div style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
        <button onClick={onBack} style={{ background: 'none', border: 'none', color: '#8A9E94', fontSize: '16px', cursor: 'pointer' }}>←</button>
        <p style={{ fontSize: '14px', fontWeight: 600, color: '#E8F0EC' }}>Pay Bill</p>
      </div>

      {/* Payee */}
      <div style={{ background: '#1A2420', border: '1px solid #243028', borderRadius: '12px', padding: '14px' }}>
        <p style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', color: '#4A5E54', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '6px' }}>Payee</p>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p style={{ fontSize: '13px', fontWeight: 600, color: '#E8F0EC' }}>KPLC Prepaid</p>
            <p style={{ fontSize: '11px', color: '#4A5E54', fontFamily: 'var(--font-mono)' }}>Paybill: 247247</p>
          </div>
          <div style={{ width: 28, height: 28, background: 'rgba(0,214,100,0.1)', border: '1px solid rgba(0,214,100,0.2)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ color: '#00D664', fontSize: '12px' }}>✓</span>
          </div>
        </div>
      </div>

      {/* Phone input */}
      <div>
        <p style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', color: '#4A5E54', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '6px' }}>Your Phone</p>
        <input
          value={phone}
          onChange={(e) => onPhoneChange(e.target.value)}
          style={{ width: '100%', background: '#1A2420', border: '1px solid #243028', borderRadius: '10px', padding: '10px 12px', color: '#E8F0EC', fontSize: '14px', fontFamily: 'var(--font-mono)', outline: 'none' }}
          placeholder="0712345678"
        />
      </div>

      {/* Amount input */}
      <div>
        <p style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', color: '#4A5E54', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '6px' }}>Amount (KES)</p>
        <input
          type="number"
          value={amount}
          onChange={(e) => onAmountChange(e.target.value)}
          style={{ width: '100%', background: '#1A2420', border: '1px solid #243028', borderRadius: '10px', padding: '10px 12px', color: '#E8F0EC', fontSize: '20px', fontFamily: 'var(--font-mono)', fontWeight: 700, outline: 'none' }}
        />
      </div>

      {/* STK Push button */}
      <button
        onClick={onPay}
        disabled={status === 'pending' || status === 'success'}
        style={{
          width: '100%',
          padding: '14px',
          background: status === 'success'
            ? 'rgba(0,214,100,0.15)'
            : status === 'pending'
              ? 'rgba(0,214,100,0.08)'
              : '#00D664',
          border: status === 'success'
            ? '1px solid rgba(0,214,100,0.3)'
            : '1px solid transparent',
          borderRadius: '12px',
          color: status === 'success' ? '#00D664' : status === 'pending' ? '#00D664' : '#0A0F0D',
          fontSize: '14px',
          fontWeight: 700,
          fontFamily: 'var(--font-body)',
          cursor: status === 'pending' || status === 'success' ? 'not-allowed' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          transition: 'all 300ms',
          marginTop: '4px',
        }}
      >
        {status === 'pending' && (
          <span style={{ width: 14, height: 14, border: '2px solid #00D664', borderTopColor: 'transparent', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} />
        )}
        {status === 'success' ? '✓ Payment Sent!' : status === 'pending' ? 'Waiting for PIN...' : '💳 Send STK Push'}
      </button>

      {/* Status message */}
      {status === 'pending' && (
        <div style={{ background: 'rgba(0,214,100,0.06)', border: '1px solid rgba(0,214,100,0.15)', borderRadius: '10px', padding: '10px 12px', textAlign: 'center' }}>
          <p style={{ fontSize: '11px', color: '#00D664' }}>📱 Check {phone} for M-Pesa PIN prompt</p>
          <p style={{ fontSize: '10px', color: '#4A5E54', marginTop: '3px' }}>Enter your 4-digit PIN to complete</p>
        </div>
      )}

      {status === 'success' && (
        <div style={{ background: 'rgba(0,214,100,0.06)', border: '1px solid rgba(0,214,100,0.2)', borderRadius: '10px', padding: '12px', animation: 'fadeIn 300ms both' }}>
          <p style={{ fontSize: '12px', color: '#00D664', fontWeight: 600, marginBottom: '4px' }}>✅ KPLC Payment Confirmed</p>
          <p style={{ fontSize: '11px', color: '#8A9E94' }}>KES {parseFloat(amount).toLocaleString()} sent to KPLC Prepaid</p>
          <p style={{ fontSize: '10px', color: '#4A5E54', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>Receipt: RBA{Math.random().toString(36).slice(2,8).toUpperCase()}</p>
          <p style={{ fontSize: '10px', color: '#F5A623', marginTop: '4px' }}>Tax locked: KES {(parseFloat(amount) * 0.015).toFixed(2)} (DST 1.5%)</p>
        </div>
      )}
    </div>
  )
}

const metaLabel = { fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', color: 'var(--color-text-muted)', textTransform: 'uppercase', marginBottom: '6px' }
const pageTitle = { fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: '28px', letterSpacing: '-0.02em', color: 'var(--color-text-primary)' }