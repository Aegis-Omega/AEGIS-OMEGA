// AEGIS-Ω Platform Pricing
// Tiers: Explorer (free / 10 runs) · Operator ($49 / 500 runs) · Sovereign ($499 / unlimited)
// Payment: PayPal Smart Buttons for paid tiers; direct provision for Explorer.
// Server captures orders + provisions API keys via supabase/functions/verify-paypal.
import { useEffect, useRef, useState } from 'react'

const SUPABASE_URL     = import.meta.env.VITE_SUPABASE_URL  as string | undefined
// Client ID is public — embedded in the PayPal SDK URL visible to all visitors
const PAYPAL_CLIENT_ID = (import.meta.env.VITE_PAYPAL_CLIENT_ID as string | undefined)
  || 'AcVwy62A-8ZX7SebJUthiqWQIxnYQHPIabLMLFeZbZX0nTT1PiNoULhTLVjkpv4yD8Kbx2Eae-6X6eGn'
const PROVISION_URL    = SUPABASE_URL ? `${SUPABASE_URL}/functions/v1/verify-paypal` : ''

declare global {
  interface Window {
    paypal?: {
      Buttons: (cfg: PayPalButtonConfig) => { render: (el: HTMLElement) => void }
    }
  }
}

interface PayPalButtonConfig {
  createOrder: (data: unknown, actions: PayPalActions) => Promise<string>
  onApprove:   (data: { orderID: string }) => Promise<void>
  onError:     (err: unknown) => void
  style?:      Record<string, unknown>
}
interface PayPalActions {
  order: { create: (o: object) => Promise<string> }
}

type Tier = 'explorer' | 'operator' | 'sovereign'

const TIERS: Record<Tier, { label: string; price: string; monthly: string; runs: string; accent: string; description: string }> = {
  explorer:  {
    label: 'Explorer',  price: 'Free',  monthly: '',
    runs: '10 runs',       accent: '#6b7280',
    description: 'Evaluate AEGIS-Ω. Run 10 governed cycles — no card required.',
  },
  operator:  {
    label: 'Operator',  price: '$49',   monthly: 'one-time',
    runs: '500 runs',      accent: '#818cf8',
    description: '500 governed API calls. Full 39-agent collaboration. SHA-256 audit chain.',
  },
  sovereign: {
    label: 'Sovereign', price: '$499',  monthly: 'one-time',
    runs: 'Unlimited runs', accent: '#f59e0b',
    description: 'No run cap. Priority throughput. Constitutional governance at every call.',
  },
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button
      onClick={copy}
      className="text-xs px-3 py-1 rounded border border-gray-600 hover:border-indigo-400 text-gray-300 hover:text-indigo-300 transition-colors"
    >
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  )
}

const BASE = 'https://aegis-vertex.aegisomega.com'

function ApiKeyDisplay({ apiKey, tier }: { apiKey: string; tier: Tier }) {
  const curlExample = `curl -X POST ${BASE}/platform/collaborate \\
  -H "x-api-key: ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"objective":"Enter EU market","mode":"gtm","live":false}'`

  const statusExample = `curl ${BASE}/platform/status \\
  -H "x-api-key: ${apiKey}"`

  return (
    <div className="mt-10 max-w-2xl mx-auto space-y-6">
      {/* Key */}
      <div className="p-6 rounded-lg border border-indigo-500/40 bg-indigo-950/30">
        <div className="flex items-center gap-2 mb-4">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-green-400 text-sm font-mono">KEY PROVISIONED — {TIERS[tier].label} tier · {TIERS[tier].runs}</span>
        </div>
        <p className="text-gray-400 text-sm mb-3">
          Store this securely — it will not be shown again. Send it as the{' '}
          <code className="text-indigo-300 text-xs">x-api-key</code> header on every request.
        </p>
        <div className="flex items-center gap-3 bg-gray-900 rounded p-3 border border-gray-700">
          <code className="text-indigo-300 font-mono text-sm flex-1 break-all">{apiKey}</code>
          <CopyButton text={apiKey} />
        </div>
      </div>

      {/* Quickstart */}
      <div className="p-6 rounded-lg border border-gray-700 bg-gray-900/50">
        <div className="text-xs font-bold tracking-widest uppercase text-indigo-400 mb-4">Quickstart — run this now</div>

        <div className="mb-4">
          <div className="text-gray-500 text-xs mb-2">1. Start a 39-agent collaboration cycle</div>
          <div className="relative bg-gray-950 rounded p-4 border border-gray-800">
            <pre className="text-xs text-gray-300 overflow-x-auto font-mono leading-relaxed whitespace-pre-wrap">{curlExample}</pre>
            <div className="absolute top-2 right-2">
              <CopyButton text={curlExample} />
            </div>
          </div>
        </div>

        <div className="mb-4">
          <div className="text-gray-500 text-xs mb-2">2. Check your remaining runs</div>
          <div className="relative bg-gray-950 rounded p-4 border border-gray-800">
            <pre className="text-xs text-gray-300 overflow-x-auto font-mono">{statusExample}</pre>
            <div className="absolute top-2 right-2">
              <CopyButton text={statusExample} />
            </div>
          </div>
        </div>

        <div className="mt-4 text-gray-600 text-xs">
          Every response includes <code className="text-gray-500">contract_version</code>,{' '}
          <code className="text-gray-500">execution_id</code>, and{' '}
          <code className="text-gray-500">audit_chain_hash</code> — your cryptographic proof of each run.
          Questions? <a href="mailto:info@aegisomega.com" className="text-gray-400 hover:text-gray-300 underline">info@aegisomega.com</a>
        </div>
      </div>
    </div>
  )
}

function TierCard({
  tier,
  selected,
  onSelect,
}: {
  tier: Tier
  selected: boolean
  onSelect: () => void
}) {
  const t = TIERS[tier]
  return (
    <button
      onClick={onSelect}
      className={`
        text-left w-full p-5 rounded-lg border transition-all
        ${selected
          ? 'border-2 bg-gray-800'
          : 'border border-gray-700 bg-gray-900 hover:border-gray-600'}
      `}
      style={{ borderColor: selected ? t.accent : undefined }}
    >
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
  const [email,     setEmail]     = useState('')
  const [tier,      setTier]      = useState<Tier>('operator')
  const [apiKey,    setApiKey]    = useState<string | null>(null)
  const [error,     setError]     = useState<string | null>(null)
  const [loading,   setLoading]   = useState(false)
  const [sdkReady,  setSdkReady]  = useState(false)

  const emailRef      = useRef(email)
  emailRef.current    = email
  const tierRef       = useRef(tier)
  tierRef.current     = tier
  const operatorRef   = useRef<HTMLDivElement>(null)
  const sovereignRef  = useRef<HTMLDivElement>(null)
  const rendered      = useRef(false)

  // Load PayPal JS SDK once
  useEffect(() => {
    if (window.paypal) { setSdkReady(true); return }
    if (!PAYPAL_CLIENT_ID) return
    if (document.getElementById('paypal-sdk')) return

    const script    = document.createElement('script')
    script.id       = 'paypal-sdk'
    script.src      = `https://www.paypal.com/sdk/js?client-id=${PAYPAL_CLIENT_ID}&currency=USD&intent=capture`
    script.onload   = () => setSdkReady(true)
    script.onerror  = () => setError('Failed to load PayPal SDK. Check your internet connection.')
    document.head.appendChild(script)
  }, [])

  async function provision(orderId: string | undefined, t: Tier) {
    const em = emailRef.current.trim()
    if (!em || !em.includes('@')) { setError('Enter a valid email first.'); return }
    if (!PROVISION_URL)           { setError('Supabase URL not configured.'); return }
    setError(null)
    setLoading(true)
    try {
      const resp = await fetch(PROVISION_URL, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ order_id: orderId, tier: t, email: em }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.error ?? `HTTP ${resp.status}`)
      setApiKey(data.api_key as string)
      setTier(t)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  // Render PayPal buttons once SDK is ready (buttons use emailRef/tierRef internally)
  useEffect(() => {
    if (!sdkReady || !window.paypal || rendered.current) return

    const renderButtons = (ref: React.RefObject<HTMLDivElement | null>, t: Tier, amount: string) => {
      if (!ref.current) return
      window.paypal!.Buttons({
        createOrder: (_d: unknown, actions: PayPalActions) => {
          const em = emailRef.current.trim()
          if (!em || !em.includes('@')) {
            setError('Enter your email above before proceeding to payment.')
            return Promise.reject(new Error('email required'))
          }
          setError(null)
          return actions.order.create({
            purchase_units: [{
              amount: { value: amount, currency_code: 'USD' },
              description: `AEGIS-Ω ${TIERS[t].label} — ${TIERS[t].runs}`,
            }],
          })
        },
        onApprove: async (data: { orderID: string }) => {
          await provision(data.orderID, t)
        },
        onError: (err: unknown) => {
          setError(`PayPal error: ${String(err)}`)
        },
        style: { shape: 'rect', color: 'black', layout: 'vertical', label: 'pay', height: 40 },
      }).render(ref.current!)
    }

    if (operatorRef.current)  renderButtons(operatorRef,  'operator',  '49.00')
    if (sovereignRef.current) renderButtons(sovereignRef, 'sovereign', '499.00')
    rendered.current = true
  }, [sdkReady])

  if (apiKey) return (
    <div className="min-h-screen bg-gray-950 text-white px-4 py-16">
      <div className="max-w-2xl mx-auto">
        <a href="/" className="flex items-center gap-2 mb-12 text-gray-400 hover:text-white transition-colors text-sm">
          ← aegisomega.com
        </a>
        <ApiKeyDisplay apiKey={apiKey} tier={tier} />
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Nav */}
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between max-w-5xl mx-auto">
        <a href="/" className="text-gray-300 hover:text-white text-sm transition-colors">← AEGIS-Ω</a>
        <span className="text-gray-500 text-xs font-mono">PLATFORM ACCESS</span>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-14">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-3xl font-bold text-white mb-3">API Access</h1>
          <p className="text-gray-400 max-w-md mx-auto text-sm leading-relaxed">
            39 Mythos-level autonomous agents. SHA-256 hash-chained audit trail.
            Constitutional governance on every collaboration cycle.
          </p>
        </div>

        {/* Email (shared across tiers) */}
        <div className="max-w-md mx-auto mb-8">
          <label className="block text-gray-400 text-xs font-mono mb-2 uppercase tracking-wider">
            Your email — API key delivered here
          </label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full bg-gray-900 border border-gray-700 rounded px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500 text-sm"
          />
        </div>

        {/* Error */}
        {error && (
          <div className="max-w-md mx-auto mb-6 p-3 rounded border border-red-800/60 bg-red-950/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Tier cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
          {(['explorer', 'operator', 'sovereign'] as Tier[]).map(t => (
            <TierCard key={t} tier={t} selected={tier === t} onSelect={() => setTier(t)} />
          ))}
        </div>

        {/* Payment / provision area */}
        <div className="max-w-sm mx-auto">
          {tier === 'explorer' && (
            <button
              onClick={() => provision(undefined, 'explorer')}
              disabled={loading}
              className="w-full py-3 rounded font-semibold text-sm bg-gray-700 hover:bg-gray-600 text-white disabled:opacity-50 transition-colors"
            >
              {loading ? 'Provisioning…' : 'Get Free Explorer Access'}
            </button>
          )}

          {tier === 'operator' && (
            <div>
              <div className="text-center text-gray-500 text-xs mb-3 font-mono">
                $49 one-time · 500 governed API calls
              </div>
              {!PAYPAL_CLIENT_ID && (
                <p className="text-yellow-600 text-xs text-center">PayPal not configured — set VITE_PAYPAL_CLIENT_ID.</p>
              )}
              <div ref={operatorRef} className={!sdkReady ? 'opacity-40' : ''}>
                {!sdkReady && PAYPAL_CLIENT_ID && (
                  <div className="text-center text-gray-600 text-xs py-4">Loading PayPal…</div>
                )}
              </div>
            </div>
          )}

          {tier === 'sovereign' && (
            <div>
              <div className="text-center text-gray-500 text-xs mb-3 font-mono">
                $499 one-time · unlimited governed API calls
              </div>
              {!PAYPAL_CLIENT_ID && (
                <p className="text-yellow-600 text-xs text-center">PayPal not configured — set VITE_PAYPAL_CLIENT_ID.</p>
              )}
              <div ref={sovereignRef} className={!sdkReady ? 'opacity-40' : ''}>
                {!sdkReady && PAYPAL_CLIENT_ID && (
                  <div className="text-center text-gray-600 text-xs py-4">Loading PayPal…</div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer note */}
        <div className="mt-14 border-t border-gray-800 pt-8 text-center">
          <p className="text-gray-600 text-xs max-w-lg mx-auto leading-relaxed">
            API keys are provisioned immediately after payment confirmation.
            Runs are counted per successful <code className="text-gray-500">POST /platform/collaborate</code> call.
            No subscription, no recurring charges.{' '}
            <a href="mailto:info@aegisomega.com" className="text-gray-500 hover:text-gray-400 underline">
              info@aegisomega.com
            </a>
          </p>
        </div>
      </main>
    </div>
  )
}
