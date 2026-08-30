import { useEffect, useState } from 'react'
import { SkillCard } from './SkillCard.js'

interface TelemetryState {
  fibonacci_loop_index: number
  fibonacci_interval: number
  active_agents: number
  convergence_reached: boolean
  epoch_hash: string | null
}

interface SkillEntry {
  skillId: string
  name: string
  confidence: number
  domains: string[]
  source: string
  tier: string
}

const INITIAL_SKILLS: readonly SkillEntry[] = [
  { skillId: 'git_workflow', name: 'git-workflow', confidence: 0.91, domains: ['version-control', 'collaboration'], source: 'obra/superpowers', tier: 'T1' },
  { skillId: 'code_review', name: 'code-review', confidence: 0.85, domains: ['quality', 'governance'], source: 'obra/superpowers', tier: 'T1' },
  { skillId: 'ui_design', name: 'ui-design-pro', confidence: 0.78, domains: ['design', 'ux'], source: 'nextlevelbuilder/ui-ux-pro-max-skill', tier: 'T2' },
  { skillId: 'deploy_pipeline', name: 'deploy-pipeline', confidence: 0.88, domains: ['deployment', 'operations'], source: 'vercel-labs/agent-skills', tier: 'T1' },
  { skillId: 'research_synthesis', name: 'research-synthesis', confidence: 0.72, domains: ['research', 'analysis'], source: 'glittercowboy/get-shit-done', tier: 'T2' },
  { skillId: 'replay_audit', name: 'replay-audit', confidence: 0.95, domains: ['constitutional', 'audit'], source: 'sovereign-omega-v2', tier: 'T0' },
  { skillId: 'telemetry_analysis', name: 'telemetry-analysis', confidence: 0.82, domains: ['telemetry', 'monitoring'], source: 'sovereign-omega-v2', tier: 'T1' },
  { skillId: 'n8n_automation', name: 'n8n-automation', confidence: 0.67, domains: ['automation', 'workflow'], source: 'nusquama/n8nworkflows.xyz', tier: 'T2' },
]

const ALL_DOMAINS = Array.from(new Set(INITIAL_SKILLS.flatMap(s => s.domains))).sort()

const BRIDGE_URL = (import.meta.env.VITE_BRIDGE_URL as string | undefined) ?? 'http://localhost:7890'

export function SkillMarketplace() {
  const [installStatuses, setInstallStatuses] = useState<Record<string, 'idle' | 'installing' | 'installed' | 'rejected'>>({})
  const [filterDomain, setFilterDomain] = useState<string>('all')
  const [telemetry, setTelemetry] = useState<TelemetryState | null>(null)

  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const res = await fetch(`${BRIDGE_URL}/telemetry`, { signal: AbortSignal.timeout(2000) })
        if (res.ok && active) {
          const data = await res.json() as Partial<TelemetryState>
          setTelemetry({
            fibonacci_loop_index: data.fibonacci_loop_index ?? 0,
            fibonacci_interval: data.fibonacci_interval ?? 1,
            active_agents: data.active_agents ?? 0,
            convergence_reached: data.convergence_reached ?? false,
            epoch_hash: data.epoch_hash ?? null,
          })
        }
      } catch { /* bridge offline */ }
    }
    void poll()
    const id = setInterval(() => void poll(), 5000)
    return () => { active = false; clearInterval(id) }
  }, [])

  const handleInstall = async (skillId: string) => {
    setInstallStatuses(prev => ({ ...prev, [skillId]: 'installing' }))
    try {
      const res = await fetch(`${BRIDGE_URL}/event`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'SKILL_INSTALL_REQUEST',
          payload: { skill_id: skillId, agent_id: 'cockpit-operator' },
          determinism_class: 'bounded',
          capability_scope: 'EMIT_EVENT',
          timestamp_ms: Date.now(),
        }),
        signal: AbortSignal.timeout(3000),
      })
      setInstallStatuses(prev => ({ ...prev, [skillId]: res.ok ? 'installed' : 'rejected' }))
    } catch {
      setInstallStatuses(prev => ({ ...prev, [skillId]: 'rejected' }))
    }
  }

  const visibleSkills = filterDomain === 'all'
    ? INITIAL_SKILLS
    : INITIAL_SKILLS.filter(s => s.domains.includes(filterDomain))

  const installedSkills = INITIAL_SKILLS.filter(s => installStatuses[s.skillId] === 'installed')

  return (
    <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2 border-b border-aegis-border bg-aegis-surface/50 flex items-center justify-between">
        <span className="text-xs font-mono text-aegis-muted">skill marketplace</span>
        <div className="flex items-center gap-3">
          {telemetry ? (
            <>
              <span className="text-[10px] text-aegis-muted">
                loop <span className="text-blue-400">{telemetry.fibonacci_loop_index}</span>
                {' '}·{' '}
                F<sub>{telemetry.fibonacci_loop_index}</sub>
                =<span className="text-blue-400">{telemetry.fibonacci_interval}</span>
              </span>
              <span className="text-[10px] text-aegis-muted">
                agents <span className={telemetry.active_agents > 0 ? 'text-green-400' : 'text-aegis-muted'}>{telemetry.active_agents}</span>
              </span>
              <span className={`text-[10px] ${telemetry.convergence_reached ? 'text-green-400' : 'text-aegis-muted'}`}>
                {telemetry.convergence_reached ? '⊕ converged' : '○ pending'}
              </span>
            </>
          ) : (
            <span className="text-[10px] text-aegis-muted">bridge offline</span>
          )}
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Catalog panel */}
        <div className="flex-1 flex flex-col overflow-hidden border-r border-aegis-border">
          {/* Domain filter */}
          <div className="px-3 py-2 border-b border-aegis-border flex gap-1.5 flex-wrap">
            <button
              onClick={() => setFilterDomain('all')}
              className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${filterDomain === 'all' ? 'border-blue-500 text-blue-400' : 'border-aegis-border text-aegis-muted hover:border-aegis-text'}`}
            >
              all
            </button>
            {ALL_DOMAINS.map(d => (
              <button
                key={d}
                onClick={() => setFilterDomain(d)}
                className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${filterDomain === d ? 'border-blue-500 text-blue-400' : 'border-aegis-border text-aegis-muted hover:border-aegis-text'}`}
              >
                {d}
              </button>
            ))}
          </div>

          {/* Skill cards */}
          <div className="flex-1 overflow-y-auto p-3 grid grid-cols-1 gap-2">
            {visibleSkills.map(skill => (
              <SkillCard
                key={skill.skillId}
                skillId={skill.skillId}
                name={skill.name}
                confidence={skill.confidence}
                domains={skill.domains}
                source={skill.source}
                tier={skill.tier}
                onInstall={handleInstall}
                installStatus={installStatuses[skill.skillId] ?? 'idle'}
              />
            ))}
          </div>
        </div>

        {/* Installed panel */}
        <div className="w-56 flex flex-col shrink-0">
          <div className="px-3 py-2 border-b border-aegis-border">
            <span className="text-[10px] font-mono text-aegis-muted">
              active skills ({installedSkills.length})
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
            {installedSkills.length === 0 ? (
              <p className="text-[10px] text-aegis-muted/50 px-1 pt-2">No skills installed yet.</p>
            ) : (
              installedSkills.map(skill => (
                <div key={skill.skillId} className="px-2 py-1.5 rounded bg-aegis-surface/40 border border-aegis-border/50">
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-[10px] font-mono text-aegis-text truncate">{skill.name}</span>
                    <span className="text-[9px] text-green-400 shrink-0">✓</span>
                  </div>
                  <span className="text-[9px] text-aegis-muted">{skill.tier}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
