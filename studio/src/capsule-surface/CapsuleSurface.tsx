import type { TelemetrySnapshot } from '../types.js'

interface Props { snapshot: TelemetrySnapshot | null }

const CAPSULES = [
  { id: 'cap-alpha', entropy_budget: 100, capabilities: ['READ_STATE', 'EMIT_EVENT'], sealed: true },
  { id: 'cap-beta',  entropy_budget: 55,  capabilities: ['READ_STATE', 'CANONICALIZE', 'REPLAY_VERIFY'], sealed: true },
  { id: 'cap-gamma', entropy_budget: 34,  capabilities: ['GATE_SIGNAL'], sealed: false },
]

export function CapsuleSurface({ snapshot }: Props) {
  if (!snapshot) return <div className="p-6 text-aegis-muted text-sm font-mono">Awaiting telemetry…</div>

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono uppercase tracking-widest text-aegis-muted">
          Capsule Manifests
        </span>
        <span className="text-[10px] font-mono text-aegis-T1">{CAPSULES.length} capsules</span>
      </div>
      <div className="space-y-3">
        {CAPSULES.map(({ id, entropy_budget, capabilities, sealed }) => (
          <div
            key={id}
            className="bg-aegis-deep rounded-xl border border-aegis-border p-4 space-y-2.5 hover:border-aegis-border-medium transition-colors"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-mono font-semibold text-aegis-text">{id}</span>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-lg border ${
                sealed
                  ? 'text-aegis-T0 bg-aegis-T0/10 border-aegis-T0/20'
                  : 'text-aegis-T3 bg-aegis-T3/10 border-aegis-T3/20'
              }`}>
                {sealed ? 'sealed' : 'open'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-4 text-[11px] font-mono">
              <span className="text-aegis-muted">entropy_budget</span>
              <span className="text-aegis-secondary">{entropy_budget}</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {capabilities.map(cap => (
                <span
                  key={cap}
                  className="text-[10px] font-mono text-aegis-T1 bg-aegis-T1/5 border border-aegis-T1/15 px-2 py-0.5 rounded"
                >
                  {cap}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
