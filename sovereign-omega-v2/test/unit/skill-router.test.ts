// Gate 164 — Skill Harness Phase 4: Orchestration Router Tests
// EPISTEMIC TIER: T2

import { describe, it, expect } from 'vitest'
import { buildSkillRecord } from '../../src/skill-harness/catalog.js'
import {
  recommendRouting,
  SkillRouterError,
  ROUTER_SCHEMA_VERSION,
  CONFIDENCE_FLOOR,
  SPECIALIST_THRESHOLD,
} from '../../src/skill-harness/router.js'
import type { AgentSkillProfile } from '../../src/skill-harness/router.js'

async function makeSkill(
  skill_id: string,
  domain: string,
  confidence: number,
  failure_rate = 0.1,
  recency_score = 0.9,
) {
  return buildSkillRecord({
    skill_id,
    name: skill_id,
    confidence,
    validated_runs: 30,
    failure_rate,
    recency_score,
    domain_affinity: [domain],
    dependencies: [],
    evidence_refs: [],
    last_validated: '2020-09-13T12:26:40.000Z',
    epistemic_tier: 'T2',
    primitive_mapping: 'SEQUENCE',
  })
}

async function profile(agent_id: string, skills: Awaited<ReturnType<typeof makeSkill>>[]): Promise<AgentSkillProfile> {
  return { agent_id, skills }
}

describe('SkillRouter — constants', () => {
  it('exports correct schema version', () => {
    expect(ROUTER_SCHEMA_VERSION).toBe('1.0.0')
  })

  it('CONFIDENCE_FLOOR is 0.3', () => {
    expect(CONFIDENCE_FLOOR).toBe(0.3)
  })

  it('SPECIALIST_THRESHOLD is 0.75', () => {
    expect(SPECIALIST_THRESHOLD).toBe(0.75)
  })
})

describe('SkillRouter — error handling', () => {
  it('throws SkillRouterError on empty profiles', async () => {
    await expect(recommendRouting('workflow', [])).rejects.toBeInstanceOf(SkillRouterError)
  })

  it('SkillRouterError is Error subclass', () => {
    expect(new SkillRouterError('x')).toBeInstanceOf(Error)
    expect(new SkillRouterError('x').name).toBe('SkillRouterError')
  })
})

describe('SkillRouter — ESCALATE_HUMAN', () => {
  it('all agents below confidence floor → ESCALATE_HUMAN', async () => {
    const s = await makeSkill('workflow_a', 'workflow', 0.1, 0.6, 0.4)
    const p = await profile('agent-a', [s])
    const result = await recommendRouting('workflow', [p])
    expect(result.decision).toBe('ESCALATE_HUMAN')
    expect(result.primary_agent_id).toBeNull()
  })

  it('ESCALATE_HUMAN → collaborators is empty', async () => {
    const s = await makeSkill('audit_a', 'audit', 0.05, 0.9, 0.2)
    const p = await profile('agent-low', [s])
    const result = await recommendRouting('audit', [p])
    expect(result.collaborators).toHaveLength(0)
  })

  it('no skills matching domain → ESCALATE_HUMAN (score=0)', async () => {
    const s = await makeSkill('replay_x', 'replay', 0.9, 0.05, 0.9)
    const p = await profile('agent-x', [s])
    const result = await recommendRouting('telemetry', [p])
    expect(result.decision).toBe('ESCALATE_HUMAN')
  })
})

describe('SkillRouter — DELEGATE_SPECIALIST', () => {
  it('high-confidence domain specialist → DELEGATE_SPECIALIST', async () => {
    const s = await makeSkill('workflow_spec', 'workflow', 0.9, 0.05, 0.95)
    const p = await profile('agent-spec', [s])
    const result = await recommendRouting('workflow', [p])
    expect(result.decision).toBe('DELEGATE_SPECIALIST')
    expect(result.primary_agent_id).toBe('agent-spec')
  })

  it('DELEGATE_SPECIALIST has non-empty reason mentioning specialist', async () => {
    // score = 0.9 * 0.95 * (1-0.03) = 0.828 >= SPECIALIST_THRESHOLD 0.75
    const s = await makeSkill('audit_spec', 'audit', 0.9, 0.03, 0.95)
    const p = await profile('agent-audit', [s])
    const result = await recommendRouting('audit', [p])
    expect(result.reason.toLowerCase()).toContain('specialist')
  })
})

describe('SkillRouter — ROUTE_TO_BEST', () => {
  it('moderate confidence above floor → ROUTE_TO_BEST', async () => {
    // score = 0.6 * 0.8 * (1 - 0.1) = 0.432 > CONFIDENCE_FLOOR 0.3, < SPECIALIST_THRESHOLD 0.75
    const s = await makeSkill('telemetry_a', 'telemetry', 0.6, 0.1, 0.8)
    const p = await profile('agent-tel', [s])
    const result = await recommendRouting('telemetry', [p])
    expect(result.decision).toBe('ROUTE_TO_BEST')
    expect(result.primary_agent_id).toBe('agent-tel')
  })

  it('ROUTE_TO_BEST selects highest-scoring agent', async () => {
    const s1 = await makeSkill('domain_a', 'domain', 0.5, 0.2, 0.7)
    const s2 = await makeSkill('domain_b', 'domain', 0.65, 0.1, 0.9)
    const p1 = await profile('agent-low', [s1])
    const p2 = await profile('agent-high', [s2])
    const result = await recommendRouting('domain', [p1, p2])
    expect(result.primary_agent_id).toBe('agent-high')
  })
})

describe('SkillRouter — COLLABORATE', () => {
  it('complementary-domain pair above floor → COLLABORATE', async () => {
    const s1 = await makeSkill('workflow_x', 'workflow', 0.6, 0.1, 0.8)
    const s2 = await makeSkill('audit_y', 'audit', 0.6, 0.1, 0.8)
    const p1 = await profile('agent-workflow', [s1])
    const p2 = await profile('agent-audit', [s2])
    const result = await recommendRouting('workflow', [p1, p2])
    expect(result.decision).toBe('COLLABORATE')
    expect(result.primary_agent_id).toBe('agent-workflow')
    expect(result.collaborators).toHaveLength(1)
    expect(result.collaborators[0]).toBe('agent-audit')
  })
})

describe('SkillRouter — structure', () => {
  it('routing_hash is 64-char hex', async () => {
    const s = await makeSkill('workflow_h', 'workflow', 0.9, 0.05, 0.9)
    const p = await profile('agent-h', [s])
    const result = await recommendRouting('workflow', [p])
    expect(result.routing_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(result.routing_hash)).toBe(true)
  })

  it('result is frozen', async () => {
    const s = await makeSkill('workflow_f', 'workflow', 0.9, 0.05, 0.9)
    const p = await profile('agent-f', [s])
    const result = await recommendRouting('workflow', [p])
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('is_replay_reconstructable is true', async () => {
    const s = await makeSkill('workflow_r', 'workflow', 0.9, 0.05, 0.9)
    const p = await profile('agent-r', [s])
    const result = await recommendRouting('workflow', [p])
    expect(result.is_replay_reconstructable).toBe(true)
  })

  it('schema_version is 1.0.0', async () => {
    const s = await makeSkill('workflow_v', 'workflow', 0.9, 0.05, 0.9)
    const p = await profile('agent-v', [s])
    const result = await recommendRouting('workflow', [p])
    expect(result.schema_version).toBe('1.0.0')
  })
})

describe('SkillRouter — determinism', () => {
  it('same inputs → identical routing_hash ×3', async () => {
    const s = await makeSkill('workflow_d', 'workflow', 0.6, 0.15, 0.8)
    const p = await profile('agent-d', [s])
    const [r1, r2, r3] = await Promise.all([
      recommendRouting('workflow', [p]),
      recommendRouting('workflow', [p]),
      recommendRouting('workflow', [p]),
    ])
    expect(r1.routing_hash).toBe(r2.routing_hash)
    expect(r2.routing_hash).toBe(r3.routing_hash)
  })

  it('different task_domain → different routing_hash', async () => {
    const s = await makeSkill('workflow_e', 'workflow', 0.6, 0.1, 0.8)
    const p = await profile('agent-e', [s])
    const r1 = await recommendRouting('workflow', [p])
    const r2 = await recommendRouting('audit', [p])
    expect(r1.routing_hash).not.toBe(r2.routing_hash)
  })

  it('confidence_score in [0, 1]', async () => {
    const s = await makeSkill('workflow_cs', 'workflow', 0.7, 0.1, 0.9)
    const p = await profile('agent-cs', [s])
    const result = await recommendRouting('workflow', [p])
    expect(result.confidence_score).toBeGreaterThanOrEqual(0)
    expect(result.confidence_score).toBeLessThanOrEqual(1)
  })
})
