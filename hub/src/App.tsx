// ── AEGIS-Ω Hub — marketing landing page ────────────────────────────────────
// All components inline · vanilla CSS via index.css · no Tailwind classes

import { Analytics } from '@vercel/analytics/react'

// ── AegisMark SVG ──
function AegisMark({ size = 32, color = 'currentColor' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" stroke={color}>
      <rect x="0.5" y="0.5" width="63" height="63" strokeWidth="1" vectorEffect="non-scaling-stroke"/>
      <path d="M 32 32 L 32 14 M 32 32 L 16.4 41 M 32 32 L 47.6 41" strokeWidth="1.6" strokeLinecap="round" vectorEffect="non-scaling-stroke"/>
      <circle cx="32" cy="12" r="4" strokeWidth="1.6" vectorEffect="non-scaling-stroke"/>
      <circle cx="14.7" cy="42" r="4" strokeWidth="1.6" vectorEffect="non-scaling-stroke"/>
      <circle cx="49.3" cy="42" r="4" strokeWidth="1.6" vectorEffect="non-scaling-stroke"/>
      <circle cx="32" cy="32" r="5" fill={color} stroke="none"/>
    </svg>
  )
}

// ── Data ────────────────────────────────────────────────────────────────────

const PRODUCTS = [
  {
    icon: '🎯',
    name: 'Platform Picker',
    tagline: 'Stop guessing which platform fits you',
    description: 'Tell the AI your niche, style, posting schedule, and monetisation goal. Get a scored breakdown across TikTok, YouTube Shorts, Instagram Reels, and Snapchat Spotlight — with a radar chart and one-click share.',
    features: [
      'Radar chart across 4 platforms',
      'Score + reasoning per platform',
      'Tailored to your monetisation goal',
      'Share summary to clipboard',
    ],
    accentColor: '#7C3AED',
    glowColor: '#A78BFA',
    price: 19,
    gumroadUrl: 'https://gumroad.com/l/aegis-platform-picker',
  },
  {
    icon: '⚡',
    name: 'Hook Generator',
    tagline: '10 scroll-stopping hooks in 10 seconds',
    description: 'Input your niche, platform, topic, and tone. The AI returns 10 ranked viral hooks — curiosity gap, controversy, social proof, numbers, pain point — each with a type badge and one-click copy.',
    features: [
      '10 hooks ranked by viral potential',
      'Type-coded with colour badges',
      'Star & save favourites locally',
      'Export all hooks at once',
    ],
    accentColor: '#D97706',
    glowColor: '#FCD34D',
    price: 19,
    gumroadUrl: 'https://gumroad.com/l/aegis-hook-generator',
  },
  {
    icon: '📅',
    name: 'Content Calendar',
    tagline: 'A month of content ideas in one click',
    description: 'Enter your niche, platforms, posting frequency, and 3 content pillars. Get a full 4-week calendar with daily ideas, viral hooks per post, formats, and production notes. Export as TXT or CSV.',
    features: [
      '4 weeks × your posting frequency',
      'Per-post copy buttons',
      'Colour-coded content pillars',
      'Export as TXT or CSV',
    ],
    accentColor: '#16A34A',
    glowColor: '#86EFAC',
    price: 19,
    gumroadUrl: 'https://gumroad.com/l/aegis-content-calendar',
  },
]

const GUARANTEES = [
  {
    icon: '🔒',
    title: 'Zero backend',
    desc: 'Runs entirely in your browser. No servers, no accounts, no data collection.',
  },
  {
    icon: '⚡',
    title: 'Your API key, your costs',
    desc: 'DashScope free tier covers hundreds of runs. You pay pennies, not subscriptions.',
  },
  {
    icon: '</>',
    title: 'Full source code',
    desc: 'Self-host on Vercel in 2 minutes. Fork, modify, make it yours.',
  },
  {
    icon: '∞',
    title: 'Buy once, own forever',
    desc: 'No recurring fees. Future updates included.',
  },
]

const TIERS = [
  {
    name: 'Single Tool',
    price: 19,
    originalPrice: undefined as number | undefined,
    desc: 'Pick any one — Platform Picker, Hook Generator, or Content Calendar.',
    items: [
      '1 AI tool of your choice',
      'Unlimited runs (your API key)',
      'No subscriptions, ever',
      'Full source code',
    ],
    highlight: false,
    badge: undefined as string | undefined,
    gumroadUrl: 'https://gumroad.com/l/aegis-single',
  },
  {
    name: 'Starter Pack',
    price: 29,
    originalPrice: 38,
    desc: 'Any two tools at a discount. Mix and match what you need.',
    items: [
      '2 AI tools of your choice',
      'Save $9 vs buying separate',
      'Unlimited runs (your API key)',
      'No subscriptions, ever',
      'Full source code',
    ],
    highlight: true,
    badge: 'Most popular',
    gumroadUrl: 'https://gumroad.com/l/aegis-starter-pack',
  },
  {
    name: 'Full Toolkit',
    price: 39,
    originalPrice: 57,
    desc: 'All three tools — the complete creator AI arsenal.',
    items: [
      'All 3 AI tools',
      'Save $18 vs buying separate',
      'Unlimited runs (your API key)',
      'No subscriptions, ever',
      'Full source code',
      'Future tool updates included',
    ],
    highlight: false,
    badge: 'Best value',
    gumroadUrl: 'https://gumroad.com/l/aegis-full-toolkit',
  },
]

const FAQ = [
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
    a: "You receive the full source code as a zip file. It's a React + TypeScript project that you deploy to Vercel. You own the code — modify it however you like.",
  },
  {
    q: 'Can I use this commercially?',
    a: 'Yes. The code is MIT licensed. Use it for your own content, your agency\'s clients, or build your own paid tool on top of it.',
  },
]

// ── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <div className="hub-shell">

      {/* ── Nav ── */}
      <nav className="hub-nav">
        <div className="hub-nav-brand">
          <div className="hub-nav-mark">
            <AegisMark size={28} color="var(--hub-accent)" />
          </div>
          <div>
            <div className="hub-nav-wordmark">AEGIS-Ω</div>
            <div className="hub-nav-subtitle">Creator Toolkit</div>
          </div>
        </div>
        <div className="hub-nav-links">
          <a href="#products" className="hub-nav-link">Products</a>
          <a href="#pricing" className="hub-nav-link">Pricing</a>
          <a
            href="https://gumroad.com/l/aegis-full-toolkit"
            target="_blank"
            rel="noopener noreferrer"
            className="hub-nav-cta"
          >
            Buy now →
          </a>
        </div>
      </nav>

      {/* ── Hero ── */}
      <div className="hub-hero hub-container--narrow">
        <div className="hub-fade-up hub-eyebrow" style={{ animationDelay: '0ms' }}>
          <span>⚡</span>
          Creator AI Toolkit — 3 tools, one DashScope key
        </div>

        <h1 className="hub-h1 hub-fade-up" style={{ animationDelay: '80ms' }}>
          AI tools that actually<br />
          <span className="hub-h1-glow">help you grow.</span>
        </h1>

        <p className="hub-lead hub-fade-up" style={{ animationDelay: '160ms' }}>
          Platform Picker. Hook Generator. Content Calendar.
          Zero backend, zero subscription. You own the code.
        </p>

        <div className="hub-hero-actions hub-fade-up" style={{ animationDelay: '240ms' }}>
          <a
            href="https://gumroad.com/l/aegis-full-toolkit"
            target="_blank"
            rel="noopener noreferrer"
            className="hub-btn-primary"
          >
            <span>⚡</span>
            Get all 3 tools — $39
          </a>
          <a href="#products" className="hub-btn-secondary">
            See the tools
          </a>
        </div>

        <p className="hub-meta-text hub-fade-up" style={{ animationDelay: '300ms' }}>
          One-time payment · Full source code · No subscriptions
        </p>
      </div>

      {/* ── Products ── */}
      <section id="products" className="hub-section hub-container--mid">
        <div className="hub-section-head">
          <h2 className="hub-h2">Three tools. One key.</h2>
          <p className="hub-section-desc">
            Each tool runs entirely in your browser using your DashScope API key. No data ever leaves your machine.
          </p>
        </div>

        <div className="hub-products-grid">
          {PRODUCTS.map((p, i) => (
            <div
              key={p.name}
              className="hub-product-card hub-fade-up"
              style={{ animationDelay: `${300 + i * 100}ms` }}
            >
              {/* Top row: icon + price */}
              <div className="hub-product-top">
                <div
                  className="hub-product-icon"
                  style={{
                    background: `${p.accentColor}20`,
                    border: `1px solid ${p.accentColor}40`,
                  }}
                >
                  {p.icon}
                </div>
                <div className="hub-product-price-wrap">
                  <span
                    className="hub-product-price-pill"
                    style={{ background: `${p.glowColor}20`, color: p.glowColor }}
                  >
                    ${p.price}
                  </span>
                  <span className="hub-product-price-sub">one-time</span>
                </div>
              </div>

              {/* Info */}
              <div>
                <h3 className="hub-product-name">{p.name}</h3>
                <p className="hub-product-tagline" style={{ color: p.glowColor }}>{p.tagline}</p>
                <p className="hub-product-desc">{p.description}</p>
              </div>

              {/* Features */}
              <ul className="hub-product-features">
                {p.features.map(f => (
                  <li key={f} className="hub-product-feature">
                    <span className="hub-product-feature-check" style={{ color: p.glowColor }}>✓</span>
                    {f}
                  </li>
                ))}
              </ul>

              {/* Buy button */}
              <a
                href={p.gumroadUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="hub-product-buy"
                style={{ background: p.accentColor }}
              >
                <span>🛒</span>
                Buy — ${p.price}
              </a>
            </div>
          ))}
        </div>
      </section>

      {/* ── Guarantees ── */}
      <section className="hub-section--sm hub-container">
        <div className="hub-guarantees-grid">
          {GUARANTEES.map(g => (
            <div key={g.title} className="hub-guarantee-card">
              <div className="hub-guarantee-icon">{g.icon}</div>
              <div className="hub-guarantee-title">{g.title}</div>
              <p className="hub-guarantee-desc">{g.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="hub-section hub-container--mid">
        <div className="hub-section-head">
          <h2 className="hub-h2">Up and running in 5 minutes</h2>
          <p className="hub-section-desc">
            No backend to set up. No API wrappers to pay for. Just your key and a Vercel deploy.
          </p>
        </div>
        <div className="hub-steps-grid">
          {[
            {
              step: '1',
              title: 'Get a free DashScope key',
              desc: 'Sign up at dashscope.aliyuncs.com. The free tier covers hundreds of requests — more than enough to start.',
            },
            {
              step: '2',
              title: 'Deploy to Vercel',
              desc: 'Import the repo, set VITE_DASHSCOPE_API_KEY, set Root Directory to the tool you bought. Done in 2 minutes.',
            },
            {
              step: '3',
              title: 'Create content',
              desc: 'Fill in the form, click Generate, get AI results instantly. Copy, share, download — no login required.',
            },
          ].map(item => (
            <div key={item.step} className="hub-step-card">
              <div className="hub-step-num">{item.step}</div>
              <div className="hub-step-title">{item.title}</div>
              <p className="hub-step-desc">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Pricing ── */}
      <section id="pricing" className="hub-section hub-container--mid">
        <div className="hub-section-head">
          <h2 className="hub-h2">Simple pricing</h2>
          <p className="hub-section-desc">Buy once. Own it forever. No subscriptions, no upsells.</p>
        </div>

        <div className="hub-pricing-grid">
          {TIERS.map(tier => (
            <div
              key={tier.name}
              className={`hub-pricing-card${tier.highlight ? ' hub-pricing-card--popular' : ''}`}
            >
              {tier.badge && (
                <span className="hub-pricing-badge">{tier.badge}</span>
              )}

              <div>
                <div className="hub-pricing-amount">
                  <span className="hub-pricing-price">${tier.price}</span>
                  {tier.originalPrice != null && (
                    <span className="hub-pricing-original">${tier.originalPrice}</span>
                  )}
                </div>
                <div className="hub-pricing-name">{tier.name}</div>
                <p className="hub-pricing-desc" style={{ marginTop: 6 }}>{tier.desc}</p>
              </div>

              <ul className="hub-pricing-items">
                {tier.items.map(item => (
                  <li key={item} className="hub-pricing-item">
                    <span className="hub-pricing-check">✓</span>
                    {item}
                  </li>
                ))}
              </ul>

              <a
                href={tier.gumroadUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={`hub-pricing-btn${tier.highlight ? ' hub-pricing-btn--popular' : ' hub-pricing-btn--default'}`}
              >
                <span>🛒</span>
                Get {tier.name}
              </a>
            </div>
          ))}
        </div>
      </section>

      {/* ── FAQ ── */}
      <section className="hub-section hub-container--narrow">
        <div className="hub-section-head">
          <h2 className="hub-h2">FAQ</h2>
        </div>
        <ul className="hub-faq-list">
          {FAQ.map(item => (
            <li key={item.q} className="hub-faq-item">
              <div className="hub-faq-q">{item.q}</div>
              <p className="hub-faq-a">{item.a}</p>
            </li>
          ))}
        </ul>
      </section>

      {/* ── Final CTA ── */}
      <section className="hub-section hub-container--narrow">
        <div className="hub-cta-box">
          <h2 className="hub-cta-h2">Ready to start?</h2>
          <p className="hub-cta-desc">All three tools for $39. One-time payment. Full source code.</p>
          <a
            href="https://gumroad.com/l/aegis-full-toolkit"
            target="_blank"
            rel="noopener noreferrer"
            className="hub-btn-primary"
            style={{ margin: '0 auto' }}
          >
            <span>⚡</span>
            Get the Full Toolkit — $39
          </a>
          <p className="hub-cta-sub">
            Or get a single tool for $19 · Starter Pack (any 2) for $29
          </p>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="hub-footer">
        <div className="hub-footer-brand">
          <AegisMark size={16} color="var(--hub-glow)" />
          AEGIS Creator Toolkit
        </div>
        <div className="hub-footer-links">
          <a href="#products" className="hub-footer-link">Products</a>
          <a href="#pricing" className="hub-footer-link">Pricing</a>
          <a
            href="https://gumroad.com/l/aegis-full-toolkit"
            target="_blank"
            rel="noopener noreferrer"
            className="hub-footer-link--accent"
          >
            Buy now →
          </a>
        </div>
      </footer>

      <Analytics />
    </div>
  )
}
