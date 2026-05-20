// ============================================================
// Gate 34 — Swarm Convergence Protocol Tests
// ~26 tests: tallyVotes, quorum thresholds, tie-breaking,
//   hash determinism, error cases, constants.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import {
  tallyVotes,
  SwarmError,
  SWARM_SCHEMA_VERSION,
  DEFAULT_QUORUM_THRESHOLD,
  type SwarmVote,
} from '../../src/consensus/swarm.js'

// ─── Helpers ───────────────────────────────────────────────

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }
function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }

const SEQ = seq(1)
const HA = h('a')
const HB = h('b')
const HC = h('c')

function vote(node_id: string, topology_hash: SHA256Hex, sequence: SequenceNumber = SEQ): SwarmVote {
  return { node_id, topology_hash, sequence }
}

// ─── Constants ─────────────────────────────────────────────

describe('constants', () => {
  it('SWARM_SCHEMA_VERSION is 1.0.0', () => {
    expect(SWARM_SCHEMA_VERSION).toBe('1.0.0')
  })

  it('DEFAULT_QUORUM_THRESHOLD is 1/φ (golden ratio reciprocal ≈ 0.6180339887)', () => {
    expect(DEFAULT_QUORUM_THRESHOLD).toBe((Math.sqrt(5) - 1) / 2)
    expect(DEFAULT_QUORUM_THRESHOLD).toBeCloseTo(0.6180339887, 9)
  })
})

// ─── SwarmError ────────────────────────────────────────────

describe('SwarmError', () => {
  it('is an Error subclass', () => {
    const e = new SwarmError('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('SwarmError')
    expect(e.message).toBe('test')
  })
})

// ─── tallyVotes — error cases ──────────────────────────────

describe('tallyVotes — error cases', () => {
  it('empty votes throws SwarmError', async () => {
    await expect(tallyVotes([])).rejects.toThrow(SwarmError)
  })

  it('sequence mismatch throws SwarmError', async () => {
    const votes = [vote('n1', HA, seq(1)), vote('n2', HA, seq(2))]
    await expect(tallyVotes(votes)).rejects.toThrow(SwarmError)
  })

  it('error message mentions sequence on mismatch', async () => {
    const votes = [vote('n1', HA, seq(1)), vote('n2', HA, seq(9))]
    const err = await tallyVotes(votes).catch((e: unknown) => e)
    expect((err as Error).message).toContain('9')
  })
})

// ─── tallyVotes — quorum logic ─────────────────────────────

describe('tallyVotes — quorum logic', () => {
  it('single vote → quorum_reached=true', async () => {
    const result = await tallyVotes([vote('n1', HA)])
    expect(result.quorum_reached).toBe(true)
    expect(result.quorum_hash).toBe(HA)
    expect(result.vote_count).toBe(1)
  })

  it('all votes identical → quorum_reached=true', async () => {
    const votes = [vote('n1', HA), vote('n2', HA), vote('n3', HA)]
    const result = await tallyVotes(votes)
    expect(result.quorum_reached).toBe(true)
    expect(result.quorum_hash).toBe(HA)
    expect(result.vote_count).toBe(3)
  })

  it('supermajority (3 of 4) with default threshold → quorum_reached=true', async () => {
    const votes = [vote('n1', HA), vote('n2', HA), vote('n3', HA), vote('n4', HB)]
    const result = await tallyVotes(votes)
    expect(result.quorum_reached).toBe(true)  // 3/4=0.75 >= 0.67
    expect(result.quorum_hash).toBe(HA)
    expect(result.vote_count).toBe(3)
  })

  it('minority (1 of 3 unique nodes agree) → quorum_reached=false', async () => {
    const votes = [vote('n1', HA), vote('n2', HB), vote('n3', HC)]
    const result = await tallyVotes(votes)
    expect(result.quorum_reached).toBe(false)  // max=1/3 < 0.67
    expect(result.vote_count).toBe(1)
  })

  it('split (2 of 3) with default threshold → quorum_reached=true', async () => {
    // 2/3 ≈ 0.6667 >= 1/φ ≈ 0.6180 — clears the golden ratio threshold
    const votes = [vote('n1', HB), vote('n2', HB), vote('n3', HA)]
    const result = await tallyVotes(votes)
    expect(result.quorum_reached).toBe(true)
  })

  it('split (2 of 3) with custom threshold 0.60 → quorum_reached=true', async () => {
    const votes = [vote('n1', HA), vote('n2', HA), vote('n3', HB)]
    const result = await tallyVotes(votes, 0.60)
    expect(result.quorum_reached).toBe(true)  // 2/3=0.667 >= 0.60
  })

  it('split (2 of 3) with custom threshold 0.70 → quorum_reached=false', async () => {
    const votes = [vote('n1', HA), vote('n2', HA), vote('n3', HB)]
    const result = await tallyVotes(votes, 0.70)
    expect(result.quorum_reached).toBe(false)  // 2/3=0.667 < 0.70
  })
})

// ─── Tie-breaking ──────────────────────────────────────────

describe('tallyVotes — tie-breaking', () => {
  it('tie → lexicographically first topology_hash wins', async () => {
    // HA='aaa...' < HB='bbb...' — HA wins
    const votes = [vote('n1', HB), vote('n2', HB), vote('n3', HA), vote('n4', HA)]
    const result = await tallyVotes(votes)
    expect(result.quorum_hash).toBe(HA)  // 'a'.repeat(64) < 'b'.repeat(64)
    expect(result.vote_count).toBe(2)
  })

  it('tie result is deterministic regardless of vote order', async () => {
    const v1 = [vote('n1', HB), vote('n2', HB), vote('n3', HA), vote('n4', HA)]
    const v2 = [vote('n3', HA), vote('n4', HA), vote('n1', HB), vote('n2', HB)]
    const r1 = await tallyVotes(v1)
    const r2 = await tallyVotes(v2)
    expect(r1.quorum_hash).toBe(r2.quorum_hash)
  })
})

// ─── Record properties ─────────────────────────────────────

describe('SwarmConvergenceRecord structure', () => {
  it('record is frozen', async () => {
    const result = await tallyVotes([vote('n1', HA)])
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('is_replay_reconstructable is true', async () => {
    const result = await tallyVotes([vote('n1', HA)])
    expect(result.is_replay_reconstructable).toBe(true)
  })

  it('schema_version is 1.0.0', async () => {
    const result = await tallyVotes([vote('n1', HA)])
    expect(result.schema_version).toBe('1.0.0')
  })

  it('sequence matches vote sequence', async () => {
    const result = await tallyVotes([vote('n1', HA, seq(42))])
    expect(result.sequence).toBe(seq(42))
  })

  it('quorum_threshold matches argument', async () => {
    const result = await tallyVotes([vote('n1', HA)], 0.80)
    expect(result.quorum_threshold).toBe(0.80)
  })
})

// ─── Hash determinism ──────────────────────────────────────

describe('convergence_hash', () => {
  it('is 64-char hex', async () => {
    const result = await tallyVotes([vote('n1', HA)])
    expect(result.convergence_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(result.convergence_hash)).toBe(true)
  })

  it('is deterministic × 3', async () => {
    const votes = [vote('n1', HA), vote('n2', HA), vote('n3', HB)]
    const h1 = (await tallyVotes(votes)).convergence_hash
    const h2 = (await tallyVotes(votes)).convergence_hash
    const h3 = (await tallyVotes(votes)).convergence_hash
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('different topology_hash → different convergence_hash', async () => {
    const r1 = await tallyVotes([vote('n1', HA)])
    const r2 = await tallyVotes([vote('n1', HB)])
    expect(r1.convergence_hash).not.toBe(r2.convergence_hash)
  })

  it('different sequence → different convergence_hash', async () => {
    const r1 = await tallyVotes([vote('n1', HA, seq(1))])
    const r2 = await tallyVotes([vote('n1', HA, seq(2))])
    expect(r1.convergence_hash).not.toBe(r2.convergence_hash)
  })
})
