// ============================================================
// Gate 76 — Consensus × Attestation Composition (Integration)
// ~18 tests: SwarmConvergenceRecord.quorum_hash feeds
//   SelfAttestationRecord.topology_hash; attestation encodes
//   the consensus state; different quorums → different attestations.
// ============================================================

import { describe, it, expect } from 'vitest'
import { tallyVotes } from '../../src/consensus/swarm.js'
import { buildSelfAttestation, verifySelfAttestation } from '../../src/frame/attestation.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

function votes(n: number, hash: SHA256Hex) {
  return Array.from({ length: n }, (_, i) => ({
    node_id: `n${i}`,
    topology_hash: hash,
    sequence: seq(1),
  }))
}

// ─── Swarm → Attestation pipeline ─────────────────────────

describe('Consensus → Attestation composition', () => {
  it('converged quorum_hash → valid SelfAttestationRecord', async () => {
    const record = await tallyVotes([...votes(3, h('a'))])
    expect(record.quorum_reached).toBe(true)
    const attestation = await buildSelfAttestation({
      dfa_certificate_hash: h('d'),
      topology_hash: record.quorum_hash,
      lineage_terminal_hash: null,
      capsule_attestation_hash: null,
      sequence: record.sequence,
    })
    expect(await verifySelfAttestation(attestation)).toBe(true)
    expect(attestation.topology_hash).toBe(record.quorum_hash)
  })

  it('different quorum_hashes → different attestation_hashes', async () => {
    const r1 = await tallyVotes([...votes(3, h('a'))])
    const r2 = await tallyVotes([...votes(3, h('b'))])
    const a1 = await buildSelfAttestation({ dfa_certificate_hash: h('d'), topology_hash: r1.quorum_hash, lineage_terminal_hash: null, capsule_attestation_hash: null, sequence: seq(1) })
    const a2 = await buildSelfAttestation({ dfa_certificate_hash: h('d'), topology_hash: r2.quorum_hash, lineage_terminal_hash: null, capsule_attestation_hash: null, sequence: seq(1) })
    expect(a1.attestation_hash).not.toBe(a2.attestation_hash)
  })

  it('convergence_hash encodes quorum state → different sequences → different hashes', async () => {
    const voteSet = votes(3, h('a'))
    const r1 = await tallyVotes(voteSet.map(v => ({ ...v, sequence: seq(1) })))
    const r2 = await tallyVotes(voteSet.map(v => ({ ...v, sequence: seq(2) })))
    expect(r1.convergence_hash).not.toBe(r2.convergence_hash)
  })

  it('5 swarm rounds → 5 distinct attestation_hashes', async () => {
    const hashes = new Set<string>()
    for (let i = 1; i <= 5; i++) {
      const record = await tallyVotes(votes(3, h(String.fromCharCode(97 + i))).map(v => ({ ...v, sequence: seq(i) })))
      const attestation = await buildSelfAttestation({
        dfa_certificate_hash: h('d'),
        topology_hash: record.quorum_hash,
        lineage_terminal_hash: null,
        capsule_attestation_hash: null,
        sequence: record.sequence,
      })
      hashes.add(attestation.attestation_hash)
    }
    expect(hashes.size).toBe(5)
  })
})

// ─── SwarmConvergenceRecord structural guarantees ─────────

describe('Consensus: SwarmConvergenceRecord structure', () => {
  it('record is frozen', async () => {
    const record = await tallyVotes([...votes(3, h('a'))])
    expect(Object.isFrozen(record)).toBe(true)
  })

  it('convergence_hash is 64-char hex', async () => {
    const record = await tallyVotes([...votes(3, h('a'))])
    expect(record.convergence_hash).toHaveLength(64)
    expect(record.convergence_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('is_replay_reconstructable=true', async () => {
    const record = await tallyVotes([...votes(3, h('a'))])
    expect(record.is_replay_reconstructable).toBe(true)
  })

  it('same votes × 3 → identical convergence_hash (deterministic)', async () => {
    const voteSet = votes(3, h('a'))
    const [r1, r2, r3] = await Promise.all([tallyVotes(voteSet), tallyVotes(voteSet), tallyVotes(voteSet)])
    expect(r1!.convergence_hash).toBe(r2!.convergence_hash)
    expect(r2!.convergence_hash).toBe(r3!.convergence_hash)
  })

  it('vote_count and quorum_threshold reflected in record', async () => {
    const record = await tallyVotes([...votes(7, h('a')), ...votes(3, h('b'))])
    expect(record.vote_count).toBe(7)  // max votes for quorum_hash
    expect(record.quorum_threshold).toBeGreaterThan(0)
  })
})
