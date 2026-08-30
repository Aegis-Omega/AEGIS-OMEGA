// ============================================================
// Gate 58 — Swarm Convergence Adversarial
// ~22 tests: tallyVotes at 100-vote scale. DEFAULT_QUORUM_THRESHOLD
//   is 1/φ ≈ 0.6180339887 (golden ratio reciprocal).
//   Boundary: 62/100 = 0.62 ≥ 1/φ → true; 61/100 = 0.61 < 1/φ → false.
//   3-way split with known winner, tie-breaking (lex first hash),
//   custom threshold, sequence mismatch, 10× concurrent
//   determinism, convergence_hash sensitivity.
//
// Gaps filled vs test/unit/swarm.test.ts:
//   - 100-vote unanimous tally (vote_count=100)
//   - 70/30 split → quorum_reached=true
//   - Golden ratio boundary: 62/100 = 0.62 ≥ 1/φ → true
//   - Sub-threshold: 61/100 = 0.61 < 1/φ → false
//   - 3-way split: 50/30/20 → quorum_hash correct (max wins)
//   - Tie 50/50: lexicographically first topology_hash wins
//   - Custom threshold 0.5: 50/100 = exactly 0.5 → true
//   - 10 concurrent tallyVotes → identical convergence_hash
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  tallyVotes, SwarmError,
  DEFAULT_QUORUM_THRESHOLD,
  type SwarmVote,
} from '../../src/consensus/swarm.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const HA = h('a')
const HB = h('b')
const HC = h('c')
const HD = h('d')

function votes(
  n: number,
  topology_hash: SHA256Hex,
  s: SequenceNumber = seq(1),
): SwarmVote[] {
  return Array.from({ length: n }, (_, i) => ({
    node_id: `node-${topology_hash.slice(0, 1)}-${i}`,
    topology_hash,
    sequence: s,
  }))
}

// ─── Scale: 100-vote sets ─────────────────────────────────

describe('Swarm: 100-vote scale tests', () => {
  it('100 unanimous votes → quorum_reached=true, vote_count=100', async () => {
    const result = await tallyVotes([...votes(100, HA)])
    expect(result.quorum_reached).toBe(true)
    expect(result.vote_count).toBe(100)
    expect(result.quorum_hash).toBe(HA)
  })

  it('70/30 split → quorum_reached=true (0.70 ≥ 1/φ)', async () => {
    const result = await tallyVotes([...votes(70, HA), ...votes(30, HB)])
    expect(result.quorum_reached).toBe(true)
    expect(result.quorum_hash).toBe(HA)
    expect(result.vote_count).toBe(70)
  })

  it('golden ratio boundary: 62/100 = 0.62 ≥ 1/φ → quorum_reached=true', async () => {
    const result = await tallyVotes([...votes(62, HA), ...votes(38, HB)])
    expect(result.quorum_reached).toBe(true)
    expect(result.vote_count).toBe(62)
    expect(result.quorum_hash).toBe(HA)
  })

  it('sub-threshold: 61/100 = 0.61 < 1/φ ≈ 0.618 → quorum_reached=false', async () => {
    const result = await tallyVotes([...votes(61, HA), ...votes(39, HB)])
    expect(result.quorum_reached).toBe(false)
    expect(result.vote_count).toBe(61)
  })
})

// ─── Multi-hash scenarios ─────────────────────────────────

describe('Swarm: multi-hash scenarios', () => {
  it('3-way split 50/30/20 → quorum_hash = h("a") (max votes)', async () => {
    const result = await tallyVotes([...votes(50, HA), ...votes(30, HB), ...votes(20, HC)])
    expect(result.quorum_hash).toBe(HA)
    expect(result.vote_count).toBe(50)
  })

  it('tie 50/50: lexicographically first hash wins (h("a") < h("b"))', async () => {
    // HA = 'a'.repeat(64), HB = 'b'.repeat(64); HA < HB lexicographically
    const result = await tallyVotes([...votes(50, HA), ...votes(50, HB)])
    expect(result.quorum_hash).toBe(HA)
    expect(result.vote_count).toBe(50)
    // 50/100 = 0.50 < 1/φ ≈ 0.618 → quorum_reached=false (tie below threshold)
    expect(result.quorum_reached).toBe(false)
  })

  it('4-way equal split (25 each): lexicographically first hash wins', async () => {
    const result = await tallyVotes([
      ...votes(25, HA), ...votes(25, HB), ...votes(25, HC), ...votes(25, HD),
    ])
    // HA < HB < HC < HD → HA wins
    expect(result.quorum_hash).toBe(HA)
    expect(result.vote_count).toBe(25)
    expect(result.quorum_reached).toBe(false)  // 25/100 = 0.25 < 1/φ
  })
})

// ─── Custom threshold ─────────────────────────────────────

describe('Swarm: custom quorum threshold', () => {
  it('custom threshold 0.5: 50/100 = 0.5 ≥ 0.5 → quorum_reached=true', async () => {
    const result = await tallyVotes([...votes(50, HA), ...votes(50, HB)], 0.5)
    expect(result.quorum_reached).toBe(true)
    expect(result.quorum_threshold).toBe(0.5)
  })

  it('custom threshold 0.5: 3-way 40/35/25 split, winner 40/100=0.4 < 0.5 → false', async () => {
    const result = await tallyVotes([...votes(40, HA), ...votes(35, HB), ...votes(25, HC)], 0.5)
    expect(result.quorum_reached).toBe(false)
    expect(result.quorum_hash).toBe(HA)  // HA has 40 votes = max
  })

  it('custom threshold 0.9: 89/100 < 0.9 → quorum_reached=false', async () => {
    const result = await tallyVotes([...votes(89, HA), ...votes(11, HB)], 0.9)
    expect(result.quorum_reached).toBe(false)
  })

  it('custom threshold 0.9: 90/100 = 0.9 ≥ 0.9 → quorum_reached=true', async () => {
    const result = await tallyVotes([...votes(90, HA), ...votes(10, HB)], 0.9)
    expect(result.quorum_reached).toBe(true)
  })
})

// ─── Error cases ──────────────────────────────────────────

describe('Swarm: error cases', () => {
  it('sequence mismatch across votes → SwarmError', async () => {
    const mixed = [
      { node_id: 'n0', topology_hash: HA, sequence: seq(1) },
      { node_id: 'n1', topology_hash: HA, sequence: seq(2) },  // different sequence
    ]
    await expect(tallyVotes(mixed)).rejects.toThrow(SwarmError)
  })

  it('single vote → quorum_reached=true (1/1 = 1.0 ≥ 1/φ)', async () => {
    const result = await tallyVotes([{ node_id: 'n0', topology_hash: HA, sequence: seq(5) }])
    expect(result.quorum_reached).toBe(true)
    expect(result.vote_count).toBe(1)
  })

  it('result is frozen and is_replay_reconstructable=true', async () => {
    const result = await tallyVotes(votes(3, HA))
    expect(Object.isFrozen(result)).toBe(true)
    expect(result.is_replay_reconstructable).toBe(true)
  })
})

// ─── Convergence hash determinism ─────────────────────────

describe('Swarm: convergence_hash determinism', () => {
  it('10 concurrent tallyVotes on identical input → identical convergence_hash', async () => {
    const input = [...votes(70, HA), ...votes(30, HB)]
    const results = await Promise.all(Array.from({ length: 10 }, () => tallyVotes(input)))
    for (const r of results) {
      expect(r.convergence_hash).toBe(results[0]!.convergence_hash)
    }
  })

  it('different quorum_reached → different convergence_hash', async () => {
    const trueResult = await tallyVotes([...votes(70, HA), ...votes(30, HB)])  // quorum=true
    const falseResult = await tallyVotes([...votes(60, HA), ...votes(40, HB)]) // quorum=false
    expect(trueResult.convergence_hash).not.toBe(falseResult.convergence_hash)
  })

  it('convergence_hash is 64-char hex', async () => {
    const result = await tallyVotes(votes(5, HA))
    expect(result.convergence_hash).toHaveLength(64)
    expect(result.convergence_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('DEFAULT_QUORUM_THRESHOLD stored in quorum_threshold field', async () => {
    const result = await tallyVotes(votes(5, HA))
    expect(result.quorum_threshold).toBe(DEFAULT_QUORUM_THRESHOLD)
  })
})
