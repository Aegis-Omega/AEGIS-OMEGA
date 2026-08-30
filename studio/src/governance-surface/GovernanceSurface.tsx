import type { TelemetrySnapshot } from '../types.js'

interface Props { snapshot: TelemetrySnapshot | null }

const AMENDMENTS = [
  { id: 'amd_a1b2c3d4', scope: 'T0 core invariants', status: 'APPLIED', epoch: 1 },
  { id: 'amd_e5f6a7b8', scope: 'Martingale suspension threshold', status: 'APPLIED', epoch: 3 },
  { id: 'amd_c9d0e1f2', scope: 'φ-quorum calibration', status: 'APPLIED', epoch: 7 },
]

export function GovernanceSurface({ snapshot }: Props) {
  if (!snapshot) return <div className="p-6 text-aegis-muted text-sm font-mono">Awaiting telemetry…</div>

  const healthy = snapshot.pgcs_passes && snapshot.corruption_count === 0 && snapshot.vcg_error < 1.0

  return (
    <div className="p-5 space-y-5">
      <div className={`rounded-xl border p-4 font-mono ${
        healthy
          ? 'bg-aegis-T0/5 border-aegis-T0/20 text-aegis-T0'
          : 'bg-aegis-T4/5 border-aegis-T4/20 text-aegis-T4'
      }`}>
        <p className="text-sm font-semibold">
          {healthy ? '✓ CONSTITUTIONAL: PERMIT' : '✗ CONSTITUTIONAL: DENY'}
        </p>
        <p className="text-[11px] mt-1 opacity-70">
          Mutation authority: {healthy ? 'ACTIVE (entropy_bounded=true)' : 'SUSPENDED (violation detected)'}
        </p>
      </div>

      <div className="space-y-2">
        <span className="text-[10px] font-mono uppercase tracking-widest text-aegis-muted">
          Active Amendments
        </span>
        <div className="bg-aegis-deep rounded-xl border border-aegis-border overflow-hidden">
          {AMENDMENTS.map(({ id, scope, status, epoch }, i) => (
            <div
              key={id}
              className={`flex items-center gap-3 px-4 py-2.5 text-xs font-mono hover:bg-aegis-surface/40 transition-colors ${
                i < AMENDMENTS.length - 1 ? 'border-b border-aegis-border/50' : ''
              }`}
            >
              <span className="text-aegis-T1 shrink-0">{id}</span>
              <span className="text-aegis-muted flex-1 truncate">{scope}</span>
              <span className="text-aegis-disabled text-[10px] mr-2">epoch {epoch}</span>
              <span className="text-aegis-T0 text-[10px]">{status}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-aegis-deep rounded-xl border border-aegis-border p-4 space-y-2 text-xs font-mono">
        {[
          { k: 'pgcs_passes',      v: String(snapshot.pgcs_passes),  ok: snapshot.pgcs_passes },
          { k: 'vcg_error',        v: snapshot.vcg_error.toFixed(4), ok: snapshot.vcg_error < 1.0 },
          { k: 'corruption_count', v: String(snapshot.corruption_count), ok: snapshot.corruption_count === 0 },
        ].map(({ k, v, ok }) => (
          <div key={k} className="flex items-center gap-2">
            <span className="text-aegis-muted w-36">{k}</span>
            <span className={ok ? 'text-aegis-text' : 'text-aegis-T4'}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
