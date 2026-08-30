// Gate 167 — Skill Harness Phase 5 Integration: Collaboration + Full Pipeline
// EPISTEMIC TIER: T2

import { describe, it, expect } from 'vitest'
import { buildSkillRecord } from '../../src/skill-harness/catalog.js'
import { processEvidence } from '../../src/skill-harness/telemetry-engine.js'
import type { SkillEvidence } from '../../src/skill-harness/telemetry-engine.js'
import { inferSkillConfidence } from '../../src/skill-harness/inference-engine.js'
import { decaySkill } from '../../src/skill-harness/decay.js'
import { recommendRouting } from '../../src/skill-harness/router.js'
import {
  proposeSkillTransfer,
  applySkillTransfer,
  peerConsensus,
} from '../../src/skill-harness/collaboration.js'
import type { PeerProfile } from '../../src/skill-harness/collaboration.js'
import type { AgentSkillProfile } from '../../src/skill-harness/router.js'
import type { SequenceNumber } from '../../src/core/types.js'

const EPOCH_TS = 1_600_000_000_000
const DAY_MS = 86_400_000

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

async function expertSkill(skill_id: string, domain: string) {
  return buildSkillRecord({
    skill_id, name: skill_id,
    confidence: 0.9, validated_runs: 50, failure_rate: 0.05, recency_score: 0.95,
    domain_affinity: [domain], dependencies: [], evidence_refs: [],
    last_validated: new Date(EPOCH_TS).toISOString(),
    epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
  })
}

describe('Transfer then route', () => {
  it('transferred skill enables routing that was previously ESCALATE_HUMAN', async () => {
    // Target agent starts with no skills for workflow domain
    const emptySkill = await buildSkillRecord({
      skill_id: 'workflow_empty', name: 'Empty',
      confidence: 0.1, validated_runs: 0, failure_rate: 0.5, recency_score: 0.3,
      domain_affinity: ['workflow'], dependencies: [], evidence_refs: [],
      last_validated: new Date(EPOCH_TS).toISOString(),
      epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
    })
    const before: AgentSkillProfile = { agent_id: 'agent-dst', skills: [emptySkill] }
    const beforeResult = await recommendRouting('workflow', [before])
    expect(beforeResult.decision).toBe('ESCALATE_HUMAN')

    // Expert agent transfers to target
    const expert = await expertSkill('workflow_orchestration', 'workflow')
    const proposal = await proposeSkillTransfer(expert, 'agent-src', 'agent-dst', seq(1))
    const transfer = await applySkillTransfer(proposal, expert)

    const after: AgentSkillProfile = { agent_id: 'agent-dst', skills: [transfer.transferred_skill] }
    const afterResult = await recommendRouting('workflow', [after])
    // Transferred confidence = 0.9 × 0.7 = 0.63 > CONFIDENCE_FLOOR 0.3
    expect(['ROUTE_TO_BEST', 'DELEGATE_SPECIALIST']).toContain(afterResult.decision)
    expect(afterResult.confidence_score).toBeGreaterThan(beforeResult.confidence_score)
  })
})

describe('Peer consensus + inference composition', () => {
  it('consensus confidence feeds routing decision consistently', async () => {
    const s1 = await expertSkill('workflow_orchestration', 'workflow')
    const s2 = await buildSkillRecord({
      skill_id: 'workflow_orchestration', name: 'Workflow',
      confidence: 0.7, validated_runs: 20, failure_rate: 0.1, recency_score: 0.85,
      domain_affinity: ['workflow'], dependencies: [], evidence_refs: [],
      last_validated: new Date(EPOCH_TS).toISOString(),
      epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
    })

    const profiles: PeerProfile[] = [
      { agent_id: 'agent-a', skill: s1 },
      { agent_id: 'agent-b', skill: s2 },
    ]
    const consensus = await peerConsensus(profiles)
    expect(consensus.consensus_confidence).toBeGreaterThan(0.3)
    expect(consensus.skill_id).toBe('workflow_orchestration')
    expect(consensus.agent_count).toBe(2)
  })

  it('inference on transferred skill accumulates evidence correctly', async () => {
    const source = await expertSkill('audit_trail', 'audit')
    const proposal = await proposeSkillTransfer(source, 'agent-src', 'agent-dst', seq(1))
    const transfer = await applySkillTransfer(proposal, source)

    // Transferred skill starts with 0 runs — evidence increases confidence
    expect(transfer.transferred_skill.validated_runs).toBe(0)

    const batch: SkillEvidence[] = Array.from({ length: 5 }, (_, i) => ({
      skill_id: 'audit_trail', agent_id: 'agent-dst', is_success: true,
      loop_hash: ('b'.repeat(64)) as ReturnType<typeof String>,
      sequence: seq(i + 1), timestamp_ms: EPOCH_TS + (i + 1) * 1000,
    } as SkillEvidence))

    const inferred = await inferSkillConfidence(transfer.transferred_skill, batch)
    expect(inferred.updated_skill.validated_runs).toBe(5)
    expect(inferred.updated_skill.confidence).toBeGreaterThan(transfer.transferred_skill.confidence)
  })
})

describe('Transfer → decay → consensus pipeline', () => {
  it('decay reduces transferred skill confidence; consensus reflects both agents', async () => {
    const source = await expertSkill('telemetry_analysis', 'telemetry')
    const proposal = await proposeSkillTransfer(source, 'src', 'dst', seq(1))
    const transfer = await applySkillTransfer(proposal, source)

    // Give the transferred skill some runs before decay
    let updated = transfer.transferred_skill
    for (let i = 1; i <= 10; i++) {
      const ev: SkillEvidence = {
        skill_id: 'telemetry_analysis', agent_id: 'dst', is_success: true,
        loop_hash: ('d'.repeat(64)) as ReturnType<typeof String>,
        sequence: seq(i), timestamp_ms: EPOCH_TS + i * 1000,
      } as SkillEvidence
      const r = await processEvidence(updated, ev)
      updated = r.updated_record
    }

    // Decay the updated transferred skill by 30 days
    const decayed = await decaySkill(updated, EPOCH_TS + 30 * DAY_MS)
    expect(decayed.was_decayed).toBe(true)
    expect(decayed.updated_skill.confidence).toBeLessThan(source.confidence)

    const profiles: PeerProfile[] = [
      { agent_id: 'src', skill: source },
      { agent_id: 'dst', skill: decayed.updated_skill },
    ]
    const consensus = await peerConsensus(profiles)

    // Consensus is weighted between expert (0.9, runs=50) and decayed (lower, runs=10)
    expect(consensus.consensus_confidence).toBeLessThan(source.confidence)
    expect(consensus.consensus_confidence).toBeGreaterThan(decayed.updated_skill.confidence)
  })
})

describe('Full pipeline determinism', () => {
  it('propose → apply → infer → route ×3 → identical routing_hash', async () => {
    const source = await expertSkill('workflow_orchestration', 'workflow')

    const run = async () => {
      const proposal = await proposeSkillTransfer(source, 'src', 'dst', seq(1))
      const transfer = await applySkillTransfer(proposal, source)
      const inferred = await inferSkillConfidence(transfer.transferred_skill, [])
      const profile: AgentSkillProfile = { agent_id: 'dst', skills: [inferred.updated_skill] }
      return recommendRouting('workflow', [profile])
    }

    const [r1, r2, r3] = await Promise.all([run(), run(), run()])
    expect(r1.routing_hash).toBe(r2.routing_hash)
    expect(r2.routing_hash).toBe(r3.routing_hash)
  })

  it('telemetry on transferred skill then decay preserves evidence_refs', async () => {
    const source = await expertSkill('replay_audit', 'audit')
    const proposal = await proposeSkillTransfer(source, 'src', 'dst', seq(1))
    const transfer = await applySkillTransfer(proposal, source)

    const ev: SkillEvidence = {
      skill_id: 'replay_audit', agent_id: 'dst', is_success: true,
      loop_hash: ('c'.repeat(64)) as ReturnType<typeof String>,
      sequence: seq(2), timestamp_ms: EPOCH_TS + 2000,
    } as SkillEvidence
    const telResult = await processEvidence(transfer.transferred_skill, ev)
    expect(telResult.updated_record.evidence_refs).toContain('c'.repeat(64))

    const decayed = await decaySkill(telResult.updated_record, EPOCH_TS + 45 * DAY_MS)
    expect(decayed.updated_skill.evidence_refs).toContain('c'.repeat(64))
    expect(decayed.was_decayed).toBe(true)
  })
})
