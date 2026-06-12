// AEGIS-Ω Platform Pricing
// Tiers: Explorer (free / 10 runs) · Operator ($49) · Sovereign ($499)
// Payment: Stripe Checkout redirect for paid tiers; direct provision for Explorer.
// Webhook: supabase/functions/verify-stripe handles checkout.session.completed → provisions key.
// Explorer: calls verify-paypal directly (handles free tier + rate limiting, no PayPal needed).
import { useEffect, useState } from 'react'
import { createGrantToken } from '@shared/lib/access.js'

const SUPABASE_URL          = (import.meta.env.VITE_SUPABASE_URL as string | undefined)
  || 'https://rwehltdwpsncnwxzkwik.supabase.co'
const STRIPE_OPERATOR_LINK  = (import.meta.env.VITE_STRIPE_OPERATOR_LINK  as string | undefined) ?? ''
const STRIPE_SOVEREIGN_LINK = (import.meta.env.VITE_STRIPE_SOVEREIGN_LINK as string | undefined) ?? ''
const PROVISION_URL         = `${SUPABASE_URL}/functions/v1/verify-paypal`

const TOOL_URLS: Record<string, string> = {
  'platform-picker':  (import.meta.env.VITE_URL_PLATFORM_PICKER  as string | undefined) ?? 'https://platform.aegisomega.com',
  'hook-generator':   (import.meta.env.VITE_URL_HOOK_GENERATOR   as string | undefined) ?? 'https://hooks.aegisomega.com',
  'content-calendar': (import.meta.env.VITE_URL_CONTENT_CALENDAR as string | undefined) ?? 'https://calendar.aegisomega.com',
}

const TOOL_LABELS: Record<string, { name: string; tagline: string }> = {
  'platform-picker':  { name: 'Platform Picker',  tagline: 'Find the right stack for any project' },
  'hook-generator':   { name: 'Hook Generator',   tagline: 'AI-crafted viral hooks for content' },
  'content-calendar': { name: 'Content Calendar', tagline: 'Plan a month of content in minutes' },
}

type Tier = 'explorer' | 'operator' | 'sovereign'

const TIERS: Record<Tier, { label: string; price: string; runs: string; accent: string; description: string; monthly: string }> = {
  explorer:  {
    label: 'Explorer',  price: 'Free',  monthly: '',
    runs: '10 runs',      accent: '#6b7280',
    description: 'Evaluate AEGIS-Ω. Run 10 governed cycles — no card required.',
  },
  operator:  {
    label: 'Operator',  price: '$49',  monthly: 'one-time',
    runs: '500 runs',     accent: '#818cf8',
    description: '500 governed API calls. Full 39-agent collaboration. SHA-256 audit chain.',
  },
  sovereign: {
    label: 'Sovereign', price: '$499', monthly: 'one-time',
    runs: 'Unlimited',   accent: '#f59e0b',
    description: 'No run cap. Priority throughput. Constitutional governance on every call.',
  },
}

const BASE = 'https://aegis-vertex.aegisomega.com'

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  function copy() {
    navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000) })
  }
  return (
    <button onClick={copy} className="text-xs px-3 py-1 rounded border border-gray-600 hover:border-indigo-400 text-gray-300 hover:text-indigo-300 transition-colors">
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  )
}

function ToolAccessSection({ tier }: { tier: Tier }) {
  if (tier === 'explorer') return null
  const token = createGrantToken('full')
  const tools = ['platform-picker', 'hook-generator', 'content-calendar'] as const
  return (
    <div className="p-6 rounded-lg border border-indigo-500/30 bg-indigo-950/20">
      <div className="text-xs font-bold tracking-widest uppercase text-indigo-400 mb-1">
        AI Creator Tools — included with {tier === 'sovereign' ? 'Sovereign' : 'Operator'} plan
      </div>
      <div className="grid grid-cols-1 gap-3 mt-4">
        {tools.map(tool => {
          const url  = `${TOOL_URLS[tool]}?aegis_token=${encodeURIComponent(token)}`
          const meta = TOOL_LABELS[tool]
          return (
            <a key={tool} href={url} target="_blank" rel="noopener noreferrer"
              className="flex items-center justify-between p-3 rounded border border-gray-700 bg-gray-900 hover:border-indigo-500/60 hover:bg-gray-800 transition-all group">
              <div>
                <div className="text-sm text-white font-medium group-hover:text-indigo-300 transition-colors">{meta.name}</div>
                <div className="text-xs text-gray-500">{meta.tagline}</div>
              </div>
              <span className="text-gray-600 group-hover:text-indigo-400 text-sm transition-colors">→</span>
            </a>
          )
        })}
      </div>
    </div>
  )
}

function ApiKeyDisplay({ apiKey, tier }: { apiKey: string; tier: Tier }) {
  const curlExample = `curl -X POST ${BASE}/platform/collaborate \\\n  -H "x-api-key: ${apiKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"objective":"Enter EU market","mode":"gtm","live":false}'`
  return (
    <div className="mt-10 max-w-2xl mx-auto space-y-6">
      <div className="p-6 rounded-lg border border-indigo-500/40 bg-indigo-950/30">
        <div className="flex items-center gap-2 mb-4">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-green-400 text-sm font-mono">KEY PROVISIONED — {TIERS[tier].label} · {TIERS[tier].runs}</span>
        </div>
        <p className="text-gray-400 text-sm mb-3">
          Store this securely — it will not be shown again.
          Send as the <code className="text-indigo-300 text-xs">x-api-key</code> header.
        </p>
        <div className="flex items-center gap-3 bg-gray-900 rounded p-3 border border-gray-700">
          <code className="text-indigo-300 font-mono text-sm flex-1 break-all">{apiKey}</code>
          <CopyButton text={apiKey} />
        </div>
      </div>
      <div className="p-6 rounded-lg border border-gray-700 bg-gray-900/50">
        <div className="text-xs font-bold tracking-widest uppercase text-indigo-400 mb-4">Quickstart</div>
        <div className="relative bg-gray-950 rounded p-4 border border-gray-800">
          <pre className="text-xs text-gray-300 overflow-x-auto font-mono leading-relaxed whitespace-pre-wrap">{curlExample}</pre>
          <div className="absolute top-2 right-2"><CopyButton text={curlExample} /></div>
        </div>
      </div>
      <ToolAccessSection tier={tier} />
    </div>
  )
}

function TierCard({ tier, selected, onSelect }: { tier: Tier; selected: boolean; onSelect: () => void }) {
  const t = TIERS[tier]
  return (
    <button onClick={onSelect}
      className={`text-left w-full p-5 rounded-lg border transition-all ${selected ? 'border-2 bg-gray-800' : 'border border-gray-700 bg-gray-900 hover:border-gray-600'}`}
      style={{ borderColor: selected ? t.accent : undefined }}>
      <div className="flex items-start justify-between mb-2">
        <span className="font-mono text-sm font-semibold" style={{ color: t.accent }}>{t.label}</span>
        <span className="text-white font-bold text-lg">{t.price}</span>
      </div>
      <div className="text-xs text-gray-400 mb-3">{t.runs}{t.monthly ? ` · ${t.monthly}` : ''}</div>
      <p className="text-gray-400 text-xs leading-relaxed">{t.description}</p>
    </button>
  )
}

export function PricingPage() {
  const [email,        setEmail]        = useState('')
  const [tier,         setTier]         = useState<Tier>('operator')
  const [apiKey,       setApiKey]       = useState<string | null>(null)
  const [error,        setError]        = useState<string | null>(null)
  const [loading,      setLoading]      = useState(false)
  const [stripeSent,   setStripeSent]   = useState(false)

  // Clear error when email/tier changes
  useEffect(() => { setError(null) }, [email, tier])

  async function provisionExplorer() {
    const em = email.trim()
    if (!em || !em.includes('@')) { setError('Enter a valid email first.'); return }
    setError(null); setLoading(true)
    try {
      const resp = await fetch(PROVISION_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier: 'explorer', email: em }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.error ?? `HTTP ${resp.status}`)
      setApiKey(data.api_key as string)
      setTier('explorer')
    } catch (e) { setError(String(e)) }
    finally { setLoading(false) }
  }

  function openStripe(t: Tier) {
    const em = email.trim()
    if (!em || !em.includes('@')) { setError('Enter a valid email first.'); return }
    const link = t === 'operator' ? STRIPE_OPERATOR_LINK : STRIPE_SOVEREIGN_LINK
    if (!link) { setError('Stripe payment link not configured. Contact api@aegisomega.com.'); return }
    setError(null)
    const url = `${link}?prefilled_email=${encodeURIComponent(em)}`
    window.open(url, '_blank', 'noopener,noreferrer')
    setStripeSent(true)
  }

  if (apiKey) return (
    <div className="min-h-screen bg-gray-950 text-white px-4 py-16">
      <div className="max-w-2xl mx-auto">
        <a href="/" className="flex items-center gap-2 mb-12 text-gray-400 hover:text-white transition-colors text-sm">← aegisomega.com</a>
        <ApiKeyDisplay apiKey={apiKey} tier={tier} />
      </div>
    </div>
  )

  if (stripeSent) return (
    <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center px-4">
      <div className="max-w-md text-center">
        <div className="text-4xl mb-6">✓</div>
        <h2 className="text-xl font-bold text-white mb-3">Stripe checkout opened</h2>
        <p className="text-gray-400 text-sm leading-relaxed mb-6">
          Complete payment in the Stripe tab. Your API key will be emailed to{' '}
          <strong className="text-white">{email}</strong> within seconds of confirmation.
        </p>
        <button onClick={() => setStripeSent(false)}
          className="text-gray-500 text-xs underline hover:text-gray-300 transition-colors">
          ← Back to pricing
        </button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between max-w-5xl mx-auto">
        <a href="/" className="text-gray-300 hover:text-white text-sm transition-colors">← AEGIS-Ω</a>
        <span className="text-gray-500 text-xs font-mono">PLATFORM ACCESS</span>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-14">
        <div className="text-center mb-12">
          <h1 className="text-3xl font-bold text-white mb-3">API Access</h1>
          <p className="text-gray-400 max-w-md mx-auto text-sm leading-relaxed">
            39 autonomous agents. SHA-256 hash-chained audit trail. Constitutional governance on every cycle.
          </p>
        </div>

        <div className="max-w-md mx-auto mb-8">
          <label className="block text-gray-400 text-xs font-mono mb-2 uppercase tracking-wider">
            Your email — key delivered here
          </label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full bg-gray-900 border border-gray-700 rounded px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500 text-sm" />
        </div>

        {error && (
          <div className="max-w-md mx-auto mb-6 p-3 rounded border border-red-800/60 bg-red-950/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
          {(['explorer', 'operator', 'sovereign'] as Tier[]).map(t => (
            <TierCard key={t} tier={t} selected={tier === t} onSelect={() => setTier(t)} />
          ))}
        </div>

        <div className="max-w-sm mx-auto">
          {tier === 'explorer' && (
            <button onClick={provisionExplorer} disabled={loading}
              className="w-full py-3 rounded font-semibold text-sm bg-gray-700 hover:bg-gray-600 text-white disabled:opacity-50 transition-colors">
              {loading ? 'Provisioning…' : 'Get Free Explorer Access'}
            </button>
          )}

          {tier === 'operator' && (
            <div>
              <div className="text-center text-gray-500 text-xs mb-3 font-mono">$49 one-time · 500 governed API calls</div>
              <button onClick={() => openStripe('operator')}
                className="w-full py-3 rounded font-semibold text-sm bg-indigo-600 hover:bg-indigo-500 text-white transition-colors">
                Pay $49 with Stripe →
              </button>
            </div>
          )}

          {tier === 'sovereign' && (
            <div>
              <div className="text-center text-gray-500 text-xs mb-3 font-mono">$499 one-time · unlimited governed API calls</div>
              <button onClick={() => openStripe('sovereign')}
                className="w-full py-3 rounded font-semibold text-sm bg-amber-600 hover:bg-amber-500 text-white transition-colors">
                Pay $499 with Stripe →
              </button>
            </div>
          )}
        </div>

        <div className="mt-14 border-t border-gray-800 pt-8 text-center">
          <p className="text-gray-600 text-xs max-w-lg mx-auto leading-relaxed">
            API keys are provisioned immediately after payment confirmation and emailed to you.
            Runs counted per successful <code className="text-gray-500">POST /platform/collaborate</code>.
            No subscription, no recurring charges.{' '}
            <a href="mailto:info@aegisomega.com" className="text-gray-500 hover:text-gray-400 underline">info@aegisomega.com</a>
          </p>
        </div>
      </main>
    </div>
  )
}
