import { useEffect, useRef } from 'react'
import { PricingTable } from './components/PricingTable.js'
import { SuccessPage } from './components/SuccessPage.js'
import { Shield, Zap, GitBranch, Lock, RefreshCw, ChevronRight, Mail } from 'lucide-react'

function captureEvent(event: string, props?: Record<string, unknown>): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ph = (window as any).posthog
  if (typeof ph?.capture === 'function') ph.capture(event, props)
}

const STATS = [
  { value: '6,400+', label: 'invariant tests' },
  { value: '436+',   label: 'gate modules' },
  { value: '1/φ',    label: 'BFT threshold' },
  { value: 'T0',     label: 'deterministic proof' },
]

const TOOLS = [
  {
    icon: '🎯',
    name: 'Platform Picker',
    tagline: 'AI-ranked platform fit',
    desc: 'Your niche, style, and monetisation goal → scored breakdown across TikTok, YouTube Shorts, Instagram Reels, Snapchat. Radar chart. One-click share.',
    accentColor: '#7C3AED',
    glowColor:   'rgba(124,58,237,0.12)',
    price: 19,
    url: 'https://aegis-platform-picker.vercel.app',
  },
  {
    icon: '⚡',
    name: 'Hook Generator',
    tagline: '10 ranked viral hooks in seconds',
    desc: 'Niche, platform, topic, tone → 10 hooks ranked by viral potential. Type-coded badges. Star favourites. Export all at once.',
    accentColor: '#F59E0B',
    glowColor:   'rgba(245,158,11,0.10)',
    price: 19,
    url: 'https://aegis-hook-generator.vercel.app',
  },
  {
    icon: '📅',
    name: 'Content Calendar',
    tagline: 'A month of content, one click',
    desc: '4-week calendar with daily ideas, viral hooks per post, formats, production notes. Export as TXT or CSV. Colour-coded pillars.',
    accentColor: '#22C55E',
    glowColor:   'rgba(34,197,94,0.10)',
    price: 19,
    url: 'https://aegis-content-calendar.vercel.app',
  },
]

const ENTERPRISE_CAPABILITIES = [
  { icon: Shield,    title: 'Deterministic replay',  desc: 'Every AI decision hash-chained. SHA-256 audit trail from genesis. Replay any past state and get the same cryptographic fingerprint every time.' },
  { icon: GitBranch, title: 'BFT consensus at 1/φ',  desc: 'Byzantine fault-tolerant quorum at the golden ratio threshold. Swarm convergence proofs. No silent failures.' },
  { icon: Lock,      title: 'EU AI Act compliance',  desc: 'Audit hooks, martingale-bounded adaptation, T0-certified epistemic tier tagging. AdaptivePower(T) ≤ ReplayVerifiability(T).' },
  { icon: RefreshCw, title: '436+ gate modules',      desc: 'Gossip layer, peer diversity, epoch convergence, RTT histograms, window fill — all hash-chained and replay-certifiable.' },
]

export default function App() {
  // Route /success to the post-payment page
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
      <nav className="border-b border-hub-border/60 sticky top-0 z-50 bg-hub-bg/90 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          {/* Wordmark: phi-gold + JetBrains Mono + 0.22em tracking */}
          <div className="flex items-center gap-3">
            <span
              className="text-sm font-semibold animate-breathe"
              style={{ fontFamily: '"JetBrains Mono", monospace', letterSpacing: '0.22em', color: '#C8A96E' }}
            >
              AEGIS-Ω
            </span>
          </div>
          <div className="flex items-center gap-6">
            <a href="/platform.html" className="text-hub-muted text-xs hover:text-hub-text transition-colors hidden sm:block">Platform</a>
            <a href="#tools"         className="text-hub-muted text-xs hover:text-hub-text transition-colors hidden sm:block">Tools</a>
            <a href="#enterprise"    className="text-hub-muted text-xs hover:text-hub-text transition-colors hidden sm:block">Enterprise</a>
            <a href="#pricing"       className="text-hub-muted text-xs hover:text-hub-text transition-colors hidden sm:block">Pricing</a>
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
        <div className="animate-fade-up inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-medium mb-8"
          style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.25)', color: '#86EFAC' }}>
          <span className="w-1.5 h-1.5 rounded-full bg-aegis-T0 animate-pulse" />
          <span style={{ fontFamily: '"JetBrains Mono", monospace' }}>6,400+ tests passing · 436+ gate modules · deterministic from genesis</span>
        </div>

        <h1 className="animate-fade-up delay-100 text-5xl md:text-6xl font-bold text-hub-text tracking-tight mb-6 leading-tight" style={{ letterSpacing: '-0.02em' }}>
          The AI runtime<br />
          <span className="text-hub-glow">that governs itself.</span>
        </h1>

        <p className="animate-fade-up delay-200 text-hub-muted text-lg max-w-2xl mx-auto mb-4 leading-relaxed">
          Constitutional state management for AI applications.
          Every decision hash-signed, sequence-numbered, replay-certifiable.
        </p>
        <p className="animate-fade-up delay-200 text-hub-muted/70 text-sm max-w-xl mx-auto mb-10">
          Built on one law:{' '}
          <code
            className="text-xs px-2 py-0.5 rounded"
            style={{ fontFamily: '"JetBrains Mono", monospace', color: '#C8A96E', background: 'rgba(200,169,110,0.10)', border: '1px solid rgba(200,169,110,0.20)' }}
          >
            AdaptivePower(T) ≤ ReplayVerifiability(T)
          </code>
        </p>

        <div className="animate-fade-up delay-300 flex flex-col sm:flex-row gap-3 justify-center mb-6">
          <a
            href="#pricing"
            onClick={() => handlePurchaseClick('hero-full-toolkit', 39)}
            className="inline-flex items-center justify-center gap-2 bg-hub-accent text-white font-semibold px-8 py-3.5 rounded-xl hover:opacity-90 transition-opacity text-sm"
          >
            <Zap size={15} />
            Get creator tools — $39
          </a>
          <a
            href="/platform.html"
            className="inline-flex items-center justify-center gap-2 border border-hub-border text-hub-muted hover:text-hub-text hover:border-hub-accent/40 font-medium px-8 py-3.5 rounded-xl transition-all text-sm"
          >
            See the platform
            <ChevronRight size={14} />
          </a>
        </div>
        <p className="text-hub-muted text-xs">One-time · Instant access · No subscriptions</p>
      </div>

      {/* Stats bar — JetBrains Mono for all numbers */}
      <div className="border-y border-hub-border/60 bg-hub-surface/40">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {STATS.map(s => (
              <div key={s.label} className="text-center">
                <div
                  className="text-2xl font-bold text-hub-glow"
                  style={{ fontFamily: '"JetBrains Mono", monospace' }}
                >
                  {s.value}
                </div>
                <div
                  className="text-hub-muted mt-1 uppercase tracking-label"
                  style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '10px', letterSpacing: '0.12em' }}
                >
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Creator Tools */}
      <div id="tools" className="max-w-5xl mx-auto px-4 py-20 scroll-mt-16">
        <div className="text-center mb-12">
          <div
            className="inline-block mb-3 uppercase"
            style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '10px', letterSpacing: '0.15em', color: '#6B6B7A' }}
          >
            Starter tools
          </div>
          <h2 className="text-3xl font-bold text-hub-text mb-3">AI tools powered by AEGIS</h2>
          <p className="text-hub-muted max-w-xl mx-auto text-sm">
            Three production-grade content tools built on the constitutional runtime.
            Full source code. Deploy on Vercel in 5 minutes.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {TOOLS.map(tool => (
            <div
              key={tool.name}
              className="flex flex-col rounded-2xl p-6 transition-all duration-200"
              style={{
                background: '#0F1117',
                border: '1px solid #1A1D27',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.borderColor = tool.accentColor + '66'
                ;(e.currentTarget as HTMLDivElement).style.boxShadow = `0 10px 28px ${tool.glowColor}`
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.borderColor = '#1A1D27'
                ;(e.currentTarget as HTMLDivElement).style.boxShadow = 'none'
              }}
            >
              <div className="text-3xl mb-4">{tool.icon}</div>
              <div
                className="text-xs font-semibold uppercase mb-1"
                style={{ color: tool.accentColor, letterSpacing: '0.08em' }}
              >
                {tool.tagline}
              </div>
              <h3 className="text-hub-text font-bold text-base mb-3">{tool.name}</h3>
              <p className="text-hub-muted text-sm leading-relaxed mb-6 flex-1">{tool.desc}</p>
              <div className="flex items-center justify-between">
                <span className="text-hub-text font-bold text-lg" style={{ fontFamily: '"JetBrains Mono", monospace' }}>
                  ${tool.price}
                </span>
                <a
                  href="#pricing"
                  onClick={() => handlePurchaseClick(tool.name.toLowerCase().replace(/ /g, '-'), tool.price)}
                  className="text-xs font-semibold px-4 py-2 rounded-lg transition-all hover:opacity-90 text-white"
                  style={{ backgroundColor: tool.accentColor }}
                >
                  Get access — ${tool.price}
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Enterprise */}
      <div id="enterprise" className="bg-hub-surface/40 border-y border-hub-border/60 scroll-mt-16">
        <div className="max-w-5xl mx-auto px-4 py-20">
          <div className="text-center mb-12">
            <div
              className="inline-flex items-center gap-2 mb-3 uppercase"
              style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '10px', letterSpacing: '0.15em', color: '#C8A96E' }}
            >
              <Shield size={10} />
              Enterprise runtime
            </div>
            <h2 className="text-3xl font-bold text-hub-text mb-3">
              AI governance infrastructure.
            </h2>
            <p className="text-hub-muted max-w-2xl mx-auto text-sm">
              The constitutional runtime underneath the tools.
              For teams deploying LLMs that need audit trails, compliance, and deterministic replay.
              Not a wrapper — a state machine with an immune system.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-5 mb-12">
            {ENTERPRISE_CAPABILITIES.map(cap => (
              <div key={cap.title} className="bg-hub-bg border border-hub-border rounded-xl p-6">
                <cap.icon size={16} className="mb-3" style={{ color: '#C8A96E' }} />
                <h3 className="text-hub-text font-semibold text-sm mb-2">{cap.title}</h3>
                <p className="text-hub-muted text-xs leading-relaxed">{cap.desc}</p>
              </div>
            ))}
          </div>

          {/* Enterprise CTA */}
          <div className="bg-hub-bg rounded-2xl p-8 text-center" style={{ border: '1px solid rgba(99,102,241,0.20)' }}>
            <div
              className="inline-flex items-center gap-2 mb-4 uppercase"
              style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '10px', letterSpacing: '0.15em', color: '#818CF8' }}
            >
              <Mail size={10} />
              Custom licensing available
            </div>
            <h3 className="text-hub-text font-bold text-xl mb-3">
              Enterprise pricing on request
            </h3>
            <p className="text-hub-muted text-sm max-w-md mx-auto mb-6">
              Constitutional runtime licensing, integration support, compliance documentation,
              and custom deployment. Minimum engagement: teams of 3+.
            </p>
            <a
              href="mailto:tarikskalic33@gmail.com?subject=AEGIS-Ω Enterprise Inquiry"
              onClick={() => captureEvent('enterprise_inquiry_click')}
              className="inline-flex items-center gap-2 bg-hub-accent text-white font-semibold px-8 py-3.5 rounded-xl hover:opacity-90 transition-opacity text-sm"
            >
              <Mail size={15} />
              Get in touch
            </a>
            <p className="text-hub-muted text-xs mt-3">Response within 24 hours</p>
          </div>
        </div>
      </div>

      {/* Why it exists */}
      <div className="max-w-3xl mx-auto px-4 py-20 text-center">
        <h2 className="text-2xl font-bold text-hub-text mb-6">Why this exists</h2>
        <div className="text-hub-muted text-sm leading-relaxed space-y-4 text-left">
          <p>
            Frontier AI labs ship models. They do not ship governance. When a model hallucinates,
            there is no audit trail. When a decision is made, it cannot be replayed. When a system
            evolves, it cannot prove it evolved within bounds.
          </p>
          <p>
            AEGIS-Ω was built to solve that. One law above all:{' '}
            <code
              className="text-xs px-1.5 py-0.5 rounded"
              style={{ fontFamily: '"JetBrains Mono", monospace', color: '#C8A96E', background: 'rgba(200,169,110,0.08)', border: '1px solid rgba(200,169,110,0.18)' }}
            >
              AdaptivePower(T) ≤ ReplayVerifiability(T)
            </code>.
            No part of the system can do more than it can prove it did.
          </p>
          <p>
            Every AI response, every state transition, every peer message, every epoch boundary
            is hash-signed, sequence-numbered, and stored in a tamper-evident chain. The system
            can replay any past state from scratch and arrive at the same cryptographic fingerprint.
            If it cannot, that is a detectable failure — not a silent one.
          </p>
        </div>
        <p
          className="mt-8"
          style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '11px', color: '#6B6B7A', opacity: 0.7 }}
        >
          113,000+ lines · AMD RX 570, 8 GB RAM · single engineer · AGPL-3.0
        </p>
      </div>

      {/* Pricing */}
      <div id="pricing" className="max-w-3xl mx-auto px-4 pb-20 scroll-mt-16">
        <div className="text-center mb-10">
          <h2 className="text-2xl font-bold text-hub-text mb-2">Simple pricing</h2>
          <p className="text-hub-muted text-sm">Buy once. Own it forever. No subscriptions, no upsells.</p>
        </div>
        <PricingTable />
      </div>

      {/* How it works */}
      <div className="bg-hub-surface/40 border-y border-hub-border/60">
        <div className="max-w-3xl mx-auto px-4 py-16 text-center">
          <h2 className="text-xl font-bold text-hub-text mb-10">Up and running in 5 minutes</h2>
          <div className="grid md:grid-cols-3 gap-4 text-left">
            {[
              {
                step: '01',
                title: 'Choose your plan',
                desc: 'One tool for $19, any two for $29, or all three for $39. One-time payment. No subscription, no upsell.',
              },
              {
                step: '02',
                title: 'Pay with Lemon Squeezy',
                desc: 'Secure checkout. Works in 130+ countries including Bosnia, Serbia, and every country Stripe blocks. Card, PayPal, and more.',
              },
              {
                step: '03',
                title: 'Instant access — no keys',
                desc: 'Redirected back here automatically. Click each tool link and it unlocks immediately in your browser. No account, no email, no keys.',
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
        <h2 className="text-2xl font-bold text-hub-text text-center mb-8">FAQ</h2>
        <div className="space-y-3">
          {[
            {
              q: 'What is DashScope / do I need to pay for it?',
              a: "DashScope is Alibaba Cloud's AI API (Qwen). The free tier covers hundreds of generations per month. Most users never need to upgrade. You supply your own key — your data, your costs, your control.",
            },
            {
              q: 'What do I actually receive when I buy?',
              a: 'Instant access to the tool(s) — no keys, no email, no account. Lemon Squeezy redirects you back here and the tools unlock immediately in your browser.',
            },
            {
              q: 'How does access work?',
              a: 'After payment, Lemon Squeezy sends you back to this page. Click each tool link and it opens with instant access — stored in your browser. On a new device, return to this page and use the email restore.',
            },
            {
              q: 'Can I use this commercially?',
              a: 'Yes. MIT licensed for the creator tools. Use for your own content, your agency\'s clients, or build your own paid product on top of it.',
            },
            {
              q: 'What about the enterprise runtime?',
              a: 'The constitutional runtime (aegis-cl-psi Rust crate + sovereign-omega-v2 TypeScript governance layer) is available for enterprise licensing. Email for details.',
            },
            {
              q: "What if it doesn't work for me?",
              a: '30-day no-questions refund. Email and it\'s done within 24 hours.',
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
        <div className="bg-hub-surface rounded-2xl p-10" style={{ border: '1px solid rgba(99,102,241,0.20)' }}>
          <div
            className="inline-flex items-center gap-2 mb-4 uppercase"
            style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '10px', letterSpacing: '0.15em', color: '#34D399' }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-aegis-T0 animate-pulse" />
            6,400+ tests passing
          </div>
          <h2 className="text-2xl font-bold text-hub-text mb-3">Start building.</h2>
          <p className="text-hub-muted text-sm mb-6">All three tools for $39. One payment. Full source code.</p>
          <a
            href="#pricing"
            onClick={() => handlePurchaseClick('final-cta', 39)}
            className="inline-flex items-center justify-center gap-2 bg-hub-accent text-white font-semibold px-10 py-4 rounded-xl hover:opacity-90 transition-opacity text-sm"
          >
            <Zap size={15} />
            Get Full Toolkit — $39
          </a>
          <p className="text-hub-muted text-xs mt-4">
            Or a single tool for $19 · Any two for $29 · Enterprise on request
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
            <a href="#tools"      className="text-hub-muted text-xs hover:text-hub-text transition-colors">Tools</a>
            <a href="#enterprise" className="text-hub-muted text-xs hover:text-hub-text transition-colors">Enterprise</a>
            <a href="#pricing"    className="text-hub-muted text-xs hover:text-hub-text transition-colors">Pricing</a>
            <a href="mailto:tarikskalic33@gmail.com" className="text-hub-muted text-xs hover:text-hub-text transition-colors">Contact</a>
          </div>
        </div>
      </div>
    </div>
  )
}
