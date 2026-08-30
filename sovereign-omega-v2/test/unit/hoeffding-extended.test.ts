// ============================================================
// Hoeffding Extended Tests — gate/hoeffding.ts
// Targets uncovered branches:
//   ConfidenceSequence constructor: alpha/rho out-of-range throws
//   predictableLambda: prevMean <= 0 → return 0
//   computeMinSampleSize: all 3 throw paths
//   getPValue: eValue <= 0 → return 1; eValue > 0 path
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  ConfidenceSequence,
  computeLCBFromSamples,
  computeMinSampleSize,
  getPValue,
} from '../../src/gate/hoeffding.js'
import { normalizeDelta } from '../../src/core/types.js'

// ─── Constructor throws ───────────────────────────────────

describe('ConfidenceSequence constructor: invalid params', () => {
  it('throws RangeError when alpha <= 0', () => {
    expect(() => new ConfidenceSequence(0)).toThrow(RangeError)
    expect(() => new ConfidenceSequence(-0.1)).toThrow(RangeError)
  })

  it('throws RangeError when alpha >= 1', () => {
    expect(() => new ConfidenceSequence(1)).toThrow(RangeError)
    expect(() => new ConfidenceSequence(1.5)).toThrow(RangeError)
  })

  it('throws RangeError when rho <= 0', () => {
    expect(() => new ConfidenceSequence(0.05, 0)).toThrow(RangeError)
    expect(() => new ConfidenceSequence(0.05, -0.1)).toThrow(RangeError)
  })

  it('throws RangeError when rho >= 1', () => {
    expect(() => new ConfidenceSequence(0.05, 1)).toThrow(RangeError)
    expect(() => new ConfidenceSequence(0.05, 2)).toThrow(RangeError)
  })

  it('accepts valid alpha and rho', () => {
    expect(() => new ConfidenceSequence(0.05, 0.5)).not.toThrow()
  })
})

// ─── predictableLambda: prevMean <= 0 ────────────────────

describe('ConfidenceSequence: predictableLambda when prevMean <= 0', () => {
  it('lambda = 0 when first observation is negative (prevMean < 0)', () => {
    const seq = new ConfidenceSequence(0.05, 0.5)
    // After adding one negative delta, prevMean < 0 → lambda = 0 → e_prod unchanged
    seq.update(normalizeDelta(-0.5))
    seq.update(normalizeDelta(-0.3))
    // Should not throw — path exercises prevMean <= 0 branch
    expect(seq.eValue()).toBeGreaterThan(0)
  })

  it('empiricalMean stays negative after all-negative updates', () => {
    const seq = new ConfidenceSequence(0.05, 0.5)
    seq.update(normalizeDelta(-0.8))
    seq.update(normalizeDelta(-0.6))
    expect(seq.empiricalMean).toBeLessThan(0)
  })
})

// ─── computeMinSampleSize: throw paths ───────────────────

describe('computeMinSampleSize: throw paths', () => {
  it('throws RangeError when targetPower <= 0', () => {
    expect(() => computeMinSampleSize(0, 0.5, 0.05)).toThrow(RangeError)
    expect(() => computeMinSampleSize(-0.1, 0.5, 0.05)).toThrow(RangeError)
  })

  it('throws RangeError when targetPower >= 1', () => {
    expect(() => computeMinSampleSize(1, 0.5, 0.05)).toThrow(RangeError)
    expect(() => computeMinSampleSize(1.5, 0.5, 0.05)).toThrow(RangeError)
  })

  it('throws RangeError when effectSize <= 0', () => {
    expect(() => computeMinSampleSize(0.8, 0, 0.05)).toThrow(RangeError)
    expect(() => computeMinSampleSize(0.8, -0.1, 0.05)).toThrow(RangeError)
  })

  it('throws RangeError when alpha <= 0', () => {
    expect(() => computeMinSampleSize(0.8, 0.5, 0)).toThrow(RangeError)
  })

  it('throws RangeError when alpha >= 1', () => {
    expect(() => computeMinSampleSize(0.8, 0.5, 1)).toThrow(RangeError)
  })

  it('returns positive integer for valid inputs', () => {
    const n = computeMinSampleSize(0.8, 0.5, 0.05)
    expect(n).toBeGreaterThan(0)
    expect(Number.isInteger(n)).toBe(true)
  })
})

// ─── getPValue ────────────────────────────────────────────

describe('getPValue', () => {
  it('returns 1 when eValue <= 0', () => {
    expect(getPValue(0)).toBe(1)
    expect(getPValue(-5)).toBe(1)
  })

  it('returns 1/eValue when eValue > 1', () => {
    expect(getPValue(10)).toBeCloseTo(0.1, 6)
    expect(getPValue(2)).toBeCloseTo(0.5, 6)
  })

  it('returns 1 when eValue < 1 (min clamp)', () => {
    expect(getPValue(0.5)).toBe(1)
  })

  it('returns 1 when eValue = 1', () => {
    expect(getPValue(1)).toBe(1)
  })
})

// ─── computeLCBFromSamples: empty input ───────────────────

describe('computeLCBFromSamples', () => {
  it('returns -Infinity for empty samples', () => {
    expect(computeLCBFromSamples([])).toBe(-Infinity)
  })

  it('returns finite value with positive samples', () => {
    const lcb = computeLCBFromSamples([0.5, 0.6, 0.7, 0.8])
    expect(isFinite(lcb)).toBe(true)
  })
})
