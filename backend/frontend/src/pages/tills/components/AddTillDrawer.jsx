import React, { useState } from 'react'
import Button from '../../../components/ui/Button'

export default function AddTillDrawer({ open, onClose, onCreate }) {
  const [form, setForm] = useState({
    display_name: '', till_number: '', till_type: 'till',
    daraja_consumer_key: '', daraja_consumer_secret: '',
    daraja_shortcode: '', daraja_passkey: '',
    float_threshold_kes: '', float_target_account: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showDaraja, setShowDaraja] = useState(false)

  function handleChange(e) {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
    setError(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.display_name.trim()) { setError('Display name is required.'); return }
    if (!form.till_number.trim()) { setError('Till number is required.'); return }

    setLoading(true)
    try {
      const payload = { ...form }
      if (!payload.daraja_consumer_key) delete payload.daraja_consumer_key
      if (!payload.daraja_consumer_secret) delete payload.daraja_consumer_secret
      if (!payload.daraja_shortcode) delete payload.daraja_shortcode
      if (!payload.daraja_passkey) delete payload.daraja_passkey
      if (!payload.float_threshold_kes) delete payload.float_threshold_kes
      if (!payload.float_target_account) delete payload.float_target_account
      await onCreate(payload)
      setForm({ display_name: '', till_number: '', till_type: 'till', daraja_consumer_key: '', daraja_consumer_secret: '', daraja_shortcode: '', daraja_passkey: '', float_threshold_kes: '', float_target_account: '' })
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to create till.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {open && <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 199 }} />}
      <div style={{
        position: 'fixed', top: 0, right: 0, width: '420px', height: '100vh',
        background: 'var(--color-surface)', borderLeft: '1px solid var(--color-border)',
        zIndex: 200, display: 'flex', flexDirection: 'column',
        transform: open ? 'translateX(0)' : 'translateX(100%)',
        transition: 'transform 300ms cubic-bezier(0.4,0,0.2,1)', overflowY: 'auto',
      }}>
        <div style={{ padding: '24px', borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
          <div>
            <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '18px', color: 'var(--color-text-primary)' }}>Register Till</h2>
            <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '2px' }}>Add an M-Pesa Till or Paybill account</p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', fontSize: '20px', cursor: 'pointer' }}>×</button>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '24px', flex: 1 }} noValidate>
          {error && <div style={{ padding: '10px 14px', background: 'var(--color-red-dim)', border: '1px solid rgba(255,77,77,0.25)', borderRadius: 'var(--radius-md)', color: 'var(--color-red)', fontSize: '13px', marginBottom: '20px' }}>{error}</div>}

          <DrawerField label="Display Name" name="display_name" placeholder="e.g. Mama Mboga Till" value={form.display_name} onChange={handleChange} />
          <DrawerField label="Till / Paybill Number" name="till_number" placeholder="e.g. 123456" value={form.till_number} onChange={handleChange} />

          <div style={{ marginBottom: '20px' }}>
            <label style={labelStyle}>Account Type</label>
            <select name="till_type" value={form.till_type} onChange={handleChange} style={{ ...inputBase, cursor: 'pointer' }}>
              <option value="till">Buy Goods (Till)</option>
              <option value="paybill">Paybill</option>
              <option value="personal">Personal M-Pesa</option>
            </select>
          </div>

          <button type="button" onClick={() => setShowDaraja(!showDaraja)} style={{ width: '100%', padding: '12px 16px', background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text-secondary)', fontSize: '13px', fontFamily: 'var(--font-body)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: showDaraja ? '16px' : '20px' }}>
            <span>⚙ Daraja API Credentials (optional)</span>
            <span>{showDaraja ? '▲' : '▼'}</span>
          </button>

          {showDaraja && (
            <div style={{ padding: '16px', background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px' }}>
              <p style={{ fontSize: '11px', color: 'var(--color-amber)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em' }}>⚠ Credentials are encrypted before storage</p>
              {[
                ['daraja_consumer_key',    'Consumer Key',    'From Safaricom Developer Portal', 'text'],
                ['daraja_consumer_secret', 'Consumer Secret', 'From Safaricom Developer Portal', 'password'],
                ['daraja_shortcode',       'Shortcode',       'Your Paybill or Till shortcode',  'text'],
                ['daraja_passkey',         'Passkey',         'Lipa na M-Pesa passkey',          'password'],
              ].map(([name, label, placeholder, type]) => (
                <DrawerField key={name} label={label} name={name} placeholder={placeholder} value={form[name]} onChange={handleChange} type={type} compact />
              ))}
            </div>
          )}

          <DrawerField label="Float Threshold (KES)" name="float_threshold_kes" placeholder="e.g. 10000" value={form.float_threshold_kes} onChange={handleChange} type="number" />
          <DrawerField label="Float Target Account" name="float_target_account" placeholder="Phone or account number" value={form.float_target_account} onChange={handleChange} />

          <div style={{ marginTop: '8px', display: 'flex', gap: '12px' }}>
            <Button variant="secondary" fullWidth onClick={onClose} type="button">Cancel</Button>
            <Button fullWidth loading={loading} type="submit">Register Till</Button>
          </div>
        </form>
      </div>
    </>
  )
}

function DrawerField({ label, name, placeholder, value, onChange, type = 'text', compact = false }) {
  return (
    <div style={{ marginBottom: compact ? '0' : '16px' }}>
      <label style={labelStyle}>{label}</label>
      <input name={name} type={type} placeholder={placeholder} value={value} onChange={onChange} style={inputBase} />
    </div>
  )
}

const labelStyle = { display: 'block', fontSize: '11px', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '6px' }
const inputBase = { width: '100%', height: '44px', padding: '0 12px', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text-primary)', fontSize: '14px', fontFamily: 'var(--font-body)', outline: 'none' }