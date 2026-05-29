import { useEffect, useRef } from 'react'
import { PricingTable } from './components/PricingTable.js'
import { SuccessPage } from './components/SuccessPage.js'
import { Zap, Lock, RefreshCw, Code, Mail } from 'lucide-react'

function captureEvent(event: string, props?: Record<string, unknown>): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ph = (window as any).posthog
  if (typeof ph?.capture === 'function') ph.capture(event, props)
}

// ── Product definitions ─────────────────────────────────────────────────
const PRODUCTS = [
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
    accent: '#D97706',
    glow:   '#FCD34D',
    price:  19,
    url:    'https://aegis-hook-generator.vercel.app',
  },
  {
    icon: '📅',
    name: 'Content Calendar',
    tagline: 'A month of content ideas in one click',
    desc: 'Enter your niche, platforms, posting frequency, and 3 content pillars. Get a full 4-week calendar with daily ideas, viral hooks per post, formats, and production notes. Export as TXT or CSV.',
    features: [
      '4 weeks × your posting frequency',
      'Per-post hook, format, and notes',
      'Colour-coded content pillars',
      'Export as TXT or CSV',
    ],
    accent: '#16A34A',
    glow:   '#86EFAC',
    price:  19,
    url:    'https://aegis-content-calendar.vercel.app',
  },
]

// ── Guarantees ──────────────────────────────────────────────────────────
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

// ── FAQs ────────────────────────────────────────────────────────────────
const FAQS = [
  {
    q: 'What is DashScope / do I need to pay for it?',
    a: "DashScope is Alibaba Cloud's AI API, powered by Qwen. The free tier gives you enough credits to run hundreds of generations per month. Most users never need to upgrade.",
  },
  {
    q: 'Do I need to know how to code?',
    a: 'You need to import the repo to Vercel and set one environment variable. Vercel walks you through it — takes about 2 minutes. No coding required.',
  },
  {
    q: 'What do I actually receive when I buy?',
    a: 'You receive the full source code as a zip file. It\'s a React + TypeScript project that you deploy to Vercel. You own the code — modify it however you like.',
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

// ── App ─────────────────────────────────────────────────────────────────
export default function App() {
  if (window.location.pathname === '/success') return <SuccessPage />

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

      {/* ── Nav ──────────────────────────────────────────────── */}
      <nav className="border-b border-hub-border/60 sticky top-0 z-50 bg-hub-bg/95 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <span
            className="text-sm font-semibold animate-breathe"
            style={{ fontFamily: '"JetBrains Mono", monospace', letterSpacing: '0.22em', color: '#C8A96E' }}
          >
            AEGIS-Ω
          </span>
          <div className="flex items-center gap-6">
            <a href="#products" className="text-hub-muted text-xs hover:text-hub-text transition-colors hidden sm:block">Products</a>
            <a href="#pricing"  className="text-hub-muted text-xs hover:text-hub-text transition-colors hidden sm:block">Pricing</a>
            <a
              href="#pricing"
              onClick={() => handlePurchaseClick('nav', 39)}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg hover:opacity-90 transition-opacity text-white"
              style={{ background: '#6366F1' }}
            >
              Get started
            </a>
          </div>
        </div>
      </nav>

      {/* ── Hero ─────────────────────────────────────────────── */}
      <div className="max-w-4xl mx-auto px-4 pt-20 pb-16 text-center">
        {/* Eyebrow pill */}
        <div
          className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-medium mb-8"
          style={{ background: 'rgba(99,102,241,0.10)', border: '1px solid rgba(99,102,241,0.30)', color: '#818CF8' }}
        >
          <Zap size={13} />
          Creator AI Toolkit — 3 tools, one DashScope key
        </div>

        {/* h1 — two lines, second in glow */}
        <h1
          className="font-bold leading-none mb-6"
          style={{ fontSize: 'clamp(42px, 7vw, 60px)', letterSpacing: '-0.02em' }}
        >
          AI tools that actually<br />
          <span style={{ color: '#818CF8' }}>help you grow.</span>
        </h1>

        <p className="text-hub-muted text-lg max-w-xl mx-auto mb-8 leading-relaxed">
          Platform Picker. Hook Generator. Content Calendar.
          Zero backend, zero subscription. You own the code.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center mb-4">
          <a
            href="#pricing"
            onClick={() => handlePurchaseClick('hero', 39)}
            className="inline-flex items-center justify-center gap-2 text-white font-semibold px-8 py-3.5 rounded-xl hover:opacity-90 transition-opacity text-sm"
            style={{ background: '#6366F1' }}
          >
            <Zap size={15} />
            Get all 3 tools — $39
          </a>
          <a
            href="#products"
            className="inline-flex items-center justify-center gap-2 border border-hub-border text-hub-muted hover:text-hub-text hover:border-hub-border/80 font-medium px-8 py-3.5 rounded-xl transition-all text-sm"
          >
            See the tools
          </a>
        </div>
        <p className="text-hub-muted/60 text-xs">One-time payment · Full source code · No subscriptions</p>
      </div>

      {/* ── Product cards ─────────────────────────────────────── */}
      <section id="products" className="max-w-5xl mx-auto px-4 pb-20 scroll-mt-16">
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
              {/* Card top row: icon tile + price */}
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

              {/* Name, tagline, desc */}
              <h3 className="font-bold text-lg text-hub-text mb-0.5">{p.name}</h3>
              <p className="text-sm font-medium mb-3" style={{ color: p.glow }}>{p.tagline}</p>
              <p className="text-hub-muted text-sm leading-relaxed mb-4">{p.desc}</p>

              {/* Feature list */}
              <ul className="flex flex-col gap-2 mb-6 flex-1">
                {p.features.map(f => (
                  <li key={f} className="flex gap-2 text-sm text-hub-muted">
                    <span style={{ color: p.glow, flexShrink: 0 }}>✓</span>
                    {f}
                  </li>
                ))}
              </ul>

              {/* Buy button */}
              <a
                href="#pricing"
                onClick={() => handlePurchaseClick(p.name.toLowerCase().replace(/ /g, '-'), p.price)}
                className="inline-flex items-center justify-center gap-2 text-white font-semibold py-3 rounded-xl hover:opacity-90 transition-opacity text-sm"
                style={{ background: p.accent }}
              >
                Buy — ${p.price}
              </a>
            </div>
          ))}
        </div>
      </section>

      {/* ── Guarantees ───────────────────────────────────────── */}
      <div className="border-y border-hub-border/60 bg-hub-surface/30">
        <div className="max-w-3xl mx-auto px-4 py-14">
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

      {/* ── How it works ──────────────────────────────────────── */}
      <div className="border-y border-hub-border/60 bg-hub-surface/30">
        <div className="max-w-3xl mx-auto px-4 py-16">
          <h2 className="text-xl font-bold text-hub-text text-center mb-10">Up and running in 5 minutes</h2>
          <div className="grid md:grid-cols-3 gap-4">
            {[
              {
                step: '01',
                title: 'Choose your plan',
                desc:  'One tool for $19, any two for $29, all three for $39. One payment. No subscription.',
              },
              {
                step: '02',
                title: 'Pay via Lemon Squeezy',
                desc:  'Works in 130+ countries — including Bosnia, Serbia, and everywhere Stripe blocks. Card, PayPal.',
              },
              {
                step: '03',
                title: 'Instant access',
                desc:  'Redirected back automatically. Click a tool link and it opens. No account, no email, no API key required.',
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

      {/* ── FAQ ───────────────────────────────────────────────── */}
      <div className="max-w-2xl mx-auto px-4 py-16">
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

      {/* ── Final CTA ─────────────────────────────────────────── */}
      <div className="max-w-2xl mx-auto px-4 pb-20">
        <div
          className="rounded-2xl p-10 text-center"
          style={{ background: '#0F1117', border: '1px solid rgba(99,102,241,0.20)' }}
        >
          <h2 className="text-2xl font-bold text-hub-text mb-3" style={{ letterSpacing: '-0.02em' }}>
            Ready to start?
          </h2>
          <p className="text-hub-muted text-sm mb-6">All three tools for $39. One-time payment. Full source code.</p>
          <a
            href="#pricing"
            onClick={() => handlePurchaseClick('final-cta', 39)}
            className="inline-flex items-center justify-center gap-2 text-white font-semibold px-10 py-4 rounded-xl hover:opacity-90 transition-opacity text-sm"
            style={{ background: '#6366F1' }}
          >
            <Zap size={15} />
            Get the Full Toolkit — $39
          </a>
          <p className="text-hub-muted/60 text-xs mt-4">
            Single tool $19 · Any two $29 · 30-day refund
          </p>
        </div>
      </div>

      {/* ── Footer ────────────────────────────────────────────── */}
      <div className="border-t border-hub-border">
        <div className="max-w-5xl mx-auto px-4 py-8 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Zap size={16} style={{ color: '#818CF8' }} />
            <span className="text-hub-muted text-sm font-medium">AEGIS Creator Toolkit</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#products" className="text-hub-muted text-xs hover:text-hub-text transition-colors">Products</a>
            <a href="#pricing"  className="text-hub-muted text-xs hover:text-hub-text transition-colors">Pricing</a>
            <a
              href="#pricing"
              onClick={() => handlePurchaseClick('footer', 39)}
              className="text-xs font-medium hover:text-hub-text transition-colors"
              style={{ color: '#818CF8' }}
            >
              Buy now →
            </a>
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
