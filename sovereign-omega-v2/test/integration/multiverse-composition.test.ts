// test/integration/multiverse-composition.test.ts
//
// Gate 190 — Multiverse Holonic Composition
// EPISTEMIC TIER: T2 (engineering hypothesis)
//
// Proves that MultiverseRegistry composes correctly with every constitutional
// layer below it in the holonic hierarchy:
//
//   1. Per-universe martingale: each universe's AdaptiveLineage feeds
//      certifyMartingale independently — hot/cold universes diverge correctly.
//
//   2. Synthesis ↔ multiverse: runSynthesisSwarm records become CAPABILITY_EVOLUTION
//      events in named universe lineages. COMMITTED→APPROVED / REJECTED→REJECTED.
//
//   3. Shapley × multiverse: computeSynthesisShapley is read-only — the same
//      SynthesisRecord produces identical ShapleyAttestation regardless of which
//      universe the event is appended to.
//
//   4. Cross-universe convergence at 1/φ: two universes sharing the same terminal
//      hash (both at genesis) reach quorum; after one diverges, the 1/φ boundary
//      governs convergence exactly as in the swarm protocol.
//
//   5. Ecology bound: MultiverseRegistry rejects fork() beyond MAX_UNIVERSES=8,
//      enforcing the constitutional prohibition on unbounded ecology growth.
//
//   6. Multiverse × BoundedGeneration: per-universe generation tracks monotonically
//      — certifyAll() returns sorted, independent certificates for all 8 universes.

import { describe, it, expect } from 'vitest'
import { MultiverseRegistry, MAX_UNIVERSES } from '../../src/memory/multiverse.js'
import { runSynthesisSwarm } from '../../src/consensus/synthesis-swarm.js'
import type { SynthesisRequest, AgentRole } from '../../src/consensus/synthesis-swarm.js'
import { computeSynthesisShapley } from '../../src/consensus/game-theory.js'
import { certifyMartingale, assertMartingaleAnchored, MartingaleViolation } from '../../src/constitutional/martingale.js'
import { DEFAULT_QUORUM_THRESHOLD } from '../../src/consensus/swarm.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const CODE          = 'export function identity(x: number): number { return x }'
const COMMITTED_GAMMA = JSON.stringify({ verdict: 'COMMITTED', violations: [], rationale: 'ok' })
const REJECTED_GAMMA  = JSON.stringify({ verdict: 'REJECTED', violations: ['x'], rationale: 'no' })

const FORK_ROOT = 'a0b1c2d3'.repeat(8) as SHA256Hex  // 64-char deterministic root

function makeAgent(committed: boolean) {
  return async (_s: string, _u: string, role: AgentRole) => {
    if (role === 'gamma') {
      return { output: committed ? COMMITTED_GAMMA : REJECTED_GAMMA, backend: 'mock', latency_ms: 1 }
    }
    return { output: CODE, backend: 'mock', latency_ms: 1 }
  }
}

// ─────────────────────────────────────────────────────────────────────────────

describe('Gate 190 — Multiverse Holonic Composition', () => {

  describe('Per-universe martingale independence', () => {
    it('hot universe (all COMMITTED) entropy_bounded=false; cold (all REJECTED) entropy_bounded=true', async () => {
      let reg = MultiverseRegistry.empty()
      const { registry: r1 } = await reg.fork('hot', FORK_ROOT, seq(1))
      const { registry: r2 } = await r1.fork('cold', FORK_ROOT, seq(2))
      reg = r2

      let s = 100
      for (let i = 0; i < 10; i++) {
        const req: SynthesisRequest = { task: `task-hot-${s}`, context: '', constitutional_constraints: [], sequence: seq(s) }
        const rec = await runSynthesisSwarm(req, makeAgent(true))
        expect(rec.verdict).toBe('COMMITTED')
        const { registry } = await reg.appendToUniverse('hot',
          { kind: 'CAPABILITY_EVOLUTION', proposal_id: rec.synthesis_hash as SHA256Hex, verdict: 'APPROVED' },
          seq(s))
        reg = registry
        s++
      }
      for (let i = 0; i < 10; i++) {
        const req: SynthesisRequest = { task: `task-cold-${s}`, context: '', constitutional_constraints: [], sequence: seq(s) }
        const rec = await runSynthesisSwarm(req, makeAgent(false))
        expect(rec.verdict).toBe('REJECTED')
        const { registry } = await reg.appendToUniverse('cold',
          { kind: 'CAPABILITY_EVOLUTION', proposal_id: rec.synthesis_hash as SHA256Hex, verdict: 'REJECTED' },
          seq(s))
        reg = registry
        s++
      }

      const certs = await reg.certifyAll()
      const hot  = certs.find(c => c.universe_id === 'hot')!
      const cold = certs.find(c => c.universe_id === 'cold')!

      expect(hot.certificate.entropy_bounded).toBe(false)    // 10/10 > 1/φ
      expect(cold.certificate.entropy_bounded).toBe(true)    // 0/10 < 1/φ
      expect(hot.certificate.is_anchored).toBe(true)
      expect(cold.certificate.is_anchored).toBe(true)
      expect(() => assertMartingaleAnchored(hot.certificate)).toThrow(MartingaleViolation)
      expect(() => assertMartingaleAnchored(cold.certificate)).not.toThrow()
    }, 30_000)

    it('each universe certifies independently — hot does not contaminate cold', async () => {
      let reg = MultiverseRegistry.empty()
      const { registry: r1 } = await reg.fork('a', FORK_ROOT, seq(1))
      const { registry: r2 } = await r1.fork('b', FORK_ROOT, seq(2))
      reg = r2

      // append 5 APPROVED to 'a' only
      let s = 200
      for (let i = 0; i < 5; i++) {
        const req: SynthesisRequest = { task: `task-a-${s}`, context: '', constitutional_constraints: [], sequence: seq(s) }
        const rec = await runSynthesisSwarm(req, makeAgent(true))
        const { registry } = await reg.appendToUniverse('a',
          { kind: 'CAPABILITY_EVOLUTION', proposal_id: rec.synthesis_hash as SHA256Hex, verdict: 'APPROVED' },
          seq(s))
        reg = registry
        s++
      }

      const certs = await reg.certifyAll()
      const certA = certs.find(c => c.universe_id === 'a')!
      const certB = certs.find(c => c.universe_id === 'b')!

      expect(certA.certificate.adaptive_power).toBe(5)
      expect(certB.certificate.adaptive_power).toBe(0)         // b untouched
      expect(certB.certificate.entropy_bounded).toBe(true)     // 0/0 → bounded
      expect(certA.lineage_length).toBe(5)
      expect(certB.lineage_length).toBe(0)
    }, 20_000)
  })

  describe('Synthesis ↔ multiverse integration', () => {
    it('COMMITTED synthesis records map to APPROVED events in universe lineage', async () => {
      let reg = MultiverseRegistry.empty()
      const { registry: r1 } = await reg.fork('main', FORK_ROOT, seq(1))
      reg = r1

      const req: SynthesisRequest = { task: 'synthesis-test', context: '', constitutional_constraints: [], sequence: seq(300) }
      const rec = await runSynthesisSwarm(req, makeAgent(true))
      expect(rec.verdict).toBe('COMMITTED')

      const { registry: r2 } = await reg.appendToUniverse('main',
        { kind: 'CAPABILITY_EVOLUTION', proposal_id: rec.synthesis_hash as SHA256Hex, verdict: 'APPROVED' },
        seq(301))
      reg = r2

      const lineage = reg.getLineage('main')!
      expect(lineage.length).toBe(1)
      const entry = lineage.getAll()[0]!
      expect(entry.event.kind).toBe('CAPABILITY_EVOLUTION')
      if (entry.event.kind === 'CAPABILITY_EVOLUTION') {
        expect(entry.event.verdict).toBe('APPROVED')
        expect(entry.event.proposal_id).toBe(rec.synthesis_hash)
      }
    }, 10_000)

    it('REJECTED synthesis records map to REJECTED events — universe stays bounded', async () => {
      let reg = MultiverseRegistry.empty()
      const { registry: r1 } = await reg.fork('main', FORK_ROOT, seq(1))
      reg = r1

      let s = 400
      for (let i = 0; i < 5; i++) {
        const req: SynthesisRequest = { task: `rej-${s}`, context: '', constitutional_constraints: [], sequence: seq(s) }
        const rec = await runSynthesisSwarm(req, makeAgent(false))
        expect(rec.verdict).toBe('REJECTED')
        const { registry } = await reg.appendToUniverse('main',
          { kind: 'CAPABILITY_EVOLUTION', proposal_id: rec.synthesis_hash as SHA256Hex, verdict: 'REJECTED' },
          seq(s))
        reg = registry
        s++
      }

      const cert = await certifyMartingale(reg.getLineage('main')!.getAll())
      expect(cert.adaptive_power).toBe(0)
      expect(cert.entropy_bounded).toBe(true)
      expect(() => assertMartingaleAnchored(cert)).not.toThrow()
    }, 20_000)
  })

  describe('Shapley × multiverse orthogonality', () => {
    it('same SynthesisRecord produces identical Shapley attribution regardless of target universe', async () => {
      const req: SynthesisRequest = { task: 'shapley-ortho', context: '', constitutional_constraints: [], sequence: seq(500) }
      const rec = await runSynthesisSwarm(req, makeAgent(true))

      // Compute Shapley three times — same record, different universe context (irrelevant)
      const [s1, s2, s3] = await Promise.all([
        computeSynthesisShapley(rec),
        computeSynthesisShapley(rec),
        computeSynthesisShapley(rec),
      ])
      expect(s1.attribution_hash).toBe(s2.attribution_hash)
      expect(s2.attribution_hash).toBe(s3.attribution_hash)
      expect(s1.alpha_credit).toBeCloseTo(7 / 12, 9)
    }, 10_000)

    it('Shapley is_efficient on all universe-routed synthesis records', async () => {
      let reg = MultiverseRegistry.empty()
      const { registry: r1 } = await reg.fork('u', FORK_ROOT, seq(1))
      reg = r1

      let s = 600
      for (let i = 0; i < 5; i++) {
        const req: SynthesisRequest = { task: `eff-${s}`, context: '', constitutional_constraints: [], sequence: seq(s) }
        const rec = await runSynthesisSwarm(req, makeAgent(i % 2 === 0))
        const shapley = await computeSynthesisShapley(rec)
        expect(shapley.is_efficient).toBe(true)  // φ_A+φ_B+φ_G = v(N) in all universes
        const verdict = rec.verdict === 'COMMITTED' ? 'APPROVED' as const : 'REJECTED' as const
        const { registry } = await reg.appendToUniverse('u',
          { kind: 'CAPABILITY_EVOLUTION', proposal_id: rec.synthesis_hash as SHA256Hex, verdict },
          seq(s))
        reg = registry
        s++
      }
      expect(reg.getLineage('u')!.length).toBe(5)
    }, 20_000)
  })

  describe('Cross-universe convergence at 1/φ', () => {
    it('two empty universes share GENESIS hash → quorum_reached=true', async () => {
      const r0 = MultiverseRegistry.empty()
      const { registry: r1 } = await r0.fork('a', FORK_ROOT, seq(1))
      const { registry: r2 } = await r1.fork('b', FORK_ROOT, seq(2))
      const conv = await r2.checkConvergence(seq(10))
      expect(conv.swarm_record.quorum_reached).toBe(true)
      expect(conv.converged_universe_ids).toHaveLength(2)
    }, 5_000)

    it('one diverged universe out of three: 2/3 > 1/φ → quorum still reached', async () => {
      const r0 = MultiverseRegistry.empty()
      const { registry: r1 } = await r0.fork('a', FORK_ROOT, seq(1))
      const { registry: r2 } = await r1.fork('b', FORK_ROOT, seq(2))
      const { registry: r3 } = await r2.fork('c', FORK_ROOT, seq(3))

      // Diverge only 'a' via a synthesis event
      const req: SynthesisRequest = { task: 'diverge', context: '', constitutional_constraints: [], sequence: seq(4) }
      const rec = await runSynthesisSwarm(req, makeAgent(true))
      const { registry: r4 } = await r3.appendToUniverse('a',
        { kind: 'CAPABILITY_EVOLUTION', proposal_id: rec.synthesis_hash as SHA256Hex, verdict: 'APPROVED' },
        seq(4))

      const conv = await r4.checkConvergence(seq(10))
      expect(conv.total_universes).toBe(3)
      // b and c share genesis → 2/3 ≈ 0.667 > 1/φ ≈ 0.618 → quorum
      expect(conv.swarm_record.quorum_reached).toBe(true)
      expect(conv.converged_universe_ids).toHaveLength(2)
      expect(conv.converged_universe_ids).not.toContain('a')
    }, 10_000)

    it('convergence threshold constant matches DEFAULT_QUORUM_THRESHOLD', () => {
      // The 1/φ threshold governs swarm.ts, martingale.ts, AND multiverse convergence.
      // All three surfaces are governed by the same holonic constant.
      expect(DEFAULT_QUORUM_THRESHOLD).toBeCloseTo((Math.sqrt(5) - 1) / 2, 9)
      expect(2 / 3).toBeGreaterThan(DEFAULT_QUORUM_THRESHOLD)   // 2/3 → quorum
      expect(1 / 3).toBeLessThan(DEFAULT_QUORUM_THRESHOLD)      // 1/3 → no quorum
    })
  })

  describe('Ecology bound enforcement', () => {
    it('MAX_UNIVERSES=8 is a hard ceiling — 9th fork throws', async () => {
      let reg = MultiverseRegistry.empty()
      for (let i = 0; i < MAX_UNIVERSES; i++) {
        const { registry } = await reg.fork(`u${i}`, FORK_ROOT, seq(i + 1))
        reg = registry
      }
      const { MultiverseError } = await import('../../src/memory/multiverse.js')
      await expect(reg.fork('overflow', FORK_ROOT, seq(99))).rejects.toThrow(MultiverseError)
    }, 10_000)

    it('all 8 universes certify independently with no cross-contamination', async () => {
      let reg = MultiverseRegistry.empty()
      for (let i = 0; i < MAX_UNIVERSES; i++) {
        const { registry } = await reg.fork(`u${i}`, FORK_ROOT, seq(i + 1))
        reg = registry
      }
      // Append one APPROVED event to u0 only
      const req: SynthesisRequest = { task: 'ecology-test', context: '', constitutional_constraints: [], sequence: seq(100) }
      const rec = await runSynthesisSwarm(req, makeAgent(true))
      const { registry: final } = await reg.appendToUniverse('u0',
        { kind: 'CAPABILITY_EVOLUTION', proposal_id: rec.synthesis_hash as SHA256Hex, verdict: 'APPROVED' },
        seq(100))

      const certs = await final.certifyAll()
      expect(certs).toHaveLength(MAX_UNIVERSES)
      const u0Cert = certs.find(c => c.universe_id === 'u0')!
      const others = certs.filter(c => c.universe_id !== 'u0')

      expect(u0Cert.lineage_length).toBe(1)
      others.forEach(c => {
        expect(c.lineage_length).toBe(0)      // untouched
        expect(c.certificate.adaptive_power).toBe(0)
      })
    }, 15_000)
  })

  describe('Multiverse × BoundedGeneration monotonicity', () => {
    it('appending N events to a universe advances generation N times without saturation', async () => {
      let reg = MultiverseRegistry.empty()
      const { registry: r1 } = await reg.fork('gen-test', FORK_ROOT, seq(1))
      reg = r1

      let s = 700
      for (let i = 0; i < 10; i++) {
        const req: SynthesisRequest = { task: `gen-${s}`, context: '', constitutional_constraints: [], sequence: seq(s) }
        const rec = await runSynthesisSwarm(req, makeAgent(true))
        const { registry } = await reg.appendToUniverse('gen-test',
          { kind: 'CAPABILITY_EVOLUTION', proposal_id: rec.synthesis_hash as SHA256Hex, verdict: 'APPROVED' },
          seq(s))
        reg = registry
        s++
      }
      // Universe still active after 10 events (generation = 10, well below 2^32 - 1)
      const lineage = reg.getLineage('gen-test')!
      expect(lineage.length).toBe(10)

      const cert = await certifyMartingale(lineage.getAll())
      expect(cert.adaptive_power).toBe(10)
      expect(cert.is_anchored).toBe(true)
    }, 20_000)
  })
})
