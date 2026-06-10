import { ShieldCheck, ShieldAlert, ShieldX, TrendingUp } from 'lucide-react'
import type { CollaborationResult } from '../types.js'

interface Props { result: CollaborationResult }

const VERDICT_CONFIG = {
  APPROVED:   { icon: ShieldCheck, color: 'text-aegis-accent', border: 'border-aegis-accent', bg: 'bg-aegis-accent/10' },
  FLAG:       { icon: ShieldAlert,  color: 'text-aegis-warn',   border: 'border-aegis-warn',   bg: 'bg-aegis-warn/10'   },
  QUARANTINE: { icon: ShieldX,      color: 'text-aegis-err',    border: 'border-aegis-err',    bg: 'bg-aegis-err/10'    },
}

export function ConsensusReport({ result }: Props) {
  const vc = VERDICT_CONFIG[result.constitutional_audit.verdict]
  const Icon = vc.icon
  const arr = result.projection.first_year_arr_usd

  return (
    <div className={`bg-aegis-panel border rounded p-4 animate-fade-in ${vc.border}`}>
      <div className="flex items-center justify-between mb-3 border-b border-aegis-border pb-2">
        <div className="flex items-center gap-2">
          <Icon size={16} className={vc.color} />
          <span className="text-xs font-mono text-white font-bold tracking-widest">BFT_CONSENSUS_REPORT</span>
        </div>
        <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${vc.color} ${vc.border} ${vc.bg}`}>
          {result.constitutional_audit.verdict}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4 text-xs font-mono">
        <div>
          <span className="text-aegis-text/50 text-[10px] tracking-widest">CYCLE_ID</span>
          <div className="text-white">{result.cycle_id.slice(0, 16)}…</div>
        </div>
        <div>
          <span className="text-aegis-text/50 text-[10px] tracking-widest">DEPTS_ACTIVE</span>
          <div className="text-aegis-accent font-bold">{result.departments_collaborated} / 39</div>
        </div>
        <div>
          <span className="text-aegis-text/50 text-[10px] tracking-widest">CHAIN_VALID</span>
          <div className={result.chain_valid ? 'text-aegis-accent' : 'text-aegis-err'}>
            {result.chain_valid ? 'YES' : 'NO'}
          </div>
        </div>
        <div>
          <span className="text-aegis-text/50 text-[10px] tracking-widest">AUDIT_HASH</span>
          <div className="text-aegis-dim truncate">{result.audit_chain_hash.slice(0, 12)}…</div>
        </div>
      </div>

      {arr !== undefined && (
        <div className="flex items-center gap-2 bg-aegis-accent/5 border border-aegis-accent/30 rounded p-2.5 mb-4">
          <TrendingUp size={14} className="text-aegis-accent shrink-0" />
          <div className="text-xs font-mono">
            <span className="text-aegis-text/60">YEAR-1 ARR PROJECTION: </span>
            <span className="text-aegis-accent font-bold">
              ${arr.toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </span>
            {result.projection.tier && (
              <span className="text-aegis-text/50 ml-2">({result.projection.tier})</span>
            )}
          </div>
        </div>
      )}

      {result.projection.governed_note && (
        <p className="text-[11px] font-mono text-aegis-text/70 mb-4 leading-relaxed border-l-2 border-aegis-border pl-3">
          {result.projection.governed_note}
        </p>
      )}

      {result.constitutional_audit.concerns && result.constitutional_audit.concerns.length > 0 && (
        <div className="mb-4">
          <div className="text-[10px] font-mono text-aegis-warn/80 tracking-widest mb-1">CONCERNS</div>
          <ul className="space-y-1">
            {result.constitutional_audit.concerns.map((c, i) => (
              <li key={i} className="text-[11px] font-mono text-aegis-warn flex gap-2">
                <span className="text-aegis-warn/50">›</span>{c}
              </li>
            ))}
          </ul>
        </div>
      )}

      <details className="group">
        <summary className="text-[10px] font-mono text-aegis-text/50 cursor-pointer hover:text-aegis-text tracking-widest select-none">
          DEPT_ARTIFACTS ({result.artifacts.length}) ▸
        </summary>
        <div className="mt-2 space-y-2 max-h-64 overflow-y-auto terminal-scroll">
          {result.artifacts.map((a, i) => (
            <div key={i} className="text-[10px] font-mono">
              <span className="text-aegis-dim font-bold">{a.role}:</span>{' '}
              <span className="text-aegis-text/70">{a.output.slice(0, 200)}{a.output.length > 200 ? '…' : ''}</span>
            </div>
          ))}
        </div>
      </details>
    </div>
  )
}
