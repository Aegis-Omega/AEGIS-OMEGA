// ============================================================
// Gate 106 — Mutation Authority Lifecycle (Integration)
// ~18 tests: Full mutation authority lifecycle — APPROVED×61
//   → entropy_bounded=true → APPROVED×62 → false → authority
//   suspended → rebuilt chain restored.
// ============================================================

import { describe, it, expect } from 'vitest'
import { AdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { certifyMartingale, assertMartingaleAnchored, MartingaleViolation, MUTATION_RATE_LIMIT } from '../../src/constitutional/martingale.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

async function buildLineage(approved: number, total: number) {
  let lineage = AdaptiveLineage.empty()
  for (let i = 1; i <= total; i++) {
    const isApproved = i <= approved
    const { lineage: next } = await lineage.append(
      isApproved
        ? { kind: 'CAPABILITY_EVOLUTION', proposal_id: h(String.fromCharCode(97 + (i % 26))), verdict: 'APPROVED' }
        : { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + (i % 26))) },
      seq(i),
    )
    lineage = next
  }
  return lineage
}

// ─── 61/100 boundary ──────────────────────────────────────

describe('Mutation Authority: 61/100 boundary', () => {
  it('61/100 APPROVED → entropy_bounded=true (authority preserved)', async () => {
    const lineage = await buildLineage(61, 100)
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.entropy_bounded).toBe(true)
    expect(cert.adaptive_power).toBe(61)
    expect(cert.replay_verifiability).toBe(100)
    expect(() => assertMartingaleAnchored(cert)).not.toThrow()
  })

  it('62/100 APPROVED → entropy_bounded=false (authority suspended)', async () => {
    const lineage = await buildLineage(62, 100)
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.entropy_bounded).toBe(false)
    expect(cert.adaptive_power).toBe(62)
    expect(() => assertMartingaleAnchored(cert)).toThrow(MartingaleViolation)
  })

  it('61/100 = 0.61 < MUTATION_RATE_LIMIT', () => {
    expect(61 / 100 < MUTATION_RATE_LIMIT).toBe(true)
  })

  it('62/100 = 0.62 ≥ MUTATION_RATE_LIMIT', () => {
    expect(62 / 100 >= MUTATION_RATE_LIMIT).toBe(true)
  })
})

// ─── Authority lifecycle ───────────────────────────────────

describe('Mutation Authority: lifecycle states', () => {
  it('0 APPROVED of 100 → adaptive_power=0, entropy_bounded=true', async () => {
    const lineage = await buildLineage(0, 100)
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.adaptive_power).toBe(0)
    expect(cert.entropy_bounded).toBe(true)
  })

  it('50 APPROVED of 50 (all approved) → entropy_bounded=false', async () => {
    const lineage = await buildLineage(50, 50)
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.adaptive_power).toBe(50)
    expect(cert.entropy_bounded).toBe(false)
  })

  it('30 APPROVED + 30 REJECTED + 40 TOPOLOGY (100 total) → bounded', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 30; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'CAPABILITY_EVOLUTION', proposal_id: h(String.fromCharCode(97 + (i % 26))), verdict: 'APPROVED' },
        seq(i),
      )
      lineage = next
    }
    for (let i = 31; i <= 60; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'CAPABILITY_EVOLUTION', proposal_id: h(String.fromCharCode(97 + (i % 26))), verdict: 'REJECTED' },
        seq(i),
      )
      lineage = next
    }
    for (let i = 61; i <= 100; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + (i % 26))) },
        seq(i),
      )
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.adaptive_power).toBe(30)
    expect(cert.adaptive_ratio).toBeLessThan(MUTATION_RATE_LIMIT)
    expect(cert.entropy_bounded).toBe(true)
  })

  it('rebuilt chain after suspension → entropy_bounded=true', async () => {
    // Build a chain that was suspended (62 approved), then rebuild with 61
    const suspended = await buildLineage(62, 100)
    const cert1 = await certifyMartingale(suspended.getAll())
    expect(cert1.entropy_bounded).toBe(false)

    // Rebuild without excess mutations
    const restored = await buildLineage(61, 100)
    const cert2 = await certifyMartingale(restored.getAll())
    expect(cert2.entropy_bounded).toBe(true)
    expect(() => assertMartingaleAnchored(cert2)).not.toThrow()
  })
})

// ─── Certificate invariants ───────────────────────────────

describe('Mutation Authority: certificate invariants', () => {
  it('certificate is frozen', async () => {
    const lineage = await buildLineage(5, 10)
    const cert = await certifyMartingale(lineage.getAll())
    expect(Object.isFrozen(cert)).toBe(true)
  })

  it('is_replay_reconstructable=true', async () => {
    const lineage = await buildLineage(5, 10)
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.is_replay_reconstructable).toBe(true)
  })

  it('adaptive_ratio = adaptive_power / replay_verifiability', async () => {
    const lineage = await buildLineage(30, 100)
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.adaptive_ratio).toBeCloseTo(30 / 100, 10)
  })

  it('mutation_rate_limit = MUTATION_RATE_LIMIT constant', async () => {
    const cert = await certifyMartingale([])
    expect(cert.mutation_rate_limit).toBe(MUTATION_RATE_LIMIT)
  })
})
