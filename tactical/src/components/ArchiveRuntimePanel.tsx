import type { ArchiveRuntimeView } from '../hooks/useArchiveRuntime.js'

interface Props { runtime: ArchiveRuntimeView }

export function ArchiveRuntimePanel({ runtime }: Props) {
  const ready = runtime.state === 'ready'
  const stateClass =
    runtime.state === 'ready' ? 'text-aegis-accent' :
    runtime.state === 'loading' ? 'text-aegis-warn' :
    'text-aegis-err'

  return (
    <section className="bg-aegis-panel border border-aegis-border rounded p-4">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 border-b border-aegis-border pb-3">
        <div>
          <div className="text-xs font-mono text-aegis-text tracking-widest">RECOVERED_ARCHIVE_RUNTIME</div>
          <div className="mt-1 text-[10px] font-mono text-aegis-text/50">
            LOCAL_EPHEMERAL_READ_COMPUTE_ONLY · NO DURABLE STATE
          </div>
        </div>
        <div className={`text-xs font-mono font-bold ${stateClass}`}>
          [{runtime.declaredState}]
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
        <Metric label="AUTHORITY_EFFECT" value={runtime.authorityEffect} ok={runtime.authorityEffect === 'NONE'} />
        <Metric label="NETWORK_AUTHORITY" value={runtime.networkAuthority ? 'TRUE' : 'FALSE'} ok={!runtime.networkAuthority} />
        <Metric label="PERSISTENT_STATE" value={runtime.persistentState ? 'TRUE' : 'FALSE'} ok={!runtime.persistentState} />
        <Metric label="SCOPE" value={runtime.scope} ok={ready} />
      </div>

      <div className="mt-3 flex flex-col md:flex-row md:items-center gap-3">
        <button
          type="button"
          onClick={() => void runtime.runArcProbe()}
          disabled={!ready || runtime.probeState === 'running'}
          className="px-3 py-2 rounded border border-aegis-accent/50 bg-aegis-accent/10 text-aegis-accent text-[10px] font-mono font-bold tracking-widest disabled:opacity-30"
        >
          {runtime.probeState === 'running' ? 'RUNNING_ARC_PROBE…' : 'VERIFY_ROT90_2X2'}
        </button>

        <div className="text-[10px] font-mono text-aegis-text/60">
          INPUT [[1,2],[3,4]] → EXPECTED [[2,4],[1,3]]
        </div>

        {runtime.probeState === 'pass' && (
          <span className="text-[10px] font-mono text-aegis-accent">
            PASS {JSON.stringify(runtime.probeOutput)}
          </span>
        )}
        {runtime.probeState === 'error' && (
          <span className="text-[10px] font-mono text-aegis-err">
            FAIL {runtime.error ?? 'UNKNOWN'}
          </span>
        )}
      </div>
    </section>
  )
}

function Metric({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="bg-aegis-bg p-2.5 rounded border border-aegis-border/50 min-w-0">
      <div className="text-[9px] font-mono text-aegis-text/50 tracking-widest">{label}</div>
      <div className={`text-[11px] font-mono font-bold truncate ${ok ? 'text-aegis-accent' : 'text-aegis-err'}`}>
        {value}
      </div>
    </div>
  )
}
