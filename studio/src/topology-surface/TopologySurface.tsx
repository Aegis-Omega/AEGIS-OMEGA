import type { TelemetrySnapshot } from '../types.js'

interface Props { snapshot: TelemetrySnapshot | null }

export function TopologySurface({ snapshot }: Props) {
  if (!snapshot) return <div className="p-6 text-aegis-muted text-sm font-mono">Awaiting telemetry…</div>

  const rows: Array<{ k: string; v: string; ok: boolean }> = [
    { k: 'failsafe_state',       v: snapshot.failsafe_state,                                ok: snapshot.failsafe_state === 'OPERATIONAL' },
    { k: 'vcg_error',            v: snapshot.vcg_error.toFixed(6),                          ok: snapshot.vcg_error < 1.0 },
    { k: 'drift_index',          v: snapshot.drift_index.toFixed(6),                        ok: snapshot.drift_index < 0.2 },
    { k: 'epoch_sequence',       v: String(snapshot.epoch_sequence),                        ok: true },
    { k: 'gate_acceptance_rate', v: (snapshot.gate_acceptance_rate * 100).toFixed(2) + '%', ok: snapshot.gate_acceptance_rate > 0.8 },
    { k: 'corruption_count',     v: String(snapshot.corruption_count),                      ok: snapshot.corruption_count === 0 },
    { k: 'pgcs_passes',          v: String(snapshot.pgcs_passes),                           ok: snapshot.pgcs_passes },
  ]

  return (
    <div className="p-5 space-y-4">
      <span className="text-[10px] font-mono uppercase tracking-widest text-aegis-muted">
        Governance Topology
      </span>
      <div className="bg-aegis-deep rounded-xl border border-aegis-border overflow-hidden">
        {rows.map(({ k, v, ok }, i) => (
          <div
            key={k}
            className={`flex items-center px-4 py-2.5 text-xs font-mono hover:bg-aegis-surface/40 transition-colors ${
              i < rows.length - 1 ? 'border-b border-aegis-border/50' : ''
            }`}
          >
            <span className="text-aegis-secondary w-44">{k}</span>
            <span className={ok ? 'text-aegis-text' : 'text-aegis-T4 font-semibold'}>{v}</span>
            <span className={`ml-auto text-[10px] ${ok ? 'text-aegis-T0' : 'text-aegis-T4'}`}>
              {ok ? '✓' : '✗'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
