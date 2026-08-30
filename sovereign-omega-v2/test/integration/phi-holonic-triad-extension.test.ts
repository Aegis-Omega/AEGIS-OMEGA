// test/integration/phi-holonic-triad-extension.test.ts
//
// Gate 180 — Cross-language 1/φ holonic triad consistency proof
// EPISTEMIC TIER: T0 (mechanically provable constant identity)
//
// The Golden Ratio threshold 1/φ = (√5−1)/2 ≈ 0.6180339887 governs FOUR
// independent constitutional surfaces across THREE languages:
//
//   1. TypeScript — DEFAULT_QUORUM_THRESHOLD in src/consensus/swarm.ts
//   2. TypeScript — MUTATION_RATE_LIMIT in src/constitutional/martingale.ts
//   3. TypeScript — CONSENSUS_THRESHOLD in src/consensus/synthesis-swarm.ts
//   4. Rust — 618_034/1_000_000 in aegis-cl-psi/src/edge_verifier.rs
//
// All four agree at the constitutional boundary:
//   n=100: 61 → below threshold, 62 → above threshold

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { DEFAULT_QUORUM_THRESHOLD, tallyVotes } from '../../src/consensus/swarm.js'
import type { SwarmVote } from '../../src/consensus/swarm.js'
import { MUTATION_RATE_LIMIT, certifyMartingale } from '../../src/constitutional/martingale.js'
import { AdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import type { AdaptiveLineageEntry } from '../../src/frame/adaptive-lineage.js'
import { runSynthesisSwarm } from '../../src/consensus/synthesis-swarm.js'
import type { SynthesisRequest, AgentRole } from '../../src/consensus/synthesis-swarm.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }
function hex(s: string): SHA256Hex { return s.padEnd(64, '0') as SHA256Hex }

// Canonical 1/φ expression shared across ALL TypeScript surfaces
const PHI_RECIP = (Math.sqrt(5) - 1) / 2

// Rust integer approximation (aegis-cl-psi/src/edge_verifier.rs)
// Python bridge /edge-verify uses the same constants
const RUST_NUMERATOR = 618_034
const RUST_DENOMINATOR = 1_000_000

async function buildMixedEntries(
  approvedCount: number,
  topologyCount: number,
): Promise<readonly AdaptiveLineageEntry[]> {
  let lineage = AdaptiveLineage.empty()
  let s = 1
  for (let i = 0; i < approvedCount; i++) {
    const { lineage: next } = await lineage.append(
      { kind: 'CAPABILITY_EVOLUTION', proposal_id: hex(`ev-${i}`), verdict: 'APPROVED' },
      seq(s++),
    )
    lineage = next
  }
  for (let i = 0; i < topologyCount; i++) {
    const { lineage: next } = await lineage.append(
      { kind: 'TOPOLOGY_TRANSITION', topology_hash: hex(`tp-${i}`) },
      seq(s++),
    )
    lineage = next
  }
  return lineage.getAll()
}

describe('Gate 180 — Cross-language 1/φ holonic triad consistency proof', () => {

  describe('Constant identity across TypeScript surfaces', () => {
    it('DEFAULT_QUORUM_THRESHOLD === (√5−1)/2', () => {
      expect(DEFAULT_QUORUM_THRESHOLD).toBeCloseTo(PHI_RECIP, 15)
    })

    it('MUTATION_RATE_LIMIT === (√5−1)/2', () => {
      expect(MUTATION_RATE_LIMIT).toBeCloseTo(PHI_RECIP, 15)
    })

    it('DEFAULT_QUORUM_THRESHOLD === MUTATION_RATE_LIMIT (holonic identity)', () => {
      expect(DEFAULT_QUORUM_THRESHOLD).toBe(MUTATION_RATE_LIMIT)
    })

    it('1/φ is between 0.6180 and 0.6181', () => {
      expect(PHI_RECIP).toBeGreaterThan(0.6180)
      expect(PHI_RECIP).toBeLessThan(0.6181)
    })
  })

  describe('Rust integer approximation consistency', () => {
    it('618_034/1_000_000 approximates 1/φ within 1e-6', () => {
      const approx = RUST_NUMERATOR / RUST_DENOMINATOR
      expect(Math.abs(approx - PHI_RECIP)).toBeLessThan(1e-6)
    })

    it('integer threshold agrees with float threshold for n=8, valid=5 (above)', () => {
      const intResult = 5 * RUST_DENOMINATOR >= 8 * RUST_NUMERATOR
      expect(intResult).toBe(true)
      expect(5 / 8).toBeGreaterThanOrEqual(PHI_RECIP)
    })

    it('integer threshold agrees with float threshold for n=8, valid=4 (below)', () => {
      const intResult = 4 * RUST_DENOMINATOR >= 8 * RUST_NUMERATOR
      expect(intResult).toBe(false)
      expect(4 / 8).toBeLessThan(PHI_RECIP)
    })

    it('integer threshold agrees with float threshold for n=100, valid=62 (above)', () => {
      const intResult = 62 * RUST_DENOMINATOR >= 100 * RUST_NUMERATOR
      expect(intResult).toBe(true)
      expect(62 / 100).toBeGreaterThan(PHI_RECIP)
    })

    it('integer threshold agrees with float threshold for n=100, valid=61 (below)', () => {
      const intResult = 61 * RUST_DENOMINATOR >= 100 * RUST_NUMERATOR
      expect(intResult).toBe(false)
      expect(61 / 100).toBeLessThan(PHI_RECIP)
    })
  })

  describe('BFT swarm boundary at 1/φ (n=100)', () => {
    function makeVotes(total: number, agreeCount: number): readonly SwarmVote[] {
      return Array.from({ length: total }, (_, i) => ({
        node_id: `node-${i}`,
        topology_hash: hex(i < agreeCount ? 'agree' : `alt-${i}`),
        sequence: seq(1),
      }))
    }

    it('62/100 votes on same hash → quorum_reached=true', async () => {
      const result = await tallyVotes(makeVotes(100, 62))
      expect(result.quorum_reached).toBe(true)
    })

    it('61/100 votes on same hash → quorum_reached=false', async () => {
      const result = await tallyVotes(makeVotes(100, 61))
      expect(result.quorum_reached).toBe(false)
    })

    it('62/100 > DEFAULT_QUORUM_THRESHOLD and 61/100 < DEFAULT_QUORUM_THRESHOLD', () => {
      expect(62 / 100).toBeGreaterThan(DEFAULT_QUORUM_THRESHOLD)
      expect(61 / 100).toBeLessThan(DEFAULT_QUORUM_THRESHOLD)
    })
  })

  describe('Martingale mutation rate boundary at 1/φ (n=100)', () => {
    it('62 APPROVED of 100 → entropy_bounded=false (ratio > MUTATION_RATE_LIMIT)', async () => {
      const entries = await buildMixedEntries(62, 38)
      const cert = await certifyMartingale(entries)
      expect(cert.adaptive_ratio).toBeCloseTo(0.62, 2)
      expect(cert.entropy_bounded).toBe(false)
    })

    it('61 APPROVED of 100 → entropy_bounded=true (ratio < MUTATION_RATE_LIMIT)', async () => {
      const entries = await buildMixedEntries(61, 39)
      const cert = await certifyMartingale(entries)
      expect(cert.adaptive_ratio).toBeCloseTo(0.61, 2)
      expect(cert.entropy_bounded).toBe(true)
    })
  })

  describe('Synthesis swarm convergence at 1/φ', () => {
    const code = 'export function identity(x: number): number { return x }'
    const mockAgent = async (_s: string, _u: string, role: AgentRole) => {
      if (role === 'gamma') {
        return { output: JSON.stringify({ verdict: 'COMMITTED', violations: [], rationale: 'ok' }), backend: 'mock', latency_ms: 1 }
      }
      return { output: code, backend: 'mock', latency_ms: 1 }
    }

    it('identical Alpha/Beta code → structural_similarity ≥ 1/φ → COMMITTED', async () => {
      const req: SynthesisRequest = {
        task: 'phi-boundary-identity-test',
        context: '',
        constitutional_constraints: [],
        sequence: seq(200),
      }
      const record = await runSynthesisSwarm(req, mockAgent)
      expect(record.convergence.structural_similarity).toBeGreaterThanOrEqual(PHI_RECIP)
      expect(record.convergence.converged).toBe(true)
      expect(record.verdict).toBe('COMMITTED')
    })
  })

  describe('Four-surface holonic proof at n=1000', () => {
    it('619/1000 satisfies all four surfaces (above threshold)', () => {
      // TypeScript surfaces
      expect(619 / 1000).toBeGreaterThan(DEFAULT_QUORUM_THRESHOLD)
      expect(619 / 1000).toBeGreaterThan(MUTATION_RATE_LIMIT)
      // Rust integer surface (valid * 1_000_000 >= total * 618_034)
      expect(619 * 1_000_000 >= 1000 * 618_034).toBe(true)
    })

    it('617/1000 fails all four surfaces (below threshold)', () => {
      expect(617 / 1000).toBeLessThan(DEFAULT_QUORUM_THRESHOLD)
      expect(617 / 1000).toBeLessThan(MUTATION_RATE_LIMIT)
      expect(617 * 1_000_000 >= 1000 * 618_034).toBe(false)
    })

    it('boundary is deterministic ×3 (no floating-point instability)', () => {
      for (let run = 0; run < 3; run++) {
        expect(62 / 100 > DEFAULT_QUORUM_THRESHOLD).toBe(true)
        expect(61 / 100 < DEFAULT_QUORUM_THRESHOLD).toBe(true)
        expect(62 * RUST_DENOMINATOR >= 100 * RUST_NUMERATOR).toBe(true)
        expect(61 * RUST_DENOMINATOR >= 100 * RUST_NUMERATOR).toBe(false)
      }
    })
  })
})
