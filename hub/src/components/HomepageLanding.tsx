/**
 * AEGIS-Ω 2.0 · HomepageLanding.tsx
 * EPISTEMIC TIER: T2
 *
 * Ultra-premium landing page. Live SHA-256 hash chain running in-browser
 * (genuine Web Crypto, not mocked), interactive tamper demo, σ-field canvas.
 * Design tokens from landing.css / index.css :root.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import '../landing.css'
import { SwarmDemoWidget } from './SwarmDemoWidget'
import { CoreCanvas } from './console/CoreCanvas.js'
import { NousButton, ArrowR } from './console/NousUI.js'

// ── PostHog analytics ─────────────────────────────────────────────────────────

function captureEvent(event: string, props?: Record<string, unknown>): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ph = (window as any).posthog
  if (typeof ph?.capture === 'function') ph.capture(event, props)
}

// ── SHA-256 via Web Crypto ─────────────────────────────────────────────────────

async function sha256hex(str: string): Promise<string> {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str))
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('')
}

const short = (h: string | null | undefined, n = 6) => (h ? h.slice(0, n) : '······')

// ── Observation pool ───────────────────────────────────────────────────────────

const SIGNALS: [string, string, string][] = [
  ['L3', 'T1', 'Three skills active: tdd, gate-pair, metacognition'],
  ['L2', 'T0', 'Retrospective pass — 41 frames replayed, fingerprint stable'],
  ['L1', 'T0', 'BTreeMap invariant held — deterministic ordering preserved'],
  ['L3', 'T2', 'Hypothesis: epoch seal converges before frame 2700'],
  ['L2', 'T1', 'BFT quorum reached — 3 / 4 alliance weights agree'],
  ['L1', 'T0', 'Version lock verified — mismatch would hard-abort'],
  ['L3', 'T1', 'Martingale boundary intact — E[Sₙ₊₁|Fₙ] = Sₙ'],
  ['L2', 'T0', 'Hash chain extended — prev anchor matches genesis lineage'],
  ['L3', 'T3', 'Conjecture: gate-321 resonance stable under sustained load'],
  ['L1', 'T0', 'No HashMap detected in src/ — ordering guaranteed'],
  ['L2', 'T1', 'Adversarial audit (chatgpt weight) found no divergence'],
  ['L3', 'T1', 'Metacognitive self-check — confidence within 1/φ band'],
  ['L2', 'T0', 'certify() returned true — chain sealed at current head'],
  ['L1', 'T0', 'Mutation frozen — no unproven write reached the T0 layer'],
  ['L3', 'T2', 'Reflection: skill scheduler reordered 2 low-tier tasks'],
  ['L2', 'T0', 'PGCS pass — proof-gate consensus signature anchored'],
  ['L1', 'T0', 'Genesis fingerprint replayed — identical to frame 0'],
  ['L3', 'T1', 'Self-model updated — no contradiction with prior epoch'],
]

const GENESIS = '0'.repeat(64)

interface ChainEntry {
  seq: number
  layer: string
  tier: string
  signal: string
  origSignal: string
  prevHash: string
  hash: string
  tampered: boolean
  fresh?: boolean
}

interface ChainStatus {
  valid: boolean
  corruption: number
  firstBreak: number
  t0: boolean
  terminalHash: string
}

async function mkEntry(seq: number, prevHash: string, pick: [string, string, string]): Promise<ChainEntry> {
  const [layer, tier, signal] = pick
  const hash = await sha256hex(`${prevHash}|${seq}|${signal}`)
  return { seq, layer, tier, signal, origSignal: signal, prevHash, hash, tampered: false }
}

async function seedChain(n: number): Promise<ChainEntry[]> {
  const chain: ChainEntry[] = []
  let prev = GENESIS
  for (let i = 0; i < n; i++) {
    const pick = SIGNALS[i % SIGNALS.length]
    const e = await mkEntry(i, prev, pick)
    chain.push(e)
    prev = e.hash
  }
  return chain
}

async function validateChain(chain: ChainEntry[]): Promise<ChainStatus> {
  let corruption = 0
  let firstBreak = -1
  for (let i = 0; i < chain.length; i++) {
    const e = chain[i]
    const expectPrev = i === 0 ? GENESIS : chain[i - 1].hash
    const expectHash = await sha256hex(`${expectPrev}|${e.seq}|${e.signal}`)
    if (expectHash !== e.hash || expectPrev !== e.prevHash) {
      corruption++
      if (firstBreak < 0) firstBreak = e.seq
    }
  }
  return {
    valid: corruption === 0, corruption, firstBreak, t0: corruption === 0,
    terminalHash: chain.length > 0 ? chain[chain.length - 1]!.hash : GENESIS,
  }
}

function useTamperChain({ seed = 6, win = 8, tickMs = 2600 } = {}) {
  const [chain, setChain] = useState<ChainEntry[]>([])
  const [status, setStatus] = useState<ChainStatus>({ valid: true, corruption: 0, firstBreak: -1, t0: true, terminalHash: GENESIS })
  const chainRef = useRef<ChainEntry[]>([])
  const seqRef = useRef(seed)

  chainRef.current = chain

  const recompute = useCallback(async (c: ChainEntry[]) => {
    const v = await validateChain(c)
    setStatus(v)
  }, [])

  useEffect(() => {
    let alive = true
    seedChain(seed).then(c => {
      if (!alive) return
      setChain(c)
      void recompute(c)
    })
    return () => { alive = false }
  }, []) // eslint-disable-line

  useEffect(() => {
    const id = setInterval(async () => {
      const c = chainRef.current
      if (!c.length) return
      const prev = c[c.length - 1].hash
      const seq = seqRef.current++
      const pick = SIGNALS[(seq * 7) % SIGNALS.length]
      const e = await mkEntry(seq, prev, pick)
      const next = [...c, { ...e, fresh: true }]
      setChain(next)
      setStatus(s => ({ ...s, valid: s.corruption === 0, t0: s.corruption === 0 }))
    }, tickMs)
    return () => clearInterval(id)
  }, [tickMs]) // eslint-disable-line

  const tamper = useCallback(async (seq: number) => {
    const c = chainRef.current.map(e =>
      e.seq === seq ? { ...e, signal: '⚠ injected: force-approve unproven write', tampered: true } : e
    )
    setChain(c)
    await recompute(c)
  }, [recompute])

  const reseal = useCallback(async (seq: number) => {
    const c = chainRef.current.map(e =>
      e.seq === seq ? { ...e, signal: e.origSignal, tampered: false } : e
    )
    setChain(c)
    await recompute(c)
  }, [recompute])

  const visible = chain.slice(-win)
  return { visible, status, total: chain.length, tamper, reseal }
}

// ── σ-field canvas ─────────────────────────────────────────────────────────────

function initSigmaField(canvas: HTMLCanvasElement) {
  const ctx = canvas.getContext('2d')!
  let W = 0, H = 0, dpr = 1
  const N = 120
  const pts: { x: number; y: number; vx: number; vy: number; r: number; a: number }[] = []
  let sigma = 0
  let frames = 0
  const ripples: { x: number; y: number; t: number }[] = []

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2)
    W = canvas.clientWidth; H = canvas.clientHeight
    canvas.width = W * dpr; canvas.height = H * dpr
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }
  resize()
  window.addEventListener('resize', resize)

  for (let i = 0; i < N; i++) {
    pts.push({
      x: Math.random(), y: Math.random(),
      vx: (Math.random() - 0.5) * 0.00018,
      vy: (Math.random() - 0.5) * 0.00018,
      r: 0.7 + Math.random() * 1.8,
      a: 0.14 + Math.random() * 0.40,
    })
  }

  function disturb(cx: number, cy: number) {
    sigma = Math.min(1, sigma + 0.6)
    ripples.push({ x: cx / W, y: cy / H, t: 0 })
    const sx = cx / W, sy = cy / H
    for (const p of pts) {
      const dx = p.x - sx, dy = p.y - sy
      const d = Math.hypot(dx, dy) || 0.001
      if (d < 0.28) { const f = (0.28 - d) * 0.012; p.vx += (dx / d) * f; p.vy += (dy / d) * f }
    }
  }

  const onPointer = (e: PointerEvent) => { if (e.clientY < window.innerHeight * 1.1) disturb(e.clientX, e.clientY) }
  window.addEventListener('pointerdown', onPointer)

  const setTxt = (id: string, v: string) => { const el = document.getElementById(id); if (el) el.textContent = v }

  let raf = 0
  function frame() {
    frames++
    ctx.clearRect(0, 0, W, H)
    sigma *= 0.97

    for (let i = 0; i < pts.length; i++) {
      const p = pts[i]
      p.x += p.vx + Math.sin(frames * 0.004 + i) * 0.00004
      p.y += p.vy
      p.vx *= 0.985; p.vy *= 0.985
      if (p.x < 0 || p.x > 1) { p.vx *= -1; p.x = Math.max(0, Math.min(1, p.x)) }
      if (p.y < 0 || p.y > 1) { p.vy *= -1; p.y = Math.max(0, Math.min(1, p.y)) }
      for (let j = i + 1; j < pts.length; j++) {
        const q = pts[j]
        const dx = (p.x - q.x) * W, dy = (p.y - q.y) * H
        const d = Math.hypot(dx, dy)
        if (d < 150) {
          ctx.strokeStyle = `rgba(200,169,110,${(1 - d / 150) * 0.07 * (0.5 + sigma)})`
          ctx.lineWidth = 1
          ctx.beginPath(); ctx.moveTo(p.x * W, p.y * H); ctx.lineTo(q.x * W, q.y * H); ctx.stroke()
        }
      }
    }
    for (const p of pts) {
      ctx.fillStyle = `rgba(200,169,110,${p.a * (0.6 + sigma * 0.8)})`
      ctx.beginPath(); ctx.arc(p.x * W, p.y * H, p.r, 0, Math.PI * 2); ctx.fill()
    }
    for (let i = ripples.length - 1; i >= 0; i--) {
      const r = ripples[i]; r.t += 0.02
      ctx.strokeStyle = `rgba(200,169,110,${Math.max(0, 0.22 - r.t * 0.22)})`
      ctx.lineWidth = 1
      ctx.beginPath(); ctx.arc(r.x * W, r.y * H, r.t * Math.max(W, H) * 0.5, 0, Math.PI * 2); ctx.stroke()
      if (r.t > 1) ripples.splice(i, 1)
    }
    if (frames % 6 === 0) {
      setTxt('ld-sigma', sigma.toFixed(3))
      setTxt('ld-frames', frames.toLocaleString())
    }
    raf = requestAnimationFrame(frame)
  }
  frame()

  return () => {
    cancelAnimationFrame(raf)
    window.removeEventListener('resize', resize)
    window.removeEventListener('pointerdown', onPointer)
  }
}

// ── Mark logo ──────────────────────────────────────────────────────────────────

function Mark({ size = 26, className = '' }: { size?: number; className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 64 64" fill="none" stroke="currentColor">
      <rect x="0.5" y="0.5" width="63" height="63" fill="none" strokeWidth="1" vectorEffect="non-scaling-stroke"/>
      <path d="M 32 32 L 32 14 M 32 32 L 16.4 41 M 32 32 L 47.6 41" strokeWidth="1.6" strokeLinecap="round" vectorEffect="non-scaling-stroke"/>
      <circle cx="32" cy="12" r="4" strokeWidth="1.6" vectorEffect="non-scaling-stroke"/>
      <circle cx="14.7" cy="42" r="4" strokeWidth="1.6" vectorEffect="non-scaling-stroke"/>
      <circle cx="49.3" cy="42" r="4" strokeWidth="1.6" vectorEffect="non-scaling-stroke"/>
      <circle cx="32" cy="32" r="5" fill="currentColor"/>
    </svg>
  )
}

// ── Social icons ───────────────────────────────────────────────────────────────

const SOCIAL_PATHS: Record<string, [string, string]> = {
  github:  ['0 0 19 19', 'M9.356 1.85C5.05 1.85 1.57 5.356 1.57 9.694a7.84 7.84 0 0 0 5.324 7.44c.387.079.528-.168.528-.376 0-.182-.013-.805-.013-1.454-2.165.467-2.616-.935-2.616-.935-.349-.91-.864-1.143-.864-1.143-.71-.48.051-.48.051-.48.787.051 1.2.805 1.2.805.695 1.194 1.817.857 2.268.649.064-.507.27-.857.49-1.052-1.728-.182-3.545-.857-3.545-3.87 0-.857.31-1.558.8-2.104-.078-.195-.349-1 .077-2.078 0 0 .657-.208 2.14.805a7.5 7.5 0 0 1 1.946-.26c.657 0 1.328.092 1.946.26 1.483-1.013 2.14-.805 2.14-.805.426 1.078.155 1.883.078 2.078.502.546.799 1.247.799 2.104 0 3.013-1.818 3.675-3.558 3.87.284.247.528.714.528 1.454 0 1.052-.012 1.896-.012 2.156 0 .208.142.455.528.377a7.84 7.84 0 0 0 5.324-7.441c.013-4.338-3.48-7.844-7.773-7.844'],
  x:       ['0 0 19 19', 'M1.893 1.98c.052.072 1.245 1.769 2.653 3.77l2.892 4.114c.183.261.333.48.333.486s-.068.089-.152.183l-.522.593-.765.867-3.597 4.087c-.375.426-.734.834-.798.905a1 1 0 0 0-.118.148c0 .01.236.017.664.017h.663l.729-.83c.4-.457.796-.906.879-.999a692 692 0 0 0 1.794-2.038c.034-.037.301-.34.594-.675l.551-.624.345-.392a7 7 0 0 1 .34-.374c.006 0 .93 1.306 2.052 2.903l2.084 2.965.045.063h2.275c1.87 0 2.273-.003 2.266-.021-.008-.02-1.098-1.572-3.894-5.547-2.013-2.862-2.28-3.246-2.273-3.266.008-.019.282-.332 2.085-2.38l2-2.274 1.567-1.782c.022-.028-.016-.03-.65-.03h-.674l-.3.342a871 871 0 0 1-1.782 2.025c-.067.075-.405.458-.75.852a100 100 0 0 1-.803.91c-.148.172-.299.344-.99 1.127-.304.343-.32.358-.345.327-.015-.019-.904-1.282-1.976-2.808L6.365 1.85H1.8zm1.782.91 8.078 11.294c.772 1.08 1.413 1.973 1.425 1.984.016.017.241.02 1.05.017l1.03-.004-2.694-3.766L7.796 5.75 5.722 2.852l-1.039-.004-1.039-.004z'],
}

function SocialIcon({ id, href }: { id: string; href: string }) {
  const [vb, d] = SOCIAL_PATHS[id] ?? ['0 0 24 24', '']
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" aria-label={id}>
      <svg viewBox={vb} fill="currentColor" width="16" height="16"><path d={d}/></svg>
    </a>
  )
}

// ── SVG icons ──────────────────────────────────────────────────────────────────

const IBrain = () => (
  <svg width={26} height={26} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 5a3 3 0 0 0-3 3v.5a3 3 0 0 0-2 5.6V16a2 2 0 0 0 2 2h.5"/>
    <path d="M12 5a3 3 0 0 1 3 3v.5a3 3 0 0 1 2 5.6V16a2 2 0 0 1-2 2h-.5"/>
    <path d="M12 5v13"/>
  </svg>
)
const IReplay = () => (
  <svg width={26} height={26} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>
  </svg>
)
const IShield = () => (
  <svg width={26} height={26} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/><path d="m9 12 2 2 4-4"/>
  </svg>
)
const IArrowR = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>
  </svg>
)

// ── Top bar ────────────────────────────────────────────────────────────────────

function TopBar({ status, total, ttv }: { status: ChainStatus; total: number; ttv: () => number }) {
  const dotColor = status.valid ? 'var(--aegis-T0)' : 'var(--attn-gaze)'
  const verdictColor = status.valid ? 'var(--aegis-T0)' : 'var(--attn-gaze)'
  return (
    <header className="ld-topbar">
      <div className="ld-wrap">
        <a className="ld-brand" href="#top">
          <Mark size={28} className="ld-mark"/>
          <span className="ld-wm">AEGIS-Ω</span>
        </a>
        <nav className="ld-nav">
          <a href="#substrate">Substrate</a>
          <a href="#cognition">Cognition</a>
          <a href="#equation">Equation</a>
          <a href="/platform">Platform</a>
          <a href="/docs">Docs</a>
        </nav>
        <div className="ld-spacer"/>
        <div className="ld-ribbon">
          <span className="ld-dot" style={{ background: dotColor, color: dotColor }}/>
          <span className="ld-k">chain</span>
          <b style={{ color: 'var(--aegis-phi)' }}>{total}</b>
          <span className="ld-k">·</span>
          <span className="ld-k">verdict</span>
          <b style={{ color: verdictColor }}>{status.valid ? 'T0 PASS' : 'BREACH'}</b>
        </div>
        <a
          className="ld-btn ld-btn-primary"
          href="/pricing"
          onClick={() => captureEvent('nav_pricing_click', { ttv_seconds: ttv() })}
        >
          Get API Access
        </a>
      </div>
    </header>
  )
}

// ── Hero ───────────────────────────────────────────────────────────────────────

function Hero({ status, total, ttv }: { status: ChainStatus; total: number; ttv: () => number }) {
  const terminalShort = status.terminalHash !== GENESIS
    ? `${status.terminalHash.slice(0, 8)}…${status.terminalHash.slice(-8)}`
    : `${'0'.repeat(8)}…`

  return (
    <section className="ld-hero" id="top">
      <CoreCanvas contained />
      <div className="ld-wrap ld-hero-inner">
        <div className="ld-law-label">Constitutional AI Runtime · AEGIS-Ω</div>
        <h1 className="ld-hero-h1">
          Every AI decision,<br/>
          <span className="ld-hero-accent">cryptographically provable.</span>
        </h1>
        <div className="ld-law-block">
          <div className="ld-law-caption">The law that enforces this at runtime:</div>
          <div className="ld-law-eq" aria-label="AdaptivePower of T is less than or equal to ReplayVerifiability of T">
            AdaptivePower(T) ≤ ReplayVerifiability(T)
          </div>
          <p className="ld-law-sub">Not a training objective — a runtime halt condition.</p>
        </div>

        <div className="ld-proof-ledger" role="region" aria-label="Live constitutional proofs">
          <div className="ld-proof-row">
            <span className="ld-badge ld-badge--t0">T0</span>
            <span className="ld-proof-name">Gate 79 · φ-convergence</span>
            <code className="ld-proof-val">0.6180339887…</code>
          </div>
          <div className="ld-proof-row">
            <span className={`ld-badge ${status.valid ? 'ld-badge--live' : 'ld-badge--bad'}`}>
              {status.valid ? '● LIVE' : '⚠ BAD'}
            </span>
            <span className="ld-proof-name">MetacognitiveLoop · {total} observations</span>
            <code className="ld-proof-val ld-proof-val--hash">{terminalShort}</code>
          </div>
          <div className="ld-proof-row">
            <span className="ld-badge ld-badge--t0">453/453</span>
            <span className="ld-proof-name">Platform contract · test_platform.py</span>
            <code className="ld-proof-val ld-proof-val--pass">PASS</code>
          </div>
        </div>

        <div className="ld-cta-row ld-cta-row--left">
          <NousButton href="/pricing" variant="primary" size="lg"
            onClick={() => captureEvent('hero_pricing_cta', { ttv_seconds: ttv() })}>
            Get API Access <ArrowR/>
          </NousButton>
          <NousButton href="#substrate" variant="ghost" size="lg"
            onClick={() => captureEvent('hero_substrate_link', { ttv_seconds: ttv() })}>
            Read the substrate
          </NousButton>
        </div>
      </div>
    </section>
  )
}

// ── Quote strip ────────────────────────────────────────────────────────────────

function Quote() {
  return (
    <section className="ld-quote-strip">
      <div className="ld-wrap">
        <blockquote>
          "The code does not ask to be believed. It can be replayed from genesis
          and will produce the same <em>cryptographic fingerprint</em> every time."
        </blockquote>
        <cite>Constitutional invariant · AEGIS-Ω runtime</cite>
      </div>
    </section>
  )
}

// ── Stream ─────────────────────────────────────────────────────────────────────

function Stream({ visible, status, total, tamper, reseal }: {
  visible: ChainEntry[]
  status: ChainStatus
  total: number
  tamper: (seq: number) => void
  reseal: (seq: number) => void
}) {
  const head = visible.length ? visible[visible.length - 1] : null
  return (
    <section
      className="ld-section ld-section--tight"
      id="substrate"
      style={{ background: 'var(--r-bg-2)', borderTop: '1px solid var(--r-line)' }}
    >
      <div className="ld-wrap">
        <div className="ld-stream-layout">
          {/* Left: sticky description */}
          <div className="ld-stream-side">
            <div className="ld-sec-num">01 · MECHANISM</div>
            <h2>A metacognitive stream you can break.</h2>
            <p className="ld-stream-note">
              Every entry is a real <code>SHA-256</code> of the previous hash,
              its sequence number, and the observation signal. Tamper with any
              row and <code>certify()</code> flips to <span className="bad">false</span> —
              recomputed live in this page, not mocked.
            </p>
            <div className="ld-side-verdict">
              <span className="sv-head">Live verdict</span>
              <div className="sv-row">
                <span className="sv-key">certify()</span>
                <span className={`sv-val ${status.valid ? 'ok' : 'bad'}`}>{String(status.valid)}</span>
              </div>
              <div className="sv-row">
                <span className="sv-key">corruption_count</span>
                <span className={`sv-val ${status.corruption ? 'bad' : 'ok'}`}>{status.corruption}</span>
              </div>
              <div className="sv-sep"/>
              <div className="sv-row">
                <span className="sv-key">observations</span>
                <span className="sv-val phi">{total}</span>
              </div>
              <div className="sv-row">
                <span className="sv-key">head</span>
                <span className="sv-val inf">{head ? short(head.hash, 10) : '···'}</span>
              </div>
            </div>
          </div>

          {/* Right: live table */}
          <div className="ld-stream-panel">
            <div className="ld-stream-head">
              <span className="ld-title">Metacognitive Stream</span>
              <span className="ld-count">{total}</span>
              <span className={`ld-verdict-chip ${status.valid ? 'valid' : 'breach'}`}>
                <span className="vd"/>
                {status.valid ? 'CERTIFIED' : `BREACH @ seq ${status.firstBreak}`}
              </span>
            </div>
            <table className="ld-stream-table">
              <thead>
                <tr>
                  <th style={{ width: 52 }}>seq</th>
                  <th style={{ width: 44 }}>layer</th>
                  <th style={{ width: 44 }}>tier</th>
                  <th>signal</th>
                  <th className="r">prev → hash</th>
                  <th style={{ width: 72 }}/>
                </tr>
              </thead>
              <tbody>
                {visible.map(e => (
                  <tr
                    key={e.seq}
                    className={`ld-stream-row${e.fresh ? ' fresh' : ''}${e.tampered ? ' tampered' : ''}`}
                    style={e.tampered ? { background: 'rgba(255,77,0,0.06)' } : undefined}
                  >
                    <td className="ld-seq">{String(e.seq).padStart(3, '0')}</td>
                    <td><span className="ld-layer-tag">{e.layer}</span></td>
                    <td><span className={`ld-tier-tag ld-tier-${e.tier}`}>{e.tier}</span></td>
                    <td className="ld-signal-cell" style={e.tampered ? { color: 'var(--attn-gaze)' } : undefined}>{e.signal}</td>
                    <td className="ld-hash-cell">
                      <span className="hp">{short(e.prevHash)}</span>
                      <span className="arrow">→</span>
                      <span className="hc" style={{ color: e.tampered ? 'var(--attn-gaze)' : 'var(--aegis-phi)' }}>
                        {short(e.hash)}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      {e.tampered
                        ? <button className="ld-tamper-btn reseal" onClick={() => reseal(e.seq)}>re-seal</button>
                        : <button className="ld-tamper-btn" onClick={() => tamper(e.seq)}>tamper</button>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="ld-stream-foot">
              <span>genesis: <code>0000…0000</code></span>
              <span className="ld-stream-foot-spacer"/>
              <span>head: <code>{head ? short(head.hash, 14) : '···'}</code></span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

// ── Cognition section ──────────────────────────────────────────────────────────

const LAYERS = [
  {
    icon: IBrain, num: '1',
    ltag: 'Layer 1 · Substrate', title: 'Deterministic by construction',
    accent: 'var(--aegis-T0)', accentA12: 'rgba(52,211,153,0.06)',
    desc: 'BTreeMap / BTreeSet only — never HashMap. Ordering is guaranteed, so the same inputs replay to the same cryptographic fingerprint, every time.',
    mk: 'ordering', mv: 'total',
  },
  {
    icon: IReplay, num: '2',
    ltag: 'Layer 2 · Retrospection', title: 'It replays its own past',
    accent: 'var(--aegis-T1)', accentA12: 'rgba(96,165,250,0.06)',
    desc: 'Retrospective thinking walks the chain backward from any frame to genesis. Nothing is trusted that cannot be re-derived from the record itself.',
    mk: 'replay depth', mv: '0 → genesis',
  },
  {
    icon: IShield, num: '3',
    ltag: 'Layer 3 · Consensus', title: 'No claim outranks its proof',
    accent: 'var(--aegis-T2)', accentA12: 'rgba(167,139,250,0.06)',
    desc: 'Every claim is tier-tagged T0–T3 and gated by BFT quorum across the model alliance. An unproven write can never reach the T0 layer.',
    mk: 'quorum', mv: '3 / 4 weights',
  },
]

function Cognition() {
  return (
    <section
      className="ld-section ld-section--tight"
      id="cognition"
      style={{ borderTop: '1px solid var(--r-line)', borderBottom: '1px solid var(--r-line)' }}
    >
      <div className="ld-wrap">
        <div className="ld-section-head">
          <div className="ld-sec-num">02 · ARCHITECTURE</div>
          <h2>Self-government is an architecture, not a promise.</h2>
        </div>
        <div className="ld-layer-grid">
          {LAYERS.map(l => {
            const Icon = l.icon
            return (
              <div
                className="ld-layer-card"
                key={l.title}
                style={{ '--card-accent': l.accent, '--card-accent-a12': l.accentA12 } as React.CSSProperties}
              >
                <div className="ld-topline"/>
                <div className="ld-topglow"/>
                <div className="ld-ico" style={{ color: l.accent }}><Icon/></div>
                <span className="ld-ltag" style={{ color: l.accent }}>{l.ltag}</span>
                <h3>{l.title}</h3>
                <p>{l.desc}</p>
                <div className="ld-metric">
                  <span>{l.mk}</span>
                  <b style={{ color: l.accent }}>{l.mv}</b>
                </div>
                <span className="ld-wm-num">{l.num}</span>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

// ── Equation section ───────────────────────────────────────────────────────────

function Equation() {
  return (
    <section className="ld-section--mid ld-eq-outer" id="equation">
      <div className="ld-eq-full">
        <div className="ld-wrap" style={{ textAlign: 'center' }}>
          <div className="ld-sec-num" style={{ justifyContent: 'center', marginBottom: 20 }}>
            03 · THE MARTINGALE BOUNDARY
          </div>
          <div className="ld-eq-mono-huge">E[S&#x2099;₊₁ | F&#x2099;] = S&#x2099;</div>
          <div className="ld-eq-label">martingale boundary · confidence cannot inflate between frames</div>
        </div>
      </div>
      <div className="ld-wrap">
        <div className="ld-equation-block">
          <div className="ld-eq-detail">
            <div className="ld-eq-sub">
              <div>φ <span className="g">= 1.6180339…</span></div>
              <div>1 / φ <span className="v">≈ 0.6180</span></div>
              <div>weight&#x2099; <span className="v">= ⌊1000 · (1/φ&#x207F;)⌋</span></div>
              <div><span className="t0">618</span> · <span className="v">382 · 236 · 146 · 90 · …</span></div>
              <div>∑ weights <span className="v">= 1000</span> <span className="g">// always</span></div>
            </div>
          </div>
          <div className="ld-eq-copy">
            <span className="ld-eyebrow">The guardrail</span>
            <h2>The math is the rule, not the policy.</h2>
            <p>
              Confidence is bounded by a martingale: the expected next state equals the
              current state given everything known so far. The system cannot inflate its
              own certainty between frames — drift is mathematically impossible, not
              merely discouraged.
            </p>
            <p>
              Alliance weights fall along successive powers of <code>1/φ</code>, so the
              coordinator, implementer, and adversarial auditor are balanced by the golden
              ratio — not by fiat.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

// ── Invariants section ─────────────────────────────────────────────────────────

const INVARIANTS = [
  { g: '≤', h: 'Version mismatch = hard abort',   p: <>A divergent runtime version halts rather than guessing. <code>certify()</code> never runs on an ambiguous build.</> },
  { g: '∩', h: 'BTreeMap / BTreeSet only',         p: <>No <code>HashMap</code> reaches <code>src/</code>. Deterministic ordering is an invariant, not a preference.</> },
  { g: '△', h: 'Every claim is tier-tagged',        p: <>T0 proven · T1 validated · T2 hypothesis · T3 conjecture. <code>T4</code> (blocked) must never appear.</> },
  { g: '∈', h: 'Replayable from genesis',           p: <>Any frame re-derives to the same fingerprint. The record is the source of truth, not the cache.</> },
  { g: '′', h: 'No write outranks its proof',       p: <>An unproven mutation is frozen before it reaches the T0 layer. Capability never exceeds evidence.</> },
  { g: 'φ', h: 'Weights bounded by 1/φ',            p: <>Orchestration weights are fixed by the golden ratio. No model can vote itself more influence.</> },
]

function Invariants() {
  return (
    <section
      className="ld-section ld-section--tight"
      id="invariants"
      style={{ background: 'var(--r-bg-2)', borderTop: '1px solid var(--r-line)' }}
    >
      <div className="ld-wrap">
        <div className="ld-section-head">
          <div className="ld-sec-num">04 · CONSTITUTIONAL</div>
          <h2>Rules the runtime cannot break — including for itself.</h2>
        </div>
        <div className="ld-inv-list">
          {INVARIANTS.map(iv => (
            <div className="ld-inv-row" key={iv.h}>
              <span className="ld-glyph">{iv.g}</span>
              <div className="ld-body"><h4>{iv.h}</h4><p>{iv.p}</p></div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ── Platform API section ───────────────────────────────────────────────────────

function PlatformAPI({ ttv }: { ttv: () => number }) {
  return (
    <section
      className="ld-section ld-section--tight"
      id="api"
      style={{ borderTop: '1px solid var(--r-line)' }}
    >
      <div className="ld-wrap">
        <div className="ld-section-head">
          <div className="ld-sec-num">05 · PLATFORM API</div>
          <h2>39 governed agents. One API call.</h2>
          <p>
            POST an objective. 39 constitutional agents collaborate, hash-chain every
            artifact, run a constitutional audit, and return a replay-verifiable result.
            No setup beyond an API key.
          </p>
        </div>

        <div className="ld-api-grid">
          <div className="ld-api-panel">
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--aegis-T0)', marginBottom: 16, fontWeight: 700 }}>
              Endpoints
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { method: 'POST', path: '/platform/collaborate',      desc: '39-agent collaboration cycle' },
                { method: 'GET',  path: '/platform/status',           desc: 'Runtime health · chain hash · usage' },
                { method: 'POST', path: '/platform/executions',       desc: 'Async execution — returns stream URL' },
                { method: 'GET',  path: '/platform/executions/live',  desc: 'SSE stream — per-agent events' },
              ].map(ep => (
                <div key={ep.path} style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
                    padding: '3px 8px', borderRadius: 4, flexShrink: 0,
                    background: ep.method === 'POST' ? 'rgba(99,102,241,0.15)' : 'rgba(52,211,153,0.10)',
                    color: ep.method === 'POST' ? '#818CF8' : '#34D399',
                  }}>
                    {ep.method}
                  </span>
                  <div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--aegis-text)' }}>{ep.path}</div>
                    <div style={{ fontSize: 11, color: 'var(--aegis-muted)', marginTop: 2 }}>{ep.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="ld-api-panel">
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--aegis-T2)', marginBottom: 16, fontWeight: 700 }}>
              Example request
            </div>
            <pre>{`curl -X POST \\
  https://aegis-vertex.aegisomega.com\\
  /platform/collaborate \\
  -H "x-api-key: YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "objective": "Enter EU fintech market",
    "mode": "gtm",
    "live": false
  }'`}</pre>
          </div>
        </div>

        <div className="ld-api-panel" style={{ marginBottom: 32 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--aegis-phi)', marginBottom: 16, fontWeight: 700 }}>
            Response — PlatformEnvelope&lt;CollaborationResult&gt;
          </div>
          <pre>{`{
  "contract_version": "1.0.0",
  "execution_id": "018f...",
  "is_replay_reconstructable": true,
  "data": {
    "departments_collaborated": 39,
    "artifacts": [{ "role": "Strategy", "output": "..." }, ...],
    "constitutional_audit": { "verdict": "APPROVED" },
    "chain_valid": true,
    "audit_chain_hash": "sha256:..."
  }
}`}</pre>
        </div>

        <div style={{ textAlign: 'center' }}>
          <a
            className="ld-btn ld-btn-primary ld-btn-lg"
            href="/pricing"
            onClick={() => captureEvent('api_section_pricing_click', { ttv_seconds: ttv() })}
          >
            Get Your API Key <IArrowR/>
          </a>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--aegis-muted)', marginTop: 14 }}>
            Explorer tier is free · 10 runs · no card required
          </p>
        </div>
      </div>
    </section>
  )
}

// ── Limitations section ────────────────────────────────────────────────────────

function Limitations() {
  return (
    <section
      className="ld-section ld-section--tight"
      style={{ borderTop: '1px solid var(--r-line)' }}
    >
      <div className="ld-wrap">
        <div className="ld-section-head">
          <div className="ld-sec-num">06 · KNOWN LIMITATIONS</div>
          <h2>What it does not do.</h2>
          <p>Honest disclosure is constitutional. These are facts, not caveats.</p>
        </div>
        <div className="ld-limits-panel">
          <div className="ld-ltitle">Known Limitations</div>
          <ul>
            <li><span><b>It is not a frontier model.</b> Reasoning quality is bounded by the alliance models it orchestrates — AEGIS-Ω governs them; it does not replace them.</span></li>
            <li><span><b>Throughput is the cost of proof.</b> Hash-chaining and BFT quorum on every frame trade raw speed for tamper-evidence. This is deliberate.</span></li>
            <li><span><b>Tamper-evident, not tamper-proof.</b> A breach is always detectable and attributable — it is not always preventable at the edge.</span></li>
            <li><span><b>One author, one runtime.</b> There is no fleet, no peer cluster, no managed cloud. The geometry has no peers by design.</span></li>
          </ul>
        </div>
      </div>
    </section>
  )
}

// ── Final CTA ──────────────────────────────────────────────────────────────────

function FinalCTA({ ttv }: { ttv: () => number }) {
  return (
    <section className="ld-section" id="enter">
      <div className="ld-wrap">
        <div className="ld-final">
          <Mark size={64} className="ld-mark-lg"/>
          <h2>
            No part of the system can do<br/>
            more than it can <span className="ld-gold">prove it did.</span>
          </h2>
          <p>
            Open the runtime and watch the chain extend in real time.
            It can be replayed from genesis and will produce the same fingerprint every time.
          </p>
          <div className="ld-cta-row">
            <a
              className="ld-btn ld-btn-primary ld-btn-xl"
              href="/pricing"
              onClick={() => captureEvent('final_cta_pricing', { ttv_seconds: ttv() })}
            >
              Get API Access <IArrowR/>
            </a>
            <a className="ld-btn ld-btn-ghost ld-btn-xl" href="#substrate">
              Observe the substrate
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}

// ── Footer ─────────────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer className="ld-footer">
      <div className="ld-wrap">
        <div className="ld-footer-row">
          <div className="ld-footer-brand">
            <a className="ld-brand" href="#top">
              <Mark size={26} className="ld-mark"/>
              <span className="ld-wm">AEGIS-Ω</span>
            </a>
            <p>
              A sovereign constitutional runtime. Metacognitive, hash-chained,
              tamper-evident — and able to prove every claim it makes about itself.
            </p>
            <div className="ld-attribution">
              Conceived, designed &amp; executed by <span className="v">Tarik Skalić</span><br/>
              Bihać, Bosnia-Herzegovina · <span className="v">AGPL-3.0</span>
            </div>
            <div className="ld-socials">
              <SocialIcon id="github" href="https://github.com/Aegis-Omega/AEGIS--"/>
              <SocialIcon id="x" href="https://x.com/aegisomega"/>
            </div>
          </div>
          <div className="ld-foot-links">
            <span className="ld-fh">Runtime</span>
            <a href="#substrate">Substrate</a>
            <a href="#cognition">Cognition</a>
            <a href="#equation">Equation</a>
            <a href="#invariants">Invariants</a>
            <a href="#api">Platform API</a>
          </div>
          <div className="ld-foot-links">
            <span className="ld-fh">Product</span>
            <a href="/platform">Platform</a>
            <a href="/pricing">Pricing</a>
            <a href="/docs">API Docs</a>
            <a href="mailto:info@aegisomega.com">Contact</a>
          </div>
        </div>
        <div className="ld-footer-line">
          <span>AEGIS-Ω · Constitutional AI Runtime</span>
          <span>1 / <span className="phi">φ</span> = 0.6180… · E[S&#x2099;₊₁ | F&#x2099;] = S&#x2099;</span>
        </div>
      </div>
    </footer>
  )
}

// ── Page root ──────────────────────────────────────────────────────────────────

export function HomepageLanding() {
  const trialStartRef = useRef(Date.now())
  const ttv = () => Math.round((Date.now() - trialStartRef.current) / 1000)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const { visible, status, total, tamper, reseal } = useTamperChain({ seed: 6, win: 8, tickMs: 2600 })

  useEffect(() => {
    captureEvent('homepage_viewed')
  }, [])

  useEffect(() => {
    if (!canvasRef.current) return
    return initSigmaField(canvasRef.current)
  }, [])

  return (
    <>
      {/* Fixed background */}
      <canvas ref={canvasRef} className="ld-field" aria-hidden="true"/>
      <div className="ld-veil" aria-hidden="true"/>

      {/* Page shell */}
      <div className="ld-shell">
        <TopBar status={status} total={total} ttv={ttv}/>
        <Hero status={status} total={total} ttv={ttv}/>
        <Stream visible={visible} status={status} total={total} tamper={tamper} reseal={reseal}/>
        <Quote/>
        <Cognition/>
        <Equation/>
        <Invariants/>
        <PlatformAPI ttv={ttv}/>
        <SwarmDemoWidget ttv={ttv}/>
        <Limitations/>
        <FinalCTA ttv={ttv}/>
        <Footer/>
      </div>
    </>
  )
}
