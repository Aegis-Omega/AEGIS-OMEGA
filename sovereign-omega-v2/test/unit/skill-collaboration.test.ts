// Gate 166 — Skill Harness Phase 5: Collaboration Unit Tests
// EPISTEMIC TIER: T2

import { describe, it, expect } from 'vitest'
import { buildSkillRecord } from '../../src/skill-harness/catalog.js'
import {
  proposeSkillTransfer,
  applySkillTransfer,
  peerConsensus,
  CollaborationError,
  COLLABORATION_SCHEMA_VERSION,
  TRANSFER_DISCOUNT,
  MIN_PEER_CONSENSUS_AGENTS,
} from '../../src/skill-harness/collaboration.js'
import type { PeerProfile } from '../../src/skill-harness/collaboration.js'
import type { SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

async function baseSkill(confidence = 0.8, failure_rate = 0.1, validated_runs = 30) {
  return buildSkillRecord({
    skill_id: 'workflow_orchestration',
    name: 'Workflow Orchestration',
    confidence,
    validated_runs,
    failure_rate,
    recency_score: 0.9,
    domain_affinity: ['workflow'],
    dependencies: [],
    evidence_refs: [],
    last_validated: '2020-09-13T12:26:40.000Z',
    epistemic_tier: 'T2',
    primitive_mapping: 'SEQUENCE',
  })
}

describe('Collaboration — constants', () => {
  it('exports correct schema version', () => {
    expect(COLLABORATION_SCHEMA_VERSION).toBe('1.0.0')
  })

  it('TRANSFER_DISCOUNT is 0.7', () => {
    expect(TRANSFER_DISCOUNT).toBe(0.7)
  })

  it('MIN_PEER_CONSENSUS_AGENTS is 2', () => {
    expect(MIN_PEER_CONSENSUS_AGENTS).toBe(2)
  })
})

describe('Collaboration — error handling', () => {
  it('CollaborationError is Error subclass', () => {
    expect(new CollaborationError('x')).toBeInstanceOf(Error)
    expect(new CollaborationError('x').name).toBe('CollaborationError')
  })

  it('proposeSkillTransfer throws when source === target', async () => {
    const skill = await baseSkill()
    await expect(proposeSkillTransfer(skill, 'agent-a', 'agent-a', seq(1)))
      .rejects.toBeInstanceOf(CollaborationError)
  })

  it('peerConsensus throws with < MIN_PEER_CONSENSUS_AGENTS', async () => {
    const skill = await baseSkill()
    const p: PeerProfile = { agent_id: 'a', skill }
    await expect(peerConsensus([p])).rejects.toBeInstanceOf(CollaborationError)
  })

  it('peerConsensus throws on skill_id mismatch', async () => {
    const s1 = await baseSkill()
    const s2 = await buildSkillRecord({
      skill_id: 'different_skill', name: 'Different',
      confidence: 0.7, validated_runs: 10, failure_rate: 0.2, recency_score: 0.8,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2020-09-13T12:26:40.000Z', epistemic_tier: 'T2', primitive_mapping: 'VERIFY',
    })
    const profiles: PeerProfile[] = [{ agent_id: 'a', skill: s1 }, { agent_id: 'b', skill: s2 }]
    await expect(peerConsensus(profiles)).rejects.toBeInstanceOf(CollaborationError)
  })
})

describe('Collaboration — proposeSkillTransfer', () => {
  it('produces frozen proposal with correct skill_id', async () => {
    const skill = await baseSkill()
    const p = await proposeSkillTransfer(skill, 'agent-src', 'agent-dst', seq(1))
    expect(Object.isFrozen(p)).toBe(true)
    expect(p.skill_id).toBe(skill.skill_id)
  })

  it('seeded_confidence = source_confidence × TRANSFER_DISCOUNT', async () => {
    const skill = await baseSkill(0.8)
    const p = await proposeSkillTransfer(skill, 'agent-src', 'agent-dst', seq(1))
    expect(p.seeded_confidence).toBeCloseTo(0.8 * 0.7, 10)
  })

  it('proposal_id is 64-char hex', async () => {
    const skill = await baseSkill()
    const p = await proposeSkillTransfer(skill, 'agent-src', 'agent-dst', seq(1))
    expect(p.proposal_id).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(p.proposal_id)).toBe(true)
  })

  it('is_replay_reconstructable is true', async () => {
    const skill = await baseSkill()
    const p = await proposeSkillTransfer(skill, 'agent-src', 'agent-dst', seq(1))
    expect(p.is_replay_reconstructable).toBe(true)
  })

  it('proposal_id deterministic ×3', async () => {
    const skill = await baseSkill()
    const [p1, p2, p3] = await Promise.all([
      proposeSkillTransfer(skill, 'agent-src', 'agent-dst', seq(1)),
      proposeSkillTransfer(skill, 'agent-src', 'agent-dst', seq(1)),
      proposeSkillTransfer(skill, 'agent-src', 'agent-dst', seq(1)),
    ])
    expect(p1.proposal_id).toBe(p2.proposal_id)
    expect(p2.proposal_id).toBe(p3.proposal_id)
  })

  it('different sequences → different proposal_id', async () => {
    const skill = await baseSkill()
    const p1 = await proposeSkillTransfer(skill, 'src', 'dst', seq(1))
    const p2 = await proposeSkillTransfer(skill, 'src', 'dst', seq(2))
    expect(p1.proposal_id).not.toBe(p2.proposal_id)
  })
})

describe('Collaboration — applySkillTransfer', () => {
  it('transferred skill has discounted confidence', async () => {
    const skill = await baseSkill(0.8)
    const proposal = await proposeSkillTransfer(skill, 'src', 'dst', seq(1))
    const result = await applySkillTransfer(proposal, skill)
    expect(result.transferred_skill.confidence).toBeCloseTo(0.8 * 0.7, 10)
  })

  it('transferred skill validated_runs is 0', async () => {
    const skill = await baseSkill()
    const proposal = await proposeSkillTransfer(skill, 'src', 'dst', seq(1))
    const result = await applySkillTransfer(proposal, skill)
    expect(result.transferred_skill.validated_runs).toBe(0)
  })

  it('result is frozen', async () => {
    const skill = await baseSkill()
    const proposal = await proposeSkillTransfer(skill, 'src', 'dst', seq(1))
    const result = await applySkillTransfer(proposal, skill)
    expect(Object.isFrozen(result)).toBe(true)
    expect(Object.isFrozen(result.transferred_skill)).toBe(true)
  })

  it('transfer_hash is 64-char hex', async () => {
    const skill = await baseSkill()
    const proposal = await proposeSkillTransfer(skill, 'src', 'dst', seq(1))
    const result = await applySkillTransfer(proposal, skill)
    expect(result.transfer_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(result.transfer_hash)).toBe(true)
  })

  it('transferred skill preserves domain_affinity', async () => {
    const skill = await baseSkill()
    const proposal = await proposeSkillTransfer(skill, 'src', 'dst', seq(1))
    const result = await applySkillTransfer(proposal, skill)
    expect(result.transferred_skill.domain_affinity).toEqual(skill.domain_affinity)
  })

  it('evidence_refs is empty after transfer', async () => {
    const skill = await baseSkill()
    const proposal = await proposeSkillTransfer(skill, 'src', 'dst', seq(1))
    const result = await applySkillTransfer(proposal, skill)
    expect(result.transferred_skill.evidence_refs).toHaveLength(0)
  })
})

describe('Collaboration — peerConsensus', () => {
  it('2-agent consensus with equal runs → mean confidence', async () => {
    const s1 = await buildSkillRecord({
      skill_id: 'workflow_orchestration', name: 'W',
      confidence: 0.6, validated_runs: 10, failure_rate: 0.1, recency_score: 0.9,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2020-09-13T12:26:40.000Z', epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
    })
    const s2 = await buildSkillRecord({
      skill_id: 'workflow_orchestration', name: 'W',
      confidence: 0.8, validated_runs: 10, failure_rate: 0.1, recency_score: 0.9,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2020-09-13T12:26:40.000Z', epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
    })
    const result = await peerConsensus([
      { agent_id: 'a', skill: s1 },
      { agent_id: 'b', skill: s2 },
    ])
    // Weighted: (0.6×10 + 0.8×10) / 20 = 0.7
    expect(result.consensus_confidence).toBeCloseTo(0.7, 10)
  })

  it('runs-weighted consensus favors agent with more runs', async () => {
    const s1 = await buildSkillRecord({
      skill_id: 'workflow_orchestration', name: 'W',
      confidence: 0.5, validated_runs: 5, failure_rate: 0.1, recency_score: 0.9,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2020-09-13T12:26:40.000Z', epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
    })
    const s2 = await buildSkillRecord({
      skill_id: 'workflow_orchestration', name: 'W',
      confidence: 0.9, validated_runs: 45, failure_rate: 0.05, recency_score: 0.95,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2020-09-13T12:26:40.000Z', epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
    })
    const result = await peerConsensus([
      { agent_id: 'a', skill: s1 },
      { agent_id: 'b', skill: s2 },
    ])
    // (0.5×5 + 0.9×45) / 50 = (2.5 + 40.5) / 50 = 0.86
    expect(result.consensus_confidence).toBeCloseTo(0.86, 10)
  })

  it('zero-runs agents → arithmetic mean', async () => {
    const s1 = await buildSkillRecord({
      skill_id: 'workflow_orchestration', name: 'W',
      confidence: 0.4, validated_runs: 0, failure_rate: 0.0, recency_score: 0.8,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2020-09-13T12:26:40.000Z', epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
    })
    const s2 = await buildSkillRecord({
      skill_id: 'workflow_orchestration', name: 'W',
      confidence: 0.6, validated_runs: 0, failure_rate: 0.0, recency_score: 0.8,
      domain_affinity: [], dependencies: [], evidence_refs: [],
      last_validated: '2020-09-13T12:26:40.000Z', epistemic_tier: 'T2', primitive_mapping: 'SEQUENCE',
    })
    const result = await peerConsensus([{ agent_id: 'a', skill: s1 }, { agent_id: 'b', skill: s2 }])
    expect(result.consensus_confidence).toBeCloseTo(0.5, 10)
  })

  it('consensus_hash is 64-char hex', async () => {
    const skill = await baseSkill()
    const skill2 = await baseSkill(0.7)
    const result = await peerConsensus([{ agent_id: 'a', skill }, { agent_id: 'b', skill: skill2 }])
    expect(result.consensus_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(result.consensus_hash)).toBe(true)
  })

  it('consensus_hash deterministic ×3', async () => {
    const s1 = await baseSkill()
    const s2 = await baseSkill(0.7)
    const profiles: PeerProfile[] = [{ agent_id: 'a', skill: s1 }, { agent_id: 'b', skill: s2 }]
    const [r1, r2, r3] = await Promise.all([
      peerConsensus(profiles),
      peerConsensus(profiles),
      peerConsensus(profiles),
    ])
    expect(r1.consensus_hash).toBe(r2.consensus_hash)
    expect(r2.consensus_hash).toBe(r3.consensus_hash)
  })

  it('result is frozen', async () => {
    const s1 = await baseSkill()
    const s2 = await baseSkill(0.7)
    const result = await peerConsensus([{ agent_id: 'a', skill: s1 }, { agent_id: 'b', skill: s2 }])
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('is_replay_reconstructable is true', async () => {
    const s1 = await baseSkill()
    const s2 = await baseSkill(0.7)
    const result = await peerConsensus([{ agent_id: 'a', skill: s1 }, { agent_id: 'b', skill: s2 }])
    expect(result.is_replay_reconstructable).toBe(true)
  })

  it('participating_agents lists all agent_ids', async () => {
    const s1 = await baseSkill()
    const s2 = await baseSkill(0.7)
    const s3 = await baseSkill(0.6)
    const result = await peerConsensus([
      { agent_id: 'alpha', skill: s1 },
      { agent_id: 'beta', skill: s2 },
      { agent_id: 'gamma', skill: s3 },
    ])
    expect(result.participating_agents).toEqual(['alpha', 'beta', 'gamma'])
    expect(result.agent_count).toBe(3)
  })
})
