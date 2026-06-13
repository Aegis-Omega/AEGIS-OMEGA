// AEGIS-Ω Console — /console
// NOUS: the operator console. A single living core you look into (CoreCanvas),
// with everything else stripped back and spacious. Cinematic hero first; the
// substance — homeostasis, verification, live stream — revealed below, calm and
// professional. Live /platform/* data with graceful demo fallback; never
// ambiguous about which.

import { T, MONO, SANS } from './consoleTokens.js'
import { CoreCanvas } from './CoreCanvas.js'
import { VerificationPanel } from './SystemStatusBar.js'
import { HomeostasisGauge } from './HomeostasisGauge.js'
import { LiveSwarmRunner } from './LiveSwarmRunner.js'
import { usePlatformConsole } from '../../lib/platformConsole.js'

function ConsoleNav() {
  const links: [string, string][] = [['/', 'Home'], ['/platform', 'Platform'], ['/console', 'Console'], ['/docs', 'Docs'], ['/pricing', 'Pricing']]
  return (
    <nav style={{
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50,
      background: 'rgba(6,7,12,0.55)', backdropFilter: 'blur(16px) saturate(150%)',
      borderBottom: `1px solid rgba(255,255,255,0.06)`,
    }} className="px-7 py-4 flex items-center justify-between">
      <a href="/" style={{ color: T.text, fontFamily: MONO, letterSpacing: '0.22em', fontSize: 13, fontWeight: 600 }}>
        NOUS<span style={{ color: T.phi }}> · Ω</span>
      </a>
      <div className="hidden md:flex items-center gap-7">
        {links.map(([href, label]) => (
          <a key={href} href={href} style={{
            color: href === '/console' ? T.text : T.muted, fontSize: 13,
            fontWeight: href === '/console' ? 600 : 400, textDecoration: 'none',
          }} className="hover:text-white transition-colors">{label}</a>
        ))}
      </div>
      <a href="/pricing" style={{
        background: 'rgba(255,255,255,0.06)', border: `1px solid rgba(255,255,255,0.12)`,
        color: '#fff', fontSize: 12, fontWeight: 600, padding: '7px 16px', borderRadius: 10, textDecoration: 'none',
      }}>Request Access</a>
    </nav>
  )
}

function StatChip({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ textAlign: 'center', padding: '0 22px' }}>
      <div style={{ fontFamily: MONO, fontSize: 17, color, letterSpacing: '0.02em' }}>{value}</div>
      <div style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.16em', marginTop: 5 }}>{label}</div>
    </div>
  )
}

export function ConsolePage() {
  const snap = usePlatformConsole()
  const memoryActive = snap.calibration.window_size > 0
  const live = snap.source === 'live'

  return (
    <div style={{ background: '#06070C', color: T.text, minHeight: '100vh', fontFamily: SANS, position: 'relative' }}>
      <CoreCanvas />
      {/* vignette for depth + legibility */}
      <div aria-hidden style={{
        position: 'fixed', inset: 0, zIndex: 1, pointerEvents: 'none',
        background: 'radial-gradient(circle at 50% 42%, transparent 0%, transparent 38%, rgba(6,7,12,0.55) 72%, rgba(6,7,12,0.92) 100%)',
      }} />

      <div style={{ position: 'relative', zIndex: 10 }}>
        <ConsoleNav />

        {/* Cinematic hero — text in clean space above, core rising below */}
        <section style={{
          minHeight: '100vh', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'flex-start', textAlign: 'center',
          padding: 'clamp(120px, 19vh, 220px) 24px 0',
        }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 9, marginBottom: 30,
            padding: '6px 14px', borderRadius: 100,
            background: 'rgba(255,255,255,0.04)', border: `1px solid rgba(255,255,255,0.10)`,
            backdropFilter: 'blur(8px)',
          }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: live ? T.green : T.amber, boxShadow: `0 0 10px ${live ? T.green : T.amber}` }} />
            <span style={{ fontFamily: MONO, fontSize: 11, color: live ? T.green : T.amber, letterSpacing: '0.12em' }}>
              {live ? 'LIVE' : 'DEMO'}
            </span>
            <span style={{ fontSize: 11, color: T.muted }}>· {snap.reason}</span>
          </div>

          <h1 style={{
            fontSize: 'clamp(44px, 9vw, 104px)', fontWeight: 700, lineHeight: 0.98,
            letterSpacing: '-0.04em', margin: 0,
            background: 'linear-gradient(180deg, #FFFFFF 0%, #C9CBD6 60%, #9A8050 130%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
            filter: 'drop-shadow(0 4px 40px rgba(6,7,12,0.8))',
          }}>NOUS</h1>
          <p style={{ fontSize: 'clamp(15px, 2.2vw, 20px)', color: T.sub, maxWidth: 560, margin: '22px auto 0', lineHeight: 1.6, fontWeight: 400, textShadow: '0 2px 28px rgba(6,7,12,0.95)' }}>
            The mind behind the shield. A governed agent swarm that converges
            <span style={{ color: T.text }}> thirty-nine departments</span> into one
            constitutionally-audited answer — and shows you every path it took.
          </p>

          <div style={{
            display: 'flex', alignItems: 'center', marginTop: 44,
            padding: '16px 8px', borderRadius: 16,
            background: 'rgba(10,11,16,0.4)', border: `1px solid rgba(255,255,255,0.07)`,
            backdropFilter: 'blur(12px)', boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
          }}>
            <StatChip label="departments" value={String(snap.status.total_agents)} color={T.text} />
            <Divider />
            <StatChip label="homeostasis" value={snap.calibration.homeostasis_zone} color={T.green} />
            <Divider />
            <StatChip label="contract" value={`v${snap.status.contract_version}`} color={T.text} />
            <Divider />
            <StatChip label="chain" value={snap.status.chain_valid ? 'valid' : 'broken'} color={snap.status.chain_valid ? T.green : T.red} />
          </div>

          <div style={{ marginTop: 40, fontSize: 11, color: T.muted, fontFamily: MONO, letterSpacing: '0.1em' }}>
            ↓ scroll to operate
          </div>
        </section>

        {/* Substance — calm, spacious, full-width */}
        <main style={{ maxWidth: 1080, margin: '0 auto', padding: '40px 24px 80px', display: 'flex', flexDirection: 'column', gap: 24 }}>
          <SectionLabel n="01" title="System state" sub="Homeostasis and self-verification — the system's felt state and its honesty." />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <HomeostasisGauge cal={snap.calibration} />
            <VerificationPanel snap={snap} />
          </div>

          <SectionLabel n="02" title="Live collaboration" sub="Stream a 39-department run — dag_step → agent_event → tool_call → completion." />
          <LiveSwarmRunner memoryActive={memoryActive} />
        </main>

        <footer style={{ borderTop: `1px solid rgba(255,255,255,0.06)`, padding: '24px', textAlign: 'center' }}>
          <span style={{ fontSize: 11, color: T.muted, fontFamily: MONO }}>
            NOUS · AEGIS-Ω · governed by AdaptivePower(T) ≤ ReplayVerifiability(T)
          </span>
        </footer>
      </div>
    </div>
  )
}

function Divider() {
  return <div style={{ width: 1, height: 34, background: 'rgba(255,255,255,0.08)' }} />
}

function SectionLabel({ n, title, sub }: { n: string; title: string; sub: string }) {
  return (
    <div style={{ marginTop: 32 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 14 }}>
        <span style={{ fontFamily: MONO, fontSize: 12, color: T.phi }}>{n}</span>
        <h2 style={{ fontSize: 26, fontWeight: 700, letterSpacing: '-0.02em', margin: 0 }}>{title}</h2>
      </div>
      <p style={{ fontSize: 14, color: T.muted, marginTop: 8, marginLeft: 26, lineHeight: 1.6, maxWidth: 620 }}>{sub}</p>
    </div>
  )
}
