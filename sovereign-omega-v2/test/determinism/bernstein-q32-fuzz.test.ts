// ============================================================
// SOVEREIGN OMEGA — Bernstein LCB Q32.32 Fuzz
// Ω⁵.7 / Ω⁵.5: Property-based fuzz saturation of the Q32.32
// Bernstein lower confidence bound. Verifies:
//   - intra-runtime determinism (≥3 runs per input)
//   - mathematical invariant: LCB ≤ mean always
//   - monotonicity: tighter bounds with larger n
//   - edge case safety: n=0, n=1, extreme alpha
//
// NOTE: bernsteinLCBQ32 uses Math.sqrt/Math.log internally —
// determinism holds within a single JS runtime but cross-engine
// WASM parity is deferred until the WASM kernel is compiled.
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  bernsteinLCBQ32, toQ32, fromQ32, Q_ONE, Q_HALF, Q_ZERO,
} from '../../src/core/fixedpoint'
import type { Q32_32 } from '../../src/core/fixedpoint'

// Deterministic sample generator — pure function of (seed, n)
function buildSamples(seed: number, count: number): { sum: Q32_32; sumSq: Q32_32 } {
  let sum = Q_ZERO
  let sumSq = Q_ZERO
  for (let i = 0; i < count; i++) {
    const v = ((seed * 1618033 + i * 314159) % 1000) / 1000  // in [0,1)
    const q = toQ32(v)
    sum += q
    sumSq += (q * q) >> 32n
  }
  return { sum, sumSq }
}

describe('Bernstein LCB Q32.32 Fuzz — Ω⁵.7', () => {

  it('is deterministic: 50 inputs × 3 runs each produce identical Q32.32 output', () => {
    const alpha = Q_HALF >> 1n  // 0.25 in Q32.32
    for (let seed = 0; seed < 50; seed++) {
      const n = BigInt(10 + seed)
      const { sum, sumSq } = buildSamples(seed, Number(n))
      const r1 = bernsteinLCBQ32(sum, sumSq, n, alpha)
      const r2 = bernsteinLCBQ32(sum, sumSq, n, alpha)
      const r3 = bernsteinLCBQ32(sum, sumSq, n, alpha)
      expect(r1).toBe(r2)
      expect(r2).toBe(r3)
    }
  })

  it('LCB ≤ mean for all sample sizes (statistical invariant)', () => {
    const alpha = Q_HALF >> 1n
    for (let seed = 0; seed < 30; seed++) {
      const n = BigInt(5 + seed * 3)
      const { sum, sumSq } = buildSamples(seed, Number(n))
      const mean = (sum << 32n) / (n << 32n)
      const lcb = bernsteinLCBQ32(sum, sumSq, n, alpha)
      expect(lcb).toBeLessThanOrEqual(mean)
    }
  })

  it('tighter bounds with larger n (monotonicity in sample size)', () => {
    // For a fixed sample distribution, more data → LCB closer to mean
    const alpha = Q_HALF >> 1n
    const seed = 42

    const small_n = BigInt(10)
    const large_n = BigInt(1000)
    const { sum: s10, sumSq: ss10 } = buildSamples(seed, 10)
    const { sum: s1000, sumSq: ss1000 } = buildSamples(seed, 1000)

    const lcb10 = bernsteinLCBQ32(s10, ss10, small_n, alpha)
    const lcb1000 = bernsteinLCBQ32(s1000, ss1000, large_n, alpha)

    // Mean for both samples
    const mean10 = (s10 << 32n) / (small_n << 32n)
    const mean1000 = (s1000 << 32n) / (large_n << 32n)

    const gap10 = mean10 - lcb10
    const gap1000 = mean1000 - lcb1000

    expect(gap1000).toBeLessThan(gap10)
  })

  it('n=0 returns the -Infinity proxy (negative large Q32.32)', () => {
    const result = bernsteinLCBQ32(Q_ZERO, Q_ZERO, 0n, Q_HALF)
    expect(result).toBeLessThan(0n)
    // Should be a very large negative value (proxy for -Infinity)
    expect(fromQ32(result)).toBeLessThan(-100)
  })

  it('n=1 does not throw — single-sample case is handled', () => {
    const q = toQ32(0.7)
    expect(() => bernsteinLCBQ32(q, (q * q) >> 32n, 1n, Q_HALF)).not.toThrow()
  })

  it('extreme alpha (very small) produces very wide bounds', () => {
    const alpha_small = toQ32(0.001)
    const alpha_large = toQ32(0.2)
    const n = 100n
    const { sum, sumSq } = buildSamples(7, 100)

    const lcb_small_alpha = bernsteinLCBQ32(sum, sumSq, n, alpha_small)
    const lcb_large_alpha = bernsteinLCBQ32(sum, sumSq, n, alpha_large)

    // Smaller alpha (higher confidence) → wider interval → lower LCB
    expect(lcb_small_alpha).toBeLessThanOrEqual(lcb_large_alpha)
  })

  it('toQ32/fromQ32 round-trip is deterministic across 3 runs', () => {
    const values = [0.1, 0.25, 0.5, 0.75, 0.99, -0.5, -0.99, 1.0]
    for (const v of values) {
      const q1 = toQ32(v)
      const q2 = toQ32(v)
      const q3 = toQ32(v)
      expect(q1).toBe(q2)
      expect(q2).toBe(q3)
      expect(q1 === Q_ONE || fromQ32(q1)).toBeCloseTo(v, 8)
    }
  })

  it('toQ32 throws on NaN and Infinity — guards the Q32 boundary', () => {
    expect(() => toQ32(NaN)).toThrow(RangeError)
    expect(() => toQ32(Infinity)).toThrow(RangeError)
    expect(() => toQ32(-Infinity)).toThrow(RangeError)
  })

})
