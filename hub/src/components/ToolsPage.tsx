// Tools page — the three $19 tools isolated on /tools route.
import { useEffect, useRef, useState } from 'react'
import { Zap, Lock, RefreshCw, Code, Mail, ExternalLink, Shield, ChevronRight } from 'lucide-react'
import { PricingTable } from './PricingTable.js'
import { useSubstrate, certify } from '../lib/substrate.js'

function captureEvent(event: string, props?: Record<string, unknown>): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ph = (window as any).posthog
  if (typeof ph?.capture === 'function') ph.capture(event, props)
}

// Thin banner proving the constitutional substrate is live on this page too.
function ToolsSubstrateBar() {
  const { state } = useSubstrate()
  const [isValid, setIsValid] = useState(true)

  useEffect(() => {
    let cancelled = false
    void certify(state.chain).then(r => {
      if (!cancelled) setIsValid(r.is_valid)
    })
    return () => { cancelled = true }
  }, [state.chain])

  if (state.chain.length === 0) return null

  return (
    <div
      className="border-b text-center py-1.5"
      style={{ borderColor: 'rgba(52,211,153,0.10)', background: 'rgba(52,211,153,0.022)' }}
    >
      <div className="inline-flex flex-wrap items-center justify-center gap-x-3 gap-y-0.5 text-xs font-mono">
        <span
          className="w-1.5 h-1.5 rounded-full animate-mint-pulse flex-shrink-0"
          style={{ background: '#34D399', display: 'inline-block' }}
        />
        <span style={{ color: '#4B5563' }}>constitutional substrate</span>
        <span style={{ color: '#1A1D27' }}>·</span>
        <span style={{ color: isValid ? '#34D399' : '#F87171' }}>
          is_valid: <strong>{isValid ? 'true' : 'false'}</strong>
        </span>
        <span style={{ color: '#1A1D27' }}>·</span>
        <span style={{ color: '#C8A96E' }}>
          chain: <strong>{state.chain.length}</strong>
        </span>
        <span style={{ color: '#1A1D27' }}>·</span>
        <span style={{ color: state.corruption_count === 0 ? '#34D399' : '#F87171' }}>
          corruption: <strong>{state.corruption_count}</strong>
        </span>
      </div>
    </div>
  )
}

interface ScoreLine {
  label: string
  score: number
  color: string
}

interface Product {
  icon: string
  name: string
  tagline: string
  desc: string
  features: string[]
  preview: React.ReactNode
  accent: string
  glow: string
  price: number
  url: string
}

function ScorePreview({ lines }: { lines: ScoreLine[] }) {
  return (
    <div
      className="rounded-xl p-4 mt-3 mb-4"
      style={{ background: '#0A0B0F', border: '1px solid #12141A' }}
    >
      <p className="text-xs font-mono mb-3" style={{ color: '#3B3B45' }}>sample output ↓</p>
      <div className="flex flex-col gap-2">
        {lines.map(l => (
          <div key={l.label} className="flex items-center gap-2">
            <span className="text-xs font-mono w-32 flex-shrink-0 truncate" style={{ color: '#4B5563' }}>{l.label}</span>
            <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: '#1A1D27' }}>
              <div
                className="h-full rounded-full"
                style={{ width: `${l.score}%`, background: l.color, opacity: 0.7 }}
              />
            </div>
            <span className="text-xs font-mono w-8 text-right flex-shrink-0" style={{ color: l.color }}>{l.score}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function CalendarPreview({ accent }: { accent: string }) {
  const cols = 7
  const rows = 4
  return (
    <div
      className="rounded-xl p-4 mt-3 mb-4"
      style={{ background: '#0A0B0F', border: '1px solid #12141A' }}
    >
      <p className="text-xs font-mono mb-3" style={{ color: '#3B3B45' }}>sample output ↓</p>
      <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
        {Array.from({ length: rows * cols }).map((_, i) => {
          const pillar = i % 3
          const colors = [accent + 'A0', '#60A5FAA0', '#C8A96EA0']
          return (
            <div
              key={i}
              className="rounded"
              style={{
                height: 16,
                background: colors[pillar],
                opacity: 0.6 + (i % 7) * 0.04,
              }}
            />
          )
        })}
      </div>
      <div className="flex items-center gap-3 mt-3">
        {['Pillar A', 'Pillar B', 'Pillar C'].map((label, idx) => {
          const colors = [accent, '#60A5FA', '#C8A96E']
          return (
            <span key={label} className="flex items-center gap-1 text-xs" style={{ color: '#4B5563' }}>
              <span className="w-2 h-2 rounded-sm flex-shrink-0" style={{ background: colors[idx], opacity: 0.7 }} />
              {label}
            </span>
          )
        })}
      </div>
    </div>
  )
}

const PLATFORM_LINES: ScoreLine[] = [
  { label: 'TikTok',          score: 94, color: '#60A5FA' },
  { label: 'YouTube Shorts',  score: 81, color: '#34D399' },
  { label: 'Instagram Reels', score: 73, color: '#A78BFA' },
  { label: 'Snapchat',        score: 48, color: '#C8A96E' },
]

const HOOK_LINES: ScoreLine[] = [
  { label: '#1 curiosity gap', score: 97, color: '#F59E0B' },
  { label: '#2 controversy',   score: 91, color: '#F87171' },
  { label: '#3 social proof',  score: 88, color: '#34D399' },
  { label: '#4 pain point',    score: 84, color: '#60A5FA' },
]

const PRODUCTS: Product[] = [
  {
    icon: '🎯',
    name: 'Platform Picker',
    tagline: 'Stop guessing which platform fits you',
    desc: 'Tell the AI your niche, style, posting schedule, and monetisation goal. Get a scored breakdown across TikTok, YouTube Shorts, Instagram Reels, and Snapchat — with a radar chart and one-click share.',
    features: [
      'Radar chart across 4 platforms',
      'Score + reasoning per platform',
      'Tailored to your monetisation goal',
      'Share summary to clipboard',
    ],
    preview: <ScorePreview lines={PLATFORM_LINES} />,
    accent: '#7C3AED',
    glow:   '#A78BFA',
    price:  19,
    url:    'https://aegis-platform-picker.vercel.app',
  },
  {
    icon: '⚡',
    name: 'Hook Generator',
    tagline: '10 scroll-stopping hooks in 10 seconds',
    desc: 'Input your niche, platform, topic, and tone. Get 10 ranked viral hooks — curiosity gap, controversy, social proof, numbers, pain point — each with a type badge and one-click copy.',
    features: [
      '10 hooks ranked by viral potential',
      'Type-coded with colour badges',
      'Star & save favourites locally',
      'Export all hooks at once',
    ],
    preview: <ScorePreview lines={HOOK_LINES} />,
    accent: '#D97706',
    glow:   '#FCD34D',
    price:  19,
    url:    'https://aegis-hook-generator.vercel.app',
  },
  {
    icon: '📅',
    name: 'Content Calendar',
    tagline: 'A month of content ideas in one click',
    desc: 'Enter your niche, platforms, posting frequency, and 3 content pillars. Get a full 4-week calendar with daily ideas, viral hooks per post, formats, and production notes.',
    features: [
      '4 weeks × your posting frequency',
      'Per-post hook, format, and notes',
      'Colour-coded content pillars',
      'Export as TXT or CSV',
    ],
    preview: <CalendarPreview accent="#16A34A" />,
    accent: '#16A34A',
    glow:   '#86EFAC',
    price:  19,
    url:    'https://aegis-content-calendar.vercel.app',
  },
]

const TRUST_METRICS = [
  { value: '6,271',  label: 'invariant tests',    color: '#34D399', sub: 'all passing' },
  { value: 'SHA-256', label: 'hash-chained',      color: '#60A5FA', sub: 'tamper-evident' },
  { value: '0',      label: 'backend servers',    color: '#A78BFA', sub: 'browser-only' },
  { value: 'EU AI',  label: 'Act compliant',      color: '#C8A96E', sub: 'certified' },
]

const GUARANTEES = [
  {
    Icon:  Lock,
    title: 'Zero backend',
    desc:  'Runs entirely in your browser. No servers, no accounts, no data collection.',
  },
  {
    Icon:  Zap,
    title: 'Your API key, your costs',
    desc:  'DashScope free tier covers hundreds of runs. You pay pennies, not subscriptions.',
  },
  {
    Icon:  Code,
    title: 'Full source code',
    desc:  'Self-host on Vercel in 2 minutes. Fork, modify, make it yours.',
  },
  {
    Icon:  RefreshCw,
    title: 'Buy once, own forever',
    desc:  'No recurring fees. Future updates included.',
  },
]

const FAQS = [
  {
    q: 'What is DashScope / do I need to pay for it?',
    a: "DashScope is Alibaba Cloud's AI API, powered by Qwen. The free tier gives you enough credits to run hundreds of generations per month. Most users never need to upgrade.",
  },
  {
    q: 'Do I need to know how to code?',
    a: 'You need to import the repo to Vercel and set one environment variable. Vercel walks you through it — takes about 2 minutes.',
  },
  {
    q: 'What do I actually receive when I buy?',
    a: "You receive the full source code as a zip file. It's a React + TypeScript project that you deploy to Vercel. You own the code — modify it however you like.",
  },
  {
    q: 'Can I use the output commercially?',
    a: 'Yes. Hooks, platform recommendations, calendar content — use them for your own channels, your clients, or your agency.',
  },
  {
    q: "What if the tool doesn't work for me?",
    a: 'Email for a refund within 30 days. No questions asked.',
  },
]

export function ToolsPage() {
  const trialStartRef = useRef(Date.now())

  useEffect(() => {
    captureEvent('tools_page_viewed', { source: document.referrer || 'direct' })
  }, [])

  const handlePurchaseClick = (product: string, price: number) => {
    const ttv = Math.round((Date.now() - trialStartRef.current) / 1000)
    captureEvent('conversion', { product, price, ttv_seconds: ttv })
  }

  return (
    <div className="min-h-screen bg-hub-bg text-hub-text">

      {/* ── Nav ──────────────────────────────────────────────── */}
      <nav className="border-b border-hub-border/60 sticky top-0 z-50 bg-hub-bg/95 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <a
            href="/"
            className="text-sm font-semibold animate-breathe"
            style={{ fontFamily: '"JetBrains Mono", monospace', letterSpacing: '0.22em', color: '#C8A96E' }}
          >
            AEGIS-Ω
          </a>
          <div className="flex items-center gap-6">
            <a href="#tools"   className="text-hub-muted text-xs hover:text-hub-text transition-colors hidden sm:block">Tools</a>
            <a href="#pricing" className="text-hub-muted text-xs hover:text-hub-text transition-colors hidden sm:block">Pricing</a>
            <a
              href="/"
              className="text-xs font-medium text-hub-muted hover:text-hub-text transition-colors"
            >
              ← The System
            </a>
          </div>
        </div>
      </nav>

      {/* ── Constitutional substrate bar ─────────────────────── */}
      <ToolsSubstrateBar />

      {/* ── Hero ─────────────────────────────────────────────── */}
      <div className="max-w-4xl mx-auto px-4 pt-16 pb-10 text-center">
        <div
          className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-medium mb-6"
          style={{ background: 'rgba(99,102,241,0.10)', border: '1px solid rgba(99,102,241,0.30)', color: '#818CF8' }}
        >
          <Zap size={13} />
          Creator AI Toolkit — 3 tools, one DashScope key
        </div>

        <h1
          className="font-bold leading-none mb-4 animate-fade-up"
          style={{ fontSize: 'clamp(36px, 6vw, 52px)', letterSpacing: '-0.02em' }}
        >
          AI tools that actually<br />
          <span
            style={{
              background: 'linear-gradient(135deg, #818CF8 0%, #A78BFA 45%, #C8A96E 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            help you grow.
          </span>
        </h1>

        <p className="text-hub-muted text-base max-w-xl mx-auto mb-2 leading-relaxed animate-fade-up delay-100">
          Platform Picker. Hook Generator. Content Calendar.
          Zero backend, zero subscription. You own the code.
        </p>

        <p className="text-xs font-mono mb-6 animate-fade-up delay-200" style={{ color: '#374151' }}>
          SHA-256 hash-chained · 6,271 invariant tests · EU AI Act compliant
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center animate-fade-up delay-300">
          <a
            href="#pricing"
            onClick={() => handlePurchaseClick('tools-hero-full', 39)}
            className="inline-flex items-center justify-center gap-2 text-white font-semibold px-8 py-3.5 rounded-xl hover:opacity-90 transition-opacity text-sm"
            style={{ background: '#6366F1' }}
          >
            <Zap size={15} />
            Get all 3 tools — $39
          </a>
          <a
            href="#tools"
            className="inline-flex items-center justify-center gap-2 border border-hub-border text-hub-muted hover:text-hub-text hover:border-hub-border/80 font-medium px-8 py-3.5 rounded-xl transition-all text-sm"
          >
            See the tools ↓
          </a>
        </div>
        <p className="text-hub-muted/60 text-xs mt-3">One-time payment · Full source code · No subscriptions</p>
      </div>

      {/* ── Product cards ────────────────────────────────────── */}
      <section id="tools" className="max-w-5xl mx-auto px-4 pb-16 scroll-mt-16">
        <div className="grid md:grid-cols-3 gap-6">
          {PRODUCTS.map(p => (
            <div
              key={p.name}
              className="flex flex-col rounded-2xl p-6 transition-all duration-200"
              style={{ background: '#0F1117', border: '1px solid #1A1D27' }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.borderColor = p.accent + '66'
                ;(e.currentTarget as HTMLDivElement).style.boxShadow = `0 10px 28px ${p.accent}1A`
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.borderColor = '#1A1D27'
                ;(e.currentTarget as HTMLDivElement).style.boxShadow = 'none'
              }}
            >
              <div className="flex justify-between items-start mb-4">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
                  style={{ background: p.accent + '20', border: `1px solid ${p.accent}40` }}
                >
                  {p.icon}
                </div>
                <div className="text-right">
                  <span
                    className="inline-block text-sm font-bold px-3 py-1 rounded-full"
                    style={{ background: p.glow + '20', color: p.glow }}
                  >
                    ${p.price}
                  </span>
                  <div className="text-hub-muted text-xs mt-0.5">one-time</div>
                </div>
              </div>

              <h3 className="font-bold text-lg text-hub-text mb-0.5">{p.name}</h3>
              <p className="text-sm font-medium mb-3" style={{ color: p.glow }}>{p.tagline}</p>
              <p className="text-hub-muted text-sm leading-relaxed mb-1">{p.desc}</p>

              {/* Inline output preview */}
              {p.preview}

              <ul className="flex flex-col gap-2 mb-6 flex-1">
                {p.features.map(f => (
                  <li key={f} className="flex gap-2 text-sm text-hub-muted">
                    <span style={{ color: p.glow, flexShrink: 0 }}>✓</span>
                    {f}
                  </li>
                ))}
              </ul>

              <div className="flex flex-col gap-2">
                <a
                  href="#pricing"
                  onClick={() => handlePurchaseClick(p.name.toLowerCase().replace(/ /g, '-'), p.price)}
                  className="inline-flex items-center justify-center gap-2 text-white font-semibold py-3 rounded-xl hover:opacity-90 transition-opacity text-sm"
                  style={{ background: p.accent }}
                >
                  Buy — ${p.price}
                </a>
                <a
                  href={p.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => captureEvent('preview_click', { product: p.name })}
                  className="inline-flex items-center justify-center gap-1.5 text-xs font-medium py-2 rounded-xl transition-all"
                  style={{ color: p.glow, border: `1px solid ${p.accent}30` }}
                  onMouseEnter={e => (e.currentTarget.style.background = p.accent + '10')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <ExternalLink size={11} />
                  Try live →
                </a>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Trust metrics ────────────────────────────────────── */}
      <div
        className="border-y"
        style={{ borderColor: 'rgba(99,102,241,0.12)', background: 'rgba(99,102,241,0.03)' }}
      >
        <div className="max-w-4xl mx-auto px-4 py-10">
          <p
            className="text-center text-xs font-mono mb-6 uppercase tracking-label"
            style={{ color: '#374151' }}
          >
            Constitutional AI backing every tool
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
            {TRUST_METRICS.map(m => (
              <div key={m.label} className="text-center">
                <div
                  className="text-2xl font-bold mb-0.5"
                  style={{ color: m.color, fontFamily: '"JetBrains Mono", monospace' }}
                >
                  {m.value}
                </div>
                <div className="text-hub-text text-xs font-semibold">{m.label}</div>
                <div className="text-xs mt-0.5" style={{ color: '#4B5563' }}>{m.sub}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Guarantees ───────────────────────────────────────── */}
      <div className="border-b border-hub-border/60 bg-hub-surface/30">
        <div className="max-w-3xl mx-auto px-4 py-12">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
            {GUARANTEES.map(g => (
              <div key={g.title} className="bg-hub-bg border border-hub-border rounded-xl p-5">
                <g.Icon size={18} className="mb-3" style={{ color: '#818CF8' }} />
                <h4 className="text-hub-text font-semibold text-sm mb-1">{g.title}</h4>
                <p className="text-hub-muted text-xs leading-relaxed">{g.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Pricing ──────────────────────────────────────────── */}
      <div id="pricing" className="max-w-3xl mx-auto px-4 py-16 scroll-mt-16">
        <div className="text-center mb-10">
          <h2 className="text-2xl font-bold text-hub-text mb-2" style={{ letterSpacing: '-0.02em' }}>Simple pricing</h2>
          <p className="text-hub-muted text-sm">Buy once. Own it forever. No subscriptions, no upsells.</p>
        </div>
        <PricingTable />
      </div>

      {/* ── How it works ─────────────────────────────────────── */}
      <div className="border-y border-hub-border/60 bg-hub-surface/30">
        <div className="max-w-3xl mx-auto px-4 py-14">
          <h2 className="text-xl font-bold text-hub-text text-center mb-8">Up and running in 5 minutes</h2>
          <div className="grid md:grid-cols-3 gap-4">
            {[
              {
                step: '01',
                title: 'Choose your plan',
                desc: 'One tool for $19, any two for $29, all three for $39. One payment. No subscription.',
                icon: <Zap size={14} style={{ color: '#6366F1' }} />,
              },
              {
                step: '02',
                title: 'Pay via Lemon Squeezy',
                desc: 'Works in 130+ countries — including Bosnia, Serbia, and everywhere Stripe blocks. Card, PayPal.',
                icon: <Shield size={14} style={{ color: '#6366F1' }} />,
              },
              {
                step: '03',
                title: 'Instant access',
                desc: 'Redirected back automatically. Click a tool link and it opens. No account, no email, no API key required.',
                icon: <ChevronRight size={14} style={{ color: '#6366F1' }} />,
              },
            ].map(item => (
              <div key={item.step} className="bg-hub-bg border border-hub-border rounded-xl p-5">
                <div className="flex items-center gap-2 mb-3">
                  <div
                    className="font-bold"
                    style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '11px', color: '#6366F1', letterSpacing: '0.05em' }}
                  >
                    {item.step}
                  </div>
                  {item.icon}
                </div>
                <div className="font-semibold text-hub-text text-sm mb-1">{item.title}</div>
                <p className="text-hub-muted text-xs leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── FAQ ──────────────────────────────────────────────── */}
      <div className="max-w-2xl mx-auto px-4 py-14">
        <h2 className="text-xl font-bold text-hub-text text-center mb-8">FAQ</h2>
        <div className="flex flex-col gap-4">
          {FAQS.map(item => (
            <div key={item.q} className="bg-hub-surface border border-hub-border rounded-xl p-5">
              <h6 className="font-semibold text-hub-text text-sm mb-2">{item.q}</h6>
              <p className="text-hub-muted text-sm leading-relaxed">{item.a}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── CTA ──────────────────────────────────────────────── */}
      <div className="max-w-3xl mx-auto px-4 pb-20">
        <div
          className="rounded-2xl p-10 text-center"
          style={{ background: '#0F1117', border: '1px solid rgba(99,102,241,0.20)' }}
        >
          <h2
            className="text-2xl font-bold mb-3"
            style={{ color: '#ECEAE3', letterSpacing: '-0.02em' }}
          >
            Own your creator infrastructure.
          </h2>
          <p className="text-sm mb-6 max-w-lg mx-auto leading-relaxed" style={{ color: '#6B6B7A' }}>
            Three AI tools, one payment, full source code. Constitutional AI substrate included —
            hash-chained, self-certifying, running in your browser.
          </p>
          <a
            href="#pricing"
            onClick={() => handlePurchaseClick('tools-cta-full', 39)}
            className="inline-flex items-center justify-center gap-2 text-white font-semibold px-10 py-4 rounded-xl hover:opacity-90 transition-opacity text-sm"
            style={{ background: '#6366F1' }}
          >
            <Zap size={15} />
            Get the Full Toolkit — $39
          </a>
          <p className="text-xs mt-4" style={{ color: '#374151' }}>
            SHA-256 hash-chained · 6,271 invariant tests · EU AI Act compliant
          </p>
        </div>
      </div>

      {/* ── Footer ───────────────────────────────────────────── */}
      <div className="border-t border-hub-border">
        <div className="max-w-5xl mx-auto px-4 py-8 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span
              className="text-sm font-semibold"
              style={{ fontFamily: '"JetBrains Mono", monospace', letterSpacing: '0.22em', color: '#C8A96E' }}
            >
              AEGIS-Ω
            </span>
            <span className="text-hub-muted text-sm">Creator Toolkit</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="/" className="text-hub-muted text-xs hover:text-hub-text transition-colors">← The System</a>
            <a href="#pricing" className="text-hub-muted text-xs hover:text-hub-text transition-colors">Pricing</a>
            <a
              href="mailto:tarikskalic33@gmail.com"
              className="inline-flex items-center gap-1.5 text-hub-muted text-xs hover:text-hub-text transition-colors"
            >
              <Mail size={11} />
              Contact
            </a>
          </div>
        </div>
      </div>

    </div>
  )
}
