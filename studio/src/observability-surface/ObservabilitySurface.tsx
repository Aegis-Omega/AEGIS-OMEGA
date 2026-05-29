import type { TelemetrySnapshot } from '../types.js'

interface Props { snapshot: TelemetrySnapshot | null }

function MetricRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center px-4 py-2.5 text-xs font-mono border-b border-aegis-border/50 last:border-0 hover:bg-aegis-surface/40 transition-colors">
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 mr-3 ${ok ? 'bg-aegis-T0' : 'bg-aegis-T4'}`} />
      <span className="text-aegis-secondary w-44">{label}</span>
      <span className={ok ? 'text-aegis-text' : 'text-aegis-T4 font-semibold'}>{value}</span>
      <span className={`ml-auto text-[10px] ${ok ? 'text-aegis-T0' : 'text-aegis-T4'}`}>
        {ok ? 'nominal' : 'VIOLATION'}
      </span>
    </div>
  )
}

export function ObservabilitySurface({ snapshot }: Props) {
  if (!snapshot) return <div className="p-6 text-aegis-muted text-sm font-mono">Awaiting telemetry…</div>

  const metrics = [
    { label: 'pgcs_passes',          value: String(snapshot.pgcs_passes),                          ok: snapshot.pgcs_passes },
    { label: 'corruption_count',     value: String(snapshot.corruption_count),                      ok: snapshot.corruption_count === 0 },
    { label: 'vcg_error',            value: snapshot.vcg_error.toFixed(4),                          ok: snapshot.vcg_error < 1.0 },
    { label: 'drift_index',          value: snapshot.drift_index.toFixed(4),                        ok: snapshot.drift_index < 0.2 },
    { label: 'gate_acceptance_rate', value: (snapshot.gate_acceptance_rate * 100).toFixed(1) + '%', ok: snapshot.gate_acceptance_rate > 0.8 },
    { label: 'failsafe_state',       value: snapshot.failsafe_state,                                ok: snapshot.failsafe_state === 'OPERATIONAL' },
  ]

  const allNominal = metrics.every(m => m.ok)

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono uppercase tracking-widest text-aegis-muted">
          Runtime Metrics
        </span>
        <span className={`text-[10px] font-mono px-2.5 py-1 rounded-lg border ${
          allNominal
            ? 'text-aegis-T0 bg-aegis-T0/10 border-aegis-T0/20'
            : 'text-aegis-T4 bg-aegis-T4/10 border-aegis-T4/20'
        }`}>
          {allNominal ? 'ALL NOMINAL' : 'VIOLATION DETECTED'}
        </span>
      </div>
      <div className="bg-aegis-deep rounded-xl border border-aegis-border overflow-hidden">
        {metrics.map(m => (
          <MetricRow key={m.label} label={m.label} value={m.value} ok={m.ok} />
        ))}
      </div>
    </div>
  )
}
