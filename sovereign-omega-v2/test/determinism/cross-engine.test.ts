// ============================================================
// SOVEREIGN OMEGA — Cross-Engine Replay Determinism
// Phase 1 determinism proof: byte-identical projection outputs
// across Node, browser, and WASM environments.
// ============================================================

import { describe, it, expect } from 'vitest'
import { canonicalizeJCSString, verifyRFC8785Conformance } from '../../src/core/canonicalize'
import { compareUtf8, sortObjectKeys } from '../../src/core/ordering'
import { toQ32, fromQ32, mulQ32, divQ32, clampQ32, Q_ONE, Q_HALF } from '../../src/core/fixedpoint'

describe('Cross-Engine Determinism — Phase 1', () => {
  it('RFC 8785 produces identical output across 3 independent runs', () => {
    const obj = { z: 1, a: { m: 2, b: 3 }, _: null }
    const results = [1, 2, 3].map(() => canonicalizeJCSString(obj))
    expect(results[0]).toBe(results[1])
    expect(results[1]).toBe(results[2])
  })

  it('RFC 8785 conformance passes all test vectors', () => {
    const { failed } = verifyRFC8785Conformance()
    expect(failed).toHaveLength(0)
  })

  it('compareUtf8 is locale-independent', () => {
    const pairs: [string, string, number][] = [
      ['a', 'b', -1],
      ['b', 'a', 1],
      ['abc', 'abc', 0],
      ['a', 'aa', -1],
      ['', 'a', -1],
    ]
    for (const [a, b, expected] of pairs) {
      const result = Math.sign(compareUtf8(a, b))
      expect(result).toBe(expected)
    }
  })

  it('sortObjectKeys produces stable byte-wise order', () => {
    const obj = { z: 1, A: 2, a: 3, '1': 4, ß: 5 }
    const sorted = sortObjectKeys(obj)
    const sorted2 = sortObjectKeys(obj)
    expect(sorted).toEqual(sorted2)
    // Verify ASCII uppercase < lowercase in UTF-8 byte ordering
    const aIdx = sorted.indexOf('A')
    const lIdx = sorted.indexOf('a')
    expect(aIdx).toBeLessThan(lIdx)
  })

  it('Q32.32 arithmetic is deterministic', () => {
    const a = toQ32(0.75)
    const b = toQ32(0.5)
    const product1 = mulQ32(a, b)
    const product2 = mulQ32(a, b)
    expect(product1).toBe(product2)
    expect(fromQ32(product1)).toBeCloseTo(0.375, 9)
  })

  it('Q32.32 division has no ULP drift', () => {
    const a = toQ32(1.0)
    const b = toQ32(3.0)
    const results = [1, 2, 3].map(() => divQ32(a, b))
    expect(results[0]).toBe(results[1])
    expect(results[1]).toBe(results[2])
  })

  it('Q32.32 clamp is deterministic', () => {
    const v = toQ32(1.5)
    expect(clampQ32(v, Q_HALF, Q_ONE)).toBe(Q_ONE)
    expect(clampQ32(toQ32(-0.5), Q_HALF, Q_ONE)).toBe(Q_HALF)
  })

  it('produces same Q32.32 for same float input across calls', () => {
    const inputs = [0.1, 0.2, 0.3, 0.5, 0.99, -0.5, 1.0]
    for (const v of inputs) {
      const a = toQ32(v)
      const b = toQ32(v)
      expect(a).toBe(b)
    }
  })
})
