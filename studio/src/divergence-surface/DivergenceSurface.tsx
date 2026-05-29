import type { DivergenceClass, TelemetrySnapshot } from '../types.js'

interface Props { snapshot: TelemetrySnapshot | null }

const CLASS_META: Record<DivergenceClass, { color: string; bg: string; border: string; label: string }> = {
  D0: { color: 'text-aegis-T0',   bg: 'bg-aegis-T0/5',   border: 'border-aegis-T0/20',   label: 'Observational' },
  D1: { color: 'text-aegis-T3',   bg: 'bg-aegis-T3/5',   border: 'border-aegis-T3/20',   label: 'Serializer' },
  D2: { color: 'text-orange-400', bg: 'bg-orange-500/5', border: 'border-orange-500/20', label: 'Topology' },
  D3: { color: 'text-aegis-T4',   bg: 'bg-aegis-T4/5',   border: 'border-aegis-T4/20',   label: 'Ownership' },
  D4: { color: 'text-aegis-T4',   bg: 'bg-aegis-T4/10',  border: 'border-aegis-T4/30',   label: 'Constitutional' },
}

function classifyDrift(snapshot: TelemetrySnapshot): DivergenceClass {
  if (snapshot.corruption_count > 0) return 'D4'
  if (snapshot.drift_index > 0.5) return 'D3'
  if (snapshot.drift_index > 0.2) return 'D2'
  if (snapshot.drift_index > 0.05) return 'D1'
  return 'D0'
}

export function DivergenceSurface({ snapshot }: Props) {
  if (!snapshot) return <div className="p-6 text-aegis-muted text-sm font-mono">Awaiting telemetry…</div>

  const cls = classifyDrift(snapshot)
  const meta = CLASS_META[cls]
  const frozen = snapshot.drift_index > 0.2 || snapshot.corruption_count > 0

  return (
    <div className="p-5 space-y-5">
      <div className={`rounded-xl border p-4 flex items-center gap-4 ${meta.bg} ${meta.border}`}>
        <span className={`text-3xl font-mono font-bold ${meta.color}`}>{cls}</span>
        <div>
          <p className={`text-sm font-semibold ${meta.color}`}>{meta.label} Divergence</p>
          <p className="text-[11px] text-aegis-muted mt-0.5">
            drift_index: {snapshot.drift_index.toFixed(4)} · corruption_count: {snapshot.corruption_count}
          </p>
        </div>
        {frozen && (
          <span className="ml-auto text-[10px] font-mono bg-aegis-T4/15 text-aegis-T4 border border-aegis-T4/30 px-2.5 py-1 rounded-lg">
            MUTATION FROZEN
          </span>
        )}
      </div>

      <div className="bg-aegis-deep rounded-xl border border-aegis-border overflow-hidden">
        {[
          { k: 'drift_index',      v: snapshot.drift_index.toFixed(6),     ok: snapshot.drift_index < 0.2 },
          { k: 'corruption_count', v: String(snapshot.corruption_count),    ok: snapshot.corruption_count === 0 },
          { k: 'vcg_error',        v: snapshot.vcg_error.toFixed(6),        ok: snapshot.vcg_error < 1.0 },
          { k: 'divergence_class', v: `${cls} — ${meta.label}`,             ok: cls === 'D0' },
        ].map(({ k, v, ok }, i, arr) => (
          <div key={k} className={`flex items-center px-4 py-2.5 text-xs font-mono ${i < arr.length - 1 ? 'border-b border-aegis-border/50' : ''}`}>
            <span className="text-aegis-secondary w-40">{k}</span>
            <span className={ok ? 'text-aegis-text' : 'text-aegis-T4'}>{v}</span>
          </div>
        ))}
      </div>

      <p className="text-[10px] text-aegis-disabled font-mono">
        D0: observational · D1: serializer · D2: topology · D3: ownership · D4: constitutional
      </p>
    </div>
  )
}
