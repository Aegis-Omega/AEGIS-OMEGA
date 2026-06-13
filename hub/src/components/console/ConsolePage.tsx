// AEGIS-Ω Console — /console
// The operator console: the vortex where every communication layer and
// information path converges. Neural-glassmorphism surface (cursor-reactive
// mesh + frosted glass) over the live /platform/* API, with graceful demo
// fallback. Every state is loud — live vs demo is never ambiguous.

import { T, MONO, SANS, glass } from './consoleTokens.js'
import { NeuralField, GlowField } from './NeuralField.js'
import { SystemStatusBar, VerificationPanel } from './SystemStatusBar.js'
import { HomeostasisGauge } from './HomeostasisGauge.js'
import { ToolVortex } from './ToolVortex.js'
import { LiveSwarmRunner } from './LiveSwarmRunner.js'
import { usePlatformConsole } from '../../lib/platformConsole.js'

function ConsoleNav() {
  const links: [string, string][] = [['/', 'Home'], ['/platform', 'Platform'], ['/console', 'Console'], ['/docs', 'API Docs'], ['/pricing', 'Pricing']]
  return (
    <nav style={{
      position: 'sticky', top: 0, zIndex: 50,
      background: 'rgba(8,9,12,0.72)', backdropFilter: 'blur(14px)',
      borderBottom: `1px solid ${T.border}`,
    }} className="px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-8">
        <a href="/" style={{ color: T.phi, fontFamily: MONO, letterSpacing: '0.15em', fontSize: 13 }}>AEGIS-Ω</a>
        <div className="hidden md:flex items-center gap-6">
          {links.map(([href, label]) => (
            <a key={href} href={href} style={{
              color: href === '/console' ? T.text : T.muted,
              fontSize: 13, fontWeight: href === '/console' ? 600 : 400,
            }} className="hover:text-white transition-colors">{label}</a>
          ))}
        </div>
      </div>
      <a href="/pricing" style={{
        background: T.indigo, color: '#fff', fontSize: 12, fontWeight: 600,
        padding: '6px 14px', borderRadius: 8, textDecoration: 'none',
      }}>Get API Key →</a>
    </nav>
  )
}

export function ConsolePage() {
  const snap = usePlatformConsole()
  const memoryActive = snap.calibration.window_size > 0

  return (
    <div style={{ background: T.bg, color: T.text, minHeight: '100vh', fontFamily: SANS, position: 'relative', overflow: 'hidden' }}>
      <GlowField />
      <NeuralField />

      <div style={{ position: 'relative', zIndex: 10 }}>
        <ConsoleNav />
        <SystemStatusBar snap={snap} />

        {/* Hero */}
        <div style={{ maxWidth: 1100, margin: '0 auto', padding: '40px 24px 8px' }}>
          <div style={{ fontSize: 11, fontFamily: MONO, color: T.phi, letterSpacing: '0.2em', marginBottom: 12 }}>
            NOUS · OPERATOR CONSOLE
          </div>
          <h1 style={{ fontSize: 'clamp(28px, 5vw, 46px)', fontWeight: 800, lineHeight: 1.1, letterSpacing: '-0.02em', marginBottom: 12 }}>
            Every path converges here.
          </h1>
          <p style={{ fontSize: 15, color: T.muted, maxWidth: 600, lineHeight: 1.65 }}>
            <span style={{ color: T.text, fontWeight: 600 }}>Nous</span>{' '}
            <span style={{ color: T.muted, fontStyle: 'italic' }}>(νοῦς — the mind behind the shield)</span>:
            system homeostasis, the agent contact list, and the live swarm stream — one surface,
            one mediated center. Live when the bridge is reachable, demo otherwise. Never ambiguous.
          </p>
        </div>

        {/* Grid */}
        <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px' }}
          className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <HomeostasisGauge cal={snap.calibration} />
          <VerificationPanel snap={snap} />
          <ToolVortex tools={snap.tools} source={snap.source} />
          <LiveSwarmRunner memoryActive={memoryActive} />
        </div>

        {/* CTA */}
        <div style={{ maxWidth: 1100, margin: '0 auto', padding: '8px 24px 64px' }}>
          <div style={{ ...glass(T.indigo), padding: '28px 32px', textAlign: 'center' }}>
            <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8 }}>Run it live.</h2>
            <p style={{ fontSize: 14, color: T.muted, marginBottom: 20, maxWidth: 460, marginLeft: 'auto', marginRight: 'auto', lineHeight: 1.6 }}>
              Get an API key to stream real 39-department collaborations and wire your own agent contact list.
            </p>
            <a href="/pricing" style={{
              background: T.indigo, color: '#fff', fontSize: 14, fontWeight: 600,
              padding: '12px 28px', borderRadius: 10, textDecoration: 'none',
            }}>Get API Key →</a>
          </div>
        </div>

        <div style={{ borderTop: `1px solid ${T.border}`, padding: '20px 24px', textAlign: 'center' }}>
          <span style={{ fontSize: 11, color: T.muted }}>
            AEGIS-Ω · operator console · contract v{snap.status.contract_version}
          </span>
        </div>
      </div>
    </div>
  )
}
