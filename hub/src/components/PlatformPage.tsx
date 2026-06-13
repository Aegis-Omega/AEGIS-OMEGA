// AEGIS-Ω Platform Page — /platform
// Product-reality page: what the swarm does, for whom, and how.
// Sections: hero · trust · agent catalog · execution trace · use cases · quick start
// Full NOUS design language: NousButton CTAs, glass surface, phi-gold, indigo.
import { useEffect, useState } from 'react'
import { T, MONO } from './console/consoleTokens.js'
import { NousButton, ArrowR, NousPill } from './console/NousUI.js'

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

// ─── Live Execution Trace ──────────────────────────────────────────────────

const TRACE_STEPS = [
  { label: 'Objective received',     detail: '"Analyze AI infrastructure competitors in EU market 2026"', icon: '◎', color: '#ECEAE3', type: null },
  { label: 'Research activating',    detail: 'RES-01 Competitive · RES-02 Customer · RES-03 Market', icon: '⬡', color: INDIGO, type: 'dag_step' },
  { label: 'Research complete',      detail: '14 competitors mapped · 3 white-space gaps identified · T1 evidence', icon: '✓', color: GREEN, type: 'agent_event' },
  { label: 'Strategy synthesizing',  detail: 'REV-01 Strategy · EXE-01 CEO · EXE-03 CTO · EXE-04 CFO', icon: '⬡', color: INDIGO, type: 'dag_step' },
  { label: 'Finance projecting',     detail: 'FIN-01 Accounting · FIN-02 Treasury → ARR = $2.4M Y1 (T2 hypothesis)', icon: '✓', color: GREEN, type: 'agent_event' },
  { label: 'Constitutional audit',   detail: 'CON-01 Audit · CON-09 Guardian · GOV-01 Ethics · GOV-02 Risk reviewing…', icon: '⬡', color: '#F59E0B', type: 'dag_step' },
  { label: 'APPROVED',               detail: 'verdict: "APPROVED" · concerns: [] · chain: a3f9c8d2e1b6… · T0 valid', icon: '✓', color: GREEN, type: 'completion' },
  { label: '39 artifacts ready',     detail: '39 departments · 4.1s · is_replay_reconstructable: true · chain_valid: true', icon: '◈', color: PHI, type: 'completion' },
]

function ExecutionTrace() {
  const [active, setActive] = useState(0)
  const [running, setRunning] = useState(true)

  useEffect(() => {
    if (!running) return
    const id = setInterval(() => setActive(a => (a + 1) % TRACE_STEPS.length), 1500)
    return () => clearInterval(id)
  }, [running])

  const step = TRACE_STEPS[active]!

  return (
    <section style={{ background: VOID, borderTop: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}` }}
      className="py-20 px-6">
      <div className="max-w-5xl mx-auto">
        <div className="mb-12">
          <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: PHI, letterSpacing: '0.2em', marginBottom: 12 }}>
            LIVE EXECUTION TRACE
          </div>
          <h2 style={{ fontSize: 'clamp(24px, 4vw, 36px)', fontWeight: 800, color: '#ECEAE3', marginBottom: 12 }}>
            See a real collaboration unfold.
          </h2>
          <p style={{ fontSize: 15, color: MUTED, maxWidth: 540, lineHeight: 1.6 }}>
            Every run streams per-department SSE events as they complete. This is what{' '}
            <code style={{ color: '#94A3B8', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
              GET /platform/executions/live
            </code>{' '}
            looks like in real time.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
          {/* Step list */}
          <div>
            {TRACE_STEPS.map((s, i) => {
              const past    = i < active
              const current = i === active
              return (
                <button key={i} onClick={() => { setRunning(false); setActive(i) }}
                  style={{
                    display: 'block', width: '100%', textAlign: 'left',
                    padding: '9px 12px', borderRadius: 8, marginBottom: 2,
                    background: current ? `${s.color}0D` : 'transparent',
                    border: current ? `1px solid ${s.color}35` : '1px solid transparent',
                    cursor: 'pointer', transition: 'all 0.3s',
                  }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{
                      color: current ? s.color : past ? '#27272D' : '#3F3F46',
                      fontFamily: 'var(--font-mono)', fontSize: 15, lineHeight: 1,
                      transition: 'color 0.3s', flexShrink: 0,
                    }}>{s.icon}</span>
                    <div>
                      <div style={{
                        fontSize: 13, fontWeight: current ? 600 : 400, transition: 'color 0.3s',
                        color: current ? '#ECEAE3' : past ? '#27272D' : '#6B6B7A',
                      }}>{s.label}</div>
                      {s.type && (
                        <div style={{
                          fontSize: 10, color: current ? s.color : '#1E1E22',
                          fontFamily: 'var(--font-mono)', marginTop: 1, transition: 'color 0.3s',
                        }}>{s.type}</div>
                      )}
                    </div>
                  </div>
                </button>
              )
            })}
            <button onClick={() => setRunning(r => !r)} style={{
              marginTop: 8, fontSize: 11, color: MUTED, fontFamily: 'var(--font-mono)',
              padding: '5px 12px', background: 'transparent', border: `1px solid ${BORDER}`,
              borderRadius: 6, cursor: 'pointer',
            }}>{running ? '⏸ pause' : '▶ play'}</button>
          </div>

          {/* Current step detail */}
          <div style={{
            background: '#0C0C0E', border: `1px solid ${step.color}35`,
            borderRadius: 12, padding: '24px',
            boxShadow: `0 0 48px ${step.color}0D`,
            transition: 'border-color 0.4s, box-shadow 0.4s',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <span style={{ fontSize: 22, color: step.color, lineHeight: 1 }}>{step.icon}</span>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: '#ECEAE3' }}>{step.label}</div>
                {step.type && (
                  <div style={{ fontSize: 11, color: step.color, fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                    event.type = &quot;{step.type}&quot;
                  </div>
                )}
              </div>
            </div>
            <div style={{
              background: '#07070A', borderRadius: 8, padding: '12px 14px',
              fontFamily: 'var(--font-mono)', fontSize: 12, color: '#6B6B7A',
              lineHeight: 1.7, wordBreak: 'break-word',
            }}>{step.detail}</div>
            <div style={{ marginTop: 20, display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ height: 2, flex: 1, background: '#17171A', borderRadius: 1, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 1,
                  width: `${((active + 1) / TRACE_STEPS.length) * 100}%`,
                  background: step.color, transition: 'width 1.5s ease',
                }} />
              </div>
              <span style={{ fontSize: 11, color: MUTED, fontFamily: 'var(--font-mono)', flexShrink: 0 }}>
                {active + 1}/{TRACE_STEPS.length}
              </span>
            </div>
          </div>
        </div>
      </div>
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
      <ExecutionTrace />
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
