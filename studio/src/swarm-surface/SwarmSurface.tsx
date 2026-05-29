import type { TelemetrySnapshot } from '../types.js'

const FIB_SEQUENCE: readonly number[] = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 89, 89]
const PHI_THRESHOLD = (Math.sqrt(5) - 1) / 2

interface SwarmAgentRow {
  agent_id: string
  agent_type: string
  epistemic_tier: 'T0' | 'T1' | 'T2'
}

const AGENT_MANIFEST: readonly SwarmAgentRow[] = [
  { agent_id: 'workspace-1',    agent_type: 'WorkspaceMappingAgent',       epistemic_tier: 'T1' },
  { agent_id: 'research-1',     agent_type: 'ResearchAgent',                epistemic_tier: 'T1' },
  { agent_id: 'replay-audit-1', agent_type: 'ReplayAuditAgent',             epistemic_tier: 'T0' },
  { agent_id: 'telemetry-1',    agent_type: 'TelemetryAnalysisAgent',       epistemic_tier: 'T1' },
  { agent_id: 'ext-gov-1',      agent_type: 'ExtensionGovernanceAgent',     epistemic_tier: 'T1' },
  { agent_id: 'invariant-1',    agent_type: 'InvariantEnforcementAgent',    epistemic_tier: 'T0' },
  { agent_id: 'docs-1',         agent_type: 'DocumentationAgent',           epistemic_tier: 'T2' },
  { agent_id: 'env-1',          agent_type: 'EnvironmentAdaptationAgent',   epistemic_tier: 'T2' },
  { agent_id: 'sentinel-1',     agent_type: 'SentinelAgent',                epistemic_tier: 'T2' },
  { agent_id: 'arbitration-1',  agent_type: 'ArbitrationAgent',             epistemic_tier: 'T2' },
  { agent_id: 'memory-1',       agent_type: 'MemoryAgent',                  epistemic_tier: 'T2' },
  { agent_id: 'entropy-1',      agent_type: 'EntropySuppressionAgent',      epistemic_tier: 'T2' },
  { agent_id: 'guardian-1',     agent_type: 'ConstitutionalGuardianAgent',  epistemic_tier: 'T2' },
  { agent_id: 'federation-1',   agent_type: 'FederationRelayAgent',         epistemic_tier: 'T2' },
  { agent_id: 'simulation-1',   agent_type: 'SimulationAgent',              epistemic_tier: 'T2' },
]

const TIER_CLS: Record<string, string> = {
  T0: 'text-aegis-T0 bg-aegis-T0/10 border-aegis-T0/20',
  T1: 'text-aegis-T1 bg-aegis-T1/10 border-aegis-T1/20',
  T2: 'text-aegis-T2 bg-aegis-T2/10 border-aegis-T2/20',
}

interface Props { snapshot: TelemetrySnapshot | null }

function StatusCard({ label, value, sub, ok }: { label: string; value: string; sub: string; ok: boolean }) {
  return (
    <div className="bg-aegis-deep rounded-xl border border-aegis-border p-3">
      <p className="text-[9px] font-mono uppercase tracking-wider text-aegis-muted mb-1.5">{label}</p>
      <p className={`text-sm font-mono font-semibold ${ok ? 'text-aegis-text' : 'text-aegis-muted'}`}>{value}</p>
      <p className="text-[9px] text-aegis-disabled mt-1">{sub}</p>
    </div>
  )
}

export function SwarmSurface({ snapshot }: Props) {
  const online = snapshot !== null
  const loopIndex = snapshot ? (snapshot.epoch_sequence % FIB_SEQUENCE.length) + 1 : 0
  const fibInterval = loopIndex > 0 ? (FIB_SEQUENCE[loopIndex - 1] ?? 89) : 0
  const adaptiveRatio = snapshot ? (1 - snapshot.gate_acceptance_rate) : 0
  const entropyBounded = adaptiveRatio <= PHI_THRESHOLD
  const isAnchored = snapshot ? snapshot.pgcs_passes && snapshot.corruption_count === 0 : false

  return (
    <div className="p-5 space-y-5">
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold text-aegis-text">Swarm Surface</span>
        <span className="text-[10px] text-aegis-muted font-mono">read-only projection · no constitutional authority</span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <StatusCard label="Fibonacci Loop" value={online ? `F${loopIndex} = ${fibInterval}` : '—'} sub={online ? `loop index ${loopIndex}` : 'bridge offline'} ok={online} />
        <StatusCard label="Martingale" value={online ? (isAnchored ? 'ANCHORED' : 'DRIFTING') : '—'} sub={online ? `entropy_bounded=${String(entropyBounded)}` : 'bridge offline'} ok={isAnchored} />
        <StatusCard label="Swarm Agents" value={String(AGENT_MANIFEST.length)} sub="agents in manifest" ok={true} />
      </div>

      <div className="bg-aegis-deep rounded-xl border border-aegis-border p-4">
        <p className="text-[10px] font-mono uppercase tracking-wider text-aegis-muted mb-3">
          fibonacci pacing — F₁..F₁₁ (cap = 89)
        </p>
        <div className="flex items-end gap-1 h-16">
          {FIB_SEQUENCE.slice(0, 11).map((f, i) => {
            const active = online && i === loopIndex - 1
            const h = Math.round((f / 89) * 56)
            return (
              <div key={i} className="flex flex-col items-center gap-0.5 flex-1">
                <div
                  className={`rounded-sm w-full transition-all ${active ? 'bg-aegis-phi' : 'bg-aegis-border-strong'}`}
                  style={{ height: `${h}px` }}
                />
                <span className="text-[8px] text-aegis-disabled font-mono">{f}</span>
              </div>
            )
          })}
        </div>
      </div>

      <div className="bg-aegis-deep rounded-xl border border-aegis-border p-4">
        <p className="text-[10px] font-mono uppercase tracking-wider text-aegis-muted mb-3">
          adaptive ratio vs 1/φ threshold ({(PHI_THRESHOLD * 100).toFixed(1)}%)
        </p>
        <div className="flex items-center gap-3">
          <div className="flex-1 h-2 bg-aegis-surface rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${adaptiveRatio > PHI_THRESHOLD ? 'bg-aegis-T4' : 'bg-aegis-T0'}`}
              style={{ width: `${Math.min(adaptiveRatio * 100, 100)}%` }}
            />
          </div>
          <span className="text-[10px] font-mono text-aegis-secondary w-24 text-right">
            {(adaptiveRatio * 100).toFixed(1)}% / {(PHI_THRESHOLD * 100).toFixed(1)}%
          </span>
        </div>
        <p className={`text-[10px] mt-2 font-mono ${entropyBounded ? 'text-aegis-T0' : 'text-aegis-T4'}`}>
          {entropyBounded
            ? 'entropy_bounded=true — mutation authority preserved'
            : 'entropy_bounded=false — mutation authority SUSPENDED'}
        </p>
      </div>

      <div className="bg-aegis-deep rounded-xl border border-aegis-border overflow-hidden">
        <div className="px-4 py-2.5 border-b border-aegis-border">
          <p className="text-[10px] font-mono uppercase tracking-wider text-aegis-muted">
            agent manifest — {AGENT_MANIFEST.length} agents
          </p>
        </div>
        <div className="overflow-auto max-h-52">
          <table className="w-full text-[10px]">
            <thead className="sticky top-0 bg-aegis-deep">
              <tr className="border-b border-aegis-border">
                <th className="text-left px-4 py-2 font-mono text-aegis-muted">agent_id</th>
                <th className="text-left px-4 py-2 font-mono text-aegis-muted">type</th>
                <th className="text-center px-4 py-2 font-mono text-aegis-muted">tier</th>
              </tr>
            </thead>
            <tbody>
              {AGENT_MANIFEST.map((row, i) => (
                <tr
                  key={row.agent_id}
                  className={`hover:bg-aegis-surface/40 transition-colors ${
                    i < AGENT_MANIFEST.length - 1 ? 'border-b border-aegis-border/40' : ''
                  }`}
                >
                  <td className="px-4 py-2 font-mono text-aegis-secondary">{row.agent_id}</td>
                  <td className="px-4 py-2 text-aegis-muted truncate max-w-[160px]">{row.agent_type}</td>
                  <td className="px-4 py-2 text-center">
                    <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${TIER_CLS[row.epistemic_tier] ?? ''}`}>
                      {row.epistemic_tier}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
