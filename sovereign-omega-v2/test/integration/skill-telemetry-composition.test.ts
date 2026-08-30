// Gate 159 — Skill Harness Phase 2: Telemetry composition with RalphExecutor
// EPISTEMIC TIER: T2

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { RalphExecutor } from '../../src/agents/executor/loop.js'
import { buildSkillRecord } from '../../src/skill-harness/catalog.js'
import { processEvidence } from '../../src/skill-harness/telemetry-engine.js'
import type { SkillEvidence } from '../../src/skill-harness/telemetry-engine.js'

const BASE_TS = 1_600_000_000_000
const FAKE_CONTEXT = 'c'.repeat(64) as SHA256Hex
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

async function freshWorkflowSkill() {
  return buildSkillRecord({
    skill_id: 'workflow_orchestration',
    name: 'Workflow Orchestration',
    confidence: 0.6,
    validated_runs: 10,
    failure_rate: 0.2,
    recency_score: 0.6,
    domain_affinity: ['workflow', 'orchestration'],
    dependencies: [],
    evidence_refs: [],
    last_validated: '2026-01-01T00:00:00.000Z',
    epistemic_tier: 'T2',
    primitive_mapping: 'SEQUENCE',
  })
}

describe('RalphExecutor → SkillTelemetryEngine composition', () => {
  it('loop_hash from RalphLoopRecord feeds into evidence_refs', async () => {
    let executor = RalphExecutor.create('agent-001')
    const { record } = await executor.executeLoop(FAKE_CONTEXT, seq(1))

    const skill = await freshWorkflowSkill()
    const evidence: SkillEvidence = {
      skill_id: 'workflow_orchestration',
      agent_id: 'agent-001',
      is_success: record.is_anchored,
      loop_hash: record.loop_hash,
      sequence: seq(1),
      timestamp_ms: BASE_TS,
    }

    const result = await processEvidence(skill, evidence)
    expect(result.updated_record.evidence_refs).toContain(record.loop_hash)
  })

  it('5-loop chain: confidence monotonically increases on all-success', async () => {
    let executor = RalphExecutor.create('agent-002')
    let skill = await freshWorkflowSkill()
    const confidences: number[] = [skill.confidence]

    for (let i = 1; i <= 5; i++) {
      const { executor: next, record } = await executor.executeLoop(FAKE_CONTEXT, seq(i))
      executor = next
      const evidence: SkillEvidence = {
        skill_id: 'workflow_orchestration',
        agent_id: 'agent-002',
        is_success: true,
        loop_hash: record.loop_hash,
        sequence: seq(i),
        timestamp_ms: BASE_TS + i,
      }
      const result = await processEvidence(skill, evidence)
      skill = result.updated_record
      confidences.push(skill.confidence)
    }

    // Every run was success → each confidence strictly greater than previous
    for (let i = 1; i < confidences.length; i++) {
      expect(confidences[i]!).toBeGreaterThan(confidences[i - 1]!)
    }
  })

  it('validated_runs matches loop count after N rounds', async () => {
    let executor = RalphExecutor.create('agent-003')
    let skill = await freshWorkflowSkill()
    const initialRuns = skill.validated_runs

    for (let i = 1; i <= 3; i++) {
      const { executor: next, record } = await executor.executeLoop(FAKE_CONTEXT, seq(i))
      executor = next
      const result = await processEvidence(skill, {
        skill_id: 'workflow_orchestration',
        agent_id: 'agent-003',
        is_success: true,
        loop_hash: record.loop_hash,
        sequence: seq(i),
        timestamp_ms: BASE_TS,
      })
      skill = result.updated_record
    }

    expect(skill.validated_runs).toBe(initialRuns + 3)
  })

  it('failure loop produces SKILL_DEGRADED event and lower confidence', async () => {
    let executor = RalphExecutor.create('agent-004')
    const skill = await freshWorkflowSkill()
    const { record } = await executor.executeLoop(FAKE_CONTEXT, seq(1))

    const result = await processEvidence(skill, {
      skill_id: 'workflow_orchestration',
      agent_id: 'agent-004',
      is_success: false,
      loop_hash: record.loop_hash,
      sequence: seq(1),
      timestamp_ms: BASE_TS,
    })

    expect(result.event_type).toBe('SKILL_DEGRADED')
    expect(result.updated_record.confidence).toBeLessThan(skill.confidence)
  })

  it('5 loops alternating success/failure: failure_rate stays near 0.5', async () => {
    let executor = RalphExecutor.create('agent-005')
    let skill = await buildSkillRecord({
      skill_id: 'workflow_orchestration',
      name: 'Workflow', confidence: 0.5,
      validated_runs: 0, failure_rate: 0.5, recency_score: 0.5,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2026-01-01T00:00:00.000Z',
      epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
    })

    for (let i = 1; i <= 6; i++) {
      const { executor: next, record } = await executor.executeLoop(FAKE_CONTEXT, seq(i))
      executor = next
      const result = await processEvidence(skill, {
        skill_id: 'workflow_orchestration',
        agent_id: 'agent-005',
        is_success: i % 2 === 1, // alternating: true, false, true, false, true, false
        loop_hash: record.loop_hash,
        sequence: seq(i),
        timestamp_ms: BASE_TS + i,
      })
      skill = result.updated_record
    }

    // failure_rate after 6 runs (3 success, 3 failure from runs starting at 0) ≈ 0.5
    // initial failure_rate = 0.5 with validated_runs=0:
    // after 3 success + 3 failure out of 6 new runs: failure_rate = 3/6 = 0.5
    expect(skill.failure_rate).toBeGreaterThan(0.3)
    expect(skill.failure_rate).toBeLessThan(0.7)
  })

  it('evidence_refs grows by one per loop', async () => {
    let executor = RalphExecutor.create('agent-006')
    let skill = await freshWorkflowSkill()
    const initialRefCount = skill.evidence_refs.length

    for (let i = 1; i <= 4; i++) {
      const { executor: next, record } = await executor.executeLoop(FAKE_CONTEXT, seq(i))
      executor = next
      const result = await processEvidence(skill, {
        skill_id: 'workflow_orchestration',
        agent_id: 'agent-006',
        is_success: true,
        loop_hash: record.loop_hash,
        sequence: seq(i),
        timestamp_ms: BASE_TS,
      })
      skill = result.updated_record
    }

    expect(skill.evidence_refs.length).toBe(initialRefCount + 4)
  })

  it('all results are replay-certifiable', async () => {
    let executor = RalphExecutor.create('agent-007')
    const skill = await freshWorkflowSkill()
    const { record } = await executor.executeLoop(FAKE_CONTEXT, seq(1))

    const result = await processEvidence(skill, {
      skill_id: 'workflow_orchestration',
      agent_id: 'agent-007',
      is_success: true,
      loop_hash: record.loop_hash,
      sequence: seq(1),
      timestamp_ms: BASE_TS,
    })

    expect(result.is_replay_reconstructable).toBe(true)
    expect(result.updated_record.is_replay_reconstructable).toBe(true)
  })

  it('deterministic: two identical evidence runs produce same skill_hash ×3', async () => {
    const skill = await freshWorkflowSkill()
    const fakeLoopHash = 'd'.repeat(64) as SHA256Hex
    const evidence: SkillEvidence = {
      skill_id: 'workflow_orchestration',
      agent_id: 'agent-det',
      is_success: true,
      loop_hash: fakeLoopHash,
      sequence: seq(1),
      timestamp_ms: BASE_TS,
    }
    const r1 = await processEvidence(skill, evidence)
    const r2 = await processEvidence(skill, evidence)
    const r3 = await processEvidence(skill, evidence)
    expect(r1.updated_record.skill_hash).toBe(r2.updated_record.skill_hash)
    expect(r2.updated_record.skill_hash).toBe(r3.updated_record.skill_hash)
  })
})
