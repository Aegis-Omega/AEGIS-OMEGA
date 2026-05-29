import type { TelemetrySnapshot } from '../types.js'

interface Props { snapshot: TelemetrySnapshot | null }

const CAPABILITIES = [
  { cap: 'READ_STATE',    tier: 'T0', desc: 'Access canonical event log' },
  { cap: 'EMIT_EVENT',    tier: 'T1', desc: 'Append to event substrate via EventEnvelope' },
  { cap: 'CANONICALIZE',  tier: 'T0', desc: 'RFC 8785 JCS hash production' },
  { cap: 'REPLAY_VERIFY', tier: 'T0', desc: 'Deterministic state reconstruction' },
  { cap: 'GATE_SIGNAL',   tier: 'T1', desc: 'Pass/fail signals to governance layer' },
]

export function OwnershipSurface({ snapshot }: Props) {
  if (!snapshot) return <div className="p-6 text-aegis-muted text-sm font-mono">Awaiting telemetry…</div>

  return (
    <div className="p-5 space-y-4">
      <span className="text-[10px] font-mono uppercase tracking-widest text-aegis-muted">
        Capability Graph
      </span>
      <div className="bg-aegis-deep rounded-xl border border-aegis-border overflow-hidden">
        {CAPABILITIES.map(({ cap, tier, desc }, i) => (
          <div
            key={cap}
            className={`flex items-center gap-3 px-4 py-3 text-xs font-mono hover:bg-aegis-surface/40 transition-colors ${
              i < CAPABILITIES.length - 1 ? 'border-b border-aegis-border/50' : ''
            }`}
          >
            <span className={`text-[10px] px-1.5 py-0.5 rounded border shrink-0 ${
              tier === 'T0'
                ? 'text-aegis-T0 bg-aegis-T0/10 border-aegis-T0/20'
                : 'text-aegis-T1 bg-aegis-T1/10 border-aegis-T1/20'
            }`}>
              {tier}
            </span>
            <span className="text-aegis-text w-36 shrink-0">{cap}</span>
            <span className="text-aegis-muted text-[11px]">{desc}</span>
            <span className="ml-auto text-aegis-T0 text-[10px]">certified</span>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-aegis-disabled font-mono">
        DelegatedCapability ⊆ CertifiedCapability — invariant enforced by replay substrate.
      </p>
    </div>
  )
}
