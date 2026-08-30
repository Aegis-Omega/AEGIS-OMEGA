// AEGIS-Ω 2.0 — AegisRuntime: constitutional runtime landing page.
// Implements the design handoff pixel-perfect:
//   TopBar → Hero (σ-field) → Stream (tamper demo) → Quote →
//   Cognition → Equation → Invariants → Limitations → FinalCTA → Footer
import { useEffect, useRef, useState, type MutableRefObject, type CSSProperties } from 'react'
import '../runtime.css'
import { useChain, short, type ChainStatus } from '../lib/useChain.js'

/* ---- AEGIS mark (inline SVG, currentColor) ---- */
function Mark({ size = 26, cls = '' }: { size?: number; cls?: string }) {
  return (
    <svg className={cls} width={size} height={size} viewBox="0 0 64 64" fill="none" stroke="currentColor">
      <rect x="0.5" y="0.5" width="63" height="63" fill="none" stroke="currentColor" strokeWidth="1" vectorEffect="non-scaling-stroke"/>
      <path d="M 32 32 L 32 14 M 32 32 L 16.4 41 M 32 32 L 47.6 41" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" vectorEffect="non-scaling-stroke"/>
      <circle cx="32" cy="12" r="4" fill="none" stroke="currentColor" strokeWidth="1.6" vectorEffect="non-scaling-stroke"/>
      <circle cx="14.7" cy="42" r="4" fill="none" stroke="currentColor" strokeWidth="1.6" vectorEffect="non-scaling-stroke"/>
      <circle cx="49.3" cy="42" r="4" fill="none" stroke="currentColor" strokeWidth="1.6" vectorEffect="non-scaling-stroke"/>
      <circle cx="32" cy="32" r="5" fill="currentColor"/>
    </svg>
  )
}

/* ---- inline icons ---- */
function IBrain({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 5a3 3 0 0 0-3 3v.5a3 3 0 0 0-2 5.6V16a2 2 0 0 0 2 2h.5"/>
      <path d="M12 5a3 3 0 0 1 3 3v.5a3 3 0 0 1 2 5.6V16a2 2 0 0 1-2 2h-.5"/>
      <path d="M12 5v13"/>
    </svg>
  )
}
function IReplay({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8"/>
      <path d="M3 3v5h5"/>
    </svg>
  )
}
function IShield({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/>
      <path d="m9 12 2 2 4-4"/>
    </svg>
  )
}
function IArrowR({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>
    </svg>
  )
}
function IArrowD({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 5v14"/><path d="m5 12 7 7 7-7"/>
    </svg>
  )
}

/* ---- σ-field canvas ---- */
function FieldCanvas({ sigmaRef, lambdaRef }: { sigmaRef: MutableRefObject<number>; lambdaRef: MutableRefObject<number> }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas!.getContext('2d')
    if (!ctx) return

    let W = 0, H = 0, dpr = 1, frames = 0
    const N = 130
    type Pt = { x: number; y: number; vx: number; vy: number; r: number; a: number }
    const pts: Pt[] = []
    const ripples: Array<{ x: number; y: number; t: number }> = []

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      W = canvas!.clientWidth; H = canvas!.clientHeight
      canvas!.width = W * dpr; canvas!.height = H * dpr
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    resize()

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
      sigmaRef.current = Math.min(1, sigmaRef.current + 0.6)
      ripples.push({ x: cx / W, y: cy / H, t: 0 })
      const sx = cx / W, sy = cy / H
      for (const p of pts) {
        const dx = p.x - sx, dy = p.y - sy
        const d = Math.hypot(dx, dy) || 0.001
        if (d < 0.28) {
          const f = (0.28 - d) * 0.012
          p.vx += (dx / d) * f; p.vy += (dy / d) * f
        }
      }
    }

    const onPointer = (e: PointerEvent) => {
      if (e.clientY < window.innerHeight * 1.1) disturb(e.clientX, e.clientY)
    }
    const onScroll = () => {
      lambdaRef.current = Math.min(1, window.scrollY / (document.body.scrollHeight - window.innerHeight || 1))
    }

    window.addEventListener('pointerdown', onPointer)
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', resize)

    let rafId = 0
    function frame() {
      frames++
      ctx!.clearRect(0, 0, W, H)
      sigmaRef.current *= 0.97

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
            ctx!.strokeStyle = `rgba(200,169,110,${(1 - d / 150) * 0.07 * (0.5 + sigmaRef.current)})`
            ctx!.lineWidth = 1
            ctx!.beginPath()
            ctx!.moveTo(p.x * W, p.y * H)
            ctx!.lineTo(q.x * W, q.y * H)
            ctx!.stroke()
          }
        }
      }

      for (const p of pts) {
        const glow = p.a * (0.6 + sigmaRef.current * 0.8)
        ctx!.fillStyle = `rgba(200,169,110,${glow})`
        ctx!.beginPath()
        ctx!.arc(p.x * W, p.y * H, p.r, 0, Math.PI * 2)
        ctx!.fill()
      }

      for (let i = ripples.length - 1; i >= 0; i--) {
        const r = ripples[i]; r.t += 0.02
        const rad = r.t * Math.max(W, H) * 0.5
        ctx!.strokeStyle = `rgba(200,169,110,${Math.max(0, 0.22 - r.t * 0.22)})`
        ctx!.lineWidth = 1
        ctx!.beginPath()
        ctx!.arc(r.x * W, r.y * H, rad, 0, Math.PI * 2)
        ctx!.stroke()
        if (r.t > 1) ripples.splice(i, 1)
      }

      rafId = requestAnimationFrame(frame)
    }
    frame()

    return () => {
      window.removeEventListener('pointerdown', onPointer)
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', resize)
      cancelAnimationFrame(rafId)
    }
  }, [])

  return <canvas ref={canvasRef} className="rt-field"/>
}

/* ---- field readout (polls canvas state) ---- */
function FieldHint({ sigmaRef, lambdaRef }: { sigmaRef: MutableRefObject<number>; lambdaRef: MutableRefObject<number> }) {
  const [sigma, setSigma] = useState('0.000')
  const [lambda, setLambda] = useState('0.000')
  const [frames, setFrames] = useState(0)

  useEffect(() => {
    const id = setInterval(() => {
      setSigma(sigmaRef.current.toFixed(3))
      setLambda(lambdaRef.current.toFixed(3))
      setFrames(f => f + 6)
    }, 100)
    return () => clearInterval(id)
  }, [sigmaRef, lambdaRef])

  return (
    <p className="rt-field-hint">
      click to disturb the σ field · scroll to deepen λ memory &nbsp;·&nbsp;
      σ=<span className="v">{sigma}</span> &nbsp;
      λ=<span className="v">{lambda}</span> &nbsp;
      <span>{frames.toLocaleString()}</span> frames
    </p>
  )
}

/* ---- TopBar ---- */
function TopBar({ status, total }: { status: ChainStatus; total: number }) {
  const dotColor = status.valid ? 'var(--aegis-T0)' : 'var(--attn-gaze)'
  const verdictColor = status.valid ? 'var(--aegis-T0)' : 'var(--attn-gaze)'
  return (
    <header className="rt-topbar">
      <div className="rt-wrap">
        <a className="rt-brand" href="#top">
          <Mark size={28} cls="rt-mark"/>
          <span className="rt-wm">AEGIS-Ω</span>
        </a>
        <nav className="rt-nav">
          <a href="#substrate">Substrate</a>
          <a href="#cognition">Cognition</a>
          <a href="#equation">Equation</a>
          <a href="#limits">Limits</a>
        </nav>
        <div className="rt-spacer"/>
        <div className="rt-ribbon-mini">
          <span className="rt-dot" style={{ background: dotColor, color: dotColor }}/>
          <span>chain</span>
          <b style={{ color: 'var(--aegis-phi)' }}>{total}</b>
          <span>·</span>
          <span>verdict</span>
          <b style={{ color: verdictColor }}>{status.valid ? 'T0 PASS' : 'BREACH'}</b>
        </div>
        <a className="rt-btn rt-btn-primary" href="#substrate">Enter the System</a>
      </div>
    </header>
  )
}

/* ---- Hero ---- */
function Hero({ status, total, sigmaRef, lambdaRef }: {
  status: ChainStatus; total: number
  sigmaRef: MutableRefObject<number>
  lambdaRef: MutableRefObject<number>
}) {
  return (
    <section className="rt-hero" id="top">
      <div className="rt-wrap">
        <div className="rt-eyebrow-pill">
          <span className="rt-live-dot"/>
          Constitutional AI Runtime · executing in your browser
        </div>
        <h1>The AI system that<br/><span className="rt-gold">governs itself.</span></h1>
        <p className="rt-lead">
          Not by description. <b>By execution.</b> Metacognitive self-awareness,
          retrospective replay, and BFT consensus — running as live substrate,
          hash-chained and tamper-evident.
        </p>
        <div className="rt-status-strip" role="status">
          <span className="cell">
            <span className="key">is_valid</span>
            <span className={`val ${status.valid ? 'ok' : 'bad'}`}>{String(status.valid)}</span>
          </span>
          <span className="cell">
            <span className="key">t0_verdict</span>
            <span className={`val ${status.t0 ? 'ok' : 'bad'}`}>{String(status.t0)}</span>
          </span>
          <span className="cell">
            <span className="key">corruption</span>
            <span className={`val ${status.corruption ? 'bad' : 'ok'}`}>{status.corruption}</span>
          </span>
          <span className="cell">
            <span className="key">chain_length</span>
            <span className="val gold">{total}</span>
          </span>
          <span className="cell">
            <span className="key">bridge</span>
            <span className="val info">online</span>
          </span>
        </div>
        <FieldHint sigmaRef={sigmaRef} lambdaRef={lambdaRef}/>
        <div className="rt-cta-row">
          <a className="rt-btn rt-btn-primary rt-btn-lg" href="#substrate">
            Observe the substrate <IArrowD size={16}/>
          </a>
          <a className="rt-btn rt-btn-ghost rt-btn-lg" href="#enter">
            Enter the System <IArrowR size={16}/>
          </a>
        </div>
      </div>
    </section>
  )
}

/* ---- Stream ---- */
function Stream({ sub }: { sub: ReturnType<typeof useChain> }) {
  const { visible, status, total, tamper, reseal } = sub
  const head = visible.length ? visible[visible.length - 1] : null
  return (
    <section className="rt-section" id="substrate" style={{ background: 'var(--r-bg-2)', borderTop: '1px solid var(--r-line)' }}>
      <div className="rt-wrap">
        <div className="rt-stream-layout">
          <div className="rt-stream-side">
            <div className="rt-sec-num">01 · MECHANISM</div>
            <h2>A metacognitive stream you can break.</h2>
            <p className="rt-stream-note">
              Every entry is a real <code>SHA-256</code> of the previous hash,
              its sequence number, and the observation signal. Tamper with any
              row and <code>certify()</code> flips to <span className="bad">false</span> —
              recomputed live in this page, not mocked.
            </p>
            <div className="rt-side-verdict">
              <span className="rt-sv-head">Live verdict</span>
              <div className="rt-sv-row">
                <span className="rt-sv-key">certify()</span>
                <span className={`rt-sv-val ${status.valid ? 'ok' : 'bad'}`}>{String(status.valid)}</span>
              </div>
              <div className="rt-sv-row">
                <span className="rt-sv-key">corruption_count</span>
                <span className={`rt-sv-val ${status.corruption ? 'bad' : 'ok'}`}>{status.corruption}</span>
              </div>
              <div className="rt-sv-sep"/>
              <div className="rt-sv-row">
                <span className="rt-sv-key">observations</span>
                <span className="rt-sv-val phi">{total}</span>
              </div>
              <div className="rt-sv-row">
                <span className="rt-sv-key">head</span>
                <span className="rt-sv-val inf">{head ? short(head.hash, 10) : '···'}</span>
              </div>
            </div>
          </div>

          <div>
            <div className="rt-stream-panel">
              <div className="rt-stream-head">
                <span className="title">Metacognitive Stream</span>
                <span className="count">{total}</span>
                <span className="spacer"/>
                <span className={`rt-verdict-chip ${status.valid ? 'valid' : 'breach'}`}>
                  <span className="rt-vd"/>
                  {status.valid ? 'CERTIFIED' : `BREACH @ seq ${status.firstBreak}`}
                </span>
              </div>

              <table className="rt-stream-table">
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
                    <tr key={e.seq} className={`rt-stream-row ${e.fresh ? 'fresh' : ''} ${e.tampered ? 'tampered' : ''}`}>
                      <td className="rt-seq">{String(e.seq).padStart(3, '0')}</td>
                      <td><span className="rt-layer-tag">{e.layer}</span></td>
                      <td><span className={`rt-tier-tag rt-tier-${e.tier}`}>{e.tier}</span></td>
                      <td className="rt-signal-cell">{e.signal}</td>
                      <td className="rt-hash-cell">
                        <span className="hp">{short(e.prevHash)}</span>
                        <span className="arrow">→</span>
                        <span className="hc" style={{ color: e.tampered ? 'var(--attn-gaze)' : 'var(--aegis-phi)' }}>
                          {short(e.hash)}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {e.tampered
                          ? <button className="rt-tamper-btn reseal" onClick={() => void reseal(e.seq)}>re-seal</button>
                          : <button className="rt-tamper-btn" onClick={() => void tamper(e.seq)}>tamper</button>
                        }
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="rt-stream-foot">
                <span>genesis: <code>0000…0000</code></span>
                <span className="spacer"/>
                <span>head: <code>{head ? short(head.hash, 14) : '···'}</code></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ---- Quote strip ---- */
function Quote() {
  return (
    <section className="rt-quote-strip">
      <div className="rt-wrap">
        <blockquote>
          "The code does not ask to be believed. It can be replayed from genesis
          and will produce the same <em>cryptographic fingerprint</em> every time."
        </blockquote>
        <cite>Constitutional invariant · AEGIS-Ω runtime</cite>
      </div>
    </section>
  )
}

/* ---- Cognition ---- */
const LAYERS = [
  {
    Icon: IBrain, num: '1',
    ltag: 'Layer 1 · Substrate', title: 'Deterministic by construction',
    accent: 'var(--aegis-T0)', accentA12: 'rgba(52,211,153,0.06)',
    desc: 'BTreeMap / BTreeSet only — never HashMap. Ordering is guaranteed, so the same inputs replay to the same cryptographic fingerprint, every time.',
    mk: 'invariant', mv: 'ordering = total',
  },
  {
    Icon: IReplay, num: '2',
    ltag: 'Layer 2 · Retrospection', title: 'It replays its own past',
    accent: 'var(--aegis-T1)', accentA12: 'rgba(96,165,250,0.06)',
    desc: 'Retrospective thinking walks the chain backward from any frame to genesis. Nothing is trusted that cannot be re-derived from the record itself.',
    mk: 'replay depth', mv: '0 → genesis',
  },
  {
    Icon: IShield, num: '3',
    ltag: 'Layer 3 · Consensus', title: 'No claim outranks its proof',
    accent: 'var(--aegis-T2)', accentA12: 'rgba(167,139,250,0.06)',
    desc: 'Every claim is tier-tagged T0–T3 and gated by BFT quorum across the model alliance. An unproven write can never reach the T0 layer.',
    mk: 'quorum', mv: '3 / 4 weights',
  },
]

function Cognition() {
  return (
    <section className="rt-section rt-section--tight" id="cognition" style={{ borderTop: '1px solid var(--r-line)', borderBottom: '1px solid var(--r-line)' }}>
      <div className="rt-wrap">
        <div className="rt-section-head">
          <div className="rt-sec-num">02 · ARCHITECTURE</div>
          <h2>Self-government is an architecture, not a promise.</h2>
        </div>
        <div className="rt-layer-grid">
          {LAYERS.map(l => (
            <div
              key={l.title}
              className="rt-layer-card"
              style={{ '--lc-accent': l.accent, '--lc-accent-a12': l.accentA12 } as CSSProperties}
            >
              <div className="topline"/>
              <div className="topglow"/>
              <div className="ico"><l.Icon size={26}/></div>
              <span className="ltag">{l.ltag}</span>
              <h3>{l.title}</h3>
              <p>{l.desc}</p>
              <div className="metric"><span>{l.mk}</span><b>{l.mv}</b></div>
              <span className="rt-wm-num">{l.num}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ---- Equation ---- */
function Equation() {
  return (
    <section className="rt-section--mid rt-eq-outer" id="equation">
      <div className="rt-eq-full">
        <div className="rt-wrap" style={{ textAlign: 'center' }}>
          <div className="rt-sec-num" style={{ justifyContent: 'center', marginBottom: 20 }}>
            03 · THE MARTINGALE BOUNDARY
          </div>
          <div className="rt-eq-mono-huge">E[Sₙ₊₁ | Fₙ] = Sₙ</div>
          <div className="rt-eq-label">martingale boundary · confidence cannot inflate between frames</div>
        </div>
      </div>
      <div className="rt-wrap">
        <div className="rt-equation-block">
          <div className="rt-eq-detail">
            <div className="rt-eq-sub">
              <div>φ <span className="g">= 1.6180339…</span></div>
              <div>1 / φ <span className="v">≈ 0.6180</span></div>
              <div>weightₙ <span className="v">= ⌊1000 · (1/φⁿ)⌋</span></div>
              <div><span className="t0">618</span> · <span className="v">382 · 236 · 146 · 90 · …</span></div>
              <div>∑ weights <span className="v">= 1000</span> <span className="g">// always</span></div>
            </div>
          </div>
          <div className="rt-eq-copy">
            <span className="eyebrow">The guardrail</span>
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
              ratio — not by fiat. The author holds the only unbounded weight: veto.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ---- Invariants ---- */
const INVARIANTS = [
  { g: '≤', h: 'Version mismatch = hard abort',
    p: <>A divergent runtime version halts rather than guessing. <code>certify()</code> never runs on an ambiguous build.</> },
  { g: '∩', h: 'BTreeMap / BTreeSet only',
    p: <>No <code>HashMap</code> reaches <code>src/</code>. Deterministic ordering is an invariant, not a preference.</> },
  { g: '△', h: 'Every claim is tier-tagged',
    p: <>T0 proven · T1 validated · T2 hypothesis · T3 conjecture. <code>T4</code> (blocked) must never appear.</> },
  { g: '∈', h: 'Replayable from genesis',
    p: <>Any frame re-derives to the same fingerprint. The record is the source of truth, not the cache.</> },
  { g: '′', h: 'No write outranks its proof',
    p: <>An unproven mutation is frozen before it reaches the T0 layer. Capability never exceeds evidence.</> },
  { g: 'φ', h: 'Weights bounded by 1/φ',
    p: <>Orchestration weights are fixed by the golden ratio. No model can vote itself more influence.</> },
]

function Invariants() {
  return (
    <section className="rt-section rt-section--tight" id="invariants" style={{ background: 'var(--r-bg-2)', borderTop: '1px solid var(--r-line)' }}>
      <div className="rt-wrap">
        <div className="rt-section-head">
          <div className="rt-sec-num">04 · CONSTITUTIONAL</div>
          <h2>Rules the runtime cannot break — including for itself.</h2>
        </div>
        <div className="rt-inv-list">
          {INVARIANTS.map(iv => (
            <div className="rt-inv-row" key={iv.h}>
              <span className="rt-glyph">{iv.g}</span>
              <div className="rt-inv-body"><h4>{iv.h}</h4><p>{iv.p}</p></div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ---- Limitations ---- */
function Limitations() {
  return (
    <section className="rt-section rt-section--tight" id="limits" style={{ borderTop: '1px solid var(--r-line)' }}>
      <div className="rt-wrap">
        <div className="rt-section-head">
          <div className="rt-sec-num">05 · KNOWN LIMITATIONS</div>
          <h2>What it does not do.</h2>
          <p>Honest disclosure is constitutional. These are facts, not caveats.</p>
        </div>
        <div className="rt-limits-panel">
          <div className="rt-limits-title">Known Limitations</div>
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

/* ---- Final CTA ---- */
function FinalCTA() {
  return (
    <section className="rt-section" id="enter">
      <div className="rt-wrap">
        <div className="rt-final">
          <Mark size={64} cls="rt-mark-lg"/>
          <h2>
            No part of the system can do<br/>
            more than it can <span className="rt-gold">prove it did.</span>
          </h2>
          <p>
            Open the runtime and watch the chain extend in real time.
            It can be replayed from genesis and will produce the same fingerprint every time.
          </p>
          <div className="rt-cta-row">
            <a className="rt-btn rt-btn-primary rt-btn-xl" href="#substrate">
              Enter the System <IArrowR size={18}/>
            </a>
            <a className="rt-btn rt-btn-ghost rt-btn-xl" href="#equation">
              Read the equation
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ---- Social icons ---- */
const SOC_PATHS: Record<string, [string, string]> = {
  github:  ['0 0 24 24', 'M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z'],
  x:       ['0 0 24 24', 'M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.74l7.73-8.835L1.254 2.25H8.08l4.213 5.567zm-1.161 17.52h1.833L7.084 4.126H5.117z'],
  bluesky: ['0 0 24 24', 'M12 10.8c-1.087-2.114-4.046-6.053-6.798-7.995C2.566.944 1.561 1.266.902 1.565.139 1.908 0 3.08 0 3.768c0 .69.378 5.65.624 6.479.815 2.736 3.713 3.66 6.383 3.364.136-.02.275-.039.415-.056-.138.022-.276.04-.415.056-3.912.58-7.387 2.005-2.83 7.078 5.013 5.19 6.87-1.113 7.823-4.308.953 3.195 2.05 9.271 7.733 4.308 4.267-4.308 1.172-6.498-2.74-7.078a8.741 8.741 0 0 1-.415-.056c.14.017.279.036.415.056 2.67.297 5.568-.628 6.383-3.364.246-.828.624-5.79.624-6.478 0-.69-.139-1.861-.902-2.204-.659-.3-1.664-.62-4.3 1.24C16.046 4.748 13.087 8.687 12 10.8z'],
  discord: ['0 0 24 24', 'M20.317 4.492c-1.53-.69-3.17-1.2-4.885-1.49a.075.075 0 0 0-.079.036c-.21.369-.444.85-.608 1.23a18.566 18.566 0 0 0-5.487 0 12.36 12.36 0 0 0-.617-1.23A.077.077 0 0 0 8.562 3c-1.714.29-3.354.8-4.885 1.491a.07.07 0 0 0-.032.027C.533 9.093-.32 13.555.099 17.961a.08.08 0 0 0 .031.055 20.03 20.03 0 0 0 5.993 2.98.078.078 0 0 0 .084-.026c.462-.62.874-1.275 1.226-1.963.021-.04.001-.088-.041-.104a13.201 13.201 0 0 1-1.872-.878.075.075 0 0 1-.008-.125c.126-.093.252-.19.372-.287a.075.075 0 0 1 .078-.01c3.927 1.764 8.18 1.764 12.061 0a.075.075 0 0 1 .079.009c.12.098.245.195.372.288a.075.075 0 0 1-.006.125c-.598.344-1.22.635-1.873.877a.075.075 0 0 0-.041.105c.36.687.772 1.341 1.225 1.962a.077.077 0 0 0 .084.028 19.963 19.963 0 0 0 6.002-2.981.076.076 0 0 0 .032-.054c.5-5.094-.838-9.52-3.549-13.442a.06.06 0 0 0-.031-.028z'],
}

function Footer() {
  return (
    <footer className="rt-footer">
      <div className="rt-wrap">
        <div className="rt-footer-row">
          <div className="rt-col-brand">
            <a className="rt-brand" href="#top">
              <Mark size={26} cls="rt-mark"/>
              <span className="rt-wm">AEGIS-Ω</span>
            </a>
            <p>
              A sovereign constitutional runtime. Metacognitive, hash-chained,
              tamper-evident — and able to prove every claim it makes about itself.
            </p>
            <div className="rt-attribution">
              Conceived, designed &amp; executed by <span className="v">Tarik Skalić</span><br/>
              Bihać, Bosnia-Herzegovina · <span className="v">AGPL-3.0</span>
            </div>
            <div className="rt-socials">
              {(['github', 'x', 'bluesky', 'discord'] as const).map(id => {
                const [vb, d] = SOC_PATHS[id]
                return (
                  <a key={id} href="#" aria-label={id}>
                    <svg viewBox={vb} fill="currentColor"><path d={d}/></svg>
                  </a>
                )
              })}
            </div>
          </div>
          <div className="rt-foot-links">
            <span className="h">Runtime</span>
            <a href="#substrate">Substrate</a>
            <a href="#cognition">Cognition</a>
            <a href="#equation">Equation</a>
            <a href="#invariants">Invariants</a>
            <a href="#limits">Known Limitations</a>
          </div>
        </div>
        <div className="rt-footer-line">
          <span>AEGIS-Ω · Constitutional AI Runtime</span>
          <span>1 / <span className="phi">φ</span> = 0.6180… · E[Sₙ₊₁ | Fₙ] = Sₙ</span>
        </div>
      </div>
    </footer>
  )
}

/* ---- Root component ---- */
export function AegisRuntime() {
  const sub = useChain({ seed: 6, window: 8, tickMs: 2600 })
  const sigmaRef = useRef(0)
  const lambdaRef = useRef(0)

  return (
    <div className="rt-shell">
      <FieldCanvas sigmaRef={sigmaRef} lambdaRef={lambdaRef}/>
      <div className="rt-veil"/>
      <div className="rt-content">
        <TopBar status={sub.status} total={sub.total}/>
        <Hero status={sub.status} total={sub.total} sigmaRef={sigmaRef} lambdaRef={lambdaRef}/>
        <Stream sub={sub}/>
        <Quote/>
        <Cognition/>
        <Equation/>
        <Invariants/>
        <Limitations/>
        <FinalCTA/>
        <Footer/>
      </div>
    </div>
  )
}
