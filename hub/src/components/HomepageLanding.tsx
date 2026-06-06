import { useEffect, useRef } from 'react'
import { Mail, Check } from 'lucide-react'

function GithubIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  )
}

function captureEvent(event: string, props?: Record<string, unknown>): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ph = (window as any).posthog
  if (typeof ph?.capture === 'function') ph.capture(event, props)
}

export function HomepageLanding() {
  const trialStartRef = useRef(Date.now())

  useEffect(() => {
    captureEvent('homepage_viewed')
  }, [])

  const ttv = () => Math.round((Date.now() - trialStartRef.current) / 1000)

  const handleDemoClick = () => {
    captureEvent('click_demo_cta', { ttv_seconds: ttv() })
    // Open Calendly popup
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Calendly = (window as any).Calendly
    if (Calendly) {
      Calendly.showPopupWidget('https://calendly.com/aegis-omega/technical-audit')
    }
  }

  return (
    <div className="min-h-screen bg-hub-bg text-hub-text">
      {/* Nav */}
      <nav className="sticky top-0 z-50 border-b border-hub-border/60 bg-hub-bg/95 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <span className="text-sm font-semibold animate-breathe" style={{ fontFamily: '"JetBrains Mono", monospace', letterSpacing: '0.22em', color: '#C8A96E' }}>
            AEGIS-Ω
          </span>
          <div className="flex items-center gap-8">
            <a href="#industries" className="text-xs text-hub-muted hover:text-hub-text transition-colors hidden sm:block">Industries</a>
            <a href="/cockpit" className="text-xs text-hub-muted hover:text-hub-text transition-colors hidden sm:block">Cockpit SaaS</a>
            <a href="https://github.com/Aegis-Omega/AEGIS--" target="_blank" rel="noopener noreferrer" className="text-xs text-hub-muted hover:text-hub-text transition-colors">
              Source
            </a>
            <button
              onClick={handleDemoClick}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg hover:opacity-90 transition-opacity text-white"
              style={{ background: '#6366F1' }}
            >
              Book Demo
            </button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-4xl mx-auto px-4 py-32 text-center">
        {/* Eyebrow */}
        <div className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-medium mb-8"
          style={{ background: 'rgba(200,169,110,0.08)', border: '1px solid rgba(200,169,110,0.20)', color: '#C8A96E' }}>
          <span className="w-1.5 h-1.5 rounded-full animate-mint-pulse flex-shrink-0" style={{ background: '#C8A96E' }} />
          EU AI Act Compliant · Enterprise-Ready
        </div>

        {/* Headline */}
        <h1 className="font-bold leading-tight mb-6 animate-fade-up" style={{ fontSize: 'clamp(36px, 6.5vw, 60px)', letterSpacing: '-0.02em' }}>
          AI That Your<br />
          <span style={{ color: '#C8A96E' }}>Compliance Team</span><br />
          <span style={{ color: '#C8A96E' }}>Will Approve</span>
        </h1>

        {/* Subheading */}
        <p className="text-hub-muted text-lg max-w-2xl mx-auto mb-6 leading-relaxed animate-fade-up delay-100">
          Not a black box. Deterministic. Auditable. Replay-verified.
          Hash-chained from first token to last output. Your data. Your model. Constitutional guarantees at every layer.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center mb-4 animate-fade-up delay-300">
          <button
            onClick={handleDemoClick}
            className="inline-flex items-center justify-center gap-2 text-white font-semibold px-8 py-3.5 rounded-xl hover:opacity-90 transition-opacity text-sm"
            style={{ background: '#6366F1' }}
          >
            Book Enterprise Demo →
          </button>
          <a
            href="/runtime"
            onClick={() => captureEvent('hero_runtime_link', { ttv_seconds: ttv() })}
            className="inline-flex items-center justify-center gap-2 border border-hub-border text-hub-muted hover:text-hub-text hover:border-hub-border/80 font-medium px-8 py-3.5 rounded-xl transition-colors text-sm"
          >
            See the Runtime →
          </a>
        </div>

        <p className="text-hub-muted/50 text-xs">
          11,337 tests · 0 failures · SHA-256 hash-chained · AGPL-3.0
        </p>
      </section>

      {/* Trust Metrics */}
      <section className="bg-hub-surface/30 border-y border-hub-border/60 py-12">
        <div className="max-w-5xl mx-auto px-4 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {[
            { value: '11,337+', label: 'Invariant Tests', sub: 'all passing' },
            { value: 'SHA-256', label: 'Hash-Chained', sub: 'tamper-evident' },
            { value: 'T0 Proven', label: 'Deterministic', sub: 'replay-verified' },
            { value: 'AGPL-3.0', label: 'Open Source', sub: 'no lock-in' },
          ].map(m => (
            <div key={m.label}>
              <div className="text-2xl font-bold mb-1" style={{ color: '#C8A96E', fontFamily: '"JetBrains Mono", monospace' }}>
                {m.value}
              </div>
              <div className="text-hub-text text-xs font-semibold">{m.label}</div>
              <div className="text-xs mt-0.5" style={{ color: '#4B5563' }}>{m.sub}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Problem → Solution */}
      <section className="max-w-4xl mx-auto px-4 py-20">
        <h2 className="text-3xl font-bold mb-12 text-center leading-tight">Why Traditional AI Fails Regulated Organizations</h2>
        <div className="grid md:grid-cols-3 gap-6">
          {[
            {
              problem: '❌ Black Box',
              title: 'You Can\'t Replay Decisions',
              desc: 'Every inference is opaque. Auditors demand proof. You can\'t provide it.',
              solution: '✓ Deterministic Replay',
              solutionDesc: 'Every decision hash-certified from genesis. Replayable byte-for-byte on any platform.',
            },
            {
              problem: '❌ Hallucination Risk',
              title: 'Models Make Up Facts',
              desc: 'Fabricated outputs create legal liability. Compliance officers say no.',
              solution: '✓ Constitutional Governance',
              solutionDesc: 'T0–T2 layers prevent hallucinations. Governance enforced mechanically, not aspirationally.',
            },
            {
              problem: '❌ Vendor Lock-In',
              title: 'Proprietary API Trap',
              desc: 'Can\'t switch vendors. Pricing opaque. Compliance audits impossible.',
              solution: '✓ Your Code',
              solutionDesc: 'Full AGPL source. Run anywhere. No vendor lock-in. Auditable end-to-end.',
            },
          ].map((item, idx) => (
            <div key={idx} className="space-y-6">
              <div className="bg-red-500/10 border border-red-500/30 p-6 rounded-lg">
                <div className="text-sm font-bold mb-1" style={{ color: '#F87171' }}>{item.problem}</div>
                <div className="font-semibold text-hub-text mb-2">{item.title}</div>
                <p className="text-sm text-hub-muted">{item.desc}</p>
              </div>
              <div className="bg-green-500/10 border border-green-500/30 p-6 rounded-lg">
                <div className="text-sm font-bold mb-1" style={{ color: '#34D399' }}>{item.solution}</div>
                <p className="text-sm text-hub-muted">{item.solutionDesc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Industries */}
      <section id="industries" className="bg-hub-surface/30 border-y border-hub-border/60 py-20">
        <div className="max-w-4xl mx-auto px-4">
          <h2 className="text-3xl font-bold mb-12 text-center">Built For Regulated Industries</h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { icon: '🏦', title: 'Fintech', desc: 'Compliance reporting · risk assessment · fraud detection · audit-proof decision logs' },
              { icon: '🏥', title: 'Healthcare', desc: 'Patient records · clinical decision support · HIPAA-ready audit trail · no hallucinations' },
              { icon: '⚖️', title: 'Legal Tech', desc: 'Contract analysis · compliance checks · litigation holds · citeable outputs' },
            ].map(ind => (
              <div key={ind.title} className="bg-hub-bg border border-hub-border p-6 rounded-lg hover:border-hub-border/80 transition-colors">
                <div className="text-3xl mb-3">{ind.icon}</div>
                <div className="font-bold text-hub-text mb-1">{ind.title}</div>
                <div className="text-sm text-hub-muted leading-relaxed">{ind.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* AEGIS Guarantees */}
      <section className="max-w-4xl mx-auto px-4 py-20">
        <h2 className="text-3xl font-bold mb-12 text-center">What AEGIS Guarantees</h2>
        <div className="grid md:grid-cols-2 gap-6">
          {[
            {
              title: 'Deterministic Replay',
              desc: 'replay(genesis, events) → identical output on Linux, macOS, WASM, ARM, x86. Prove it works anywhere.',
            },
            {
              title: 'Hash-Chained Audit Trail',
              desc: 'Every state transition signed. Every decision citeable. HIPAA/PCI/SOX ready. Litigation-proof.',
            },
            {
              title: 'Constitutional Governance',
              desc: 'T0–T2 layers prevent hallucinations and unauthorized adaptation. Governance is mechanical law, not a policy.',
            },
            {
              title: 'EU AI Act Compliant',
              desc: 'Article 12 audit binders generated automatically. No custom integration. Pass audits by design.',
            },
          ].map((g, idx) => (
            <div key={idx} className="bg-hub-bg border border-hub-border/60 p-6 rounded-lg">
              <div className="flex items-start gap-3">
                <Check size={20} style={{ color: '#34D399', flexShrink: 0 }} className="mt-1" />
                <div>
                  <div className="font-bold text-hub-text mb-1">{g.title}</div>
                  <p className="text-sm text-hub-muted">{g.desc}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA Footer */}
      <section className="max-w-3xl mx-auto px-4 py-20 text-center">
        <h2 className="text-2xl font-bold mb-4">Ready to Deploy Constitutional AI?</h2>
        <p className="text-hub-muted mb-8 max-w-xl mx-auto">
          30-minute technical audit. See deterministic replay in action. No pressure. No sales pitch.
        </p>
        <button
          onClick={handleDemoClick}
          className="px-8 py-3 rounded-lg text-white font-semibold hover:opacity-90 transition-opacity"
          style={{ background: '#6366F1' }}
        >
          Book Demo →
        </button>
      </section>

      {/* Footer */}
      <footer className="border-t border-hub-border/60 py-8">
        <div className="max-w-5xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-sm font-semibold" style={{ fontFamily: '"JetBrains Mono", monospace', letterSpacing: '0.22em', color: '#C8A96E' }}>
            AEGIS-Ω
          </span>
          <div className="flex items-center gap-6">
            <a href="/cockpit" className="text-hub-muted text-xs hover:text-hub-text transition-colors">Cockpit</a>
            <a href="#industries" className="text-hub-muted text-xs hover:text-hub-text transition-colors">Industries</a>
            <a href="https://github.com/Aegis-Omega/AEGIS--" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-hub-muted text-xs hover:text-hub-text transition-colors">
              <GithubIcon size={11} />
              Source
            </a>
            <a href="mailto:info@aegisomega.com" className="inline-flex items-center gap-1.5 text-hub-muted text-xs hover:text-hub-text transition-colors">
              <Mail size={11} />
              Contact
            </a>
          </div>
        </div>
      </footer>

      {/* Calendly widget */}
      <script src="https://assets.calendly.com/assets/external/widget.js" async />
    </div>
  )
}
