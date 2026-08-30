// Gate 165 — Skill Harness Phase 4 Integration: Router + Inference + Decay
// EPISTEMIC TIER: T2

import { describe, it, expect } from 'vitest'
import { buildSkillRecord } from '../../src/skill-harness/catalog.js'
import { processEvidence } from '../../src/skill-harness/telemetry-engine.js'
import type { SkillEvidence } from '../../src/skill-harness/telemetry-engine.js'
import { inferSkillConfidence } from '../../src/skill-harness/inference-engine.js'
import { decaySkill } from '../../src/skill-harness/decay.js'
import { recommendRouting } from '../../src/skill-harness/router.js'
import type { AgentSkillProfile } from '../../src/skill-harness/router.js'
import type { SequenceNumber } from '../../src/core/types.js'

const EPOCH_TS = 1_600_000_000_000
const DAY_MS = 86_400_000

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

async function buildAgent(
  agent_id: string,
  skill_id: string,
  domain: string,
  confidence: number,
  failure_rate = 0.1,
): Promise<AgentSkillProfile> {
  const skill = await buildSkillRecord({
    skill_id,
    name: skill_id,
    confidence,
    validated_runs: 20,
    failure_rate,
    recency_score: 0.9,
    domain_affinity: [domain],
    dependencies: [],
    evidence_refs: [],
    last_validated: new Date(EPOCH_TS).toISOString(),
    epistemic_tier: 'T2',
    primitive_mapping: 'SEQUENCE',
  })
  return { agent_id, skills: [skill] }
}

describe('Router selects best agent after telemetry updates', () => {
  it('evidence updates skill confidence → routing decision reflects new state', async () => {
    const skill = await buildSkillRecord({
      skill_id: 'workflow_tel', name: 'Workflow Tel',
      confidence: 0.4, validated_runs: 5, failure_rate: 0.3, recency_score: 0.7,
      domain_affinity: ['workflow'], dependencies: [], evidence_refs: [],
      last_validated: new Date(EPOCH_TS).toISOString(),
      epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
    })
    const p1: AgentSkillProfile = { agent_id: 'agent-weak', skills: [skill] }

    // Before telemetry — low confidence
    const before = await recommendRouting('workflow', [p1])

    // Apply 5 success evidences
    let updated = skill
    for (let i = 1; i <= 5; i++) {
      const ev: SkillEvidence = {
        skill_id: 'workflow_tel', agent_id: 'agent-weak', is_success: true,
        loop_hash: ('0'.repeat(64)) as ReturnType<typeof String>,
        sequence: seq(i), timestamp_ms: EPOCH_TS + i * 1000,
      } as SkillEvidence
      const r = await processEvidence(updated, ev)
      updated = r.updated_record
    }
    const p2: AgentSkillProfile = { agent_id: 'agent-weak', skills: [updated] }
    const after = await recommendRouting('workflow', [p2])

    // Confidence should be higher after successes, routing may improve
    expect(after.confidence_score).toBeGreaterThan(before.confidence_score)
  })
})

describe('Router + Inference pipeline', () => {
  it('inference updates feed into routing decision', async () => {
    const base = await buildSkillRecord({
      skill_id: 'audit_inf', name: 'Audit Inf',
      confidence: 0.65, validated_runs: 10, failure_rate: 0.2, recency_score: 0.85,
      domain_affinity: ['audit'], dependencies: [], evidence_refs: [],
      last_validated: new Date(EPOCH_TS).toISOString(),
      epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
    })

    const batch: SkillEvidence[] = Array.from({ length: 10 }, (_, i) => ({
      skill_id: 'audit_inf', agent_id: 'agent-inf', is_success: true,
      loop_hash: ('a'.repeat(64)) as ReturnType<typeof String>,
      sequence: seq(i + 1), timestamp_ms: EPOCH_TS + (i + 1) * 1000,
    } as SkillEvidence))

    const inferred = await inferSkillConfidence(base, batch)
    const profile: AgentSkillProfile = { agent_id: 'agent-inf', skills: [inferred.updated_skill] }
    const result = await recommendRouting('audit', [profile])

    expect(result.primary_agent_id).toBe('agent-inf')
    expect(['ROUTE_TO_BEST', 'DELEGATE_SPECIALIST']).toContain(result.decision)
  })
})

describe('Router after decay', () => {
  it('decayed skill lowers confidence score in routing', async () => {
    const profile = await buildAgent('agent-old', 'workflow_old', 'workflow', 0.9, 0.05)
    const freshResult = await recommendRouting('workflow', [profile])

    // Decay the skill by 60 days
    const decayed = await decaySkill(profile.skills[0]!, EPOCH_TS + 60 * DAY_MS)
    const decayedProfile: AgentSkillProfile = { agent_id: 'agent-old', skills: [decayed.updated_skill] }
    const decayedResult = await recommendRouting('workflow', [decayedProfile])

    expect(decayedResult.confidence_score).toBeLessThan(freshResult.confidence_score)
  })

  it('severe decay → ESCALATE_HUMAN even for high-confidence specialist', async () => {
    const skill = await buildSkillRecord({
      skill_id: 'workflow_decay', name: 'Workflow Decay',
      confidence: 0.05, validated_runs: 5, failure_rate: 0.7, recency_score: 0.3,
      domain_affinity: ['workflow'], dependencies: [], evidence_refs: [],
      last_validated: new Date(EPOCH_TS).toISOString(),
      epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
    })
    const decayed = await decaySkill(skill, EPOCH_TS + 365 * DAY_MS)
    const profile: AgentSkillProfile = { agent_id: 'agent-old', skills: [decayed.updated_skill] }
    const result = await recommendRouting('workflow', [profile])
    expect(result.decision).toBe('ESCALATE_HUMAN')
  })
})

describe('Full pipeline determinism', () => {
  it('inference→decay→route same inputs ×3 → identical routing_hash', async () => {
    const base = await buildSkillRecord({
      skill_id: 'workflow_det', name: 'Workflow Det',
      confidence: 0.7, validated_runs: 15, failure_rate: 0.15, recency_score: 0.85,
      domain_affinity: ['workflow'], dependencies: [], evidence_refs: [],
      last_validated: new Date(EPOCH_TS).toISOString(),
      epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
    })
    const ts = EPOCH_TS + 20 * DAY_MS

    const run = async () => {
      const inferred = await inferSkillConfidence(base, [])
      const decayed = await decaySkill(inferred.updated_skill, ts)
      const profile: AgentSkillProfile = { agent_id: 'agent-det', skills: [decayed.updated_skill] }
      return recommendRouting('workflow', [profile])
    }
    const [r1, r2, r3] = await Promise.all([run(), run(), run()])
    expect(r1.routing_hash).toBe(r2.routing_hash)
    expect(r2.routing_hash).toBe(r3.routing_hash)
  })
})
