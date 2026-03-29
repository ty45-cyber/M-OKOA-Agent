import React, { useState } from 'react'
import { useAuthStore } from '../../store/auth.store'
import api from '../../lib/api'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'

const SECTIONS = [
  { key: 'profile',      label: 'Profile',      icon: '◈' },
  { key: 'security',     label: 'Security',      icon: '⊙' },
  { key: 'telegram',     label: 'Telegram',      icon: '◻' },
  { key: 'subscription', label: 'Subscription',  icon: '⬗' },
]

export default function SettingsPage() {
  const [activeSection, setActiveSection] = useState('profile')

  return (
    <div className="animate-fade-in">
      <div style={{ marginBottom: '32px' }}>
        <p style={metaLabel}>ACCOUNT</p>
        <h1 style={pageTitle}>Settings</h1>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: '24px' }}>
        {/* Left nav */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {SECTIONS.map((s) => (
            <button key={s.key} onClick={() => setActiveSection(s.key)} style={{ padding: '10px 14px', background: activeSection === s.key ? 'var(--color-green-muted)' : 'transparent', border: `1px solid ${activeSection === s.key ? 'rgba(0,214,100,0.15)' : 'transparent'}`, borderRadius: 'var(--radius-md)', color: activeSection === s.key ? 'var(--color-green)' : 'var(--color-text-secondary)', fontSize: '14px', fontFamily: 'var(--font-body)', cursor: 'pointer', textAlign: 'left', display: 'flex', alignItems: 'center', gap: '10px', transition: 'all var(--transition-fast)' }}>
              <span style={{ fontSize: '15px', width: 18, textAlign: 'center' }}>{s.icon}</span>
              {s.label}
            </button>
          ))}
        </div>

        {/* Right panel */}
        <div>
          {activeSection === 'profile'      && <ProfileSection />}
          {activeSection === 'security'     && <SecuritySection />}
          {activeSection === 'telegram'     && <TelegramSection />}
          {activeSection === 'subscription' && <SubscriptionSection />}
        </div>
      </div>
    </div>
  )
}

function ProfileSection() {
  const { user } = useAuthStore()
  return (
    <Card className="animate-fade-up">
      <SectionHeader title="Profile Information" desc="Your M-Okoa account details." />
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <ReadOnlyField label="Full Name"     value={user?.full_name ?? '—'} />
        <ReadOnlyField label="Phone Number"  value={user?.phone_number ?? '—'} mono />
        <ReadOnlyField label="Email"         value={user?.email ?? 'Not set'} />
        <div>
          <label style={labelStyle}>Account Status</label>
          <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
            <Badge variant={user?.is_verified ? 'green' : 'amber'} dot>
              {user?.is_verified ? 'Verified' : 'Phone not verified'}
            </Badge>
          </div>
        </div>
      </div>
      <div style={{ marginTop: '24px', padding: '12px 14px', background: 'var(--color-surface)', border: '1px solid var(--color-border-dim)', borderRadius: 'var(--radius-md)', fontSize: '12px', color: 'var(--color-text-muted)' }}>
        To update your name or phone number, contact{' '}
        <a href="mailto:support@mokoa.co.ke" style={{ color: 'var(--color-green)' }}>support@mokoa.co.ke</a>
      </div>
    </Card>
  )
}

function SecuritySection() {
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm_password: '' })
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState(null)

  function handleChange(e) {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
    setError(null); setSuccess(false)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (form.new_password !== form.confirm_password) { setError('Passwords do not match.'); return }
    if (form.new_password.length < 8) { setError('Password must be at least 8 characters.'); return }
    setLoading(true)
    try {
      await api.post('/api/v1/auth/change-password', { current_password: form.current_password, new_password: form.new_password })
      setSuccess(true)
      setForm({ current_password: '', new_password: '', confirm_password: '' })
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to change password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="animate-fade-up">
      <SectionHeader title="Security" desc="Change your password." />
      {error   && <AlertBox variant="error"   message={error} />}
      {success && <AlertBox variant="success" message="Password changed successfully." />}
      <form onSubmit={handleSubmit} noValidate>
        {[['current_password','Current Password','current-password'],['new_password','New Password','new-password'],['confirm_password','Confirm New Password','new-password']].map(([name, label, autoComplete]) => (
          <div key={name} style={{ marginBottom: '14px' }}>
            <label style={labelStyle}>{label}</label>
            <input name={name} type="password" placeholder="••••••••" value={form[name]} onChange={handleChange} autoComplete={autoComplete} style={inputStyle} />
          </div>
        ))}
        <div style={{ marginTop: '8px' }}>
          <Button type="submit" loading={loading}>Update Password</Button>
        </div>
      </form>
    </Card>
  )
}

function TelegramSection() {
  const [chatId, setChatId] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState(null)

  async function handleBind(e) {
    e.preventDefault()
    if (!chatId.trim()) return
    setLoading(true); setError(null); setSuccess(false)
    try {
      await api.post('/api/v1/auth/bind-telegram', { telegram_chat_id: parseInt(chatId.trim(), 10) })
      setSuccess(true); setChatId('')
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to link Telegram.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="animate-fade-up">
      <SectionHeader title="Telegram Bot" desc="Link your Telegram account to use the M-Okoa bot." />
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '24px' }}>
        {[
          ['1', 'Open Telegram and search for @MokoaAgentBot'],
          ['2', 'Send /start to the bot'],
          ['3', 'The bot will reply with your Chat ID'],
          ['4', 'Paste your Chat ID below and click Link'],
        ].map(([step, text]) => (
          <div key={step} style={{ display: 'flex', gap: '12px', alignItems: 'flex-start', padding: '10px 12px', background: 'var(--color-surface)', border: '1px solid var(--color-border-dim)', borderRadius: 'var(--radius-md)' }}>
            <span style={{ width: 22, height: 22, borderRadius: '50%', background: 'var(--color-green-muted)', border: '1px solid rgba(0,214,100,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 700, color: 'var(--color-green)', flexShrink: 0 }}>{step}</span>
            <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>{text}</p>
          </div>
        ))}
      </div>
      {error   && <AlertBox variant="error"   message={error} />}
      {success && <AlertBox variant="success" message="Telegram linked successfully! You can now use the bot." />}
      <form onSubmit={handleBind} noValidate>
        <div style={{ marginBottom: '14px' }}>
          <label style={labelStyle}>Your Telegram Chat ID</label>
          <input type="number" placeholder="e.g. 1234567890" value={chatId} onChange={(e) => { setChatId(e.target.value); setError(null) }} style={inputStyle} />
        </div>
        <Button type="submit" loading={loading} disabled={!chatId.trim()}>Link Telegram</Button>
      </form>
    </Card>
  )
}

function SubscriptionSection() {
  const { user } = useAuthStore()

  const plans = [
    { key: 'msingi',    name: 'Msingi',    price: 'KES 499/mo',   color: 'var(--color-text-muted)', features: ['1 Till','Ledger & SMS parsing','Balance queries','Telegram bot'] },
    { key: 'biashara',  name: 'Biashara',  price: 'KES 1,499/mo', color: 'var(--color-green)',      features: ['5 Tills','Smart Float automation','Tax vault','Bill payment','Priority support'] },
    { key: 'enterprise',name: 'Enterprise',price: 'KES 4,999/mo', color: 'var(--color-amber)',      features: ['Unlimited tills','Custom rules','VAT support','API access','Dedicated support'] },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <Card className="animate-fade-up">
        <SectionHeader title="Subscription" desc="Your current plan and available upgrades." />
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 16px', background: 'var(--color-green-muted)', border: '1px solid rgba(0,214,100,0.15)', borderRadius: 'var(--radius-md)', marginBottom: '20px' }}>
          <span style={{ fontSize: '18px' }}>⬡</span>
          <div>
            <p style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
              Current plan: <span style={{ color: 'var(--color-green)' }}>{user?.subscription_tier?.charAt(0).toUpperCase()}{user?.subscription_tier?.slice(1)}</span>
            </p>
            <p style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>Contact us to upgrade.</p>
          </div>
        </div>
      </Card>

      {plans.map((plan) => {
        const isCurrent = user?.subscription_tier === plan.key
        return (
          <Card key={plan.key} className="animate-fade-up" style={{ border: isCurrent ? '1px solid rgba(0,214,100,0.3)' : '1px solid var(--color-border)', background: isCurrent ? 'rgba(0,214,100,0.03)' : 'var(--color-card)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
              <div>
                <p style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '16px', color: plan.color }}>{plan.name}</p>
                <p style={{ fontFamily: 'var(--font-mono)', fontSize: '14px', fontWeight: 600, color: 'var(--color-text-primary)', marginTop: '2px' }}>{plan.price}</p>
              </div>
              {isCurrent
                ? <Badge variant="green" dot>Current Plan</Badge>
                : <a href={`mailto:support@mokoa.co.ke?subject=Upgrade to ${plan.name}`} style={{ padding: '6px 14px', background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text-secondary)', fontSize: '12px', textDecoration: 'none' }}>Upgrade →</a>
              }
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {plan.features.map((f) => (
                <span key={f} style={{ padding: '3px 10px', background: 'var(--color-surface)', border: '1px solid var(--color-border-dim)', borderRadius: 'var(--radius-full)', fontSize: '11px', color: 'var(--color-text-secondary)' }}>{f}</span>
              ))}
            </div>
          </Card>
        )
      })}
    </div>
  )
}

function SectionHeader({ title, desc }) {
  return (
    <div style={{ marginBottom: '24px' }}>
      <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '18px', color: 'var(--color-text-primary)', marginBottom: '4px' }}>{title}</h2>
      <p style={{ fontSize: '13px', color: 'var(--color-text-muted)' }}>{desc}</p>
    </div>
  )
}

function ReadOnlyField({ label, value, mono = false }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <p style={{ padding: '10px 14px', background: 'var(--color-surface)', border: '1px solid var(--color-border-dim)', borderRadius: 'var(--radius-md)', fontSize: '14px', fontFamily: mono ? 'var(--font-mono)' : 'var(--font-body)', color: 'var(--color-text-primary)', letterSpacing: mono ? '0.04em' : 'normal' }}>{value}</p>
    </div>
  )
}

function AlertBox({ variant, message }) {
  const isError = variant === 'error'
  return (
    <div style={{ padding: '10px 14px', background: isError ? 'var(--color-red-dim)' : 'var(--color-green-muted)', border: `1px solid ${isError ? 'rgba(255,77,77,0.25)' : 'rgba(0,214,100,0.2)'}`, borderRadius: 'var(--radius-md)', color: isError ? 'var(--color-red)' : 'var(--color-green)', fontSize: '13px', marginBottom: '16px' }}>
      {message}
    </div>
  )
}

const metaLabel = { fontSize: '11px', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', color: 'var(--color-text-muted)', textTransform: 'uppercase', marginBottom: '6px' }
const pageTitle = { fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: '28px', letterSpacing: '-0.02em', color: 'var(--color-text-primary)' }
const labelStyle = { display: 'block', fontSize: '11px', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '6px' }
const inputStyle = { width: '100%', height: '46px', padding: '0 14px', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text-primary)', fontSize: '14px', fontFamily: 'var(--font-body)', outline: 'none' }