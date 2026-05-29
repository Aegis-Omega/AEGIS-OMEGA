import { useEffect, useRef } from 'react'
import { PricingTable } from './components/PricingTable.js'
import { SuccessPage } from './components/SuccessPage.js'
import { Shield, Zap, GitBranch, Lock, RefreshCw, ChevronRight, Mail, Activity } from 'lucide-react'

function captureEvent(event: string, props?: Record<string, unknown>): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ph = (window as any).posthog
  if (typeof ph?.capture === 'function') ph.capture(event, props)
}

const TOOLS = [
  {
    num: '01',
    name: 'Platform Picker',
    tagline: 'Platform-fit scoring',
    desc: '6 questions about your niche, style, and goals. Ranked scores across TikTok, YouTube Shorts, Instagram Reels, Snapchat — with reasoning and a radar chart.',
    accentColor: '#7C3AED',
    glowColor: 'rgba(124,58,237,0.12)',
    price: 19,
    url: 'https://aegis-platform-picker.vercel.app',
  },
  {
    num: '02',
    name: 'Hook Generator',
    tagline: 'Viral hook ranking',
    desc: '10 hooks generated and ranked by viral potential. Type-coded by mechanism: curiosity, controversy, value, social proof. Star favourites. Export all at once.',
    accentColor: '#D97706',
    glowColor: 'rgba(217,119,6,0.10)',
    price: 19,
    url: 'https://aegis-hook-generator.vercel.app',
  },
  {
    num: '03',
    name: 'Content Calendar',
    tagline: '4-week content system',
    desc: 'A full month of content — hook, format, and production note for every post. Colour-coded pillars. Export as TXT or CSV.',
    accentColor: '#16A34A',
    glowColor: 'rgba(22,163,74,0.10)',
    price: 19,
    url: 'https://aegis-content-calendar.vercel.app',
  },
]

const PILLARS = [
  {
    icon: Shield,
    title: 'Hash-certified decisions',
    desc: 'Every AI call produces a SHA-256 chain: request → response → chain hash. Any past state can be replayed from scratch and arrive at the same cryptographic fingerprint.',
  },
  {
    icon: GitBranch,
    title: 'Byzantine fault-tolerant at 1/φ',
    desc: 'Swarm convergence threshold set at the golden ratio. No silent failures — quorum proofs with every state transition.',
  },
  {
    icon: Lock,
    title: 'EU AI Act compliance layer',
    desc: 'Martingale-bounded adaptation. AdaptivePower(T) ≤ ReplayVerifiability(T). T0-certified epistemic tier tagging baked into every response.',
  },
  {
    icon: RefreshCw,
    title: '6,400+ invariant tests',
    desc: '436 gate modules. Gossip epoch sealing, peer diversity, RTT histograms, window fill — all hash-chained, all replay-certifiable.',
  },
  {
    icon: Activity,
    title: 'Autopoietic runtime',
    desc: 'Satisfies all five Maturana-Varela autopoietic criteria by architectural necessity. The system knows when it is no longer itself.',
  },
  {
    icon: Zap,
    title: 'Single constitutional law',
    desc: 'One invariant governs everything: AdaptivePower(T) ≤ ReplayVerifiability(T). No part of the system can do more than it can prove it did.',
  },
]

export default function App() {
  if (window.location.pathname === '/success') {
    return <SuccessPage />
  }

  const trialStartRef = useRef(Date.now())

  useEffect(() => {
    captureEvent('trial_started', { product: 'hub', source: document.referrer || 'direct' })
  }, [])

  const handlePurchaseClick = (product: string, price: number) => {
    const ttv = Math.round((Date.now() - trialStartRef.current) / 1000)
    captureEvent('conversion', { product, price, ttv_seconds: ttv })
  }

  return (
    <div className="min-h-screen bg-hub-bg text-hub-text">

      {/* Nav */}
      <nav className="border-b border-hub-border/60 sticky top-0 z-50 bg-hub-bg/95 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div
            className="text-sm font-semibold tracking-widest animate-breathe"
            style={{ fontFamily: '"JetBrains Mono", monospace', color: '#C8A96E', letterSpacing: '0.22em' }}
          >
            AEGIS-Ω
          </div>
          <div className="flex items-center gap-6">
            <a href="#platform" className="text-hub-muted text-xs hover:text-hub-text transition-colors hidden sm:block">Platform</a>
            <a href="#tools"    className="text-hub-muted text-xs hover:text-hub-text transition-colors hidden sm:block">Tools</a>
            <a href="#pricing"  className="text-hub-muted text-xs hover:text-hub-text transition-colors hidden sm:block">Pricing</a>
            <a
              href="#pricing"
              onClick={() => handlePurchaseClick('nav', 39)}
              className="text-xs bg-hub-accent text-white px-3 py-1.5 rounded-lg hover:opacity-90 transition-opacity font-semibold"
            >
              Get started
            </a>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <div className="max-w-4xl mx-auto px-4 pt-24 pb-16 text-center">
        {/* Status badge */}
        <div
          className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-medium mb-8"
          style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.22)', color: '#86EFAC', fontFamily: '"JetBrains Mono", monospace' }}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          6,400+ tests passing · t0_verdict: true · corruption_count: 0
        </div>

        <h1
          className="text-5xl md:text-7xl font-bold text-hub-text mb-6 leading-none"
          style={{ letterSpacing: '-0.03em' }}
        >
          The AI runtime<br />
          <span className="text-hub-glow">that governs itself.</span>
        </h1>

        <p className="text-hub-muted text-lg max-w-2xl mx-auto mb-5 leading-relaxed">
          Constitutional AI infrastructure. Every decision hash-signed, sequence-numbered,
          and replay-certifiable from genesis. Not a wrapper — a state machine with an immune system.
        </p>

        <div
          className="inline-block mb-10 px-3 py-1.5 rounded"
          style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '12px', color: '#C8A96E', background: 'rgba(200,169,110,0.08)', border: '1px solid rgba(200,169,110,0.20)' }}
        >
          AdaptivePower(T) ≤ ReplayVerifiability(T)
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center mb-4">
          <a
            href="#platform"
            className="inline-flex items-center justify-center gap-2 bg-hub-accent text-white font-semibold px-8 py-3.5 rounded-xl hover:opacity-90 transition-opacity text-sm"
          >
            <Shield size={15} />
            See the platform
          </a>
          <a
            href="#tools"
            className="inline-flex items-center justify-center gap-2 border border-hub-border text-hub-muted hover:text-hub-text hover:border-hub-border/80 font-medium px-8 py-3.5 rounded-xl transition-all text-sm"
          >
            Creator tools — from $19
            <ChevronRight size={14} />
          </a>
        </div>
        <p className="text-hub-muted/60 text-xs">
          113,000+ lines · AMD RX 570, 8 GB RAM · single engineer · AGPL-3.0
        </p>
      </div>

      {/* Stats */}
      <div className="border-y border-hub-border/60 bg-hub-surface/30">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {[
              { value: '6,400+', label: 'invariant tests' },
              { value: '436+',   label: 'gate modules' },
              { value: '1/φ',    label: 'BFT threshold' },
              { value: 'T0',     label: 'deterministic' },
            ].map(s => (
              <div key={s.label} className="text-center">
                <div
                  className="text-2xl font-bold text-hub-glow"
                  style={{ fontFamily: '"JetBrains Mono", monospace' }}
                >
                  {s.value}
                </div>
                <div
                  className="text-hub-muted mt-1 uppercase"
                  style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '10px', letterSpacing: '0.12em' }}
                >
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Platform section */}
      <div id="platform" className="max-w-5xl mx-auto px-4 py-20 scroll-mt-16">
        <div className="text-center mb-14">
          <div
            className="inline-flex items-center gap-2 mb-4 uppercase"
            style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '10px', letterSpacing: '0.18em', color: '#C8A96E' }}
          >
            <Shield size={10} />
            Constitutional runtime
          </div>
          <h2 className="text-3xl md:text-4xl font-bold text-hub-text mb-4" style={{ letterSpacing: '-0.02em' }}>
            Built on six constitutional pillars.
          </h2>
          <p className="text-hub-muted max-w-xl mx-auto text-sm leading-relaxed">
            Frontier AI labs ship models. They don't ship governance. AEGIS-Ω ships
            both — a production runtime where every AI call is mathematically bounded
            and cryptographically accountable.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mb-16">
          {PILLARS.map(pillar => (
            <div
              key={pillar.title}
              className="rounded-xl p-5 border border-hub-border bg-hub-surface/40 hover:border-hub-border/80 transition-colors"
            >
              <pillar.icon size={15} className="mb-3" style={{ color: '#C8A96E' }} />
              <h3 className="text-hub-text font-semibold text-sm mb-2">{pillar.title}</h3>
              <p className="text-hub-muted text-xs leading-relaxed">{pillar.desc}</p>
            </div>
          ))}
        </div>

        {/* Why it exists */}
        <div className="max-w-2xl mx-auto text-center">
          <h3 className="text-lg font-bold text-hub-text mb-5">Why this exists.</h3>
          <div className="text-hub-muted text-sm leading-relaxed space-y-3 text-left">
            <p>
              When a model hallucinates, there is no audit trail.
              When a decision is made, it cannot be replayed.
              When a system evolves, it cannot prove it evolved within bounds.
            </p>
            <p>
              AEGIS-Ω was built to fix that. One law governs everything:{' '}
              <code
                className="text-xs px-1.5 py-0.5 rounded"
                style={{ fontFamily: '"JetBrains Mono", monospace', color: '#C8A96E', background: 'rgba(200,169,110,0.08)', border: '1px solid rgba(200,169,110,0.18)' }}
              >
                AdaptivePower(T) ≤ ReplayVerifiability(T)
              </code>.
              No part of the system can do more than it can prove it did.
            </p>
            <p>
              Every AI response, every state transition, every peer message, every epoch
              boundary is hash-signed, sequence-numbered, and stored in a tamper-evident chain.
              The system can replay any past state and arrive at the same fingerprint.
              If it can't, that's a detectable failure — not a silent one.
            </p>
          </div>
        </div>
      </div>

      {/* Creator tools */}
      <div id="tools" className="bg-hub-surface/30 border-y border-hub-border/60 scroll-mt-16">
        <div className="max-w-5xl mx-auto px-4 py-20">
          <div className="text-center mb-12">
            <div
              className="inline-block mb-4 uppercase"
              style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '10px', letterSpacing: '0.18em', color: '#6B6B7A' }}
            >
              Built on AEGIS-Ω
            </div>
            <h2 className="text-3xl font-bold text-hub-text mb-3" style={{ letterSpacing: '-0.02em' }}>
              Creator tools. Constitutional core.
            </h2>
            <p className="text-hub-muted max-w-lg mx-auto text-sm leading-relaxed">
              Three production tools for content creators — each AI call hash-certified, each recommendation
              reproducible. Built on the same runtime. From $19.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-5">
            {TOOLS.map(tool => (
              <div
                key={tool.name}
                className="flex flex-col rounded-2xl p-6 transition-all duration-200"
                style={{ background: '#0C0E14', border: '1px solid #1A1D27' }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLDivElement).style.borderColor = tool.accentColor + '55'
                  ;(e.currentTarget as HTMLDivElement).style.boxShadow = `0 8px 28px ${tool.glowColor}`
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLDivElement).style.borderColor = '#1A1D27'
                  ;(e.currentTarget as HTMLDivElement).style.boxShadow = 'none'
                }}
              >
                <div
                  className="text-xs font-bold mb-3"
                  style={{ fontFamily: '"JetBrains Mono", monospace', color: tool.accentColor, letterSpacing: '0.1em' }}
                >
                  {tool.num} · {tool.tagline}
                </div>
                <h3 className="text-hub-text font-bold text-base mb-3">{tool.name}</h3>
                <p className="text-hub-muted text-sm leading-relaxed mb-6 flex-1">{tool.desc}</p>
                <div className="flex items-center justify-between gap-3">
                  <span
                    className="font-bold text-xl text-hub-text"
                    style={{ fontFamily: '"JetBrains Mono", monospace' }}
                  >
                    ${tool.price}
                  </span>
                  <a
                    href="#pricing"
                    onClick={() => handlePurchaseClick(tool.name.toLowerCase().replace(/ /g, '-'), tool.price)}
                    className="text-xs font-semibold px-4 py-2 rounded-lg transition-all hover:opacity-90 text-white shrink-0"
                    style={{ backgroundColor: tool.accentColor }}
                  >
                    Get access
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Enterprise */}
      <div className="max-w-5xl mx-auto px-4 py-20">
        <div className="rounded-2xl p-10 md:p-12" style={{ background: '#0C0E14', border: '1px solid rgba(99,102,241,0.22)' }}>
          <div className="flex flex-col md:flex-row md:items-center gap-8">
            <div className="flex-1">
              <div
                className="inline-flex items-center gap-2 mb-4 uppercase"
                style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '10px', letterSpacing: '0.18em', color: '#818CF8' }}
              >
                <Shield size={10} />
                Enterprise runtime
              </div>
              <h2 className="text-2xl font-bold text-hub-text mb-3" style={{ letterSpacing: '-0.02em' }}>
                Constitutional runtime licensing.
              </h2>
              <p className="text-hub-muted text-sm leading-relaxed max-w-md">
                The full aegis-cl-psi Rust crate + sovereign-omega-v2 TypeScript governance layer.
                Audit hooks, compliance documentation, custom deployment, EU AI Act Article 12
                binders. Minimum engagement: teams of 3+.
              </p>
            </div>
            <div className="shrink-0 text-center md:text-right">
              <a
                href="mailto:tarikskalic33@gmail.com?subject=AEGIS-Ω Enterprise Inquiry"
                onClick={() => captureEvent('enterprise_inquiry_click')}
                className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-7 py-3.5 rounded-xl transition-colors text-sm"
              >
                <Mail size={14} />
                Get in touch
              </a>
              <p className="text-hub-muted text-xs mt-2">Response within 24 hours</p>
            </div>
          </div>
        </div>
      </div>

      {/* Pricing */}
      <div id="pricing" className="max-w-3xl mx-auto px-4 pb-20 scroll-mt-16">
        <div className="text-center mb-10">
          <h2 className="text-2xl font-bold text-hub-text mb-2">Simple pricing</h2>
          <p className="text-hub-muted text-sm">Buy once. Own it forever. No subscriptions.</p>
        </div>
        <PricingTable />
      </div>

      {/* How it works */}
      <div className="bg-hub-surface/30 border-y border-hub-border/60">
        <div className="max-w-3xl mx-auto px-4 py-16">
          <h2 className="text-xl font-bold text-hub-text text-center mb-10">Up and running in 5 minutes</h2>
          <div className="grid md:grid-cols-3 gap-4">
            {[
              {
                step: '01',
                title: 'Choose your plan',
                desc: 'One tool for $19, any two for $29, all three for $39. One payment. No subscription, no upsell.',
              },
              {
                step: '02',
                title: 'Pay via Lemon Squeezy',
                desc: 'Secure checkout in 130+ countries — including Bosnia, Serbia, and everywhere Stripe blocks. Card, PayPal.',
              },
              {
                step: '03',
                title: 'Instant access',
                desc: 'Redirected back automatically. Click a tool link and it unlocks immediately. No account, no email, no API key.',
              },
            ].map(item => (
              <div key={item.step} className="bg-hub-bg border border-hub-border rounded-xl p-5">
                <div
                  className="font-bold mb-3"
                  style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '11px', color: '#6366F1', letterSpacing: '0.05em' }}
                >
                  {item.step}
                </div>
                <div className="font-semibold text-hub-text text-sm mb-1">{item.title}</div>
                <p className="text-hub-muted text-xs leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* FAQ */}
      <div className="max-w-2xl mx-auto px-4 py-16">
        <h2 className="text-xl font-bold text-hub-text text-center mb-8">FAQ</h2>
        <div className="space-y-3">
          {[
            {
              q: 'Do I need to pay for an AI API key?',
              a: "The creator tools run on DashScope (Alibaba Cloud's Qwen). The free tier covers hundreds of generations per month — most users never hit the limit. You supply your own key so your data stays yours.",
            },
            {
              q: 'What exactly do I get when I buy?',
              a: 'Instant access to the tool(s). Lemon Squeezy redirects you back here and the tools unlock in your browser. No download, no account, no email confirmation required.',
            },
            {
              q: 'Can I use the output commercially?',
              a: "Yes. Hooks, calendar content, platform recommendations — use them for your own channels, your clients, your agency. No restrictions.",
            },
            {
              q: 'What about the enterprise runtime?',
              a: 'The constitutional runtime (aegis-cl-psi Rust crate + sovereign-omega-v2 TypeScript governance layer) is available for enterprise licensing. Email for details.',
            },
            {
              q: "What if it doesn't work for me?",
              a: "30-day no-questions refund. Email tarikskalic33@gmail.com and it's done within 24 hours.",
            },
          ].map(item => (
            <div key={item.q} className="bg-hub-surface border border-hub-border rounded-xl p-5">
              <div className="font-semibold text-hub-text text-sm mb-2">{item.q}</div>
              <p className="text-hub-muted text-sm leading-relaxed">{item.a}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Final CTA */}
      <div className="max-w-2xl mx-auto px-4 pb-20 text-center">
        <div className="rounded-2xl p-10" style={{ background: '#0C0E14', border: '1px solid rgba(200,169,110,0.20)' }}>
          <div
            className="inline-flex items-center gap-2 mb-4 uppercase"
            style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '10px', letterSpacing: '0.15em', color: '#34D399' }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            All systems operational
          </div>
          <h2 className="text-2xl font-bold text-hub-text mb-3">Start building.</h2>
          <p className="text-hub-muted text-sm mb-6">All three tools for $39. One payment. Full source code.</p>
          <a
            href="#pricing"
            onClick={() => handlePurchaseClick('final-cta', 39)}
            className="inline-flex items-center justify-center gap-2 bg-hub-accent text-white font-semibold px-10 py-4 rounded-xl hover:opacity-90 transition-opacity text-sm"
          >
            <Zap size={15} />
            Get all three — $39
          </a>
          <p className="text-hub-muted text-xs mt-4">
            Single tool $19 · Any two $29 · Enterprise on request
          </p>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-hub-border">
        <div className="max-w-5xl mx-auto px-4 py-8 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span
              className="text-xs font-semibold"
              style={{ fontFamily: '"JetBrains Mono", monospace', letterSpacing: '0.22em', color: '#C8A96E' }}
            >
              AEGIS-Ω
            </span>
            <span className="text-hub-border">·</span>
            <span className="text-hub-muted text-xs">Built by Tarik Skalić · AGPL-3.0</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#platform"  className="text-hub-muted text-xs hover:text-hub-text transition-colors">Platform</a>
            <a href="#tools"     className="text-hub-muted text-xs hover:text-hub-text transition-colors">Tools</a>
            <a href="#pricing"   className="text-hub-muted text-xs hover:text-hub-text transition-colors">Pricing</a>
            <a href="mailto:tarikskalic33@gmail.com" className="text-hub-muted text-xs hover:text-hub-text transition-colors">Contact</a>
          </div>
        </div>
      </div>

    </div>
  )
}
