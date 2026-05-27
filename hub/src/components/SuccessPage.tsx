import { useEffect, useState } from 'react'
import { CheckCircle, ExternalLink, Zap } from 'lucide-react'
import { createGrantToken, type Plan } from '../../../packages/shared/lib/access.js'

const TOOL_URLS: Record<string, string> = {
  'platform-picker':  import.meta.env.VITE_URL_PLATFORM_PICKER  ?? 'https://aegis-platform-picker.vercel.app',
  'hook-generator':   import.meta.env.VITE_URL_HOOK_GENERATOR   ?? 'https://aegis-hook-generator.vercel.app',
  'content-calendar': import.meta.env.VITE_URL_CONTENT_CALENDAR ?? 'https://aegis-content-calendar.vercel.app',
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

interface ToolLinkProps {
  tool: string
  token: string
}

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
      <span className="font-semibold text-sm" style={{ color: '#EDEAE3' }}>
        {TOOL_NAMES[tool]}
      </span>
      <div className="flex items-center gap-1.5 text-xs font-medium" style={{ color: accent }}>
        Open
        <ExternalLink size={12} />
      </div>
    </a>
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
    // Clean URL
    window.history.replaceState({}, '', window.location.pathname)
  }, [])

  if (!plan || !token) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#08090C' }}>
        <div className="text-center">
          <p className="text-sm" style={{ color: '#6B6E80' }}>No active session. <a href="/#pricing" style={{ color: '#6366F1' }}>See pricing →</a></p>
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
          Access is stored in your browser. To use on another device,{' '}
          <a href={`/success?plan=${plan}`} style={{ color: '#6366F1' }}>open this page again</a>{' '}
          and click each tool link.
        </p>

        <div className="mt-8 text-center">
          <a href="/" className="inline-flex items-center gap-1.5 text-xs" style={{ color: '#6B6E80' }}>
            <Zap size={12} />
            Back to AEGIS-Ω
          </a>
        </div>
      </div>
    </div>
  )
}
