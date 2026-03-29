import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import { useAuthStore } from '../../store/auth.store'
import Button from '../../components/ui/Button'

export default function LoginPage() {
  const navigate = useNavigate()
  const { setUser } = useAuthStore()
  const [form, setForm] = useState({ phone_number: '', password: '' })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)

  function handleChange(e) {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
    setErrors((prev) => ({ ...prev, [name]: undefined, general: undefined }))
  }

  function validate() {
    const next = {}
    if (!form.phone_number.trim()) next.phone_number = 'Phone number is required.'
    if (!form.password) next.password = 'Password is required.'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!validate()) return
    setLoading(true)
    try {
      const { data } = await api.post('/api/v1/auth/login', form)
      setUser(data.user, data.access_token, data.refresh_token)
      navigate('/dashboard')
    } catch (err) {
      const detail = err?.response?.data?.detail
      setErrors({ general: detail ?? 'Login failed. Please try again.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-fade-up">
      <div style={{ marginBottom: '36px' }}>
        <h2 style={{
          fontFamily: 'var(--font-display)', fontWeight: 800,
          fontSize: '28px', letterSpacing: '-0.02em',
          color: 'var(--color-text-primary)', marginBottom: '8px',
        }}>
          Karibu tena
        </h2>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px' }}>
          Welcome back. Sign in to your account.
        </p>
      </div>

      {errors.general && <ErrorBox message={errors.general} />}

      <form onSubmit={handleSubmit} noValidate>
        <Field
          label="Phone Number" name="phone_number" type="tel"
          placeholder="+254712345678" value={form.phone_number}
          onChange={handleChange} error={errors.phone_number}
          autoComplete="tel"
        />
        <div style={{ marginBottom: '24px' }}>
          <Field
            label="Password" name="password" type="password"
            placeholder="••••••••" value={form.password}
            onChange={handleChange} error={errors.password}
            autoComplete="current-password"
          />
        </div>

        <Button type="submit" fullWidth loading={loading}
          style={{ height: '48px', fontSize: '15px', fontWeight: 600 }}>
          Sign In
        </Button>
      </form>

      <p style={{
        textAlign: 'center', marginTop: '24px',
        fontSize: '14px', color: 'var(--color-text-secondary)',
      }}>
        Don't have an account?{' '}
        <Link to="/register" style={{ color: 'var(--color-green)', fontWeight: 500 }}>
          Create one
        </Link>
      </p>
    </div>
  )
}

function Field({ label, name, type, placeholder, value, onChange, error, autoComplete }) {
  return (
    <div style={{ marginBottom: '16px' }}>
      <label style={labelStyle}>{label}</label>
      <input
        name={name} type={type} placeholder={placeholder}
        value={value} onChange={onChange} autoComplete={autoComplete}
        style={{
          width: '100%', height: '48px', padding: '0 14px',
          background: 'var(--color-card)',
          border: `1px solid ${error ? 'var(--color-red)' : 'var(--color-border)'}`,
          borderRadius: 'var(--radius-md)',
          color: 'var(--color-text-primary)',
          fontSize: '15px', fontFamily: 'var(--font-body)', outline: 'none',
          transition: 'border-color var(--transition-fast)',
        }}
      />
      {error && <p style={{ fontSize: '12px', color: 'var(--color-red)', marginTop: '5px' }}>{error}</p>}
    </div>
  )
}

function ErrorBox({ message }) {
  return (
    <div style={{
      padding: '12px 16px',
      background: 'var(--color-red-dim)',
      border: '1px solid rgba(255,77,77,0.25)',
      borderRadius: 'var(--radius-md)',
      color: 'var(--color-red)',
      fontSize: '13px', marginBottom: '20px',
    }}>
      {message}
    </div>
  )
}

const labelStyle = {
  display: 'block', fontSize: '12px', fontWeight: 600,
  letterSpacing: '0.06em', textTransform: 'uppercase',
  color: 'var(--color-text-muted)', marginBottom: '6px',
}