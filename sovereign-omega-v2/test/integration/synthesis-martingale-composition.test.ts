// test/integration/synthesis-martingale-composition.test.ts
//
// Gate 185 — Martingale-Synthesis Holonic Composition
// EPISTEMIC TIER: T2 (engineering hypothesis)
//
// Proves that synthesis-swarm COMMITTED decisions feed the martingale correctly:
// when APPROVED capability evolutions exceed 1/φ of total lineage entries,
// certifyMartingale detects entropy_bounded=false — the same 61/62 boundary
// that governs swarm quorum (swarm.ts) and constitutional mutation rate (martingale.ts).
//
// This is the fourth holonic proof surface: synthesis decisions obey the same
// golden-ratio governance constant as BFT consensus and martingale anchoring.

import { describe, it, expect } from 'vitest'
import { runSynthesisSwarm } from '../../src/consensus/synthesis-swarm.js'
import type { SynthesisRequest, AgentRole } from '../../src/consensus/synthesis-swarm.js'
import { AdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { certifyMartingale, assertMartingaleAnchored, MUTATION_RATE_LIMIT, MartingaleViolation } from '../../src/constitutional/martingale.js'
import { DEFAULT_QUORUM_THRESHOLD } from '../../src/consensus/swarm.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const CODE = 'export function identity(x: number): number { return x }'
const COMMITTED_GAMMA = JSON.stringify({ verdict: 'COMMITTED', violations: [], rationale: 'ok' })
const REJECTED_GAMMA  = JSON.stringify({ verdict: 'REJECTED',  violations: ['test'], rationale: 'no' })

function makeSynthesisAgent(committed: boolean) {
  return async (_s: string, _u: string, role: AgentRole) => {
    if (role === 'gamma') {
      return { output: committed ? COMMITTED_GAMMA : REJECTED_GAMMA, backend: 'mock', latency_ms: 1 }
    }
    return { output: CODE, backend: 'mock', latency_ms: 1 }
  }
}

async function buildSynthesisLineage(
  committedCount: number,
  rejectedCount: number,
  seqBase: number,
) {
  let lineage = AdaptiveLineage.empty()
  let s = seqBase

  // COMMITTED rounds first
  const committedAgent = makeSynthesisAgent(true)
  for (let i = 0; i < committedCount; i++) {
    const req: SynthesisRequest = {
      task: `synthesis-task-${s}`,
      context: '',
      constitutional_constraints: [],
      sequence: seq(s),
    }
    const rec = await runSynthesisSwarm(req, committedAgent)
    expect(rec.verdict).toBe('COMMITTED')
    const { lineage: next } = await lineage.append(
      { kind: 'CAPABILITY_EVOLUTION', proposal_id: rec.synthesis_hash as SHA256Hex, verdict: 'APPROVED' },
      seq(s),
    )
    lineage = next
    s++
  }

  // REJECTED rounds
  const rejectedAgent = makeSynthesisAgent(false)
  for (let i = 0; i < rejectedCount; i++) {
    const req: SynthesisRequest = {
      task: `synthesis-task-${s}`,
      context: '',
      constitutional_constraints: [],
      sequence: seq(s),
    }
    const rec = await runSynthesisSwarm(req, rejectedAgent)
    expect(rec.verdict).toBe('REJECTED')
    const { lineage: next } = await lineage.append(
      { kind: 'CAPABILITY_EVOLUTION', proposal_id: rec.synthesis_hash as SHA256Hex, verdict: 'REJECTED' },
      seq(s),
    )
    lineage = next
    s++
  }

  return lineage
}

// ─────────────────────────────────────────────────────────────────────────────

describe('Gate 185 — Martingale-Synthesis holonic composition', () => {

  describe('61/62 boundary mirrors swarm quorum and martingale mutation rate', () => {
    it('62/100 synthesis rounds COMMITTED → entropy_bounded=false (above 1/φ)', async () => {
      const lineage = await buildSynthesisLineage(62, 38, 1000)
      const cert = await certifyMartingale(lineage.getAll())
      expect(cert.adaptive_power).toBe(62)
      expect(cert.replay_verifiability).toBe(100)
      expect(cert.adaptive_ratio).toBeCloseTo(0.62, 2)
      expect(cert.entropy_bounded).toBe(false)
    }, 30_000)

    it('61/100 synthesis rounds COMMITTED → entropy_bounded=true (below 1/φ)', async () => {
      const lineage = await buildSynthesisLineage(61, 39, 2000)
      const cert = await certifyMartingale(lineage.getAll())
      expect(cert.adaptive_power).toBe(61)
      expect(cert.replay_verifiability).toBe(100)
      expect(cert.adaptive_ratio).toBeCloseTo(0.61, 2)
      expect(cert.entropy_bounded).toBe(true)
    }, 30_000)

    it('boundary is identical to MUTATION_RATE_LIMIT and DEFAULT_QUORUM_THRESHOLD', () => {
      expect(MUTATION_RATE_LIMIT).toBe(DEFAULT_QUORUM_THRESHOLD)
      expect(62 / 100).toBeGreaterThan(MUTATION_RATE_LIMIT)
      expect(61 / 100).toBeLessThan(MUTATION_RATE_LIMIT)
    })
  })

  describe('Martingale enforcement on synthesis chains', () => {
    it('all-COMMITTED chain triggers assertMartingaleAnchored (entropy_bounded=false)', async () => {
      const lineage = await buildSynthesisLineage(10, 0, 3000)
      const cert = await certifyMartingale(lineage.getAll())
      expect(cert.entropy_bounded).toBe(false)
      expect(() => assertMartingaleAnchored(cert)).toThrow(MartingaleViolation)
    }, 15_000)

    it('all-REJECTED chain passes assertMartingaleAnchored (entropy_bounded=true)', async () => {
      const lineage = await buildSynthesisLineage(0, 10, 4000)
      const cert = await certifyMartingale(lineage.getAll())
      expect(cert.entropy_bounded).toBe(true)
      expect(cert.adaptive_power).toBe(0)
      expect(() => assertMartingaleAnchored(cert)).not.toThrow()
    }, 15_000)
  })

  describe('Martingale certificate properties over synthesis lineage', () => {
    it('certificate is frozen and replay-certifiable', async () => {
      const lineage = await buildSynthesisLineage(5, 5, 5000)
      const cert = await certifyMartingale(lineage.getAll())
      expect(Object.isFrozen(cert)).toBe(true)
      expect(cert.certificate_hash.length).toBe(64)
      expect(cert.is_replay_reconstructable).toBe(true)
      expect(cert.schema_version).toBe('1.0.0')
    }, 15_000)

    it('is_anchored=true when synthesis chain is tamper-free', async () => {
      const lineage = await buildSynthesisLineage(3, 3, 6000)
      const cert = await certifyMartingale(lineage.getAll())
      expect(cert.is_anchored).toBe(true)
      expect(cert.drift_bounded).toBe(true)
    }, 15_000)

    it('terminal_hash matches last entry_hash in synthesis lineage', async () => {
      const lineage = await buildSynthesisLineage(2, 2, 7000)
      const entries = lineage.getAll()
      const cert = await certifyMartingale(entries)
      const lastEntry = entries[entries.length - 1]!
      expect(cert.terminal_hash).toBe(lastEntry.entry_hash)
    }, 15_000)

    it('mutation_rate_limit in certificate equals MUTATION_RATE_LIMIT export', async () => {
      const lineage = await buildSynthesisLineage(2, 2, 8000)
      const cert = await certifyMartingale(lineage.getAll())
      expect(cert.mutation_rate_limit).toBe(MUTATION_RATE_LIMIT)
    }, 15_000)
  })
})
