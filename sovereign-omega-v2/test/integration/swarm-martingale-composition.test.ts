// ============================================================
// Gate 72 — Swarm × Martingale Composition (Integration)
// ~18 tests: swarm convergence quorum_hash used as TOPOLOGY_TRANSITION
//   event in AdaptiveLineage → MartingaleCertificate pipeline;
//   quorum boundary mirrors martingale boundary at 1/φ.
// ============================================================

import { describe, it, expect } from 'vitest'
import { tallyVotes, DEFAULT_QUORUM_THRESHOLD } from '../../src/consensus/swarm.js'
import { AdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { certifyMartingale, MUTATION_RATE_LIMIT } from '../../src/constitutional/martingale.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

function votes(n: number, hash: SHA256Hex) {
  return Array.from({ length: n }, (_, i) => ({
    node_id: `node_${hash[0]}_${i}`,
    topology_hash: hash,
    sequence: seq(1),
  }))
}

// ─── Swarm → AdaptiveLineage pipeline ─────────────────────

describe('Swarm → AdaptiveLineage → Martingale pipeline', () => {
  it('converged swarm quorum_hash feeds TOPOLOGY_TRANSITION in lineage', async () => {
    const record = await tallyVotes([...votes(3, h('a'))])
    let lineage = AdaptiveLineage.empty()
    const { lineage: next } = await lineage.append(
      { kind: 'TOPOLOGY_TRANSITION', topology_hash: record.quorum_hash },
      seq(1),
    )
    lineage = next
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.is_anchored).toBe(true)
    expect(cert.entropy_bounded).toBe(true)
    expect(cert.adaptive_power).toBe(0)
  })

  it('10 swarm rounds → 10 TOPOLOGY_TRANSITION entries → martingale bounded', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 10; i++) {
      const record = await tallyVotes([...votes(3, h(String.fromCharCode(97 + i)))])
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: record.quorum_hash },
        seq(i),
      )
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.is_anchored).toBe(true)
    expect(cert.entropy_bounded).toBe(true)
    expect(cert.replay_verifiability).toBe(10)
    expect(cert.adaptive_power).toBe(0)
  })

  it('swarm quorum boundary 62/100 ≥ 1/φ — both constants agree', () => {
    expect(MUTATION_RATE_LIMIT).toBe(DEFAULT_QUORUM_THRESHOLD)
    expect(62 / 100 >= DEFAULT_QUORUM_THRESHOLD).toBe(true)
    expect(61 / 100 >= DEFAULT_QUORUM_THRESHOLD).toBe(false)
  })
})

// ─── Martingale + swarm at boundary ───────────────────────

describe('Swarm × Martingale: 1/φ boundary proof', () => {
  it('61 APPROVED + 39 TOPOLOGY → martingale entropy_bounded=true', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 61; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'CAPABILITY_EVOLUTION', proposal_id: h(String.fromCharCode(97 + (i % 26))), verdict: 'APPROVED' },
        seq(i),
      )
      lineage = next
    }
    for (let i = 62; i <= 100; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + (i % 26))) },
        seq(i),
      )
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.entropy_bounded).toBe(true)
    expect(cert.adaptive_power).toBe(61)
  })

  it('62 APPROVED + 38 TOPOLOGY → martingale entropy_bounded=false', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 62; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'CAPABILITY_EVOLUTION', proposal_id: h(String.fromCharCode(97 + (i % 26))), verdict: 'APPROVED' },
        seq(i),
      )
      lineage = next
    }
    for (let i = 63; i <= 100; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + (i % 26))) },
        seq(i),
      )
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.entropy_bounded).toBe(false)
    expect(cert.adaptive_power).toBe(62)
  })

  it('swarm quorum threshold === martingale mutation rate limit (same 1/φ)', () => {
    expect(DEFAULT_QUORUM_THRESHOLD).toBe(MUTATION_RATE_LIMIT)
  })

  it('62/100 above swarm threshold: quorum_reached=true', async () => {
    const ha = h('a')
    const hb = h('b')
    const vA = votes(62, ha)
    const vB = votes(38, hb)
    const record = await tallyVotes([...vA, ...vB])
    expect(record.quorum_reached).toBe(true)
  })

  it('61/100 below swarm threshold: quorum_reached=false', async () => {
    const ha = h('a')
    const hb = h('b')
    const vA = votes(61, ha)
    const vB = votes(39, hb)
    const record = await tallyVotes([...vA, ...vB])
    expect(record.quorum_reached).toBe(false)
  })
})
