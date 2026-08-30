// ============================================================
// Core Types Extended Tests — core/types.ts
// Targets uncovered branches:
//   assertBoundedDelta: x < -1 throw, x > 1 throw, valid no-throw
//   normalizeDelta: clamps to [-1, 1]
// ============================================================

import { describe, it, expect } from 'vitest'
import { normalizeDelta, assertBoundedDelta } from '../../src/core/types.js'

describe('assertBoundedDelta', () => {
  it('throws RangeError when x < -1', () => {
    expect(() => assertBoundedDelta(-1.5)).toThrow(RangeError)
    expect(() => assertBoundedDelta(-2)).toThrow(RangeError)
  })

  it('throws RangeError when x > 1', () => {
    expect(() => assertBoundedDelta(1.1)).toThrow(RangeError)
    expect(() => assertBoundedDelta(99)).toThrow(RangeError)
  })

  it('does not throw for valid bounded delta', () => {
    expect(() => assertBoundedDelta(0)).not.toThrow()
    expect(() => assertBoundedDelta(-1)).not.toThrow()
    expect(() => assertBoundedDelta(1)).not.toThrow()
    expect(() => assertBoundedDelta(0.5)).not.toThrow()
  })

  it('error message includes the offending value', () => {
    expect(() => assertBoundedDelta(2)).toThrow('2')
  })
})

describe('normalizeDelta', () => {
  it('returns value unchanged for in-range input', () => {
    expect(normalizeDelta(0.5)).toBe(0.5)
    expect(normalizeDelta(-0.5)).toBe(-0.5)
    expect(normalizeDelta(0)).toBe(0)
  })

  it('clamps to -1 when input < -1', () => {
    expect(normalizeDelta(-5)).toBe(-1)
    expect(normalizeDelta(-1.001)).toBe(-1)
  })

  it('clamps to 1 when input > 1', () => {
    expect(normalizeDelta(5)).toBe(1)
    expect(normalizeDelta(1.001)).toBe(1)
  })
})
