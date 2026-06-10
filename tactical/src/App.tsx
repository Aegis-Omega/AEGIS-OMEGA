import { Activity, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { BridgeStatus } from './components/BridgeStatus.js'
import { ConsensusReport } from './components/ConsensusReport.js'
import { ControlPanel } from './components/ControlPanel.js'
import { ExecutionTrace } from './components/ExecutionTrace.js'
import { KeyEntry } from './components/KeyEntry.js'
import { SwarmGrid } from './components/SwarmGrid.js'
import { useBridgeStatus } from './hooks/useBridgeStatus.js'
import { useExecution } from './hooks/useExecution.js'

const ENV_KEY = (import.meta.env.VITE_AEGIS_API_KEY as string | undefined) ?? ''
const LS_KEY  = 'aegis_tactical_api_key'

function loadKey(): string {
  return ENV_KEY || localStorage.getItem(LS_KEY) || ''
}

function saveKey(k: string) {
  if (!ENV_KEY) localStorage.setItem(LS_KEY, k)
}

export default function App() {
  const [apiKey, setApiKey] = useState(loadKey)

  function handleKey(k: string) { saveKey(k); setApiKey(k) }

  if (!apiKey) return <KeyEntry onKey={handleKey} />

  return <Dashboard apiKey={apiKey} onLogout={() => { localStorage.removeItem(LS_KEY); setApiKey('') }} />
}

function Dashboard({ apiKey, onLogout }: { apiKey: string; onLogout: () => void }) {
  const health                            = useBridgeStatus()
  const { status, agents, logs, result, execute, reset } = useExecution(apiKey)

  return (
    <div className="min-h-screen bg-aegis-bg p-4 md:p-6 flex flex-col gap-4 max-w-[1600px] mx-auto">

      {/* Header */}
      <header className="relative scanlines flex items-center justify-between border-b border-aegis-border pb-3">
        <div className="flex items-center gap-3">
          <div className="bg-aegis-accent/10 border border-aegis-accent/40 p-2 rounded">
            <Activity size={20} className="text-aegis-accent animate-pulse" />
          </div>
          <div>
            <h1 className="text-base font-mono font-bold text-white tracking-widest">AEGIS-Ω</h1>
            <p className="text-[10px] font-mono text-aegis-text/50 tracking-widest">TACTICAL OPERATIONS CENTER · CONSTITUTIONAL AI</p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-right font-mono text-xs">
          {health.t0_verdict && (
            <div className="hidden sm:flex items-center gap-1.5 text-aegis-accent">
              <ShieldCheck size={12} />
              <span className="text-[10px] tracking-widest">T0_VERIFIED</span>
            </div>
          )}
          <div>
            <div className="text-[9px] text-aegis-text/40 tracking-widest">SYSTEM_STATE</div>
            <div className={`font-bold text-[11px] ${
              status === 'STREAMING' ? 'text-aegis-warn animate-pulse' :
              status === 'COMPLETE'  ? 'text-aegis-accent' :
              status === 'ERROR'     ? 'text-aegis-err' :
              'text-aegis-text/50'
            }`}>[{status}]</div>
          </div>
          <button
            type="button"
            onClick={onLogout}
            className="text-[10px] text-aegis-text/30 hover:text-aegis-text/60 font-mono transition-colors"
          >LOGOUT</button>
        </div>
      </header>

      {/* Infrastructure row */}
      <BridgeStatus health={health} />

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1">

        {/* Left column: controls + swarm */}
        <div className="lg:col-span-1 flex flex-col gap-4">
          <ControlPanel status={status} onExecute={execute} onReset={reset} />
          <SwarmGrid agents={agents} status={status} />
        </div>

        {/* Right column: trace + result */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div className="flex-1 min-h-[320px]">
            <ExecutionTrace logs={logs} />
          </div>
          {result && <ConsensusReport result={result} />}
        </div>
      </div>

      <footer className="text-center text-[9px] font-mono text-aegis-text/25 tracking-widest">
        AEGIS-Ω · AdaptivePower(T) ≤ ReplayVerifiability(T) · φ = 0.6180339887
      </footer>
    </div>
  )
}
