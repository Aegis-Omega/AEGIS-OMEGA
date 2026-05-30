// AEGIS Omega — ToolsPage (/tools): the first applications, kept apart from the
// automaton's main narrative. These commercial tools are deployed ON the
// platform — they are not the platform. Pricing lives here and only here.

import { PricingTable } from './PricingTable.js'

const TOOLS = [
  { name: 'Platform Picker',   desc: 'Tell the AI your niche and audience. Get a ranked breakdown of the best platforms with growth strategies tailored to you.', color: '#7C3AED', href: import.meta.env.VITE_URL_PLATFORM_PICKER  ?? '#pricing' },
  { name: 'Hook Generator',    desc: 'Paste your topic. Get 20 scroll-stopping hooks — curiosity gaps, controversies, numbers, pain points — one-click copy.', color: '#06B6D4', href: import.meta.env.VITE_URL_HOOK_GENERATOR   ?? '#pricing' },
  { name: 'Content Calendar',  desc: 'Define your pillars and posting frequency. Get a full 30-day calendar with topics, formats, and publish times.', color: '#F59E0B', href: import.meta.env.VITE_URL_CONTENT_CALENDAR ?? '#pricing' },
]

export function ToolsPage() {
  return (
    <div style={{ background: '#030712', minHeight: '100vh', color: '#F1F5F9', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' }}>
      <nav style={{
        padding: '0 32px', height: 64, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}>
        <a href="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg, #7C3AED, #F59E0B)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 900, color: 'white' }}>Ω</div>
          <span style={{ fontWeight: 800, fontSize: 16, letterSpacing: '0.08em', color: '#F1F5F9' }}>AEGIS OMEGA</span>
        </a>
        <a href="/" style={{ color: '#64748B', textDecoration: 'none', fontSize: 14, fontWeight: 500 }}>← Back to the platform</a>
      </nav>

      <section style={{ padding: '80px 24px 40px', maxWidth: 1000, margin: '0 auto' }}>
        <div style={{ color: '#475569', fontSize: 11, fontWeight: 700, letterSpacing: '0.2em', marginBottom: 12 }}>FIRST APPLICATIONS</div>
        <h1 style={{ fontSize: 'clamp(32px, 5vw, 48px)', fontWeight: 800, color: '#F1F5F9', marginBottom: 16, letterSpacing: '-0.02em' }}>
          Built on the platform. Built for creators.
        </h1>
        <p style={{ color: '#64748B', fontSize: 17, maxWidth: 640, marginBottom: 56, lineHeight: 1.7 }}>
          Three tools — the first applications deployed on AEGIS Omega. Each governed by the same constitutional system. Each accessible with a single one-time payment.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginBottom: 80 }}>
          {TOOLS.map(tool => (
            <div key={tool.name} style={{
              background: 'rgba(13,17,27,0.95)', border: '1px solid rgba(255,255,255,0.07)',
              borderRadius: 16, padding: 24, display: 'flex', flexDirection: 'column', gap: 12,
            }}>
              <div style={{ width: 32, height: 3, background: tool.color, borderRadius: 2 }} />
              <div style={{ fontWeight: 700, fontSize: 17, color: '#F1F5F9' }}>{tool.name}</div>
              <div style={{ color: '#64748B', fontSize: 14, lineHeight: 1.65, flex: 1 }}>{tool.desc}</div>
              <a href={tool.href} style={{ color: tool.color, fontWeight: 600, fontSize: 14, textDecoration: 'none' }}>Open →</a>
            </div>
          ))}
        </div>

        <div style={{ textAlign: 'center' }}>
          <div style={{ color: '#475569', fontSize: 11, fontWeight: 700, letterSpacing: '0.2em', marginBottom: 12 }}>ACCESS</div>
          <h2 style={{ fontSize: 32, fontWeight: 800, color: '#F1F5F9', marginBottom: 12, letterSpacing: '-0.02em' }}>One price. No recurring fees.</h2>
          <p style={{ color: '#64748B', fontSize: 16, marginBottom: 48 }}>Permanent access. No subscription. No hidden API costs.</p>
          <PricingTable />
        </div>
      </section>

      <footer style={{ borderTop: '1px solid rgba(255,255,255,0.05)', padding: '32px', textAlign: 'center' }}>
        <a href="/" style={{ color: '#334155', fontSize: 13, textDecoration: 'none' }}>© 2026 AEGIS Omega — return to the platform</a>
      </footer>
    </div>
  )
}
