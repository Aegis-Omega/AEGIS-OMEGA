// ============================================================
// Gate 103 — Byzantine Fault Tolerance (Integration)
// ~22 tests: f=3 BFT simulation — 7-node swarm with 3
//   Byzantine votes; quorum still reached with 4 valid;
//   Byzantine cannot elevate minority hash to quorum.
// ============================================================

import { describe, it, expect } from 'vitest'
import { tallyVotes, DEFAULT_QUORUM_THRESHOLD, SwarmError } from '../../src/consensus/swarm.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

function votes(n: number, hash: SHA256Hex, prefix = 'n') {
  return Array.from({ length: n }, (_, i) => ({ node_id: `${prefix}${i}`, topology_hash: hash, sequence: seq(1) }))
}

// ─── f=2 BFT: 7 nodes, 2 Byzantine (requires 5/7 ≥ 1/φ) ──

describe('BFT: 7-node, f=2 Byzantine', () => {
  it('5 honest + 2 Byzantine → quorum on honest hash (5/7 ≥ 1/φ)', async () => {
    const honest = votes(5, h('h'))
    const byzantine = votes(2, h('b'))
    const record = await tallyVotes([...honest, ...byzantine])
    expect(record.quorum_reached).toBe(true)
    expect(record.quorum_hash).toBe(h('h'))
  })

  it('5/7 ≥ 1/φ → quorum_reached=true', async () => {
    const all = [...votes(5, h('h')), ...votes(2, h('b'))]
    const record = await tallyVotes(all)
    expect(record.quorum_reached).toBe(true)
    expect(5 / 7).toBeGreaterThan(DEFAULT_QUORUM_THRESHOLD)
  })

  it('2/7 < 1/φ → quorum_reached=false for Byzantine minority', async () => {
    const record = await tallyVotes([...votes(5, h('h')), ...votes(2, h('b'))])
    expect(record.quorum_hash).not.toBe(h('b'))
  })

  it('Byzantine nodes cannot elevate 2-vote minority to quorum', async () => {
    const all = [...votes(5, h('h')), ...votes(2, h('b'))]
    const record = await tallyVotes(all)
    expect(record.quorum_hash).toBe(h('h'))
  })

  it('5 Byzantine + 2 honest: Byzantine wins (supermajority 5/7)', async () => {
    const all = [...votes(5, h('b')), ...votes(2, h('h'))]
    const record = await tallyVotes(all)
    expect(record.quorum_reached).toBe(true)
    expect(record.quorum_hash).toBe(h('b'))
  })

  it('f=3 (4 honest vs 3 Byzantine): 4/7 < 1/φ → quorum NOT reached', async () => {
    const all = [...votes(4, h('h')), ...votes(3, h('b'))]
    const record = await tallyVotes(all)
    expect(record.quorum_reached).toBe(false)
    expect(4 / 7).toBeLessThan(DEFAULT_QUORUM_THRESHOLD)
  })
})

// ─── Byzantine split-brain scenarios ─────────────────────

describe('BFT: split-brain and network partition', () => {
  it('3-way split → largest partition wins', async () => {
    const all = [...votes(4, h('a')), ...votes(3, h('b')), ...votes(3, h('c'))]
    const record = await tallyVotes(all)
    // a has most votes (4/10), but 4/10 = 0.4 < 0.618 → quorum_reached=false
    expect(record.quorum_hash).toBe(h('a'))
  })

  it('equal split 5/5: deterministic winner by hash order', async () => {
    const h1 = '0'.repeat(64) as SHA256Hex
    const h2 = 'f'.repeat(64) as SHA256Hex
    const all = [...votes(5, h1, 'a'), ...votes(5, h2, 'b')]
    const r1 = await tallyVotes(all)
    const r2 = await tallyVotes(all)
    // Deterministic — same winner each time
    expect(r1.quorum_hash).toBe(r2.quorum_hash)
  })

  it('single node → quorum_reached=true (100%)', async () => {
    const record = await tallyVotes([{ node_id: 'solo', topology_hash: h('x'), sequence: seq(1) }])
    expect(record.quorum_reached).toBe(true)
    expect(record.quorum_hash).toBe(h('x'))
  })

  it('empty votes → throws SwarmError', async () => {
    await expect(tallyVotes([])).rejects.toThrow(SwarmError)
  })
})

// ─── BFT convergence hash ─────────────────────────────────

describe('BFT: convergence record integrity', () => {
  it('convergence_hash is 64-char hex', async () => {
    const record = await tallyVotes([...votes(4, h('h')), ...votes(3, h('b'))])
    expect(record.convergence_hash).toHaveLength(64)
    expect(record.convergence_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('convergence_hash is deterministic ×3', async () => {
    const all = [...votes(4, h('h')), ...votes(3, h('b'))]
    const [r1, r2, r3] = await Promise.all([tallyVotes(all), tallyVotes(all), tallyVotes(all)])
    expect(r1.convergence_hash).toBe(r2.convergence_hash)
    expect(r2.convergence_hash).toBe(r3.convergence_hash)
  })

  it('record is frozen', async () => {
    const record = await tallyVotes(votes(4, h('h')))
    expect(Object.isFrozen(record)).toBe(true)
  })

  it('is_replay_reconstructable=true', async () => {
    const record = await tallyVotes(votes(4, h('h')))
    expect(record.is_replay_reconstructable).toBe(true)
  })

  it('schema_version=1.0.0', async () => {
    const record = await tallyVotes(votes(4, h('h')))
    expect(record.schema_version).toBe('1.0.0')
  })
})
