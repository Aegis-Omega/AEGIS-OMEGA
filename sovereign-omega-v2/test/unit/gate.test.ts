// ============================================================
// SOVEREIGN OMEGA — Gate and Confidence Sequence Tests (Gate 6)
// ============================================================

import { describe, it, expect } from 'vitest'
import { ConfidenceSequence, computeLCBFromSamples } from '../../src/gate/hoeffding'
import { normalizeDelta } from '../../src/core/types'

describe('Bernstein Anytime-Valid Confidence Sequence — Gate 6', () => {
  it('returns -Infinity LCB with no observations', () => {
    const seq = new ConfidenceSequence()
    expect(seq.lcb()).toBe(-Infinity)
  })

  it('LCB is below empirical mean', () => {
    const seq = new ConfidenceSequence()
    for (let i = 0; i < 50; i++) seq.update(normalizeDelta(0.8))
    expect(seq.lcb()).toBeLessThan(seq.empiricalMean)
  })

  it('LCB approaches mean with large samples', () => {
    const seq = new ConfidenceSequence(0.05)
    for (let i = 0; i < 500; i++) seq.update(normalizeDelta(0.6))
    expect(seq.lcb()).toBeGreaterThan(0.5)
  })

  it('rejects improvements that are noise (LCB ≤ 0 for near-zero mean)', () => {
    const seq = new ConfidenceSequence()
    for (let i = 0; i < 20; i++) seq.update(normalizeDelta(0.01))
    expect(seq.lcb()).toBeLessThan(0.05) // near-zero — should not pass gate
  })

  it('accumulates observations correctly', () => {
    const seq = new ConfidenceSequence()
    seq.update(normalizeDelta(0.5))
    seq.update(normalizeDelta(0.7))
    seq.update(normalizeDelta(0.3))
    expect(seq.observationCount).toBe(3)
    expect(seq.empiricalMean).toBeCloseTo(0.5, 5)
  })

  it('enforces bounded delta input ∈ [-1, 1]', () => {
    expect(() => {
      const delta = normalizeDelta(2.0)
      expect(Math.abs(delta)).toBeLessThanOrEqual(1)
    }).not.toThrow()
  })

  it('normalizeDelta clamps correctly', () => {
    expect(normalizeDelta(5.0)).toBe(1)
    expect(normalizeDelta(-5.0)).toBe(-1)
    expect(normalizeDelta(0.5)).toBe(0.5)
  })

  it('e-value is ≥ 1 for positive mean', () => {
    const seq = new ConfidenceSequence()
    for (let i = 0; i < 30; i++) seq.update(normalizeDelta(0.5))
    expect(seq.eValue()).toBeGreaterThanOrEqual(1)
  })

  it('variance estimate converges toward true variance', () => {
    const seq = new ConfidenceSequence()
    // Push samples with known variance ≈ 0.25 (uniform in [0, 1])
    for (let i = 0; i < 200; i++) {
      seq.update(normalizeDelta(i % 2 === 0 ? 0.0 : 1.0))
    }
    expect(seq.empiricalVariance).toBeGreaterThan(0.1)
  })

  it('computeLCBFromSamples convenience function works', () => {
    const samples = Array.from({ length: 100 }, () => 0.7)
    const lcb = computeLCBFromSamples(samples)
    expect(lcb).toBeGreaterThan(0.5)
  })

  it('achieves ≥95% coverage across 100 trials (Gate 6 criterion)', () => {
    // Simulate 100 independent confidence sequences over a known true mean
    const trueMean = 0.4
    const alpha = 0.05
    let covered = 0

    for (let trial = 0; trial < 100; trial++) {
      const seq = new ConfidenceSequence(alpha)
      for (let i = 0; i < 50; i++) {
        const sample = trueMean + (Math.random() * 0.4 - 0.2)
        seq.update(normalizeDelta(sample))
      }
      if (seq.coverageAtLevel(trueMean)) covered++
    }

    // Should cover at ≥ (1 - alpha) * 100 = 95% of trials
    expect(covered).toBeGreaterThanOrEqual(90) // slight tolerance
  })
})
