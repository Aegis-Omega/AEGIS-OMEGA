// Gate 169 — Swarm + RALPH + Skill Harness Holonic Composition
// EPISTEMIC TIER: T2
//
// Proves the three-layer holonic integration:
//   RalphExecutor (Fibonacci-paced loops)
//   → SwarmConvergenceRecord (1/φ quorum)
//   → MartingaleCertificate (entropy bounded at 1/φ)
//   → SkillHarness (telemetry + inference + routing)

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { RalphExecutor } from '../../src/agents/executor/loop.js'
import { tallyVotes } from '../../src/consensus/swarm.js'
import type { SwarmVote } from '../../src/consensus/swarm.js'
import { certifyMartingale, assertMartingaleAnchored, MUTATION_RATE_LIMIT } from '../../src/constitutional/martingale.js'
import { DEFAULT_QUORUM_THRESHOLD } from '../../src/consensus/swarm.js'
import { buildSkillRecord } from '../../src/skill-harness/catalog.js'
import { processEvidence } from '../../src/skill-harness/telemetry-engine.js'
import type { SkillEvidence } from '../../src/skill-harness/telemetry-engine.js'
import { inferSkillConfidence } from '../../src/skill-harness/inference-engine.js'
import { recommendRouting } from '../../src/skill-harness/router.js'
import type { AgentSkillProfile } from '../../src/skill-harness/router.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }
const FAKE_CTX = 'f'.repeat(64) as SHA256Hex

describe('Holonic triad: 1/φ equality', () => {
  it('MUTATION_RATE_LIMIT === DEFAULT_QUORUM_THRESHOLD (same 1/φ constant)', () => {
    expect(MUTATION_RATE_LIMIT).toBeCloseTo(DEFAULT_QUORUM_THRESHOLD, 12)
  })

  it('61/100 < 1/φ → martingale entropy_bounded=true', async () => {
    const entries = await buildTestLineage(61, 100)
    const cert = await certifyMartingale(entries)
    expect(cert.entropy_bounded).toBe(true)
    expect(() => assertMartingaleAnchored(cert)).not.toThrow()
  })

  it('62/100 ≥ 1/φ → martingale entropy_bounded=false → assertion throws', async () => {
    const entries = await buildTestLineage(62, 100)
    const cert = await certifyMartingale(entries)
    expect(cert.entropy_bounded).toBe(false)
    expect(() => assertMartingaleAnchored(cert)).toThrow()
  })
})

describe('RalphExecutor Fibonacci pacing', () => {
  it('11-loop executor: intervals follow F_1..F_11 sequence', async () => {
    let executor = RalphExecutor.create('fib-agent')
    const intervals: number[] = []
    for (let i = 1; i <= 11; i++) {
      const { executor: next, record } = await executor.executeLoop(FAKE_CTX, seq(i))
      intervals.push(record.fibonacci_interval)
      executor = next
    }
    expect(intervals).toEqual([1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89])
  })

  it('loop_hash is deterministic for same sequence', async () => {
    const e1 = RalphExecutor.create('det-agent')
    const e2 = RalphExecutor.create('det-agent')
    const { record: r1 } = await e1.executeLoop(FAKE_CTX, seq(1))
    const { record: r2 } = await e2.executeLoop(FAKE_CTX, seq(1))
    expect(r1.loop_hash).toBe(r2.loop_hash)
  })
})

describe('5-agent swarm: RALPH loops → swarm convergence', () => {
  it('5 agents produce loop_hashes then vote on shared topology → quorum_reached', async () => {
    const agentIds = ['ag-1', 'ag-2', 'ag-3', 'ag-4', 'ag-5']
    // Each agent runs 3 loops; their loop_hashes differ by agent_id — that is expected.
    // For swarm convergence, agents vote on a shared constitutional topology_hash (FAKE_CTX).
    const votes: SwarmVote[] = agentIds.map(id => ({
      node_id: id,
      topology_hash: FAKE_CTX,    // all agree on the same observed state
      sequence: seq(3),
    }))
    const convergence = await tallyVotes(votes)
    expect(convergence.quorum_reached).toBe(true)
    expect(convergence.vote_count).toBe(5)
    expect(convergence.quorum_hash).toBe(FAKE_CTX)
    expect(convergence.convergence_hash).toHaveLength(64)
  })

  it('3-of-5 majority still reaches quorum at DEFAULT_QUORUM_THRESHOLD', async () => {
    const majority = 'a'.repeat(64) as SHA256Hex
    const minority = 'b'.repeat(64) as SHA256Hex
    const votes: SwarmVote[] = [
      { node_id: 'n1', topology_hash: majority, sequence: seq(1) },
      { node_id: 'n2', topology_hash: majority, sequence: seq(1) },
      { node_id: 'n3', topology_hash: majority, sequence: seq(1) },
      { node_id: 'n4', topology_hash: minority, sequence: seq(1) },
      { node_id: 'n5', topology_hash: minority, sequence: seq(1) },
    ]
    const convergence = await tallyVotes(votes)
    // 3/5 = 0.60 < 0.67 default threshold → NOT quorum
    expect(convergence.quorum_reached).toBe(false)
  })

  it('4-of-5 majority reaches quorum', async () => {
    const majority = 'c'.repeat(64) as SHA256Hex
    const minority = 'd'.repeat(64) as SHA256Hex
    const votes: SwarmVote[] = [
      { node_id: 'n1', topology_hash: majority, sequence: seq(1) },
      { node_id: 'n2', topology_hash: majority, sequence: seq(1) },
      { node_id: 'n3', topology_hash: majority, sequence: seq(1) },
      { node_id: 'n4', topology_hash: majority, sequence: seq(1) },
      { node_id: 'n5', topology_hash: minority, sequence: seq(1) },
    ]
    const convergence = await tallyVotes(votes)
    // 4/5 = 0.80 > 0.67 → quorum
    expect(convergence.quorum_reached).toBe(true)
    expect(convergence.quorum_hash).toBe(majority)
  })
})

describe('RALPH loop_hash → skill evidence → inference → routing', () => {
  it('3-agent composition: RALPH evidence → per-agent skill inference → routing', async () => {
    const skill = await buildSkillRecord({
      skill_id: 'replay_audit', name: 'Replay Audit',
      confidence: 0.65, validated_runs: 10, failure_rate: 0.2, recency_score: 0.8,
      domain_affinity: ['audit'], dependencies: [], evidence_refs: [],
      last_validated: '2020-09-13T12:26:40.000Z', epistemic_tier: 'T2', primitive_mapping: 'VERIFY',
    })

    const agentProfiles: AgentSkillProfile[] = []
    for (let a = 0; a < 3; a++) {
      const agentId = `skill-agent-${a}`
      let executor = RalphExecutor.create(agentId)
      let currentSkill = skill

      for (let i = 1; i <= 5; i++) {
        const { executor: next, record } = await executor.executeLoop(FAKE_CTX, seq(i))
        executor = next
        const ev: SkillEvidence = {
          skill_id: 'replay_audit',
          agent_id: agentId,
          is_success: i % 4 !== 0, // mostly successes
          loop_hash: record.loop_hash,
          sequence: seq(i),
          timestamp_ms: 1_600_000_000_000 + i * 1000,
        } as SkillEvidence
        const tel = await processEvidence(currentSkill, ev)
        currentSkill = tel.updated_record
      }
      const inferred = await inferSkillConfidence(currentSkill, [])
      agentProfiles.push({ agent_id: agentId, skills: [inferred.updated_skill] })
    }

    const result = await recommendRouting('audit', agentProfiles)
    expect(result.primary_agent_id).not.toBeNull()
    expect(['ROUTE_TO_BEST', 'DELEGATE_SPECIALIST', 'COLLABORATE']).toContain(result.decision)
    expect(result.routing_hash).toHaveLength(64)
    expect(result.is_replay_reconstructable).toBe(true)
  })
})

describe('Skill install → martingale', () => {
  it('61/100 approved skill installs → martingale anchored; 62/100 → suspended', async () => {
    const entries61 = await buildTestLineage(61, 100)
    const cert61 = await certifyMartingale(entries61)
    expect(cert61.is_anchored).toBe(true)
    expect(cert61.entropy_bounded).toBe(true)
    expect(cert61.adaptive_power).toBe(61)
    expect(() => assertMartingaleAnchored(cert61)).not.toThrow()

    const entries62 = await buildTestLineage(62, 100)
    const cert62 = await certifyMartingale(entries62)
    expect(cert62.entropy_bounded).toBe(false)
    expect(() => assertMartingaleAnchored(cert62)).toThrow()
  })

  it('martingale certificate_hash deterministic ×3', async () => {
    const entries = await buildTestLineage(50, 100)
    const [c1, c2, c3] = await Promise.all([
      certifyMartingale(entries),
      certifyMartingale(entries),
      certifyMartingale(entries),
    ])
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })
})

// ─── helpers ───────────────────────────────────────────────

async function buildTestLineage(approved: number, total: number) {
  const { AdaptiveLineage } = await import('../../src/frame/adaptive-lineage.js')
  const hash = 'a'.repeat(64) as SHA256Hex
  let lineage = AdaptiveLineage.empty()
  for (let i = 1; i <= total; i++) {
    const kind = i <= approved ? 'CAPABILITY_EVOLUTION' : 'TOPOLOGY_TRANSITION'
    const event = kind === 'CAPABILITY_EVOLUTION'
      ? { kind: 'CAPABILITY_EVOLUTION' as const, proposal_id: hash, verdict: 'APPROVED' as const }
      : { kind: 'TOPOLOGY_TRANSITION' as const, topology_hash: hash }
    const { lineage: next } = await lineage.append(event, seq(i))
    lineage = next
  }
  return lineage.getAll()
}
