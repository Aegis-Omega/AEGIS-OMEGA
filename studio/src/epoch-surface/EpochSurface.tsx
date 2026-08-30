import type { TelemetrySnapshot } from '../types.js'

interface Props { snapshot: TelemetrySnapshot | null }

export function EpochSurface({ snapshot }: Props) {
  if (!snapshot) return <div className="p-6 text-aegis-muted text-sm font-mono">Awaiting telemetry…</div>

  const epochs = Math.min(snapshot.epoch_sequence, 10)
  const links = Array.from({ length: epochs }, (_, i) => ({
    seq: i + 1,
    hash: `epoch_${(i + 1).toString().padStart(3, '0')}_${'0'.repeat(8)}`,
    valid: snapshot.vcg_error < 1.0,
  }))

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono uppercase tracking-widest text-aegis-muted">
          Epoch Chain
        </span>
        <span className="text-xs font-mono text-aegis-T1">
          {epochs} links · vcg_error {snapshot.vcg_error.toFixed(4)}
        </span>
      </div>
      <div className="bg-aegis-deep rounded-xl border border-aegis-border overflow-hidden">
        {links.map((l, idx) => (
          <div
            key={l.seq}
            className={`flex items-center gap-4 px-4 py-2.5 text-xs font-mono hover:bg-aegis-surface/50 transition-colors ${
              idx < links.length - 1 ? 'border-b border-aegis-border/50' : ''
            }`}
          >
            <span className="text-aegis-disabled w-6 text-right">{l.seq}</span>
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${l.valid ? 'bg-aegis-T0' : 'bg-aegis-T4'}`} />
            <span className="text-aegis-secondary flex-1">{l.hash}</span>
            <span className={`text-[10px] ${l.valid ? 'text-aegis-T0' : 'text-aegis-T4'}`}>
              {l.valid ? 'valid' : 'invalid'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
