import { describe, it, expect } from 'vitest'
import { RalphExecutor } from '../../src/agents/executor/loop.js'
import { certifyMartingale, assertMartingaleAnchored, MartingaleViolation, MUTATION_RATE_LIMIT } from '../../src/constitutional/martingale.js'
import { DEFAULT_QUORUM_THRESHOLD } from '../../src/consensus/swarm.js'
import { FIBONACCI_CAP, fibonacciInterval } from '../../src/agents/scheduler/fibonacci.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import type { AdaptiveLineageEntry } from '../../src/frame/adaptive-lineage.js'
import { AdaptiveLineage } from '../../src/frame/adaptive-lineage.js'

// ============================================================
// Gate 133 — Fibonacci × Martingale Composition Tests
// Verifies: 62-loop RALPH executor, Fibonacci cap at loop 12+,
// martingale suspension at 1/φ boundary, holonic triad identity.
// ============================================================

const CTX = 'e'.repeat(64) as SHA256Hex
const seq = (n: number) => BigInt(n) as SequenceNumber

async function buildExecutor(agentId: string, loops: number) {
  let ex = RalphExecutor.create(agentId)
  for (let i = 0; i < loops; i++) {
    const { executor } = await ex.executeLoop(CTX, seq(i + 1))
    ex = executor
  }
  return ex
}


describe('62-loop RALPH executor — Fibonacci cap verification', () => {
  it('loop 12: fibonacci_interval=89 (cap)', async () => {
    const ex = await buildExecutor('fib-cap-12', 12)
    expect(ex.lastRecord?.fibonacci_interval).toBe(FIBONACCI_CAP)
  })

  it('loop 62: fibonacci_interval=89 (cap stable)', async () => {
    const ex = await buildExecutor('fib-cap-62', 62)
    expect(ex.lastRecord?.fibonacci_interval).toBe(FIBONACCI_CAP)
    expect(ex.loopCount).toBe(62)
  })

  it('fibonacci pacing: F_1..F_11 then cap for remaining loops', () => {
    const expected = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89]
    for (let i = 0; i < 11; i++) {
      expect(fibonacciInterval(i + 1)).toBe(expected[i])
    }
    for (let i = 11; i < 20; i++) {
      expect(fibonacciInterval(i + 1)).toBe(FIBONACCI_CAP)
    }
  })
})

describe('62-loop executor with 40 APPROVED evolutions → martingale suspension', () => {
  it('40/62 = 0.645 > 1/φ → entropy_bounded=false', async () => {
    // Build adaptive lineage with 40 APPROVED out of 62 total
    let lineage = AdaptiveLineage.empty()
    for (let i = 0; i < 62; i++) {
      const verdict = i < 40 ? 'APPROVED' as const : 'REJECTED' as const
      const r = await lineage.append(
        { kind: 'CAPABILITY_EVOLUTION', proposal_id: 'f'.repeat(64) as SHA256Hex, verdict },
        seq(i + 1)
      )
      lineage = r.lineage
    }
    const entries: readonly AdaptiveLineageEntry[] = lineage.getAll()
    const mc = await certifyMartingale(entries)
    expect(mc.adaptive_power).toBe(40)
    expect(mc.replay_verifiability).toBe(62)
    expect(mc.adaptive_ratio).toBeCloseTo(40 / 62)
    expect(mc.entropy_bounded).toBe(false)
    expect(() => assertMartingaleAnchored(mc)).toThrow(MartingaleViolation)
  })

  it('38/62 = 0.613 < 1/φ → entropy_bounded=true', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 0; i < 62; i++) {
      const verdict = i < 38 ? 'APPROVED' as const : 'REJECTED' as const
      const r = await lineage.append(
        { kind: 'CAPABILITY_EVOLUTION', proposal_id: 'f'.repeat(64) as SHA256Hex, verdict },
        seq(i + 1)
      )
      lineage = r.lineage
    }
    const mc = await certifyMartingale(lineage.getAll())
    expect(mc.entropy_bounded).toBe(true)
    expect(() => assertMartingaleAnchored(mc)).not.toThrow()
  })
})

describe('Holonic triad — 1/φ boundary identity', () => {
  it('MUTATION_RATE_LIMIT === DEFAULT_QUORUM_THRESHOLD (both equal 1/φ)', () => {
    expect(MUTATION_RATE_LIMIT).toBeCloseTo(DEFAULT_QUORUM_THRESHOLD)
    expect(MUTATION_RATE_LIMIT).toBeCloseTo((Math.sqrt(5) - 1) / 2)
  })

  it('62/100: ratio=0.62 > 1/φ → entropy_bounded=false', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 0; i < 100; i++) {
      const verdict = i < 62 ? 'APPROVED' as const : 'REJECTED' as const
      const r = await lineage.append(
        { kind: 'CAPABILITY_EVOLUTION', proposal_id: '9'.repeat(64) as SHA256Hex, verdict },
        seq(i + 1)
      )
      lineage = r.lineage
    }
    const mc = await certifyMartingale(lineage.getAll())
    expect(mc.entropy_bounded).toBe(false)
  })

  it('61/100: ratio=0.61 < 1/φ → entropy_bounded=true', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 0; i < 100; i++) {
      const verdict = i < 61 ? 'APPROVED' as const : 'REJECTED' as const
      const r = await lineage.append(
        { kind: 'CAPABILITY_EVOLUTION', proposal_id: '9'.repeat(64) as SHA256Hex, verdict },
        seq(i + 1)
      )
      lineage = r.lineage
    }
    const mc = await certifyMartingale(lineage.getAll())
    expect(mc.entropy_bounded).toBe(true)
  })

  it('certifyMartingale result is frozen and replay-reconstructable', async () => {
    const mc = await certifyMartingale([])
    expect(Object.isFrozen(mc)).toBe(true)
    expect(mc.is_replay_reconstructable).toBe(true)
    expect(mc.certificate_hash).toMatch(/^[0-9a-f]{64}$/)
  })
})
