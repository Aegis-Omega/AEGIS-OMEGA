import type { TelemetrySnapshot } from '../types.js'

interface Props { snapshot: TelemetrySnapshot | null }

export function RollbackSurface({ snapshot }: Props) {
  if (!snapshot) return <div className="p-6 text-aegis-muted text-sm font-mono">Awaiting telemetry…</div>

  const canRollback = snapshot.pgcs_passes && snapshot.corruption_count === 0

  return (
    <div className="p-5 space-y-5">
      <div className={`rounded-xl border p-4 font-mono text-sm font-semibold ${
        canRollback
          ? 'bg-aegis-T0/5 border-aegis-T0/20 text-aegis-T0'
          : 'bg-aegis-T4/5 border-aegis-T4/20 text-aegis-T4'
      }`}>
        {canRollback
          ? '✓ Rollback certified — replay reconstruction available'
          : '✗ Rollback blocked — integrity violation detected'}
      </div>

      <div className="bg-aegis-deep rounded-xl border border-aegis-border overflow-hidden">
        {[
          { k: 'rollback_target',  v: `epoch ${Math.max(1, snapshot.epoch_sequence - 1)}` },
          { k: 'pgcs_passes',      v: String(snapshot.pgcs_passes) },
          { k: 'corruption_count', v: String(snapshot.corruption_count) },
          { k: 'certification',    v: canRollback ? 'CERTIFIED' : 'BLOCKED' },
        ].map(({ k, v }, i, arr) => (
          <div key={k} className={`flex items-center px-4 py-2.5 text-xs font-mono ${i < arr.length - 1 ? 'border-b border-aegis-border/50' : ''}`}>
            <span className="text-aegis-secondary w-40">{k}</span>
            <span className="text-aegis-text">{v}</span>
          </div>
        ))}
      </div>

      <p className="text-[10px] text-aegis-disabled font-mono italic">
        Studio possesses no direct mutation authority. All rollback actions enter via
        EventEnvelope → replay certification → governance validation.
      </p>
    </div>
  )
}
