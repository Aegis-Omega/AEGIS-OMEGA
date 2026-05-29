import type { ReplayEvent, TelemetrySnapshot } from '../types.js'

interface Props { snapshot: TelemetrySnapshot | null }

function ReplayNode({ event }: { event: ReplayEvent }) {
  return (
    <div className="flex items-center gap-3 py-1.5 border-b border-aegis-border/50 text-xs font-mono hover:bg-aegis-surface/40 transition-colors">
      <span className="text-aegis-disabled w-8 text-right shrink-0">{event.sequence}</span>
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${event.is_replay_reconstructable ? 'bg-aegis-T0' : 'bg-aegis-T4'}`} />
      <span className="text-aegis-T1 w-40 shrink-0">{event.kind}</span>
      <span className="text-aegis-muted truncate">{event.hash.slice(0, 20)}…</span>
      {event.is_replay_reconstructable && (
        <span className="ml-auto text-aegis-T0 text-[10px] shrink-0">✓</span>
      )}
    </div>
  )
}

function buildDemoEvents(snapshot: TelemetrySnapshot): ReplayEvent[] {
  const n = Math.min(snapshot.epoch_sequence, 20)
  return Array.from({ length: n }, (_, i) => ({
    sequence: i + 1,
    kind: i % 3 === 0 ? 'TOPOLOGY_TRANSITION' : i % 3 === 1 ? 'CAPABILITY_EVOLUTION' : 'DFA_PHASE',
    hash: `${'a'.charCodeAt(0) + (i % 26)}`.padEnd(64, '0'),
    is_replay_reconstructable: true,
  }))
}

export function ReplaySurface({ snapshot }: Props) {
  if (!snapshot) {
    return <div className="p-6 text-aegis-muted text-sm font-mono">Awaiting bridge telemetry…</div>
  }

  const events = buildDemoEvents(snapshot)

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3 border-b border-aegis-border flex items-center gap-5 bg-aegis-deep">
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-aegis-muted font-mono uppercase tracking-wider">epoch</span>
          <span className="text-sm font-mono text-aegis-text font-semibold">{snapshot.epoch_sequence}</span>
        </div>
        <div className="h-3 w-px bg-aegis-border" />
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-aegis-muted font-mono uppercase tracking-wider">gate_rate</span>
          <span className="text-sm font-mono text-aegis-text">{(snapshot.gate_acceptance_rate * 100).toFixed(1)}%</span>
        </div>
        <div className="h-3 w-px bg-aegis-border" />
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-aegis-muted font-mono uppercase tracking-wider">events</span>
          <span className="text-sm font-mono text-aegis-T1">{events.length}</span>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-3">
        {events.length === 0 ? (
          <p className="text-aegis-disabled text-xs font-mono">No replay events yet.</p>
        ) : (
          events.map(ev => <ReplayNode key={ev.sequence} event={ev} />)
        )}
      </div>
    </div>
  )
}
