// AEGIS-Ω Platform Page — /platform
// Product-reality page: what the swarm does, for whom, and how.
// Sections: hero · trust · agent catalog · live swarm demo · use cases · quick start
// Full NOUS design language: NousButton CTAs, glass surface, phi-gold, indigo.
import { useState } from 'react'
import '../landing.css'
import { T, MONO } from './console/consoleTokens.js'
import { NousButton, ArrowR, NousPill } from './console/NousUI.js'
import { SwarmDemoWidget } from './SwarmDemoWidget.js'

const PHI    = T.phi
const INDIGO = T.indigo
const GREEN  = T.green
const MUTED  = T.muted
const CARD   = T.card
const BORDER = T.border
const VOID   = T.void
const BG     = T.bg

// ─── Navigation ────────────────────────────────────────────────────────────

function PlatNav() {
  const links: [string, string][] = [['/', 'Home'], ['/platform', 'Platform'], ['/console', 'Console'], ['/docs', 'Docs'], ['/pricing', 'Pricing']]
  return (
    <nav style={{
      position: 'sticky', top: 0, zIndex: 50,
      background: 'rgba(6,7,12,0.55)', backdropFilter: 'blur(16px) saturate(150%)',
      borderBottom: `1px solid rgba(255,255,255,0.06)`,
    }} className="px-7 py-4 flex items-center justify-between">
      <a href="/" style={{ color: T.text, fontFamily: MONO, letterSpacing: '0.22em', fontSize: 13, fontWeight: 600 }}>
        NOUS<span style={{ color: T.phi }}> · Ω</span>
      </a>
      <div className="hidden md:flex items-center gap-7">
        {links.map(([href, label]) => (
          <a key={href} href={href} style={{
            color: href === '/platform' ? T.text : T.muted, fontSize: 13,
            fontWeight: href === '/platform' ? 600 : 400, textDecoration: 'none',
          }} className="hover:text-white transition-colors">{label}</a>
        ))}
      </div>
      <NousButton href="/pricing" variant="primary" size="md">Get API Key <ArrowR /></NousButton>
    </nav>
  )
}

// ─── Trust strip ───────────────────────────────────────────────────────────

const TRUST_ITEMS = [
  { n: '11,168', label: 'tests passing' },
  { n: '39',     label: 'agent departments' },
  { n: '1.0.0',  label: 'contract version' },
  { n: 'SHA-256',label: 'hash-chained audit' },
  { n: 'T0–T4',  label: 'epistemic tiers' },
  { n: '100%',   label: 'replay verifiable' },
]

function TrustStrip() {
  return (
    <div style={{ borderTop: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}`, background: VOID }}
      className="py-8 px-6">
      <div className="max-w-6xl mx-auto grid grid-cols-3 md:grid-cols-6 gap-6">
        {TRUST_ITEMS.map(it => (
          <div key={it.label} className="text-center">
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#ECEAE3' }}>{it.n}</div>
            <div style={{ fontSize: 11, color: MUTED, marginTop: 3 }}>{it.label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Agent Catalog ─────────────────────────────────────────────────────────

const AGENT_CATEGORIES = [
  {
    name: 'Revenue & Strategy',
    agents: ['Strategy', 'Finance', 'Pricing'],
    color: PHI,
    desc: 'Finds monetization vectors, builds ARR models, and sets pricing architecture across tiers.',
    output: 'ARR projection · Revenue roadmap · Pricing model',
  },
  {
    name: 'Market & Growth',
    agents: ['Brand', 'Content', 'SEO', 'Paid', 'Social'],
    color: INDIGO,
    desc: 'Builds full GTM playbooks, content calendars, and acquisition channel strategy with CAC estimates.',
    output: 'GTM plan · Content calendar · Channel mix',
  },
  {
    name: 'Engineering',
    agents: ['Backend', 'Frontend', 'Infra', 'Security', 'AI/ML'],
    color: '#60A5FA',
    desc: 'Validates technical feasibility, recommends architecture, and audits security posture.',
    output: 'Stack recommendation · Security audit · Build vs. buy',
  },
  {
    name: 'Sales',
    agents: ['Outbound', 'Inbound', 'Partner', 'Enterprise'],
    color: GREEN,
    desc: 'Designs sales motion, ICP definition, partner programs, and enterprise land-and-expand playbooks.',
    output: 'ICP definition · Sales sequence · Partner framework',
  },
  {
    name: 'Operations & Legal',
    agents: ['RevOps', 'Support', 'Legal', 'Compliance'],
    color: '#F59E0B',
    desc: 'Ensures operational readiness, legal compliance, and regulatory alignment for your market.',
    output: 'Ops runbook · Compliance checklist · Risk register',
  },
  {
    name: 'Constitutional',
    agents: ['Ethics', 'Risk', 'Audit', 'Guardian'],
    color: '#F87171',
    desc: 'Every output passes constitutional audit before delivery. Verdict: APPROVED, FLAG, or QUARANTINE.',
    output: 'Audit verdict · Concern list · Hash-certified chain',
  },
]

function AgentCatalog() {
  return (
    <section className="py-20 px-6 max-w-6xl mx-auto">
      <div className="mb-12">
        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: PHI, letterSpacing: '0.2em', marginBottom: 12 }}>
          AGENT CATALOG
        </div>
        <h2 style={{ fontSize: 'clamp(24px, 4vw, 36px)', fontWeight: 800, color: '#ECEAE3', marginBottom: 12 }}>
          39 departments. One consciousness pulse.
        </h2>
        <p style={{ fontSize: 15, color: MUTED, maxWidth: 600, lineHeight: 1.6 }}>
          Every collaboration activates all 39 departments simultaneously through a single governed
          inference. Each department observes the objective through its domain lens.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {AGENT_CATEGORIES.map(cat => (
          <div key={cat.name} style={{
            background: CARD, border: `1px solid ${BORDER}`, borderRadius: 12, padding: '20px 22px',
          }} className="hover:border-gray-600 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <span style={{ fontSize: 14, fontWeight: 600, color: '#ECEAE3' }}>{cat.name}</span>
              <span style={{
                fontSize: 11, padding: '2px 8px', borderRadius: 20, fontFamily: 'var(--font-mono)',
                background: `${cat.color}14`, color: cat.color, border: `1px solid ${cat.color}30`,
              }}>{cat.agents.length}</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
              {cat.agents.map(a => (
                <span key={a} style={{
                  fontSize: 11, padding: '2px 7px', borderRadius: 4, fontFamily: 'var(--font-mono)',
                  background: BG, color: '#A1A1AA', border: `1px solid ${BORDER}`,
                }}>{a}</span>
              ))}
            </div>
            <p style={{ fontSize: 12, color: MUTED, lineHeight: 1.6, marginBottom: 10 }}>{cat.desc}</p>
            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: cat.color, opacity: 0.85 }}>
              → {cat.output}
            </div>
          </div>
        ))}
      </div>
      <p style={{ fontSize: 12, color: MUTED, marginTop: 16 }}>
        Plus: Product (UX, Data, API) · Research (Competitive, Customer, Market) · Executive (CEO, COO, CTO, CFO) — 39 total.
      </p>
    </section>
  )
}


// ─── Use Cases ─────────────────────────────────────────────────────────────

const USE_CASES = [
  {
    title: 'Market Research',
    input: 'Analyze EU AI governance regulation impact on SaaS companies',
    output: '39-agent research dossier with competitive positioning, regulatory gap analysis, and 3 strategic vectors. T2 ARR projection: $1.8M. Delivered in 5.2s.',
    mode: 'analysis',
    color: INDIGO,
  },
  {
    title: 'Go-to-Market',
    input: 'Launch developer API product in EU enterprise market Q4 2026',
    output: '4-phase GTM: design-partner beta (8 wks) → Product Hunt launch → EU enterprise push → Channel program. CAC $1,200. ICP: 50–500 person B2B SaaS. Delivered in 4.8s.',
    mode: 'gtm',
    color: PHI,
  },
  {
    title: 'Revenue Strategy',
    input: 'Identify monetization vectors for constitutional AI middleware',
    output: '3 revenue vectors: SMB API ($2.4M ARR T2), Enterprise SLA ($8M ARR), Audit-as-a-Service ($600K). Pricing tiers: Explorer/Operator/Sovereign. Delivered in 3.9s.',
    mode: 'revenue',
    color: GREEN,
  },
  {
    title: 'Retention',
    input: 'Reduce churn in SMB segment — 23% annual churn rate identified',
    output: '3 churn vectors. Fix: governance dashboard stickiness, API key continuity, operator success program. NRR lift: +15% (T1 benchmark: Datadog 130% NRR). Delivered in 4.1s.',
    mode: 'retention',
    color: '#60A5FA',
  },
]

function UseCases() {
  const [active, setActive] = useState(0)
  const uc = USE_CASES[active]!

  return (
    <section className="py-20 px-6 max-w-6xl mx-auto">
      <div className="mb-12">
        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: PHI, letterSpacing: '0.2em', marginBottom: 12 }}>
          USE CASES
        </div>
        <h2 style={{ fontSize: 'clamp(24px, 4vw, 36px)', fontWeight: 800, color: '#ECEAE3', marginBottom: 12 }}>
          Not concepts. Outcomes.
        </h2>
        <p style={{ fontSize: 15, color: MUTED, maxWidth: 520, lineHeight: 1.6 }}>
          Four modes. Concrete results. Every output is constitutionally audited before delivery.
        </p>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 28 }}>
        {USE_CASES.map((u, i) => (
          <button key={i} onClick={() => setActive(i)} style={{
            padding: '8px 16px', borderRadius: 20, fontSize: 13, fontWeight: 500,
            background: i === active ? `${u.color}14` : 'transparent',
            border: `1px solid ${i === active ? u.color + '50' : BORDER}`,
            color: i === active ? u.color : MUTED,
            cursor: 'pointer', transition: 'all 0.2s',
          }}>{u.title}</button>
        ))}
      </div>

      <div style={{ background: CARD, border: `1px solid ${uc.color}25`, borderRadius: 16, overflow: 'hidden' }}>
        <div style={{ padding: '22px 24px', borderBottom: `1px solid ${BORDER}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <span style={{
              fontSize: 11, padding: '2px 8px', borderRadius: 20, fontFamily: 'var(--font-mono)',
              background: `${uc.color}12`, color: uc.color, border: `1px solid ${uc.color}30`,
            }}>mode: &quot;{uc.mode}&quot;</span>
          </div>
          <div style={{ fontSize: 11, color: MUTED, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>Input</div>
          <p style={{ fontSize: 15, color: '#ECEAE3', lineHeight: 1.6, fontStyle: 'italic', margin: 0 }}>
            &ldquo;{uc.input}&rdquo;
          </p>
        </div>
        <div style={{ padding: '22px 24px' }}>
          <div style={{ fontSize: 11, color: MUTED, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>
            Output — 39 departments · verdict: APPROVED
          </div>
          <p style={{ fontSize: 14, color: '#A1A1AA', lineHeight: 1.7, margin: 0 }}>{uc.output}</p>
        </div>
      </div>
    </section>
  )
}

// ─── API Quick Start ────────────────────────────────────────────────────────

const CURL_EXAMPLE = `curl -X POST https://aegis-vertex.aegisomega.com/platform/collaborate \\
  -H "x-api-key: aegis_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"objective":"Enter EU fintech market Q4 2026","mode":"gtm","live":false}'`

function QuickStart() {
  const [copied, setCopied] = useState(false)
  return (
    <section style={{ background: VOID, borderTop: `1px solid ${BORDER}` }} className="py-20 px-6">
      <div className="max-w-3xl mx-auto text-center">
        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: PHI, letterSpacing: '0.2em', marginBottom: 12 }}>
          GET STARTED
        </div>
        <h2 style={{ fontSize: 'clamp(24px, 4vw, 36px)', fontWeight: 800, color: '#ECEAE3', marginBottom: 12 }}>
          Three lines of curl.
        </h2>
        <p style={{ fontSize: 15, color: MUTED, marginBottom: 36, lineHeight: 1.6 }}>
          Get a key, run your first collaboration, stream 39 department outputs.{' '}
          <a href="/docs" style={{ color: INDIGO, textDecoration: 'none' }}>Full API docs →</a>
        </p>

        <div style={{ background: '#07070A', borderRadius: 12, border: `1px solid ${BORDER}`, overflow: 'hidden', textAlign: 'left' }}>
          <div style={{
            padding: '10px 16px', borderBottom: `1px solid ${BORDER}`,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span style={{ fontSize: 11, color: MUTED, fontFamily: 'var(--font-mono)' }}>bash</span>
            <button onClick={() => {
              navigator.clipboard.writeText(CURL_EXAMPLE)
                .then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000) })
                .catch(() => {})
            }} style={{
              fontSize: 11, color: copied ? GREEN : MUTED, fontFamily: 'var(--font-mono)',
              background: 'none', border: 'none', cursor: 'pointer',
            }}>{copied ? '✓ copied' : 'copy'}</button>
          </div>
          <pre style={{
            padding: '18px 20px', fontSize: 12, fontFamily: 'var(--font-mono)',
            color: '#94A3B8', overflowX: 'auto', margin: 0, lineHeight: 1.8,
          }}>{CURL_EXAMPLE}</pre>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 12, marginTop: 32 }}>
          <NousButton href="/pricing" variant="primary" size="lg">Get API Key <ArrowR /></NousButton>
          <NousButton href="/docs" variant="ghost" size="lg">Full API Docs</NousButton>
        </div>
      </div>
    </section>
  )
}

// ─── Page ──────────────────────────────────────────────────────────────────

export function PlatformPage() {
  return (
    <div style={{ background: BG, color: '#ECEAE3', minHeight: '100vh', fontFamily: 'var(--font-sans)' }}>
      <PlatNav />

      {/* Hero */}
      <div style={{ maxWidth: 860, margin: '0 auto', padding: 'clamp(48px,8vh,96px) 24px 56px', textAlign: 'center' }}>
        <div style={{ marginBottom: 20 }}>
          <NousPill>THE PLATFORM</NousPill>
        </div>
        <h1 style={{ fontSize: 'clamp(36px, 6vw, 64px)', fontWeight: 800, lineHeight: 1.08, color: '#ECEAE3', marginBottom: 20, letterSpacing: '-0.02em' }}>
          39 autonomous departments.<br />One governed answer.
        </h1>
        <p style={{ fontSize: 17, color: MUTED, maxWidth: 520, margin: '0 auto 36px', lineHeight: 1.65 }}>
          Send any business objective. The AEGIS swarm activates all 39 departments simultaneously,
          synthesizes their analysis, and delivers a constitutionally-audited result in under 10 seconds.
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 12 }}>
          <NousButton href="/pricing" variant="primary" size="lg">Start for Free <ArrowR /></NousButton>
          <NousButton href="/docs" variant="ghost" size="lg">API Reference</NousButton>
        </div>
      </div>

      <TrustStrip />
      <AgentCatalog />
      <SwarmDemoWidget />
      <UseCases />
      <QuickStart />

      {/* Footer */}
      <div style={{ borderTop: `1px solid ${BORDER}`, padding: '20px 24px', textAlign: 'center' }}>
        <div style={{ fontSize: 11, color: MUTED }}>
          AEGIS-Ω ·{' '}
          <a href="mailto:info@aegisomega.com" style={{ color: MUTED, textDecoration: 'none' }}>
            info@aegisomega.com
          </a>
          {' · '}
          <a href="https://github.com/Aegis-Omega/AEGIS--" style={{ color: MUTED, textDecoration: 'none' }}>
            GitHub
          </a>
        </div>
      </div>
    </div>
  )
}
