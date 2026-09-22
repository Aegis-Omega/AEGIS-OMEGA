import { useMemo, useState, type FormEvent } from 'react'
import { CheckCircle, ExternalLink, Loader2, Mail, ShieldCheck } from 'lucide-react'
import {
  storeServerToken,
  verifyServerToken,
  type ServerGrantPayload,
} from '@shared/lib/access.js'

const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL as string | undefined)
  ?? 'https://rwehltdwpsncnwxzkwik.supabase.co'

const TOOL_URLS: Record<string, string> = {
  'platform-picker': (import.meta.env.VITE_URL_PLATFORM_PICKER as string | undefined)
    ?? 'https://platform.aegisomega.com',
  'hook-generator': (import.meta.env.VITE_URL_HOOK_GENERATOR as string | undefined)
    ?? 'https://hooks.aegisomega.com',
  'content-calendar': (import.meta.env.VITE_URL_CONTENT_CALENDAR as string | undefined)
    ?? 'https://calendar.aegisomega.com',
}

const TOOL_NAMES: Record<string, string> = {
  'platform-picker': 'Platform Picker',
  'hook-generator': 'Hook Generator',
  'content-calendar': 'Content Calendar',
}

type Status = 'idle' | 'loading' | 'issued' | 'restore-sent' | 'verifying-token' | 'error'

export function SuccessPage() {
  const orderId = useMemo(
    () => new URLSearchParams(window.location.search).get('order_id')?.trim() ?? '',
    [],
  )
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [message, setMessage] = useState('')
  const [token, setToken] = useState<string | null>(null)
  const [tokenInput, setTokenInput] = useState('')
  const [payload, setPayload] = useState<ServerGrantPayload | null>(null)

  async function activateToken(candidate: string) {
    const normalized = candidate.trim()
    if (!normalized) return

    setStatus('verifying-token')
    setMessage('')

    const verified = await verifyServerToken(normalized)
    if (!verified) {
      setStatus('error')
      setMessage('That token is invalid, expired, or not signed by the current AEGIS access key.')
      return
    }

    for (const tool of verified.tools) storeServerToken(tool, normalized)
    setToken(normalized)
    setPayload(verified)
    setStatus('issued')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const normalizedEmail = email.trim().toLowerCase()
    if (!normalizedEmail || !normalizedEmail.includes('@')) return

    setStatus('loading')
    setMessage('')

    try {
      if (orderId) {
        const response = await fetch(SUPABASE_URL + '/functions/v1/issue-token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ order_id: orderId, email: normalizedEmail }),
        })
        const data = await response.json() as { aegis_token?: string; error?: string }
        if (!response.ok || !data.aegis_token) {
          throw new Error(data.error ?? 'Token issue failed (HTTP ' + response.status + ')')
        }

        await activateToken(data.aegis_token)
        const url = new URL(window.location.href)
        url.searchParams.delete('order_id')
        window.history.replaceState({}, '', url.toString())
        return
      }

      const response = await fetch(SUPABASE_URL + '/functions/v1/restore-access', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalizedEmail }),
      })
      if (!response.ok) throw new Error('Restore request failed (HTTP ' + response.status + ')')

      setStatus('restore-sent')
      setMessage('If that address has an eligible purchase, its signed access token is on the way.')
    } catch (error) {
      setStatus('error')
      setMessage(error instanceof Error ? error.message : 'Unable to restore access')
    }
  }

  if (status === 'issued' && token && payload) {
    return (
      <main
        className="min-h-screen flex items-center justify-center px-4"
        style={{ background: '#06070C', color: '#F3F4F6' }}
      >
        <section className="w-full max-w-md text-center">
          <CheckCircle size={48} className="mx-auto mb-5" style={{ color: '#34D399' }} />
          <h1 className="text-2xl font-bold mb-2">Access verified</h1>
          <p className="text-sm mb-8" style={{ color: '#9CA3AF' }}>
            Your signed access token was verified locally and stored for the eligible tools.
          </p>
          <div className="space-y-3">
            {payload.tools.map(tool => {
              const base = TOOL_URLS[tool]
              if (!base) return null
              return (
                <a
                  key={tool}
                  href={base + '?aegis_token=' + encodeURIComponent(token)}
                  className="flex items-center justify-between rounded-xl border px-4 py-3 text-left"
                  style={{ borderColor: '#2D3140', background: '#11131A' }}
                >
                  <span>{TOOL_NAMES[tool] ?? tool}</span>
                  <ExternalLink size={15} />
                </a>
              )
            })}
          </div>
          <a href="/" className="inline-block mt-8 text-sm" style={{ color: '#8B93A7' }}>
            Back to AEGIS Omega
          </a>
        </section>
      </main>
    )
  }

  return (
    <main
      className="min-h-screen flex items-center justify-center px-4"
      style={{ background: '#06070C', color: '#F3F4F6' }}
    >
      <section className="w-full max-w-md">
        <div className="text-center mb-8">
          <ShieldCheck size={44} className="mx-auto mb-5" style={{ color: '#818CF8' }} />
          <h1 className="text-2xl font-bold mb-2">
            {orderId ? 'Confirm purchase access' : 'Restore access'}
          </h1>
          <p className="text-sm" style={{ color: '#9CA3AF' }}>
            {orderId
              ? 'Enter the email used for the purchase. The order ID alone is not accepted as proof of ownership.'
              : 'Enter the purchase email. The response is intentionally the same whether or not a purchase exists.'}
          </p>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <input
            type="email"
            value={email}
            onChange={event => setEmail(event.target.value)}
            placeholder="you@example.com"
            autoComplete="email"
            required
            className="w-full rounded-xl border px-4 py-3 outline-none"
            style={{ background: '#11131A', borderColor: '#2D3140', color: '#F3F4F6' }}
          />
          <button
            type="submit"
            disabled={status === 'loading'}
            className="w-full flex items-center justify-center gap-2 rounded-xl px-4 py-3 font-semibold disabled:opacity-60"
            style={{ background: '#6366F1', color: '#FFFFFF' }}
          >
            {status === 'loading'
              ? <Loader2 size={16} className="animate-spin" />
              : <Mail size={16} />}
            {status === 'loading'
              ? 'Checking…'
              : orderId ? 'Verify purchase' : 'Send restore token'}
          </button>
        </form>

        {(status === 'restore-sent' || status === 'error') && (
          <p
            className="mt-4 text-sm text-center"
            style={{ color: status === 'error' ? '#F87171' : '#A7F3D0' }}
          >
            {message}
          </p>
        )}

        {!orderId && status === 'restore-sent' && (
          <div className="mt-6 space-y-3">
            <p className="text-xs text-center" style={{ color: '#9CA3AF' }}>
              The current restore email contains the signed token. Paste it here to activate it on this device.
            </p>
            <textarea
              value={tokenInput}
              onChange={event => setTokenInput(event.target.value)}
              placeholder="Paste signed AEGIS token"
              rows={3}
              className="w-full rounded-xl border px-4 py-3 outline-none text-xs"
              style={{ background: '#11131A', borderColor: '#2D3140', color: '#F3F4F6' }}
            />
            <button
              type="button"
              onClick={() => { void activateToken(tokenInput) }}
              disabled={!tokenInput.trim() || status === 'verifying-token'}
              className="w-full rounded-xl border px-4 py-3 text-sm font-semibold disabled:opacity-50"
              style={{ borderColor: '#374151', background: '#151821', color: '#F3F4F6' }}
            >
              {status === 'verifying-token' ? 'Verifying…' : 'Verify signed token'}
            </button>
          </div>
        )}

        <p className="mt-7 text-center text-xs" style={{ color: '#6B7280' }}>
          No access yet? <a href="/pricing" style={{ color: '#818CF8' }}>View current plans</a>
        </p>
      </section>
    </main>
  )
}
