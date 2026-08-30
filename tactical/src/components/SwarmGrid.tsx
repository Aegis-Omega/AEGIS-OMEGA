import { Cpu } from 'lucide-react'
import type { AgentNode, SystemStatus } from '../types.js'
import { CATEGORY_COLOR } from '../types.js'

interface Props {
  agents: AgentNode[]
  status: SystemStatus
}

export function SwarmGrid({ agents, status }: Props) {
  const done    = agents.filter(a => a.state === 'done').length
  const active  = agents.filter(a => a.state === 'active').length

  return (
    <div className="bg-aegis-panel border border-aegis-border rounded p-4">
      <div className="flex items-center justify-between mb-3 border-b border-aegis-border pb-2">
        <h3 className="text-xs font-mono text-aegis-accent flex items-center gap-2">
          <Cpu size={14} />
          SWARM_TOPOLOGY — 39 NODES
        </h3>
        <span className="text-[10px] font-mono text-aegis-text/60">
          {done}/39 DONE · {active} ACTIVE
        </span>
      </div>

      <div className="grid grid-cols-13 gap-1">
        {agents.map(agent => <AgentCell key={agent.id} agent={agent} />)}
      </div>

      {status === 'STREAMING' && (
        <div className="mt-3 h-0.5 bg-aegis-border rounded overflow-hidden">
          <div
            className="h-full bg-aegis-accent transition-all duration-500 ease-out"
            style={{ width: `${Math.round((done / 39) * 100)}%` }}
          />
        </div>
      )}

      <CategoryLegend />
    </div>
  )
}

function AgentCell({ agent }: { agent: AgentNode }) {
  const base    = CATEGORY_COLOR[agent.category] ?? 'border-aegis-border text-aegis-text'
  const isIdle  = agent.state === 'idle'
  const isActive = agent.state === 'active'

  const cellCls = isIdle
    ? 'bg-aegis-bg border-aegis-border/40 text-aegis-text/30'
    : isActive
      ? `${base} animate-pulse-fast`
      : agent.state === 'done'
        ? `${base} opacity-70`
        : 'bg-red-900/30 border-red-500 text-red-400'

  return (
    <div
      title={`${agent.id} — ${agent.role} (${agent.category})`}
      className={`aspect-square rounded-sm border flex flex-col items-center justify-center cursor-default transition-all duration-200 ${cellCls}`}
    >
      <span className="text-[6px] font-mono leading-tight font-bold">
        {agent.id.split('-')[0]}
      </span>
      <span className="text-[5px] font-mono leading-tight opacity-70">
        {agent.id.split('-')[1]}
      </span>
    </div>
  )
}

const CATEGORIES = [
  ['revenue','Revenue'], ['marketing','Mktg'], ['sales','Sales'],
  ['product','Product'], ['engineering','Eng'], ['operations','Ops'],
  ['research','Research'], ['finance','Finance'], ['executive','Exec'],
  ['governance','Gov'], ['constitutional','Const'],
] as const

function CategoryLegend() {
  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {CATEGORIES.map(([cat, label]) => {
        const cls = CATEGORY_COLOR[cat] ?? ''
        const borderCls = cls.split(' ').find(c => c.startsWith('border-')) ?? 'border-aegis-border'
        const textCls   = cls.split(' ').find(c => c.startsWith('text-')) ?? 'text-aegis-text'
        return (
          <span key={cat} className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${borderCls} ${textCls} opacity-70`}>
            {label}
          </span>
        )
      })}
    </div>
  )
}
