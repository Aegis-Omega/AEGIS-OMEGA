import { useEffect, useState } from 'react'
import { CheckCircle, ExternalLink, Zap, Mail, Loader2 } from 'lucide-react'
import { createGrantToken, type Plan } from '../lib/access.js'

const TOOL_URLS: Record<string, string> = {
  'platform-picker':  import.meta.env.VITE_URL_PLATFORM_PICKER  ?? 'https://platform.aegisomega.com',
  'hook-generator':   import.meta.env.VITE_URL_HOOK_GENERATOR   ?? 'https://hooks.aegisomega.com',
  'content-calendar': import.meta.env.VITE_URL_CONTENT_CALENDAR ?? 'https://calendar.aegisomega.com',
}

const TOOL_NAMES: Record<string, string> = {
  'platform-picker':  'Platform Picker',
  'hook-generator':   'Hook Generator',
  'content-calendar': 'Content Calendar',
}

const TOOL_ACCENTS: Record<string, string> = {
  'platform-picker':  '#7C3AED',
  'hook-generator':   '#F59E0B',
  'content-calendar': '#22C55E',
}

const PLAN_TOOLS: Record<Plan, string[]> = {
  single:  ['platform-picker'],
  starter: ['platform-picker', 'hook-generator'],
  full:    ['platform-picker', 'hook-generator', 'content-calendar'],
}

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL ?? 'https://rwehltdwpsncnwxzkwik.supabase.co'

interface ToolLinkProps { tool: string; token: string }

function ToolLink({ tool, token }: ToolLinkProps) {
  const url = `${TOOL_URLS[tool]}?aegis_token=${encodeURIComponent(token)}`
  const accent = TOOL_ACCENTS[tool]
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center justify-between p-4 rounded-xl border transition-all hover:opacity-90"
      style={{ background: `${accent}10`, border: `1px solid ${accent}30` }}
    >
      <span className="font-semibold text-sm" style={{ color: '#EDEAE3' }}>{TOOL_NAMES[tool]}</span>
      <div className="flex items-center gap-1.5 text-xs font-medium" style={{ color: accent }}>
        Open <ExternalLink size={12} />
      </div>
    </a>
  )
}

function RestoreForm() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'found' | 'notfound' | 'error'>('idle')
  const [restoreUrl, setRestoreUrl] = useState('')

  const handleRestore = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.includes('@')) return
    setStatus('loading')
    try {
      const res = await fetch(`${SUPABASE_URL}/functions/v1/restore-access`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      })
      const data = await res.json() as { found: boolean; restore_url?: string; plan?: string }
      if (data.found && data.restore_url) {
        setRestoreUrl(data.restore_url)
        setStatus('found')
      } else {
        setStatus('notfound')
      }
    } catch {
      setStatus('error')
    }
  }

  if (status === 'found') {
    return (
      <div className="text-center">
        <CheckCircle size={32} className="mx-auto mb-3" style={{ color: '#34D399' }} />
        <p className="text-sm font-semibold mb-1" style={{ color: '#EDEAE3' }}>Purchase found</p>
        <p className="text-xs mb-4" style={{ color: '#6B6E80' }}>Click below to restore your access.</p>
        <a
          href={restoreUrl}
          className="inline-flex items-center gap-2 text-sm font-semibold py-2.5 px-5 rounded-xl transition-opacity hover:opacity-90"
          style={{ background: '#6366F1', color: '#fff' }}
        >
          <Zap size={13} /> Restore access
        </a>
      </div>
    )
  }

  return (
    <form onSubmit={handleRestore} className="space-y-3">
      <div className="flex gap-2">
        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          placeholder="you@example.com"
          required
          className="flex-1 text-sm px-3 py-2.5 rounded-xl border outline-none"
          style={{ background: '#12141A', border: '1px solid #2A2D3A', color: '#EDEAE3' }}
        />
        <button
          type="submit"
          disabled={status === 'loading'}
          className="flex items-center gap-1.5 text-sm font-semibold px-4 py-2.5 rounded-xl transition-opacity hover:opacity-90 disabled:opacity-50"
          style={{ background: '#6366F1', color: '#fff' }}
        >
          {status === 'loading' ? <Loader2 size={14} className="animate-spin" /> : <Mail size={14} />}
          {status === 'loading' ? '' : 'Restore'}
        </button>
      </div>
      {status === 'notfound' && (
        <p className="text-xs text-center" style={{ color: '#EF4444' }}>
          No purchase found for that email. <a href="/#pricing" style={{ color: '#6366F1' }}>Buy access →</a>
        </p>
      )}
      {status === 'error' && (
        <p className="text-xs text-center" style={{ color: '#EF4444' }}>Something went wrong. Try again.</p>
      )}
    </form>
  )
}

export function SuccessPage() {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [token, setToken] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const p = params.get('plan') as Plan | null
    if (p && ['single', 'starter', 'full'].includes(p)) {
      setPlan(p)
      setToken(createGrantToken(p))
    }
    window.history.replaceState({}, '', window.location.pathname)
  }, [])

  if (!plan || !token) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ background: '#08090C' }}>
        <div className="w-full max-w-sm">
          <div className="text-center mb-8">
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto mb-4"
              style={{ background: '#6366F120', border: '1px solid #6366F140' }}
            >
              <Zap size={20} style={{ color: '#6366F1' }} />
            </div>
            <h1 className="text-xl font-bold mb-2" style={{ color: '#EDEAE3' }}>Restore your access</h1>
            <p className="text-sm" style={{ color: '#6B6E80' }}>
              Enter the email you used to purchase — we'll look up your plan instantly.
            </p>
          </div>
          <RestoreForm />
          <p className="text-center text-xs mt-6" style={{ color: '#6B6E80' }}>
            Don't have access yet? <a href="/#pricing" style={{ color: '#6366F1' }}>See pricing →</a>
          </p>
        </div>
      </div>
    )
  }

  const tools = PLAN_TOOLS[plan]

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: '#08090C' }}>
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <CheckCircle size={48} className="mx-auto mb-4" style={{ color: '#34D399' }} />
          <h1 className="text-2xl font-bold mb-2" style={{ color: '#EDEAE3' }}>Payment confirmed</h1>
          <p className="text-sm" style={{ color: '#6B6E80' }}>
            Click each tool to open it with instant access — no keys, no email.
          </p>
        </div>

        <div className="space-y-3 mb-8">
          {tools.map(tool => (
            <ToolLink key={tool} tool={tool} token={token} />
          ))}
        </div>

        <p className="text-center text-xs" style={{ color: '#6B6B7A' }}>
          Access is stored in your browser. New device?{' '}
          <a href="/success" style={{ color: '#6366F1' }}>Restore by email →</a>
        </p>

        <div className="mt-8 text-center">
          <a href="/" className="inline-flex items-center gap-1.5 text-xs" style={{ color: '#6B6E80' }}>
            <Zap size={12} /> Back to AEGIS-Ω
          </a>
        </div>
      </div>
    </div>
  )
}
