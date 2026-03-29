import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import { useAuthStore } from '../../store/auth.store'
import Button from '../../components/ui/Button'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { setUser } = useAuthStore()
  const [form, setForm] = useState({
    full_name: '', phone_number: '', email: '',
    password: '', confirm_password: '',
  })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)

  function handleChange(e) {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
    setErrors((prev) => ({ ...prev, [name]: undefined, general: undefined }))
  }

  function validate() {
    const next = {}
    if (!form.full_name.trim() || form.full_name.trim().length < 2)
      next.full_name = 'Full name must be at least 2 characters.'
    if (!form.phone_number.trim())
      next.phone_number = 'Phone number is required.'
    if (!form.password || form.password.length < 8)
      next.password = 'Password must be at least 8 characters.'
    if (!/[A-Z]/.test(form.password))
      next.password = 'Password must contain at least one uppercase letter.'
    if (!/[0-9]/.test(form.password))
      next.password = 'Password must contain at least one number.'
    if (form.password !== form.confirm_password)
      next.confirm_password = 'Passwords do not match.'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!validate()) return
    setLoading(true)
    try {
      const payload = {
        full_name: form.full_name.trim(),
        phone_number: form.phone_number.trim(),
        email: form.email.trim() || undefined,
        password: form.password,
      }
      const { data } = await api.post('/api/v1/auth/register', payload)
      setUser(data.user, data.access_token, data.refresh_token)
      navigate('/dashboard')
    } catch (err) {
      const detail = err?.response?.data?.detail
      setErrors({ general: detail ?? 'Registration failed. Please try again.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-fade-up">
      <div style={{ marginBottom: '32px' }}>
        <h2 style={{
          fontFamily: 'var(--font-display)', fontWeight: 800,
          fontSize: '28px', letterSpacing: '-0.02em',
          color: 'var(--color-text-primary)', marginBottom: '8px',
        }}>
          Anza Safari
        </h2>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px' }}>
          Create your M-Okoa account. Free to start.
        </p>
      </div>

      {errors.general && (
        <div style={{
          padding: '12px 16px',
          background: 'var(--color-red-dim)',
          border: '1px solid rgba(255,77,77,0.25)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--color-red)',
          fontSize: '13px', marginBottom: '20px',
        }}>
          {errors.general}
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate>
        {[
          ['full_name',        'Full Name',          'text',     'Kamau Wanjiku',      'name'],
          ['phone_number',     'Phone Number',       'tel',      '+254712345678',      'tel'],
          ['email',            'Email (optional)',   'email',    'kamau@example.com',  'email'],
          ['password',         'Password',           'password', 'Min 8 chars, 1 uppercase, 1 number', 'new-password'],
          ['confirm_password', 'Confirm Password',  'password', '••••••••',           'new-password'],
        ].map(([name, label, type, placeholder, autoComplete]) => (
          <div key={name} style={{ marginBottom: '14px' }}>
            <label style={labelStyle}>{label}</label>
            <input
              name={name} type={type} placeholder={placeholder}
              value={form[name]} onChange={handleChange}
              autoComplete={autoComplete}
              style={{
                width: '100%', height: '46px', padding: '0 14px',
                background: 'var(--color-card)',
                border: `1px solid ${errors[name] ? 'var(--color-red)' : 'var(--color-border)'}`,
                borderRadius: 'var(--radius-md)',
                color: 'var(--color-text-primary)',
                fontSize: '14px', fontFamily: 'var(--font-body)', outline: 'none',
              }}
            />
            {errors[name] && (
              <p style={{ fontSize: '12px', color: 'var(--color-red)', marginTop: '4px' }}>
                {errors[name]}
              </p>
            )}
          </div>
        ))}

        <div style={{ marginTop: '8px' }}>
          <Button type="submit" fullWidth loading={loading}
            style={{ height: '48px', fontSize: '15px', fontWeight: 600 }}>
            Create Account
          </Button>
        </div>
      </form>

      <p style={{
        textAlign: 'center', marginTop: '24px',
        fontSize: '14px', color: 'var(--color-text-secondary)',
      }}>
        Already have an account?{' '}
        <Link to="/login" style={{ color: 'var(--color-green)', fontWeight: 500 }}>
          Sign in
        </Link>
      </p>
    </div>
  )
}

const labelStyle = {
  display: 'block', fontSize: '11px', fontWeight: 600,
  letterSpacing: '0.06em', textTransform: 'uppercase',
  color: 'var(--color-text-muted)', marginBottom: '6px',
}