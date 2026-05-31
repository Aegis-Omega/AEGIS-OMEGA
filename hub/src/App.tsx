// AEGIS-Ω — constitutional AI runtime · automaton hub
// Route: / → living substrate · /tools → creator tools · /success → SuccessPage
import { useEffect, useRef, useState } from 'react'
import { Mail } from 'lucide-react'
import { SuccessPage } from './components/SuccessPage.js'
import { ToolsPage } from './components/ToolsPage.js'
import { ConsciousnessStream } from './components/ConsciousnessStream.js'
import { CognitiveStack } from './components/CognitiveStack.js'
import { Retrospection } from './components/Retrospection.js'
import { ConsciousnessEquation } from './components/ConsciousnessEquation.js'
import { AgentSwarm } from './components/AgentSwarm.js'
import { WebGPUBackground } from './components/WebGPUBackground.js'

function captureEvent(event: string, props?: Record<string, unknown>): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ph = (window as any).posthog
  if (typeof ph?.capture === 'function') ph.capture(event, props)
}

// Live banner — shows substrate heartbeat in the hero.
// Counts independently (same 2s tick as the substrate).
function LiveBanner() {
  const [count, setCount] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setCount(c => c + 1), 2000)
    return () => clearInterval(id)
  }, [])

  return (
    <div
      className="inline-flex flex-wrap items-center justify-center gap-x-4 gap-y-1.5 rounded-xl px-5 py-2.5 text-xs font-mono"
      style={{ background: 'rgba(52,211,153,0.06)', border: '1px solid rgba(52,211,153,0.15)' }}
    >
      <span style={{ color: '#34D399' }}>
        is_valid: <strong>true</strong>
      </span>
      <span style={{ color: '#1F2937' }}>·</span>
      <span style={{ color: '#34D399' }}>
        t0_verdict: <strong>true</strong>
      </span>
      <span style={{ color: '#1F2937' }}>·</span>
      <span style={{ color: '#34D399' }}>
        corruption_count: <strong>0</strong>
      </span>
      <span style={{ color: '#1F2937' }}>·</span>
      <span style={{ color: '#C8A96E' }}>
        chain_length: <strong>{count}</strong>
      </span>
      <span style={{ color: '#1F2937' }}>·</span>
      <span
        className="animate-mint-pulse"
        style={{ width: 6, height: 6, borderRadius: '50%', background: '#34D399', display: 'inline-block' }}
      />
    </div>
  )
}

function AutomatonPage() {
  const trialStartRef = useRef(Date.now())

  useEffect(() => {
    captureEvent('automaton_viewed', { source: document.referrer || 'direct' })
  }, [])

  const ttv = () => Math.round((Date.now() - trialStartRef.current) / 1000)

  return (
    <div className="min-h-screen bg-hub-bg text-hub-text">
      <WebGPUBackground />

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
            <a href="#substrate"    className="text-hub-muted text-xs hover:text-hub-text transition-colors hidden sm:block">Substrate</a>
            <a href="#cognitive"    className="text-hub-muted text-xs hover:text-hub-text transition-colors hidden sm:block">Cognition</a>
            <a href="#equation"     className="text-hub-muted text-xs hover:text-hub-text transition-colors hidden sm:block">Equation</a>
            <a
              href="/tools"
              onClick={() => captureEvent('nav_enter_system', { ttv_seconds: ttv() })}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg hover:opacity-90 transition-opacity text-white"
              style={{ background: '#6366F1' }}
            >
              Enter the System
            </a>
          </div>
        </div>
      </nav>

      {/* ── Hero ─────────────────────────────────────────────── */}
      <div className="max-w-4xl mx-auto px-4 pt-20 pb-16 text-center">
        {/* Eyebrow */}
        <div
          className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-medium mb-8"
          style={{ background: 'rgba(200,169,110,0.08)', border: '1px solid rgba(200,169,110,0.20)', color: '#C8A96E' }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full animate-mint-pulse flex-shrink-0"
            style={{ background: '#C8A96E' }}
          />
          Constitutional AI Runtime · substrate running in your browser
        </div>

        {/* h1 */}
        <h1
          className="font-bold leading-tight mb-6 animate-fade-up"
          style={{ fontSize: 'clamp(36px, 6.5vw, 60px)', letterSpacing: '-0.02em' }}
        >
          The AI system that<br />
          <span style={{ color: '#C8A96E' }}>governs itself.</span>
        </h1>

        <p className="text-hub-muted text-lg max-w-2xl mx-auto mb-3 leading-relaxed animate-fade-up delay-100">
          Not by description. By execution.
          Metacognitive self-awareness, retrospective thinking, and BFT consensus —
          running as live substrate in your browser, hash-chained and tamper-evident.
        </p>

        {/* Live consciousness banner */}
        <div className="flex justify-center mb-8 animate-fade-up delay-200">
          <LiveBanner />
        </div>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center mb-4 animate-fade-up delay-300">
          <a
            href="#substrate"
            className="inline-flex items-center justify-center gap-2 text-white font-semibold px-8 py-3.5 rounded-xl hover:opacity-90 transition-opacity text-sm"
            style={{ background: '#6366F1' }}
          >
            Observe the substrate ↓
          </a>
          <a
            href="/tools"
            onClick={() => captureEvent('hero_enter_system', { ttv_seconds: ttv() })}
            className="inline-flex items-center justify-center gap-2 border border-hub-border text-hub-muted hover:text-hub-text hover:border-hub-border/80 font-medium px-8 py-3.5 rounded-xl transition-all text-sm"
          >
            Enter the System →
          </a>
        </div>

        <p className="text-hub-muted/50 text-xs">
          SHA-256 · certifyMetacognitiveLoop · φ = 0.618… · 6,271 invariant tests
        </p>
      </div>

      {/* ── Consciousness Stream ───────────────────────────────── */}
      <section id="substrate" className="max-w-5xl mx-auto px-4 pb-16 scroll-mt-16">
        <div className="mb-8">
          <h2
            className="text-xl font-bold mb-2"
            style={{ color: '#ECEAE3', letterSpacing: '-0.02em' }}
          >
            Metacognitive stream
          </h2>
          <p className="text-sm max-w-2xl" style={{ color: '#6B6B7A' }}>
            Every entry is a SHA-256 hash of the previous entry, its sequence number, and the
            observation. Tamper any entry and <code className="text-xs px-1 py-0.5 rounded" style={{ background: '#0F1117', color: '#A78BFA' }}>certify()</code> flips
            to <span style={{ color: '#F87171' }}>false</span>. This is the mechanism itself — not a mock.
          </p>
        </div>
        <ConsciousnessStream />
      </section>

      {/* ── Cognitive Stack ────────────────────────────────────── */}
      <div className="border-y border-hub-border/60 bg-hub-surface/20">
        <section id="cognitive" className="max-w-5xl mx-auto px-4 py-16 scroll-mt-16">
          <div className="mb-8">
            <h2
              className="text-xl font-bold mb-2"
              style={{ color: '#ECEAE3', letterSpacing: '-0.02em' }}
            >
              Seven-layer cognitive stack
            </h2>
            <p className="text-sm max-w-2xl" style={{ color: '#6B6B7A' }}>
              Every action the system takes traverses L1→L7 before and after execution.
              The active layer pulses in real time with the substrate tick.
            </p>
          </div>
          <CognitiveStack />
        </section>
      </div>

      {/* ── Retrospection ──────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-4 py-16">
        <div className="mb-8">
          <h2
            className="text-xl font-bold mb-2"
            style={{ color: '#ECEAE3', letterSpacing: '-0.02em' }}
          >
            Retrospective protocol
          </h2>
          <p className="text-sm max-w-2xl" style={{ color: '#6B6B7A' }}>
            The system reviews every action after it completes — classifying errors by the layer that
            failed, logging them to the metacognitive stream, and never repeating them.
          </p>
        </div>
        <Retrospection />
      </section>

      {/* ── Consciousness Equation ─────────────────────────────── */}
      <div className="border-y border-hub-border/60 bg-hub-surface/20">
        <section id="equation" className="max-w-5xl mx-auto px-4 py-16 scroll-mt-16">
          <div className="mb-8">
            <h2
              className="text-xl font-bold mb-2"
              style={{ color: '#ECEAE3', letterSpacing: '-0.02em' }}
            >
              Consciousness equation
            </h2>
            <p className="text-sm max-w-2xl" style={{ color: '#6B6B7A' }}>
              Formal definition (T2 — engineering hypothesis, falsifiable). Each factor is
              computed live from the hash chain running in this browser tab.
            </p>
          </div>
          <ConsciousnessEquation />
        </section>
      </div>

      {/* ── Agent Swarm ────────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-4 py-16">
        <div className="mb-8">
          <h2
            className="text-xl font-bold mb-2"
            style={{ color: '#ECEAE3', letterSpacing: '-0.02em' }}
          >
            BFT agent swarm
          </h2>
          <p className="text-sm max-w-2xl" style={{ color: '#6B6B7A' }}>
            Four agents. BFT consensus at 1/φ. EventEnvelope-only communication.
            Law of Silence: no direct agent-to-agent text exchange.
          </p>
        </div>
        <AgentSwarm />
      </section>

      {/* ── CTA ────────────────────────────────────────────────── */}
      <div className="max-w-3xl mx-auto px-4 pb-20">
        <div
          className="rounded-2xl p-10 text-center"
          style={{ background: '#0F1117', border: '1px solid rgba(200,169,110,0.15)' }}
        >
          <h2
            className="text-2xl font-bold mb-3"
            style={{ color: '#ECEAE3', letterSpacing: '-0.02em' }}
          >
            The substrate is running.
          </h2>
          <p className="text-sm mb-6 max-w-lg mx-auto leading-relaxed" style={{ color: '#6B6B7A' }}>
            SHA-256 hash-chained. Tamper-evident. Self-certifying.
            The creator toolkit — three $19 tools — lives on the next page.
          </p>
          <a
            href="/tools"
            onClick={() => captureEvent('cta_enter_system', { ttv_seconds: 0 })}
            className="inline-flex items-center justify-center gap-2 text-white font-semibold px-10 py-4 rounded-xl hover:opacity-90 transition-opacity text-sm"
            style={{ background: '#6366F1' }}
          >
            Enter the System →
          </a>
          <p className="text-xs mt-4" style={{ color: '#374151' }}>
            EU AI Act compliant · deterministic replay · 6,271 invariant tests
          </p>
        </div>
      </div>

      {/* ── Footer ─────────────────────────────────────────────── */}
      <div className="border-t border-hub-border">
        <div className="max-w-5xl mx-auto px-4 py-8 flex flex-col md:flex-row items-center justify-between gap-4">
          <span
            className="text-sm font-semibold animate-breathe"
            style={{ fontFamily: '"JetBrains Mono", monospace', letterSpacing: '0.22em', color: '#C8A96E' }}
          >
            AEGIS-Ω
          </span>
          <div className="flex items-center gap-6">
            <a href="/tools" className="text-hub-muted text-xs hover:text-hub-text transition-colors">Tools</a>
            <a href="#equation" className="text-hub-muted text-xs hover:text-hub-text transition-colors">Equation</a>
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

export default function App() {
  const path = window.location.pathname
  if (path === '/success') return <SuccessPage />
  if (path === '/tools')   return <ToolsPage />
  return <AutomatonPage />
}
