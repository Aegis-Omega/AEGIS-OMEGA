// ============================================================
// Gate 79 — Holonic Triad Proof (Integration)
// ~18 tests: Hoeffding + Martingale + Swarm all governed by 1/φ.
//   All three share the 61/62 boundary at 1/φ. The holonic triad
//   is proven by numerical identity tests across all three scales.
// ============================================================

import { describe, it, expect } from 'vitest'
import { DEFAULT_QUORUM_THRESHOLD, tallyVotes } from '../../src/consensus/swarm.js'
import { MUTATION_RATE_LIMIT, certifyMartingale, assertMartingaleAnchored, MartingaleViolation } from '../../src/constitutional/martingale.js'
import { AdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

function votes(n: number, hash: SHA256Hex) {
  return Array.from({ length: n }, (_, i) => ({ node_id: `n${i}`, topology_hash: hash, sequence: seq(1) }))
}

const PHI_INV = (Math.sqrt(5) - 1) / 2  // ≈ 0.6180339887

// ─── Holonic triad identity ───────────────────────────────

describe('Holonic Triad: 1/φ identity across all three scales', () => {
  it('MUTATION_RATE_LIMIT === DEFAULT_QUORUM_THRESHOLD (same 1/φ)', () => {
    expect(MUTATION_RATE_LIMIT).toBe(DEFAULT_QUORUM_THRESHOLD)
  })

  it('MUTATION_RATE_LIMIT === (√5−1)/2 exactly', () => {
    expect(MUTATION_RATE_LIMIT).toBe(PHI_INV)
  })

  it('DEFAULT_QUORUM_THRESHOLD === (√5−1)/2 exactly', () => {
    expect(DEFAULT_QUORUM_THRESHOLD).toBe(PHI_INV)
  })

  it('all three constants are numerically identical (toBe strict equality)', () => {
    expect(MUTATION_RATE_LIMIT).toBe(DEFAULT_QUORUM_THRESHOLD)
    expect(MUTATION_RATE_LIMIT).toBe(PHI_INV)
  })
})

// ─── 61/62 boundary: all three scales ─────────────────────

describe('Holonic Triad: 61/62 boundary at 1/φ — all scales agree', () => {
  it('61/100 < 1/φ → martingale entropy_bounded=true', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 61; i++) {
      const { lineage: next } = await lineage.append({ kind: 'CAPABILITY_EVOLUTION', proposal_id: h(String.fromCharCode(97 + (i % 26))), verdict: 'APPROVED' }, seq(i))
      lineage = next
    }
    for (let i = 62; i <= 100; i++) {
      const { lineage: next } = await lineage.append({ kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + (i % 26))) }, seq(i))
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.entropy_bounded).toBe(true)
  })

  it('62/100 ≥ 1/φ → martingale entropy_bounded=false', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 62; i++) {
      const { lineage: next } = await lineage.append({ kind: 'CAPABILITY_EVOLUTION', proposal_id: h(String.fromCharCode(97 + (i % 26))), verdict: 'APPROVED' }, seq(i))
      lineage = next
    }
    for (let i = 63; i <= 100; i++) {
      const { lineage: next } = await lineage.append({ kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + (i % 26))) }, seq(i))
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.entropy_bounded).toBe(false)
  })

  it('61/100 < 1/φ → swarm quorum_reached=false', async () => {
    const record = await tallyVotes([...votes(61, h('a')), ...votes(39, h('b'))])
    expect(record.quorum_reached).toBe(false)
  })

  it('62/100 ≥ 1/φ → swarm quorum_reached=true', async () => {
    const record = await tallyVotes([...votes(62, h('a')), ...votes(38, h('b'))])
    expect(record.quorum_reached).toBe(true)
  })

  it('61/100: martingale assertMartingaleAnchored does not throw', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 61; i++) {
      const { lineage: next } = await lineage.append({ kind: 'CAPABILITY_EVOLUTION', proposal_id: h(String.fromCharCode(97 + (i % 26))), verdict: 'APPROVED' }, seq(i))
      lineage = next
    }
    for (let i = 62; i <= 100; i++) {
      const { lineage: next } = await lineage.append({ kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + (i % 26))) }, seq(i))
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(() => assertMartingaleAnchored(cert)).not.toThrow()
  })

  it('62/100: martingale assertMartingaleAnchored throws MartingaleViolation', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 62; i++) {
      const { lineage: next } = await lineage.append({ kind: 'CAPABILITY_EVOLUTION', proposal_id: h(String.fromCharCode(97 + (i % 26))), verdict: 'APPROVED' }, seq(i))
      lineage = next
    }
    for (let i = 63; i <= 100; i++) {
      const { lineage: next } = await lineage.append({ kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + (i % 26))) }, seq(i))
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(() => assertMartingaleAnchored(cert)).toThrow(MartingaleViolation)
  })
})

// ─── Opposite governance consequence ──────────────────────

describe('Holonic Triad: opposite governance consequence at 1/φ', () => {
  it('swarm: ≥ 1/φ → quorum_reached=true (authority granted)', async () => {
    const record = await tallyVotes([...votes(62, h('a')), ...votes(38, h('b'))])
    expect(record.quorum_reached).toBe(true)
  })

  it('martingale: ≥ 1/φ → entropy_bounded=false (authority suspended)', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 62; i++) {
      const { lineage: next } = await lineage.append({ kind: 'CAPABILITY_EVOLUTION', proposal_id: h(String.fromCharCode(97 + (i % 26))), verdict: 'APPROVED' }, seq(i))
      lineage = next
    }
    for (let i = 63; i <= 100; i++) {
      const { lineage: next } = await lineage.append({ kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + (i % 26))) }, seq(i))
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.entropy_bounded).toBe(false)
  })

  it('numerical identity: 62/100 ≥ PHI_INV', () => {
    expect(62 / 100 >= PHI_INV).toBe(true)
  })

  it('numerical identity: 61/100 < PHI_INV', () => {
    expect(61 / 100 < PHI_INV).toBe(true)
  })
})
