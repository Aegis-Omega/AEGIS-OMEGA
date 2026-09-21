import { AlertTriangle, Archive, Database, Layers3 } from 'lucide-react'
import type { OperationsSourcesState } from '../hooks/useOperationsSources.js'

interface Props {
  sources: OperationsSourcesState
}

const ICONS = {
  catalogued_sources: Database,
  archive_project_files: Archive,
  coverage_groups: Layers3,
  unsurfaced_no_counterpart: AlertTriangle,
} as const

export function SourcesCoverage({ sources }: Props) {
  if (sources.state === 'LOADING') {
    return (
      <section className="bg-aegis-panel border border-aegis-border rounded p-4">
        <Header state="LOADING" />
        <div className="text-[10px] font-mono text-aegis-text/50">SOURCE_COVERAGE_LOADING</div>
      </section>
    )
  }

  if (sources.state !== 'READY') {
    return (
      <section className="bg-aegis-panel border border-aegis-err/50 rounded p-4">
        <Header state={sources.state} />
        <div className="flex items-start gap-2 text-aegis-err">
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />
          <div>
            <div className="text-xs font-mono font-bold">SOURCE_COVERAGE_UNAVAILABLE</div>
            <div className="mt-1 text-[10px] font-mono text-aegis-text/55">
              {sources.error}
            </div>
            <div className="mt-1 text-[10px] font-mono text-aegis-warn">
              LEGACY_COMPLETENESS_FALLBACK_DISABLED
            </div>
          </div>
        </div>
      </section>
    )
  }

  const payload = sources.payload
  const observed = payload.source.observed_at_utc.replace('T', ' ').replace('+00:00', 'Z')

  return (
    <section className="bg-aegis-panel border border-aegis-border rounded p-4">
      <Header state="VERIFIED_EVIDENCE_PACKAGE_SNAPSHOT" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {payload.cards.map(card => {
          const Icon = ICONS[card.id]
          const warn = card.id === 'coverage_groups' || card.id === 'unsurfaced_no_counterpart'
          return (
            <div
              key={card.id}
              className="bg-aegis-bg border border-aegis-border/50 rounded p-3 min-w-0"
              title={card.note}
            >
              <div className="flex items-center justify-between gap-2">
                <Icon size={15} className={warn ? 'text-aegis-warn' : 'text-aegis-accent'} />
                <span className="text-[9px] font-mono text-aegis-text/35 truncate">{card.status}</span>
              </div>
              <div className="mt-2 text-xl font-mono font-bold text-white">{card.value}</div>
              <div className="mt-0.5 text-[9px] font-mono text-aegis-text/55 tracking-wide">
                {card.label.toUpperCase()}
              </div>
            </div>
          )
        })}
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[9px] font-mono text-aegis-text/45">
        <span>MAIN: {payload.source.observed_main_head.slice(0, 12)}</span>
        <span>OBSERVED: {observed}</span>
        <span>PROJECTION: {payload.projection_root.slice(0, 12)}</span>
        <span>AUTHORITY: {payload.authority_effect}</span>
      </div>
    </section>
  )
}

function Header({ state }: { state: string }) {
  const ready = state === 'VERIFIED_EVIDENCE_PACKAGE_SNAPSHOT'
  const stateClass =
    ready ? 'text-aegis-accent' :
    state === 'LOADING' ? 'text-aegis-text/40' :
    'text-aegis-err'

  return (
    <div className="flex items-center justify-between mb-3 border-b border-aegis-border pb-2">
      <span className="text-xs font-mono text-aegis-text tracking-widest">SOURCE_COVERAGE</span>
      <span className={'text-[9px] font-mono tracking-widest ' + stateClass}>
        {state}
      </span>
    </div>
  )
}
