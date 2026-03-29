import React, { useEffect, useRef, useState } from 'react'
import api from '../../lib/api'
import { useAuthStore } from '../../store/auth.store'
import { format } from 'date-fns'

const QUICK_PROMPTS = [
  'Uko na pesa ngapi kwa till zote?',
  'Nionyeshe transactions za wiki iliyopita',
  'Kodi yangu ya KRA mwezi huu ni ngapi?',
  'Lipa KPLC 1000 kama balance iko juu ya 5k',
  'Nionyeshe malipo ya leo',
  'Taarifa ya Chama yetu',
]

export default function AgentPage() {
  const { user } = useAuthStore()
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: `Habari ${user?.full_name?.split(' ')[0] ?? ''}! 👋\n\nMimi ni M-Okoa Agent — msaidizi wako wa fedha.\n\nNinaweza kukusaidia kuangalia balance za tills zako, kulipa bili, kuhamisha pesa, na kukuonyesha hali ya kodi yako ya KRA.\n\nNiambie — unataka kufanya nini leo?`,
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  // ── Read prefill from DomainPage "Try →" button ──────────
  useEffect(() => {
    const prefill = sessionStorage.getItem('mokoa_agent_prefill')
    if (prefill) {
      sessionStorage.removeItem('mokoa_agent_prefill')
      // Small delay so the welcome message renders first
      setTimeout(() => sendMessage(prefill), 400)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function getHistory() {
    return messages
      .filter((m) => m.id !== 'welcome' && !m.loading)
      .map((m) => ({ role: m.role, content: m.content }))
  }

  async function sendMessage(text) {
    if (!text.trim() || isLoading) return

    const userMsg = {
      id: String(Date.now()),
      role: 'user',
      content: text.trim(),
      timestamp: new Date(),
    }
    const loadingMsg = {
      id: 'loading',
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      loading: true,
    }

    setMessages((prev) => [...prev, userMsg, loadingMsg])
    setInput('')
    setIsLoading(true)

    try {
      const { data } = await api.post('/api/v1/agent/message', {
        message: text.trim(),
        conversation_history: getHistory(),
      })
      const assistantMsg = {
        id: String(Date.now()) + '_a',
        role: 'assistant',
        content: data.response,
        timestamp: new Date(),
      }
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== 'loading'),
        assistantMsg,
      ])
    } catch {
      const errMsg = {
        id: String(Date.now()) + '_e',
        role: 'assistant',
        content: 'Samahani, kuna tatizo la kiufundi. Jaribu tena baadaye. 🙏',
        timestamp: new Date(),
      }
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== 'loading'),
        errMsg,
      ])
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: 'calc(100vh - 64px)',
      maxWidth: '760px',
      margin: '0 auto',
    }}>
      {/* Header */}
      <div style={{ padding: '0 0 24px', flexShrink: 0 }}>
        <p style={{
          fontSize: '11px',
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.1em',
          color: 'var(--color-text-muted)',
          textTransform: 'uppercase',
          marginBottom: '6px',
        }}>
          AI FINANCIAL CO-PILOT
        </p>
        <h1 style={{
          fontFamily: 'var(--font-display)',
          fontWeight: 800,
          fontSize: '26px',
          letterSpacing: '-0.02em',
          color: 'var(--color-text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          flexWrap: 'wrap',
        }}>
          M-Okoa Agent
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '5px',
            padding: '3px 10px',
            background: 'var(--color-green-muted)',
            border: '1px solid rgba(0,214,100,0.2)',
            borderRadius: 'var(--radius-full)',
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            fontWeight: 400,
            color: 'var(--color-green)',
            letterSpacing: '0.04em',
          }}>
            <span style={{
              width: 5, height: 5,
              borderRadius: '50%',
              background: 'var(--color-green)',
              animation: 'pulse-green 2s infinite',
              flexShrink: 0,
            }} />
            ONLINE
          </span>
        </h1>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        paddingRight: '4px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}>
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Quick prompts */}
      {messages.length <= 1 && (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '8px',
          padding: '16px 0',
          flexShrink: 0,
        }}>
          {QUICK_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              onClick={() => sendMessage(prompt)}
              style={{
                padding: '8px 14px',
                background: 'var(--color-card)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-full)',
                color: 'var(--color-text-secondary)',
                fontSize: '12px',
                fontFamily: 'var(--font-body)',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all var(--transition-fast)',
              }}
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div style={{
        flexShrink: 0,
        paddingTop: '16px',
        borderTop: '1px solid var(--color-border)',
      }}>
        <div style={{
          display: 'flex',
          gap: '12px',
          alignItems: 'flex-end',
          background: 'var(--color-card)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)',
          padding: '12px 16px',
        }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Andika hapa... (Enter kutuma, Shift+Enter mstari mpya)"
            rows={1}
            style={{
              flex: 1,
              background: 'none',
              border: 'none',
              outline: 'none',
              color: 'var(--color-text-primary)',
              fontSize: '14px',
              fontFamily: 'var(--font-body)',
              resize: 'none',
              lineHeight: 1.6,
              maxHeight: '120px',
              overflowY: 'auto',
            }}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isLoading}
            style={{
              width: 38, height: 38,
              borderRadius: 'var(--radius-md)',
              background: input.trim() && !isLoading
                ? 'var(--color-green)'
                : 'var(--color-card)',
              border: '1px solid ' + (input.trim() && !isLoading
                ? 'transparent'
                : 'var(--color-border)'),
              color: input.trim() && !isLoading ? '#0A0F0D' : 'var(--color-text-muted)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '16px',
              cursor: input.trim() && !isLoading ? 'pointer' : 'not-allowed',
              transition: 'all var(--transition-fast)',
              flexShrink: 0,
            }}
          >
            ↑
          </button>
        </div>
        <p style={{
          fontSize: '11px',
          color: 'var(--color-text-muted)',
          textAlign: 'center',
          marginTop: '8px',
          fontFamily: 'var(--font-mono)',
        }}>
          M-Okoa Agent · Swahili · Sheng · English · Daraja 3.0
        </p>
      </div>
    </div>
  )
}

function MessageBubble({ message }) {
  const isUser = message.role === 'user'

  if (message.loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
        <div style={{
          width: 28, height: 28,
          borderRadius: '8px',
          background: 'linear-gradient(135deg, var(--color-green-dim), var(--color-green))',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '11px',
          fontWeight: 800,
          color: '#0A0F0D',
          flexShrink: 0,
          marginRight: '10px',
          marginTop: '2px',
        }}>
          M
        </div>
        <div style={{
          background: 'var(--color-card)',
          border: '1px solid var(--color-border)',
          borderRadius: '16px 16px 16px 4px',
          padding: '14px 18px',
          display: 'flex',
          gap: '5px',
          alignItems: 'center',
        }}>
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-dot" />
        </div>
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      animation: 'fadeUp 200ms both',
    }}>
      {!isUser && (
        <div style={{
          width: 28, height: 28,
          borderRadius: '8px',
          background: 'linear-gradient(135deg, var(--color-green-dim), var(--color-green))',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '11px',
          fontWeight: 800,
          color: '#0A0F0D',
          flexShrink: 0,
          marginRight: '10px',
          marginTop: '2px',
        }}>
          M
        </div>
      )}
      <div style={{
        maxWidth: '75%',
        padding: '12px 16px',
        background: isUser ? 'var(--color-green)' : 'var(--color-card)',
        border: '1px solid ' + (isUser ? 'transparent' : 'var(--color-border)'),
        borderRadius: isUser
          ? '16px 16px 4px 16px'
          : '16px 16px 16px 4px',
        color: isUser ? '#0A0F0D' : 'var(--color-text-primary)',
        fontSize: '14px',
        lineHeight: 1.65,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>
        {message.content}
        <p style={{
          fontSize: '10px',
          marginTop: '6px',
          color: isUser ? 'rgba(0,0,0,0.45)' : 'var(--color-text-muted)',
          fontFamily: 'var(--font-mono)',
          textAlign: 'right',
        }}>
          {format(message.timestamp, 'HH:mm')}
        </p>
      </div>
    </div>
  )
}