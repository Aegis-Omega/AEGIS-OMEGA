// ============================================================
// Fixed-Point Arithmetic Tests — core/fixedpoint.ts
// Targets uncovered branches: toQ32 non-finite, divQ32 zero,
// clampQ32 all three paths, absQ32 negative/zero,
// computeCorrelationPenalty (excess≤0, denom≤0, normal),
// bernsteinLCBQ32 (n=0, n=1, n>1, non-finite guards).
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  toQ32, fromQ32, mulQ32, divQ32,
  clampQ32, addQ32, subQ32, absQ32, absDiffQ32,
  computeCorrelationPenalty, bernsteinLCBQ32,
  Q_ONE, Q_HALF, Q_ZERO, Q_SCALE,
} from '../../src/core/fixedpoint.js'

// ─── Constants ─────────────────────────────────────────────

describe('Q32.32 constants', () => {
  it('Q_ONE represents 1.0', () => {
    expect(fromQ32(Q_ONE)).toBeCloseTo(1.0, 10)
  })

  it('Q_HALF represents 0.5', () => {
    expect(fromQ32(Q_HALF)).toBeCloseTo(0.5, 10)
  })

  it('Q_ZERO is 0n', () => {
    expect(Q_ZERO).toBe(0n)
  })

  it('Q_SCALE is 2^32', () => {
    expect(Q_SCALE).toBe(BigInt(2 ** 32))
  })
})

// ─── toQ32 ─────────────────────────────────────────────────

describe('toQ32', () => {
  it('converts 1.0 correctly', () => {
    expect(fromQ32(toQ32(1.0))).toBeCloseTo(1.0, 6)
  })

  it('converts 0.0 to Q_ZERO', () => {
    expect(toQ32(0.0)).toBe(Q_ZERO)
  })

  it('converts negative values', () => {
    expect(fromQ32(toQ32(-0.5))).toBeCloseTo(-0.5, 6)
  })

  it('throws RangeError for Infinity', () => {
    expect(() => toQ32(Infinity)).toThrow(RangeError)
  })

  it('throws RangeError for -Infinity', () => {
    expect(() => toQ32(-Infinity)).toThrow(RangeError)
  })

  it('throws RangeError for NaN', () => {
    expect(() => toQ32(NaN)).toThrow(RangeError)
  })
})

// ─── fromQ32 ───────────────────────────────────────────────

describe('fromQ32', () => {
  it('round-trips values through toQ32/fromQ32', () => {
    for (const v of [0, 0.25, 0.5, 0.75, 1.0]) {
      expect(fromQ32(toQ32(v))).toBeCloseTo(v, 6)
    }
  })
})

// ─── mulQ32 ────────────────────────────────────────────────

describe('mulQ32', () => {
  it('0.5 × 0.5 ≈ 0.25', () => {
    expect(fromQ32(mulQ32(Q_HALF, Q_HALF))).toBeCloseTo(0.25, 6)
  })

  it('1 × 1 = 1', () => {
    expect(fromQ32(mulQ32(Q_ONE, Q_ONE))).toBeCloseTo(1.0, 6)
  })

  it('any × 0 = 0', () => {
    expect(mulQ32(Q_ONE, Q_ZERO)).toBe(Q_ZERO)
  })
})

// ─── divQ32 ────────────────────────────────────────────────

describe('divQ32', () => {
  it('1 / 2 ≈ 0.5', () => {
    expect(fromQ32(divQ32(Q_ONE, toQ32(2.0)))).toBeCloseTo(0.5, 6)
  })

  it('throws on division by zero', () => {
    expect(() => divQ32(Q_ONE, Q_ZERO)).toThrow('FIXED_POINT_DIV_ZERO')
  })
})

// ─── clampQ32 ──────────────────────────────────────────────

describe('clampQ32', () => {
  it('returns min when value is below min', () => {
    const result = clampQ32(toQ32(-1.0), Q_ZERO, Q_ONE)
    expect(result).toBe(Q_ZERO)
  })

  it('returns max when value is above max', () => {
    const result = clampQ32(toQ32(2.0), Q_ZERO, Q_ONE)
    expect(result).toBe(Q_ONE)
  })

  it('returns value when within [min, max]', () => {
    const v = Q_HALF
    expect(clampQ32(v, Q_ZERO, Q_ONE)).toBe(v)
  })
})

// ─── addQ32 / subQ32 / absQ32 / absDiffQ32 ────────────────

describe('addQ32 / subQ32', () => {
  it('0.5 + 0.5 = 1.0', () => {
    expect(fromQ32(addQ32(Q_HALF, Q_HALF))).toBeCloseTo(1.0, 6)
  })

  it('1.0 - 0.5 = 0.5', () => {
    expect(fromQ32(subQ32(Q_ONE, Q_HALF))).toBeCloseTo(0.5, 6)
  })
})

describe('absQ32', () => {
  it('returns positive value unchanged', () => {
    expect(absQ32(Q_ONE)).toBe(Q_ONE)
  })

  it('returns zero unchanged', () => {
    expect(absQ32(Q_ZERO)).toBe(Q_ZERO)
  })

  it('negates negative value', () => {
    const neg = toQ32(-0.75)
    expect(fromQ32(absQ32(neg))).toBeCloseTo(0.75, 6)
  })
})

describe('absDiffQ32', () => {
  it('|0.75 - 0.25| = 0.5', () => {
    expect(fromQ32(absDiffQ32(toQ32(0.75), toQ32(0.25)))).toBeCloseTo(0.5, 6)
  })

  it('|a - a| = 0', () => {
    expect(absDiffQ32(Q_ONE, Q_ONE)).toBe(Q_ZERO)
  })
})

// ─── computeCorrelationPenalty ────────────────────────────

describe('computeCorrelationPenalty', () => {
  it('returns Q_ONE when excess is zero (agreement_rate ≤ baseline)', () => {
    const penalty = computeCorrelationPenalty(toQ32(0.5), toQ32(0.6))
    expect(penalty).toBe(Q_ONE)
  })

  it('returns Q_ONE when excess equals zero exactly', () => {
    const penalty = computeCorrelationPenalty(toQ32(0.5), toQ32(0.5))
    expect(penalty).toBe(Q_ONE)
  })

  it('returns floor Q_ONE>>2 when denom is zero (excess>0, baseline=1.0)', () => {
    // agreement_rate > baseline = 1.0 → excess > 0, denom = Q_ONE - Q_ONE = 0 → floor
    const floor = Q_ONE >> 2n
    const penalty = computeCorrelationPenalty(toQ32(1.1), Q_ONE)
    expect(penalty).toBe(floor)
  })

  it('returns clamped value in normal case', () => {
    const penalty = computeCorrelationPenalty(toQ32(0.9), toQ32(0.5))
    const v = fromQ32(penalty)
    expect(v).toBeGreaterThanOrEqual(0.25)
    expect(v).toBeLessThanOrEqual(1.0)
  })

  it('minimum floor is 0.25', () => {
    const penalty = computeCorrelationPenalty(toQ32(0.99), toQ32(0.01))
    expect(fromQ32(penalty)).toBeGreaterThanOrEqual(0.24)
  })
})

// ─── bernsteinLCBQ32 ──────────────────────────────────────

describe('bernsteinLCBQ32', () => {
  const alpha = toQ32(0.05)

  it('returns -Infinity proxy when n = 0', () => {
    const result = bernsteinLCBQ32(Q_ZERO, Q_ZERO, 0n, alpha)
    expect(result).toBeLessThan(0n)
  })

  it('n = 1 returns a valid Q32 value', () => {
    const q = toQ32(0.7)
    const result = bernsteinLCBQ32(q, mulQ32(q, q), 1n, alpha)
    expect(typeof result).toBe('bigint')
  })

  it('n > 1 returns LCB below mean', () => {
    const q = toQ32(0.8)
    const sumQ = q * 5n
    const sumSqQ = mulQ32(q, q) * 5n
    const result = bernsteinLCBQ32(sumQ, sumSqQ, 5n, alpha)
    const mean = fromQ32(sumQ / 5n)
    const lcb = fromQ32(result)
    expect(lcb).toBeLessThanOrEqual(mean)
  })

  it('throws RangeError for alpha = 0 (non-finite log)', () => {
    expect(() => bernsteinLCBQ32(Q_HALF, mulQ32(Q_HALF, Q_HALF), 1n, Q_ZERO)).toThrow(RangeError)
  })

  it('n = 1, zero variance returns bounded result', () => {
    const sum = toQ32(0.5)
    const sumSq = mulQ32(sum, sum)
    const result = bernsteinLCBQ32(sum, sumSq, 1n, alpha)
    expect(typeof result).toBe('bigint')
  })
})
