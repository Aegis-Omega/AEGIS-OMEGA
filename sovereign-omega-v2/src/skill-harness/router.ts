// ============================================================
// Skill Harness — Phase 4 Orchestration-Aware Routing
// EPISTEMIC TIER: T2 · Gate 164
//
// Routes tasks to best-qualified agents using 5 skill signals:
//   competency confidence · specialization domain · failure history
//   domain affinity · recency score
//
// Routing decisions:
//   ROUTE_TO_BEST       — highest-scoring agent in domain
//   DELEGATE_SPECIALIST — domain expert (high affinity + confidence)
//   ESCALATE_HUMAN      — all agents below CONFIDENCE_FLOOR
//   COLLABORATE         — complementary-affinity pair both above floor
//
// Agent score = mean_confidence × recency_score × (1 − failure_rate)
// Averaged over skills matching the requested domain.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { hashValue } from '../core/hashing.js'
import type { SHA256Hex } from '../core/types.js'
import type { SkillRecord } from './types.js'

export const ROUTER_SCHEMA_VERSION = '1.0.0' as const

export const CONFIDENCE_FLOOR = 0.3           // below → ESCALATE_HUMAN
export const SPECIALIST_THRESHOLD = 0.75      // above + domain match → DELEGATE_SPECIALIST

export interface AgentSkillProfile {
  readonly agent_id: string
  readonly skills: readonly SkillRecord[]
}

export type RoutingDecision =
  | 'ROUTE_TO_BEST'
  | 'DELEGATE_SPECIALIST'
  | 'ESCALATE_HUMAN'
  | 'COLLABORATE'

export interface RoutingRecommendation {
  readonly task_domain: string
  readonly decision: RoutingDecision
  readonly primary_agent_id: string | null
  readonly collaborators: readonly string[]
  readonly confidence_score: number
  readonly reason: string
  readonly routing_hash: SHA256Hex
  readonly schema_version: typeof ROUTER_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class SkillRouterError extends Error {
  override readonly name = 'SkillRouterError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

// Skills relevant to a domain: domain_affinity includes domain OR skill_id contains domain.
function domainSkills(skills: readonly SkillRecord[], domain: string): readonly SkillRecord[] {
  const lc = domain.toLowerCase()
  return skills.filter(s =>
    s.domain_affinity.some(d => d.toLowerCase().includes(lc)) ||
    s.skill_id.toLowerCase().includes(lc)
  )
}

// Agent composite score for a domain (0.0–1.0).
function agentScore(profile: AgentSkillProfile, domain: string): number {
  const relevant = domainSkills(profile.skills, domain)
  if (relevant.length === 0) return 0
  const avg = relevant.reduce((sum, s) => sum + s.confidence * s.recency_score * (1 - s.failure_rate), 0) / relevant.length
  return avg
}

// Whether an agent has deep domain affinity (not just keyword match).
function hasDeepAffinity(profile: AgentSkillProfile, domain: string): boolean {
  const lc = domain.toLowerCase()
  return profile.skills.some(s => s.domain_affinity.some(d => d.toLowerCase() === lc))
}

// Overall average skill score for an agent (all skills, not filtered by domain).
function generalScore(profile: AgentSkillProfile): number {
  if (profile.skills.length === 0) return 0
  return profile.skills.reduce((sum, s) => sum + s.confidence * s.recency_score * (1 - s.failure_rate), 0) / profile.skills.length
}

// Set of all domain affinities for an agent.
function affinitySet(profile: AgentSkillProfile): Set<string> {
  const out = new Set<string>()
  for (const s of profile.skills) for (const d of s.domain_affinity) out.add(d.toLowerCase())
  return out
}

// Are two affinity sets complementary (no overlap)?
function complementary(a: Set<string>, b: Set<string>): boolean {
  for (const x of a) if (b.has(x)) return false
  return true
}

export async function recommendRouting(
  task_domain: string,
  profiles: readonly AgentSkillProfile[],
): Promise<RoutingRecommendation> {
  if (profiles.length === 0) {
    throw new SkillRouterError(`No agent profiles supplied for domain '${task_domain}'`)
  }

  const scored = profiles
    .map(p => ({ profile: p, score: agentScore(p, task_domain) }))
    .sort((a, b) => b.score - a.score)

  const best = scored[0]!
  const bestId = best.profile.agent_id
  const bestScore = best.score

  let decision: RoutingDecision
  let primary: string | null
  let collaborators: readonly string[]
  let reason: string

  if (bestScore < CONFIDENCE_FLOOR) {
    // All agents are below the confidence floor
    decision = 'ESCALATE_HUMAN'
    primary = null
    collaborators = []
    reason = `Best agent score ${bestScore.toFixed(3)} is below confidence floor ${CONFIDENCE_FLOOR}`
  } else if (bestScore >= SPECIALIST_THRESHOLD && hasDeepAffinity(best.profile, task_domain)) {
    // High-confidence domain specialist
    decision = 'DELEGATE_SPECIALIST'
    primary = bestId
    collaborators = []
    reason = `Agent '${bestId}' is a domain specialist for '${task_domain}' (score ${bestScore.toFixed(3)})`
  } else if (profiles.length >= 2) {
    // Find a collaborator: any other agent with general score >= floor and complementary affinity
    const others = profiles.filter(p => p.agent_id !== bestId)
    const aSet = affinitySet(best.profile)
    const collab = others.find(p => generalScore(p) >= CONFIDENCE_FLOOR && complementary(aSet, affinitySet(p)))
    if (collab !== undefined) {
      decision = 'COLLABORATE'
      primary = bestId
      collaborators = [collab.agent_id]
      reason = `Agents '${bestId}' and '${collab.agent_id}' have complementary domains for '${task_domain}'`
    } else {
      decision = 'ROUTE_TO_BEST'
      primary = bestId
      collaborators = []
      reason = `Agent '${bestId}' is best qualified for '${task_domain}' (score ${bestScore.toFixed(3)})`
    }
  } else {
    decision = 'ROUTE_TO_BEST'
    primary = bestId
    collaborators = []
    reason = `Agent '${bestId}' is best qualified for '${task_domain}' (score ${bestScore.toFixed(3)})`
  }

  const routing_hash = await hashValue({
    task_domain,
    decision,
    primary_agent_id: primary ?? 'none',
    confidence_score: bestScore.toString(),
  }) as SHA256Hex

  return deepFreeze({
    task_domain,
    decision,
    primary_agent_id: primary,
    collaborators,
    confidence_score: bestScore,
    reason,
    routing_hash,
    schema_version: ROUTER_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}
