import { useState } from 'react'
import { useTelemetry } from './useTelemetry.js'
import { ReplaySurface } from './replay-surface/ReplaySurface.js'
import { EpochSurface } from './epoch-surface/EpochSurface.js'
import { DivergenceSurface } from './divergence-surface/DivergenceSurface.js'
import { RollbackSurface } from './rollback-surface/RollbackSurface.js'
import { LineageSurface } from './lineage-surface/LineageSurface.js'
import { TopologySurface } from './topology-surface/TopologySurface.js'
import { OwnershipSurface } from './ownership-surface/OwnershipSurface.js'
import { CapsuleSurface } from './capsule-surface/CapsuleSurface.js'
import { ObservabilitySurface } from './observability-surface/ObservabilitySurface.js'
import { GovernanceSurface } from './governance-surface/GovernanceSurface.js'
import { SwarmSurface } from './swarm-surface/SwarmSurface.js'
import { HolographicSubstrate } from './holographic-surface/HolographicSubstrate.js'

type Surface = 'replay' | 'epoch' | 'divergence' | 'rollback' | 'lineage' |
  'topology' | 'ownership' | 'capsule' | 'observability' | 'governance' | 'swarm' | 'holographic'

const NAV: Array<{ id: Surface; label: string }> = [
  { id: 'replay', label: 'Replay' },
  { id: 'epoch', label: 'Epoch' },
  { id: 'divergence', label: 'Divergence' },
  { id: 'rollback', label: 'Rollback' },
  { id: 'lineage', label: 'Lineage' },
  { id: 'topology', label: 'Topology' },
  { id: 'ownership', label: 'Ownership' },
  { id: 'capsule', label: 'Capsule' },
  { id: 'observability', label: 'Observability' },
  { id: 'governance', label: 'Governance' },
  { id: 'swarm', label: 'Swarm' },
  { id: 'holographic', label: 'Holographic' },
]

export function App() {
  const [active, setActive] = useState<Surface>('replay')
  const { snapshot, error } = useTelemetry()

  return (
    <div className="min-h-screen bg-aegis-void text-aegis-text flex flex-col font-sans">
      <header className="border-b border-aegis-border px-5 py-3 flex items-center gap-4 flex-shrink-0 bg-aegis-deep">
        <div className="flex items-baseline gap-2.5">
          <span className="font-mono font-semibold tracking-[0.2em] text-sm text-aegis-phi">
            AEGIS-Ω
          </span>
          <span className="font-mono text-[10px] tracking-widest uppercase text-aegis-muted opacity-60">
            Studio
          </span>
        </div>
        <div className="h-3.5 w-px bg-aegis-border" />
        <span className="text-[11px] text-aegis-muted">Constitutional Observability · Projection Only</span>
        <div className="ml-auto flex items-center gap-2">
          {error ? (
            <span className="text-[10px] font-mono bg-aegis-T4/10 text-aegis-T4 border border-aegis-T4/20 px-2.5 py-1 rounded-lg">
              bridge offline
            </span>
          ) : snapshot ? (
            <>
              <span className="text-[10px] font-mono bg-aegis-T0/10 text-aegis-T0 border border-aegis-T0/20 px-2.5 py-1 rounded-lg flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-aegis-T0 animate-pulse-slow" />
                live · epoch {snapshot.epoch_sequence}
              </span>
              <span className={`text-[10px] font-mono px-2.5 py-1 rounded-lg border ${
                snapshot.pgcs_passes
                  ? 'bg-aegis-T0/10 text-aegis-T0 border-aegis-T0/20'
                  : 'bg-aegis-T4/10 text-aegis-T4 border-aegis-T4/20'
              }`}>
                {snapshot.pgcs_passes ? 'PGCS PASS' : 'PGCS FAIL'}
              </span>
            </>
          ) : (
            <span className="text-[10px] font-mono text-aegis-disabled px-2.5 py-1">
              awaiting bridge…
            </span>
          )}
        </div>
      </header>
      <div className="flex flex-1 min-h-0">
        <nav className="w-40 border-r border-aegis-border flex-shrink-0 py-3 bg-aegis-deep flex flex-col gap-0.5 px-2">
          {NAV.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setActive(id)}
              className={`w-full text-left px-3 py-2 text-xs rounded-lg transition-colors font-mono tracking-wide ${
                active === id
                  ? 'bg-aegis-surface text-aegis-text border border-aegis-border-medium'
                  : 'text-aegis-muted hover:text-aegis-text hover:bg-aegis-bg'
              }`}
            >
              {active === id && (
                <span className="inline-block w-1 h-1 rounded-full bg-aegis-phi mr-2 mb-0.5" />
              )}
              {label}
            </button>
          ))}
        </nav>
        <main className="flex-1 overflow-auto bg-aegis-bg">
          {active === 'replay' && <ReplaySurface snapshot={snapshot} />}
          {active === 'epoch' && <EpochSurface snapshot={snapshot} />}
          {active === 'divergence' && <DivergenceSurface snapshot={snapshot} />}
          {active === 'rollback' && <RollbackSurface snapshot={snapshot} />}
          {active === 'lineage' && <LineageSurface snapshot={snapshot} />}
          {active === 'topology' && <TopologySurface snapshot={snapshot} />}
          {active === 'ownership' && <OwnershipSurface snapshot={snapshot} />}
          {active === 'capsule' && <CapsuleSurface snapshot={snapshot} />}
          {active === 'observability' && <ObservabilitySurface snapshot={snapshot} />}
          {active === 'governance' && <GovernanceSurface snapshot={snapshot} />}
          {active === 'swarm' && <SwarmSurface snapshot={snapshot} />}
          {active === 'holographic' && <HolographicSubstrate />}
        </main>
      </div>
    </div>
  )
}
