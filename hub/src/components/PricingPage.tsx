// AEGIS-Ω Pricing — the revenue gate.
// Tiers: Explorer (free/10) · Operator ($49/500) · Sovereign ($499/unlimited)
// Payment: Stripe Checkout for paid tiers; direct provision for Explorer.
// Full NOUS design language: CoreCanvas hero, NousButton CTAs, glass tier cards.
import { useEffect, useState } from 'react'
import { createGrantToken } from '@shared/lib/access.js'
import { T, MONO, SANS } from './console/consoleTokens.js'
import { CoreCanvas } from './console/CoreCanvas.js'
import { NousButton, ArrowR, NousPill } from './console/NousUI.js'

const SUPABASE_URL          = (import.meta.env.VITE_SUPABASE_URL as string | undefined)
  || 'https://rwehltdwpsncnwxzkwik.supabase.co'
const STRIPE_OPERATOR_LINK  = (import.meta.env.VITE_STRIPE_OPERATOR_LINK  as string | undefined) ?? ''
const STRIPE_SOVEREIGN_LINK = (import.meta.env.VITE_STRIPE_SOVEREIGN_LINK as string | undefined) ?? ''
const PROVISION_URL         = `${SUPABASE_URL}/functions/v1/verify-paypal`
const BASE                  = 'https://aegis-vertex.aegisomega.com'

const TOOL_URLS: Record<string, string> = {
  'platform-picker':  (import.meta.env.VITE_URL_PLATFORM_PICKER  as string | undefined) ?? 'https://platform.aegisomega.com',
  'hook-generator':   (import.meta.env.VITE_URL_HOOK_GENERATOR   as string | undefined) ?? 'https://hooks.aegisomega.com',
  'content-calendar': (import.meta.env.VITE_URL_CONTENT_CALENDAR as string | undefined) ?? 'https://calendar.aegisomega.com',
}
const TOOL_LABELS: Record<string, { name: string; tagline: string }> = {
  'platform-picker':  { name: 'Platform Picker',  tagline: 'Right stack for any project' },
  'hook-generator':   { name: 'Hook Generator',   tagline: 'Viral hooks for any audience' },
  'content-calendar': { name: 'Content Calendar', tagline: 'A month of content in minutes' },
}

type Tier = 'explorer' | 'operator' | 'sovereign'

interface TierDef {
  label: string; price: string; priceNote: string; runs: string
  accent: string; pill: string; desc: string
  features: string[]
}

const TIERS: Record<Tier, TierDef> = {
  explorer: {
    label: 'Explorer', price: 'Free', priceNote: 'no card required',
    runs: '10 governed runs', accent: T.sub, pill: '',
    desc: 'Evaluate the swarm. Run 10 full 39-department collaborations.',
    features: [
      '10 governed API calls',
      'Full 39-agent collaboration',
      'SHA-256 audit chain',
      'Constitutional verdict',
      'JSON response payload',
    ],
  },
  operator: {
    label: 'Operator', price: '$49', priceNote: 'one-time',
    runs: '500 governed runs', accent: T.indigo, pill: 'POPULAR',
    desc: '500 governed cycles. Build integrations, automate workflows, run serious analysis.',
    features: [
      '500 governed API calls',
      'Full 39-agent collaboration',
      'SHA-256 audit chain',
      'Constitutional verdict',
      'SSE stream: dag_step events',
      'AI Creator Tools suite',
      'priority queue access',
    ],
  },
  sovereign: {
    label: 'Sovereign', price: '$499', priceNote: 'one-time',
    runs: 'Unlimited runs', accent: T.phi, pill: 'BEST VALUE',
    desc: 'No run cap. No throttling. Constitutional governance on every call, always.',
    features: [
      'Unlimited governed API calls',
      'Full 39-agent collaboration',
      'SHA-256 audit chain + replay',
      'Constitutional verdict',
      'SSE stream: all event types',
      'AI Creator Tools suite',
      'Priority throughput',
      'Agent API tool profiles',
      'Raw artifact access',
    ],
  },
}

const FEATURE_ROWS = [
  ['Governed API calls',     '10',         '500',           '∞'],
  ['39-dept collaboration',  '✓',          '✓',             '✓'],
  ['Hash-chained audit',     '✓',          '✓',             '✓'],
  ['Constitutional verdict', '✓',          '✓',             '✓'],
  ['SSE live stream',        '—',          'dag_step only', 'all events'],
  ['AI Creator Tools',       '—',          '✓',             '✓'],
  ['Priority throughput',    '—',          '—',             '✓'],
  ['Agent API profiles',     '—',          '—',             '✓'],
]

function PricingNav() {
  const links: [string, string][] = [['/', 'Home'], ['/platform', 'Platform'], ['/console', 'Console'], ['/docs', 'Docs'], ['/pricing', 'Pricing']]
  return (
    <nav style={{
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50,
      background: 'rgba(6,7,12,0.55)', backdropFilter: 'blur(16px) saturate(150%)',
      borderBottom: `1px solid rgba(255,255,255,0.06)`,
    }} className="px-7 py-4 flex items-center justify-between">
      <a href="/" style={{ color: T.text, fontFamily: MONO, letterSpacing: '0.22em', fontSize: 13, fontWeight: 600 }}>
        NOUS<span style={{ color: T.phi }}> · Ω</span>
      </a>
      <div className="hidden md:flex items-center gap-7">
        {links.map(([href, label]) => (
          <a key={href} href={href} style={{
            color: href === '/pricing' ? T.text : T.muted, fontSize: 13,
            fontWeight: href === '/pricing' ? 600 : 400, textDecoration: 'none',
          }} className="hover:text-white transition-colors">{label}</a>
        ))}
      </div>
      <NousButton href="/console" variant="ghost" size="md">Open Console</NousButton>
    </nav>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  function copy() {
    navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000) })
  }
  return (
    <button onClick={copy} style={{
      fontSize: 11, padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
      background: copied ? `${T.green}15` : 'rgba(255,255,255,0.06)',
      border: `1px solid ${copied ? T.green + '40' : 'rgba(255,255,255,0.12)'}`,
      color: copied ? T.green : T.sub, fontFamily: MONO, transition: 'all 0.2s',
    }}>{copied ? '✓ copied' : 'copy'}</button>
  )
}

function ToolAccessSection({ tier }: { tier: Tier }) {
  if (tier === 'explorer') return null
  const token = createGrantToken('full')
  const tools = ['platform-picker', 'hook-generator', 'content-calendar'] as const
  return (
    <div style={{
      padding: '20px 24px', borderRadius: 12, marginTop: 24,
      background: `${T.indigo}08`, border: `1px solid ${T.indigo}25`,
    }}>
      <div style={{ fontSize: 11, fontFamily: MONO, color: T.indigo, letterSpacing: '0.14em', marginBottom: 16 }}>
        AI CREATOR TOOLS — INCLUDED
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {tools.map(tool => {
          const url  = `${TOOL_URLS[tool]}?aegis_token=${encodeURIComponent(token)}`
          const meta = TOOL_LABELS[tool]
          return (
            <a key={tool} href={url} target="_blank" rel="noopener noreferrer" style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '12px 16px', borderRadius: 10,
              background: 'rgba(255,255,255,0.03)', border: `1px solid rgba(255,255,255,0.07)`,
              textDecoration: 'none', transition: 'border-color 0.2s, background 0.2s',
            }} className="hover:!bg-white/5 hover:!border-indigo-500/30">
              <div>
                <div style={{ fontSize: 13, color: T.text, fontWeight: 500 }}>{meta.name}</div>
                <div style={{ fontSize: 11, color: T.muted, marginTop: 2 }}>{meta.tagline}</div>
              </div>
              <span style={{ color: T.indigo, fontSize: 13 }}>→</span>
            </a>
          )
        })}
      </div>
    </div>
  )
}

function ApiKeyDisplay({ apiKey, tier }: { apiKey: string; tier: Tier }) {
  const t = TIERS[tier]
  const curlExample = `curl -X POST ${BASE}/platform/collaborate \\\n  -H "x-api-key: ${apiKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"objective":"Enter EU market","mode":"gtm","live":false}'`
  return (
    <div style={{ minHeight: '100vh', background: '#06070C', color: T.text, fontFamily: SANS, position: 'relative' }}>
      <PricingNav />
      <div style={{ maxWidth: 680, margin: '0 auto', padding: '120px 24px 80px' }}>
        <a href="/pricing" style={{ color: T.muted, fontSize: 13, textDecoration: 'none', display: 'inline-block', marginBottom: 40 }}>
          ← back to pricing
        </a>
        <div style={{
          padding: '28px 30px', borderRadius: 16, marginBottom: 24,
          background: `${T.green}08`, border: `1px solid ${T.green}30`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: T.green, boxShadow: `0 0 12px ${T.green}` }} />
            <span style={{ fontFamily: MONO, fontSize: 12, color: T.green, letterSpacing: '0.1em' }}>
              KEY PROVISIONED · {t.label.toUpperCase()} · {t.runs.toUpperCase()}
            </span>
          </div>
          <p style={{ fontSize: 13, color: T.sub, marginBottom: 16, lineHeight: 1.6 }}>
            Store this securely — it will not be shown again. Send it as the{' '}
            <code style={{ color: T.indigo, fontFamily: MONO, fontSize: 11 }}>x-api-key</code> header.
          </p>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            background: 'rgba(0,0,0,0.4)', borderRadius: 10, padding: '12px 16px',
            border: `1px solid rgba(255,255,255,0.08)`,
          }}>
            <code style={{ color: T.indigo, fontFamily: MONO, fontSize: 13, flex: 1, wordBreak: 'break-all' }}>{apiKey}</code>
            <CopyButton text={apiKey} />
          </div>
        </div>

        <div style={{
          padding: '24px 28px', borderRadius: 16, marginBottom: 24,
          background: 'rgba(255,255,255,0.02)', border: `1px solid rgba(255,255,255,0.08)`,
        }}>
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.phi, letterSpacing: '0.14em', marginBottom: 16 }}>
            QUICKSTART
          </div>
          <div style={{ position: 'relative', background: '#06070C', borderRadius: 10, border: `1px solid rgba(255,255,255,0.07)`, overflow: 'hidden' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 16px', borderBottom: `1px solid rgba(255,255,255,0.06)` }}>
              <span style={{ fontSize: 11, color: T.muted, fontFamily: MONO }}>bash</span>
              <CopyButton text={curlExample} />
            </div>
            <pre style={{ padding: '16px 20px', fontSize: 12, fontFamily: MONO, color: '#94A3B8', overflowX: 'auto', margin: 0, lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>{curlExample}</pre>
          </div>
        </div>

        <ToolAccessSection tier={tier} />
      </div>
    </div>
  )
}

function TierCard({ tier, selected, onSelect }: { tier: Tier; selected: boolean; onSelect: () => void }) {
  const t    = TIERS[tier]
  const glow = selected ? `0 0 40px ${t.accent}20, 0 8px 40px rgba(0,0,0,0.6)` : '0 4px 24px rgba(0,0,0,0.4)'
  return (
    <button onClick={onSelect} style={{
      textAlign: 'left', width: '100%', cursor: 'pointer',
      padding: '28px 26px', borderRadius: 16,
      background: selected ? `${t.accent}06` : 'rgba(255,255,255,0.02)',
      border: `${selected ? 2 : 1}px solid ${selected ? t.accent + '60' : 'rgba(255,255,255,0.08)'}`,
      boxShadow: glow,
      transition: 'all 0.3s cubic-bezier(0.2,0.8,0.2,1)',
      transform: selected ? 'translateY(-2px)' : 'translateY(0)',
      position: 'relative',
    }}>
      {t.pill && (
        <div style={{
          position: 'absolute', top: -12, right: 20,
          fontSize: 10, fontFamily: MONO, letterSpacing: '0.14em',
          padding: '4px 10px', borderRadius: 20,
          background: `${t.accent}20`, border: `1px solid ${t.accent}50`,
          color: t.accent,
        }}>{t.pill}</div>
      )}
      <div style={{ marginBottom: 6, display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <span style={{ fontFamily: MONO, fontSize: 12, color: t.accent, letterSpacing: '0.12em' }}>{t.label.toUpperCase()}</span>
        <div style={{ textAlign: 'right' }}>
          <span style={{ fontSize: 26, fontWeight: 800, color: T.text, letterSpacing: '-0.02em' }}>{t.price}</span>
          {t.priceNote && (
            <span style={{ fontSize: 11, color: T.muted, marginLeft: 6, fontFamily: MONO }}>{t.priceNote}</span>
          )}
        </div>
      </div>
      <div style={{ fontSize: 12, color: t.accent, fontFamily: MONO, marginBottom: 14 }}>{t.runs}</div>
      <p style={{ fontSize: 13, color: T.sub, lineHeight: 1.6, marginBottom: 20 }}>{t.desc}</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {t.features.map(f => (
          <div key={f} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ color: selected ? t.accent : T.muted, fontSize: 12, flexShrink: 0 }}>✓</span>
            <span style={{ fontSize: 12, color: T.sub }}>{f}</span>
          </div>
        ))}
      </div>
    </button>
  )
}

function CompareTable() {
  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '0 24px 80px' }}>
      <div style={{ fontSize: 11, fontFamily: MONO, color: T.phi, letterSpacing: '0.2em', marginBottom: 20, textAlign: 'center' }}>
        FULL COMPARISON
      </div>
      <div style={{ borderRadius: 14, overflow: 'hidden', border: `1px solid rgba(255,255,255,0.08)` }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: SANS }}>
          <thead>
            <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
              <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: 12, color: T.muted, fontWeight: 500, borderBottom: `1px solid rgba(255,255,255,0.07)` }}>Feature</th>
              {(['Explorer', 'Operator', 'Sovereign'] as const).map((l, i) => (
                <th key={l} style={{
                  padding: '14px 20px', textAlign: 'center', fontSize: 12, fontWeight: 600,
                  color: [T.sub, T.indigo, T.phi][i],
                  borderBottom: `1px solid rgba(255,255,255,0.07)`,
                }}>{l}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {FEATURE_ROWS.map(([feat, ex, op, sov], rowIdx) => (
              <tr key={feat} style={{ background: rowIdx % 2 ? 'rgba(255,255,255,0.01)' : 'transparent' }}>
                <td style={{ padding: '13px 20px', fontSize: 13, color: T.sub, borderBottom: `1px solid rgba(255,255,255,0.04)` }}>{feat}</td>
                {[ex, op, sov].map((val, i) => (
                  <td key={i} style={{
                    padding: '13px 20px', textAlign: 'center', fontSize: 12,
                    color: val === '—' ? 'rgba(255,255,255,0.15)' : val === '✓' ? T.green : [T.sub, T.indigo, T.phi][i],
                    fontFamily: MONO, borderBottom: `1px solid rgba(255,255,255,0.04)`,
                  }}>{val}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function PricingPage() {
  const [email,      setEmail]      = useState('')
  const [tier,       setTier]       = useState<Tier>('operator')
  const [apiKey,     setApiKey]     = useState<string | null>(null)
  const [error,      setError]      = useState<string | null>(null)
  const [loading,    setLoading]    = useState(false)
  const [stripeSent, setStripeSent] = useState(false)

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
      const data = await resp.json() as { api_key?: string; error?: string }
      if (!resp.ok) throw new Error(data.error ?? `HTTP ${resp.status}`)
      setApiKey(data.api_key!)
      setTier('explorer')
    } catch (e) { setError(String(e)) }
    finally { setLoading(false) }
  }

  function openStripe(t: Tier) {
    const em = email.trim()
    if (!em || !em.includes('@')) { setError('Enter a valid email first.'); return }
    const link = t === 'operator' ? STRIPE_OPERATOR_LINK : STRIPE_SOVEREIGN_LINK
    if (!link) { setError('Stripe payment link not configured — contact api@aegisomega.com'); return }
    setError(null)
    window.open(`${link}?prefilled_email=${encodeURIComponent(em)}`, '_blank', 'noopener,noreferrer')
    setStripeSent(true)
  }

  function handleCTA() {
    if (tier === 'explorer')  return provisionExplorer()
    if (tier === 'operator')  return openStripe('operator')
    if (tier === 'sovereign') return openStripe('sovereign')
  }

  if (apiKey)     return <ApiKeyDisplay apiKey={apiKey} tier={tier} />
  if (stripeSent) return (
    <div style={{ minHeight: '100vh', background: '#06070C', color: T.text, fontFamily: SANS, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center', maxWidth: 440, padding: '0 24px' }}>
        <div style={{
          width: 64, height: 64, borderRadius: '50%', margin: '0 auto 28px',
          background: `${T.green}15`, border: `2px solid ${T.green}50`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 28, color: T.green,
        }}>✓</div>
        <h2 style={{ fontSize: 26, fontWeight: 700, marginBottom: 16 }}>Stripe checkout opened</h2>
        <p style={{ color: T.sub, fontSize: 15, lineHeight: 1.6, marginBottom: 32 }}>
          Complete payment in the Stripe tab. Your API key will be emailed to{' '}
          <strong style={{ color: T.text }}>{email}</strong> within seconds of confirmation.
        </p>
        <NousButton onClick={() => setStripeSent(false)} variant="ghost">← Back to pricing</NousButton>
      </div>
    </div>
  )

  return (
    <div style={{ background: '#06070C', color: T.text, minHeight: '100vh', fontFamily: SANS }}>
      <PricingNav />

      {/* Hero with contained NOUS core */}
      <section style={{
        position: 'relative', textAlign: 'center', overflow: 'hidden',
        padding: 'clamp(110px,16vh,180px) 24px 0', minHeight: '60vh',
      }}>
        <CoreCanvas contained />
        {/* scrim so text reads above the core */}
        <div aria-hidden style={{
          position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 1,
          background: 'linear-gradient(180deg, rgba(6,7,12,0.85) 0%, rgba(6,7,12,0.50) 50%, rgba(6,7,12,0.95) 100%)',
        }} />
        <div style={{ position: 'relative', zIndex: 2 }}>
          <NousPill>API ACCESS</NousPill>
          <h1 style={{
            fontSize: 'clamp(38px, 7vw, 80px)', fontWeight: 800, lineHeight: 1.0,
            letterSpacing: '-0.04em', margin: '24px 0 20px',
            background: 'linear-gradient(180deg, #FFFFFF 0%, #C9CBD6 55%, #9A8050 130%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
          }}>Choose your access</h1>
          <p style={{ fontSize: 'clamp(15px,2vw,18px)', color: '#CBCDD8', maxWidth: 520, margin: '0 auto', lineHeight: 1.65 }}>
            39 governed departments. SHA-256 audit chain. Constitutional verdict on every cycle.
            One flat price — no subscription.
          </p>
        </div>
      </section>

      {/* Main content */}
      <div style={{ maxWidth: 1000, margin: '0 auto', padding: '60px 24px 0' }}>

        {/* Email */}
        <div style={{ maxWidth: 440, margin: '0 auto 40px' }}>
          <label style={{ display: 'block', fontSize: 11, fontFamily: MONO, color: T.muted, letterSpacing: '0.12em', marginBottom: 10, textTransform: 'uppercase' }}>
            Your email — key delivered here
          </label>
          <input
            type="email" value={email} onChange={e => setEmail(e.target.value)}
            placeholder="you@company.com"
            style={{
              width: '100%', boxSizing: 'border-box',
              background: 'rgba(255,255,255,0.04)', border: `1px solid rgba(255,255,255,0.12)`,
              borderRadius: 10, padding: '13px 16px', fontSize: 14, color: T.text,
              outline: 'none', fontFamily: SANS, transition: 'border-color 0.2s',
            }}
            className="focus:!border-indigo-500/60"
          />
        </div>

        {/* Tier cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-10">
          {(['explorer', 'operator', 'sovereign'] as Tier[]).map(t => (
            <TierCard key={t} tier={t} selected={tier === t} onSelect={() => setTier(t)} />
          ))}
        </div>

        {/* Error */}
        {error && (
          <div style={{
            maxWidth: 440, margin: '0 auto 20px', padding: '12px 16px', borderRadius: 10,
            background: `${T.red}10`, border: `1px solid ${T.red}40`, color: T.red, fontSize: 13,
          }}>{error}</div>
        )}

        {/* CTA */}
        <div style={{ maxWidth: 440, margin: '0 auto 16px', textAlign: 'center' }}>
          <NousButton
            onClick={handleCTA}
            variant="primary" size="lg"
            style={{ width: '100%', justifyContent: 'center', opacity: loading ? 0.6 : 1 }}
          >
            {loading ? 'Provisioning…' : tier === 'explorer' ? 'Get Free Explorer Access' : tier === 'operator' ? `Pay $49 · Operator` : `Pay $499 · Sovereign`}
            {!loading && <ArrowR />}
          </NousButton>
          <div style={{ fontSize: 11, color: T.muted, fontFamily: MONO, marginTop: 12 }}>
            {tier === 'explorer' && 'No card required · key emailed instantly'}
            {tier === 'operator' && 'Stripe checkout · key emailed on confirmation'}
            {tier === 'sovereign' && 'Stripe checkout · unlimited runs · priority throughput'}
          </div>
        </div>

        {/* Tool access preview for selected tier */}
        {tier !== 'explorer' && (
          <div style={{ maxWidth: 480, margin: '0 auto' }}>
            <ToolAccessSection tier={tier} />
          </div>
        )}
      </div>

      {/* Comparison table */}
      <div style={{ marginTop: 80 }}>
        <CompareTable />
      </div>

      {/* Footer */}
      <div style={{ borderTop: `1px solid rgba(255,255,255,0.06)`, padding: '28px 24px', textAlign: 'center' }}>
        <p style={{ fontSize: 12, color: T.muted, fontFamily: MONO }}>
          Keys provisioned immediately after confirmation · no subscription · no recurring charges ·{' '}
          <a href="mailto:api@aegisomega.com" style={{ color: T.muted, textDecoration: 'none' }}>api@aegisomega.com</a>
        </p>
      </div>
    </div>
  )
}
