import { useState } from 'react'
import type { TelemetrySnapshot } from '../types.js'

interface Props { snapshot: TelemetrySnapshot | null }

const EVENT_KINDS = ['TOPO_TRANSITION', 'CAP_EVOLUTION', 'TIER_PROMOTION', 'GATE_PASS', 'EPOCH_SEAL']

export function LineageSurface({ snapshot }: Props) {
  const [expanded, setExpanded] = useState(false)
  if (!snapshot) return <div className="p-6 text-aegis-muted text-sm font-mono">Awaiting telemetry…</div>

  const total = snapshot.epoch_sequence
  const visible = expanded ? total : Math.min(total, 8)

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono uppercase tracking-widest text-aegis-muted">
          Adaptive Lineage — {total} entries
        </span>
        {total > 8 && (
          <button
            className="text-xs font-mono text-aegis-T1 hover:text-aegis-phi transition-colors"
            onClick={() => setExpanded(e => !e)}
          >
            {expanded ? 'collapse' : `show all ${total}`}
          </button>
        )}
      </div>

      <div className="bg-aegis-deep rounded-xl border border-aegis-border overflow-hidden">
        {Array.from({ length: visible }, (_, i) => {
          const kind = EVENT_KINDS[i % EVENT_KINDS.length] ?? 'CAP_EVOLUTION'
          const isT0 = kind === 'EPOCH_SEAL'
          return (
            <div
              key={i}
              className={`flex items-center gap-3 px-4 py-2 text-xs font-mono hover:bg-aegis-surface/40 transition-colors ${
                i < visible - 1 ? 'border-b border-aegis-border/50' : ''
              }`}
            >
              <span className="text-aegis-disabled w-5 text-right">{total - i}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded border shrink-0 ${
                isT0
                  ? 'text-aegis-T0 bg-aegis-T0/10 border-aegis-T0/20'
                  : 'text-aegis-T1 bg-aegis-T1/10 border-aegis-T1/20'
              }`}>
                {kind}
              </span>
              <span className="text-aegis-muted flex-1 truncate">a1b2c3d4e5f6a7b8…</span>
              <span className="text-aegis-T0 text-[10px]">✓</span>
            </div>
          )
        })}
      </div>

      {!expanded && total > 8 && (
        <p className="text-[10px] text-aegis-disabled font-mono">
          …{total - 8} more entries (expand to view)
        </p>
      )}
    </div>
  )
}
