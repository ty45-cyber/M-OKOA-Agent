import React, { useState } from 'react'
import { useTills } from '../../../hooks/useTills'
import Button from '../../../components/ui/Button'
import { formatKES } from '../../../lib/decimal'

export default function SmartFloatDrawer({ open, till, onClose }) {
  const { addSmartFloatRule } = useTills()
  const [form, setForm] = useState({
    rule_name: '', trigger_threshold_kes: '', transfer_amount_kes: '',
    destination_type: 'mpesa_phone', destination_ref: '', destination_name: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  function handleChange(e) {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
    setError(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.rule_name || !form.trigger_threshold_kes || !form.destination_ref) {
      setError('Rule name, threshold, and destination are required.')
      return
    }
    setLoading(true)
    try {
      await addSmartFloatRule(till.public_id, {
        rule_name: form.rule_name,
        trigger_threshold_kes: form.trigger_threshold_kes,
        transfer_amount_kes: form.transfer_amount_kes || undefined,
        destination_type: form.destination_type,
        destination_ref: form.destination_ref,
        destination_name: form.destination_name || undefined,
      })
      setSuccess(true)
      setTimeout(onClose, 1500)
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to save rule.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {open && <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 199 }} />}
      <div style={{ position: 'fixed', top: 0, right: 0, width: '420px', height: '100vh', background: 'var(--color-surface)', borderLeft: '1px solid var(--color-border)', zIndex: 200, display: 'flex', flexDirection: 'column', transform: open ? 'translateX(0)' : 'translateX(100%)', transition: 'transform 300ms cubic-bezier(0.4,0,0.2,1)', overflowY: 'auto' }}>
        <div style={{ padding: '24px', borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '18px', color: 'var(--color-text-primary)' }}>Smart Float Rule</h2>
            <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '2px' }}>{till.display_name}</p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', fontSize: '20px', cursor: 'pointer' }}>×</button>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '24px', flex: 1 }} noValidate>
          <div style={{ padding: '12px 14px', background: 'var(--color-green-muted)', border: '1px solid rgba(0,214,100,0.15)', borderRadius: 'var(--radius-md)', marginBottom: '20px', fontSize: '12px', color: 'var(--color-green)', lineHeight: 1.6 }}>
            ⚡ When balance exceeds the threshold, M-Okoa Agent will automatically move the excess to your chosen destination.
          </div>

          {error && <div style={{ padding: '10px 14px', background: 'var(--color-red-dim)', border: '1px solid rgba(255,77,77,0.25)', borderRadius: 'var(--radius-md)', color: 'var(--color-red)', fontSize: '13px', marginBottom: '16px' }}>{error}</div>}
          {success && <div style={{ padding: '10px 14px', background: 'var(--color-green-muted)', border: '1px solid rgba(0,214,100,0.2)', borderRadius: 'var(--radius-md)', color: 'var(--color-green)', fontSize: '13px', marginBottom: '16px' }}>✓ Rule saved successfully!</div>}

          {[
            ['rule_name',              'Rule Name',                                            'text',   'e.g. Move excess to KCB'],
            ['trigger_threshold_kes',  'Trigger Threshold (KES)',                              'number', 'e.g. 10000'],
            ['transfer_amount_kes',    'Transfer Amount (KES, blank = all excess)',             'number', 'e.g. 5000'],
            ['destination_ref',        'Destination (Phone / Account)',                        'text',   'e.g. 0712345678'],
            ['destination_name',       'Destination Label (optional)',                         'text',   'e.g. KCB Savings'],
          ].map(([name, label, type, placeholder]) => (
            <div key={name} style={{ marginBottom: '14px' }}>
              <label style={labelStyle}>{label}</label>
              <input name={name} type={type} placeholder={placeholder} value={form[name]} onChange={handleChange} style={inputStyle} />
            </div>
          ))}

          <div style={{ marginBottom: '20px' }}>
            <label style={labelStyle}>Destination Type</label>
            <select name="destination_type" value={form.destination_type} onChange={handleChange} style={{ ...inputStyle, cursor: 'pointer' }}>
              <option value="mpesa_phone">M-Pesa Phone</option>
              <option value="bank_account">Bank Account</option>
              <option value="chama_paybill">Chama / SACCO Paybill</option>
            </select>
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <Button variant="secondary" fullWidth onClick={onClose} type="button">Cancel</Button>
            <Button fullWidth loading={loading} type="submit">Save Rule</Button>
          </div>
        </form>
      </div>
    </>
  )
}

const labelStyle = { display: 'block', fontSize: '11px', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '6px' }
const inputStyle = { width: '100%', height: '44px', padding: '0 12px', background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', color: 'var(--color-text-primary)', fontSize: '14px', fontFamily: 'var(--font-body)', outline: 'none' }