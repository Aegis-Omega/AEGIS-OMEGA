// AEGIS-Ω Console — system status bar + loud verification panel.
// The top strip: LIVE/DEMO source badge (never ambiguous), contract version,
// terminal chain hash. Below it, the verification checklist — every check
// states its reason out loud.

import { T, MONO, glass } from './consoleTokens.js'
import type { ConsoleSnapshot } from '../../lib/platformConsole.js'

export function SystemStatusBar({ snap }: { snap: ConsoleSnapshot }) {
  const live = snap.source === 'live'
  const dot = live ? T.green : T.amber
  return (
    <div style={{ borderBottom: `1px solid ${T.border}`, background: T.void }}
      className="px-6 py-3 flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <span style={{
          width: 8, height: 8, borderRadius: '50%', background: dot,
          boxShadow: `0 0 10px ${dot}`, display: 'inline-block',
        }} />
        <span style={{ fontFamily: MONO, fontSize: 12, color: live ? T.green : T.amber, letterSpacing: '0.1em' }}>
          {live ? '● LIVE' : '○ DEMO'}
        </span>
        <span style={{ fontSize: 12, color: T.muted }}>{snap.reason}</span>
      </div>
      <div className="flex items-center gap-5">
        <Field label="contract" value={`v${snap.status.contract_version}`} />
        <Field label="agents" value={String(snap.status.total_agents)} />
        <Field label="chain" value={snap.status.audit_chain_hash.slice(0, 12) + '…'}
          color={snap.status.chain_valid ? T.green : T.red} />
      </div>
    </div>
  )
}

function Field({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</span>
      <span style={{ fontFamily: MONO, fontSize: 12, color: color ?? T.text }}>{value}</span>
    </div>
  )
}

export function VerificationPanel({ snap }: { snap: ConsoleSnapshot }) {
  return (
    <div style={{ ...glass(T.green), padding: 20 }}>
      <Heading>VERIFICATION · loud by design</Heading>
      <p style={{ fontSize: 12, color: T.muted, marginTop: 6, marginBottom: 16, lineHeight: 1.5 }}>
        No silent degradation. Every check states its reason — a failing system tells you why.
      </p>
      <div className="flex flex-col gap-2">
        {snap.checks.map(c => (
          <div key={c.label} style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '9px 12px', borderRadius: 8,
            background: c.ok ? `${T.green}0A` : `${T.amber}0F`,
            border: `1px solid ${c.ok ? T.green + '22' : T.amber + '33'}`,
          }}>
            <span style={{ color: c.ok ? T.green : T.amber, fontFamily: MONO, fontSize: 13, flexShrink: 0 }}>
              {c.ok ? '✓' : '!'}
            </span>
            <span style={{ fontSize: 13, color: T.text, minWidth: 150, fontWeight: 500 }}>{c.label}</span>
            <span style={{ fontSize: 12, color: c.ok ? T.sub : T.amber, fontFamily: MONO }}>{c.reason}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function Heading({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 11, fontFamily: MONO, color: T.phi, letterSpacing: '0.2em' }}>
      {children}
    </div>
  )
}
