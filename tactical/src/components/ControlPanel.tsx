import { Play, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import type { CollaborationMode, SystemStatus } from '../types.js'

const MODES: CollaborationMode[] = ['revenue', 'analysis', 'gtm', 'retention', 'competitive', 'technical', 'regulatory', 'fundraising']

interface Props {
  status: SystemStatus
  onExecute: (objective: string, mode: CollaborationMode, live: boolean) => void
  onReset: () => void
}

export function ControlPanel({ status, onExecute, onReset }: Props) {
  const [objective, setObjective] = useState('')
  const [mode, setMode]           = useState<CollaborationMode>('revenue')
  const [live, setLive]           = useState(false)

  const busy = status === 'INITIALIZING' || status === 'STREAMING'

  function handleFire() {
    const obj = objective.trim()
    if (!obj || busy) return
    onExecute(obj, mode, live)
  }

  return (
    <div className="bg-aegis-panel border border-aegis-border rounded p-4 space-y-4">
      <div className="flex items-center justify-between border-b border-aegis-border pb-2">
        <span className="text-xs font-mono text-aegis-text tracking-widest">MISSION_CONTROL</span>
        <span className={`text-xs font-mono font-bold ${
          status === 'COMPLETE' ? 'text-aegis-accent' :
          status === 'ERROR'    ? 'text-aegis-err'    :
          busy                  ? 'text-aegis-warn animate-pulse' :
          'text-aegis-text/50'
        }`}>[{status}]</span>
      </div>

      <div className="space-y-1">
        <label className="text-[10px] font-mono text-aegis-text/60 tracking-widest">OBJECTIVE</label>
        <textarea
          className="w-full bg-aegis-bg border border-aegis-border rounded px-3 py-2 text-sm font-mono text-white placeholder-aegis-text/30 resize-none focus:outline-none focus:border-aegis-accent/60 transition-colors"
          rows={3}
          placeholder="Enter strategic objective…"
          value={objective}
          onChange={e => setObjective(e.target.value)}
          disabled={busy}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-[10px] font-mono text-aegis-text/60 tracking-widest">MODE</label>
          <select
            className="w-full bg-aegis-bg border border-aegis-border rounded px-2 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-aegis-accent/60"
            value={mode}
            onChange={e => setMode(e.target.value as CollaborationMode)}
            disabled={busy}
          >
            {MODES.map(m => <option key={m} value={m}>{m.toUpperCase()}</option>)}
          </select>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-mono text-aegis-text/60 tracking-widest">LIVE_CLAUDE</label>
          <button
            type="button"
            onClick={() => setLive(v => !v)}
            disabled={busy}
            className={`w-full rounded px-2 py-1.5 text-xs font-mono font-bold border transition-colors ${
              live
                ? 'bg-aegis-accent/20 border-aegis-accent text-aegis-accent'
                : 'bg-aegis-bg border-aegis-border text-aegis-text/50'
            }`}
          >{live ? '● LIVE' : '○ DEMO'}</button>
        </div>
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleFire}
          disabled={!objective.trim() || busy}
          className="flex-1 flex items-center justify-center gap-2 bg-aegis-accent/10 border border-aegis-accent/60 hover:bg-aegis-accent/20 disabled:opacity-30 disabled:cursor-not-allowed text-aegis-accent text-xs font-mono font-bold rounded py-2 transition-colors glow-accent"
        >
          <Play size={12} />
          {busy ? 'EXECUTING…' : 'EXECUTE_SWARM'}
        </button>

        <button
          type="button"
          onClick={onReset}
          disabled={busy}
          title="Reset"
          className="px-3 py-2 bg-aegis-bg border border-aegis-border hover:border-aegis-text/40 disabled:opacity-30 rounded transition-colors"
        >
          <RotateCcw size={14} className="text-aegis-text/60" />
        </button>
      </div>
    </div>
  )
}
