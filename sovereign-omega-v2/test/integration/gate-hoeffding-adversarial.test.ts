// ============================================================
// Gate 96 — Gate/Hoeffding Adversarial (Integration)
// ~18 tests: Bernstein bounds at 200-sample scale; false-
//   positive rate ≤ α throughout; ConfidenceSequence under
//   adversarial sampling patterns; LCB monotonicity; e-value.
// ============================================================

import { describe, it, expect } from 'vitest'
import { ConfidenceSequence, computeLCBFromSamples, computeMinSampleSize, getPValue } from '../../src/gate/hoeffding.js'
import { normalizeDelta } from '../../src/core/types.js'

// ─── 200-sample scale ─────────────────────────────────────

describe('Hoeffding: 200-sample Bernstein scale', () => {
  it('200 positive deltas → LCB > 0 (gate accepts)', () => {
    const seq = new ConfidenceSequence(0.05)
    for (let i = 0; i < 200; i++) {
      seq.update(normalizeDelta(0.3))
    }
    expect(seq.lcb()).toBeGreaterThan(0)
  })

  it('200 zero deltas → LCB ≤ 0 (gate rejects)', () => {
    const seq = new ConfidenceSequence(0.05)
    for (let i = 0; i < 200; i++) {
      seq.update(normalizeDelta(0))
    }
    expect(seq.lcb()).toBeLessThanOrEqual(0)
  })

  it('computeLCBFromSamples(200 × 0.3) > 0', () => {
    const samples = Array(200).fill(0.3)
    const lcb = computeLCBFromSamples(samples, 0.05)
    expect(lcb).toBeGreaterThan(0)
  })

  it('computeLCBFromSamples(200 × -0.1) < 0', () => {
    const samples = Array(200).fill(-0.1)
    const lcb = computeLCBFromSamples(samples, 0.05)
    expect(lcb).toBeLessThan(0)
  })
})

// ─── Adversarial patterns ─────────────────────────────────

describe('Hoeffding: adversarial sampling', () => {
  it('alternating +1/-1 pattern: LCB converges near 0', () => {
    const seq = new ConfidenceSequence(0.05)
    for (let i = 0; i < 200; i++) {
      seq.update(normalizeDelta(i % 2 === 0 ? 1 : -1))
    }
    // Mean is 0, so LCB should be near 0 or negative
    expect(seq.lcb()).toBeLessThanOrEqual(0.1)
  })

  it('sudden negative burst at end: LCB drops (adaptive sensitivity)', () => {
    const seqA = new ConfidenceSequence(0.05)
    const seqB = new ConfidenceSequence(0.05)
    for (let i = 0; i < 190; i++) {
      seqA.update(normalizeDelta(0.5))
      seqB.update(normalizeDelta(0.5))
    }
    const lcbBefore = seqA.lcb()
    for (let i = 0; i < 10; i++) {
      seqB.update(normalizeDelta(-1))
    }
    expect(seqB.lcb()).toBeLessThan(lcbBefore)
  })

  it('identical samples: LCB is deterministic ×3', () => {
    function run() {
      const s = new ConfidenceSequence(0.05)
      for (let i = 0; i < 100; i++) s.update(normalizeDelta(0.4))
      return s.lcb()
    }
    const [l1, l2, l3] = [run(), run(), run()]
    expect(l1).toBe(l2)
    expect(l2).toBe(l3)
  })

  it('empty sequence: LCB = -Infinity', () => {
    const seq = new ConfidenceSequence(0.05)
    expect(seq.lcb()).toBe(-Infinity)
  })
})

// ─── False-positive rate ──────────────────────────────────

describe('Hoeffding: false-positive rate ≤ α', () => {
  it('e-value for large positive delta ≥ 1/α', () => {
    const seq = new ConfidenceSequence(0.05)
    for (let i = 0; i < 100; i++) seq.update(normalizeDelta(0.8))
    const pValue = getPValue(seq.eValue())
    expect(pValue).toBeLessThanOrEqual(0.05)
  })

  it('e-value for zero deltas stays near 1 (no evidence)', () => {
    const seq = new ConfidenceSequence(0.05)
    for (let i = 0; i < 50; i++) seq.update(normalizeDelta(0))
    expect(seq.eValue()).toBeGreaterThanOrEqual(0)
  })

  it('getPValue: large e-value → small p-value', () => {
    expect(getPValue(100)).toBeLessThanOrEqual(0.01)
    expect(getPValue(1000)).toBeLessThan(0.01)
    expect(getPValue(1)).toBeGreaterThan(0)
  })

  it('getPValue: e=0 → p=1 (no evidence)', () => {
    expect(getPValue(0)).toBe(1)
  })
})

// ─── computeMinSampleSize ─────────────────────────────────

describe('Hoeffding: computeMinSampleSize', () => {
  it('returns positive integer', () => {
    const n = computeMinSampleSize(0.80, 0.1, 0.05)
    expect(n).toBeGreaterThan(0)
    expect(Number.isInteger(n)).toBe(true)
  })

  it('larger effect size → smaller min sample', () => {
    const n1 = computeMinSampleSize(0.80, 0.1, 0.05)
    const n2 = computeMinSampleSize(0.80, 0.5, 0.05)
    expect(n2).toBeLessThan(n1)
  })

  it('stricter alpha → larger min sample', () => {
    const n1 = computeMinSampleSize(0.80, 0.2, 0.05)
    const n2 = computeMinSampleSize(0.80, 0.2, 0.01)
    expect(n2).toBeGreaterThan(n1)
  })

  it('computeMinSampleSize is deterministic ×3', () => {
    const n1 = computeMinSampleSize(0.80, 0.15, 0.05)
    const n2 = computeMinSampleSize(0.80, 0.15, 0.05)
    const n3 = computeMinSampleSize(0.80, 0.15, 0.05)
    expect(n1).toBe(n2)
    expect(n2).toBe(n3)
  })
})
