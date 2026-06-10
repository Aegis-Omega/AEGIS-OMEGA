import { Cloud, Database, Lock, ShieldCheck } from 'lucide-react'
import type { BridgeHealth } from '../hooks/useBridgeStatus.js'

interface Props { health: BridgeHealth }

export function BridgeStatus({ health }: Props) {
  const ok  = (v: boolean | undefined) => v ? 'text-aegis-accent' : 'text-aegis-err'
  const dot = health.online ? 'bg-aegis-accent animate-pulse' : 'bg-aegis-err'

  return (
    <div className="bg-aegis-panel border border-aegis-border rounded p-4">
      <div className="flex items-center justify-between mb-3 border-b border-aegis-border pb-2">
        <span className="text-xs font-mono text-aegis-text tracking-widest">INFRASTRUCTURE_TELEMETRY</span>
        <span className="flex items-center gap-1.5 text-xs font-mono">
          <span className={`w-2 h-2 rounded-full ${dot}`} />
          <span className={health.online ? 'text-aegis-accent' : 'text-aegis-err'}>
            {health.online ? 'BRIDGE_LIVE' : 'BRIDGE_OFFLINE'}
          </span>
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Item icon={Cloud}       label="CLOUD_RUN"     value={health.version ?? '—'}               color="text-aegis-accent" />
        <Item icon={ShieldCheck} label="T0_VERDICT"    value={health.t0_verdict ? 'PASS' : '—'}    color={ok(health.t0_verdict)} />
        <Item icon={Lock}        label="CHAIN_VALID"   value={health.chain_valid ? 'VALID' : '—'}  color={ok(health.chain_valid)} />
        <Item icon={Database}    label="CORRUPTION"    value={health.corruption_count === 0 ? 'ZERO' : String(health.corruption_count ?? '—')} color={health.corruption_count === 0 ? 'text-aegis-accent' : 'text-aegis-err'} />
      </div>

      <div className="mt-3 flex gap-4 text-[10px] font-mono text-aegis-text/60">
        <span>AGENTS: {health.total_agents ?? '—'}</span>
        <span>CONTRACT: {health.contract_version ?? '—'}</span>
        <span>BRIDGE: {(import.meta.env.VITE_BRIDGE_URL as string | undefined) ?? 'localhost:7890'}</span>
      </div>
    </div>
  )
}

function Item({ icon: Icon, label, value, color }: { icon: React.FC<{ size: number; className: string }>; label: string; value: string; color: string }) {
  return (
    <div className="flex items-start gap-2 bg-aegis-bg p-2.5 rounded border border-aegis-border/50">
      <Icon size={16} className={`mt-0.5 shrink-0 ${color}`} />
      <div className="min-w-0">
        <div className="text-[9px] font-mono text-aegis-text/50 tracking-widest">{label}</div>
        <div className={`text-xs font-mono font-bold truncate ${color}`}>{value}</div>
      </div>
    </div>
  )
}
