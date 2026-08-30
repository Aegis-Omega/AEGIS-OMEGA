// ============================================================
// VCG Extended Tests — calibration/vcg.ts
// Targets uncovered branches: ADVISORY_EXCLUDED silent ignore,
// window trimming, shouldAlert/shouldSuspend true paths,
// isStale both branches, resetEpoch, getConfidenceInterval,
// getCalibrationBias, getBrierScore, buildConfidence paths.
// Timestamps: derived from epoch constant 1_600_000_000_000.
// ============================================================

import { describe, it, expect } from 'vitest'
import { VCGTracker, buildConfidence } from '../../src/calibration/vcg.js'
import { CalibrationDomain } from '../../src/core/types.js'
import type { SHA256Hex } from '../../src/core/types.js'
import type { VerifierOutput } from '../../src/verifier/types.js'

// ─── Fixtures ──────────────────────────────────────────────

const TS = 1_600_000_000_000  // epoch constant — never Date.now()
const DAY_MS = 24 * 60 * 60 * 1000

function output(
  passed: boolean,
  confidence: number,
  trust: CalibrationDomain = CalibrationDomain.GROUND_TRUTH
): VerifierOutput {
  return {
    verifier_id: `v-${trust}`,
    claim_id: 'c1',
    passed,
    raw_confidence: confidence,
    evidence_refs: [],
    latency_ms: 10,
    determinism_flag: true,
    verifier_version: '1.0.0',
    trust_class: trust,
    artifact_hash: '0'.repeat(64) as SHA256Hex,
  }
}

// ─── Advisory-Excluded silent ignore ──────────────────────

describe('addResult: ADVISORY_EXCLUDED is silently ignored', () => {
  it('does not add sample when trust class is ADVISORY_EXCLUDED', () => {
    const t = new VCGTracker('s1')
    t.addResult(output(true, 0.9, CalibrationDomain.ADVISORY_EXCLUDED), 0.9, TS)
    expect(t.compute(TS).sample_count).toBe(0)
  })

  it('RETRIEVAL_ASSISTED contributes at weight 0.5 (not ignored)', () => {
    const t = new VCGTracker('s2')
    t.addResult(output(true, 1.0, CalibrationDomain.RETRIEVAL_ASSISTED), 1.0, TS)
    expect(t.compute(TS).sample_count).toBe(1)
    expect(t.compute(TS).effective_sample_size).toBeCloseTo(0.5, 4)
  })
})

// ─── Window trimming ──────────────────────────────────────

describe('addResult: window trimming', () => {
  it('trims to windowSize when samples exceed limit', () => {
    const t = new VCGTracker('s3', 3)  // window = 3
    for (let i = 0; i < 5; i++) {
      t.addResult(output(true, 0.9), 0.9, TS + i)
    }
    expect(t.compute(TS + 5).sample_count).toBe(3)
  })
})

// ─── canEmitVerifiedConfidence ────────────────────────────

describe('canEmitVerifiedConfidence', () => {
  it('returns false when fewer than 100 samples', () => {
    const t = new VCGTracker('s4')
    t.addResult(output(true, 1.0), 1.0, TS)
    expect(t.canEmitVerifiedConfidence(TS)).toBe(false)
  })

  it('returns true when 100+ samples', () => {
    const t = new VCGTracker('s5')
    for (let i = 0; i < 100; i++) {
      t.addResult(output(true, 1.0), 1.0, TS + i)
    }
    expect(t.canEmitVerifiedConfidence(TS + 100)).toBe(true)
  })
})

// ─── shouldAlert / shouldSuspend ──────────────────────────

describe('shouldAlert', () => {
  it('returns true when weighted_error > 0.35', () => {
    const t = new VCGTracker('s6')
    // Claim 0.9 but fail: error = |0.9 - 0| = 0.9 > 0.35
    t.addResult(output(false, 0), 0.9, TS)
    expect(t.shouldAlert(TS)).toBe(true)
  })

  it('returns false when weighted_error ≤ 0.35', () => {
    const t = new VCGTracker('s7')
    t.addResult(output(true, 1.0), 1.0, TS)
    expect(t.shouldAlert(TS)).toBe(false)
  })
})

describe('shouldSuspend', () => {
  it('returns true when weighted_error > 0.50', () => {
    const t = new VCGTracker('s8')
    t.addResult(output(false, 0), 0.9, TS)
    expect(t.shouldSuspend(TS)).toBe(true)
  })

  it('returns false when weighted_error ≤ 0.50', () => {
    const t = new VCGTracker('s9')
    t.addResult(output(true, 1.0), 1.0, TS)
    expect(t.shouldSuspend(TS)).toBe(false)
  })
})

// ─── isStale ──────────────────────────────────────────────

describe('isStale', () => {
  it('returns false when lastUpdateMs is 0 (no samples ever added)', () => {
    const t = new VCGTracker('s10')
    expect(t.isStale(TS)).toBe(false)
  })

  it('returns true when last update > 24h ago', () => {
    const t = new VCGTracker('s11')
    t.addResult(output(true, 1.0), 1.0, TS)
    expect(t.isStale(TS + DAY_MS + 1)).toBe(true)
  })

  it('returns false when last update < 24h ago', () => {
    const t = new VCGTracker('s12')
    t.addResult(output(true, 1.0), 1.0, TS)
    expect(t.isStale(TS + DAY_MS - 1)).toBe(false)
  })
})

// ─── resetEpoch ───────────────────────────────────────────

describe('resetEpoch', () => {
  it('clears samples and increments epoch on drift', () => {
    const t = new VCGTracker('s13')
    t.addResult(output(true, 1.0), 1.0, TS)
    const epochBefore = t.getEpochId()
    t.resetEpoch('drift')
    expect(t.compute(TS).sample_count).toBe(0)
    expect(t.getEpochId()).not.toBe(epochBefore)
  })

  it('clears samples on manual reset', () => {
    const t = new VCGTracker('s14')
    t.addResult(output(true, 1.0), 1.0, TS)
    t.resetEpoch('manual')
    expect(t.compute(TS).sample_count).toBe(0)
  })

  it('clears samples on low_sample reset', () => {
    const t = new VCGTracker('s15')
    t.addResult(output(true, 1.0), 1.0, TS)
    t.resetEpoch('low_sample')
    expect(t.compute(TS).sample_count).toBe(0)
  })

  it('epoch ID increments on consecutive resets', () => {
    const t = new VCGTracker('s16')
    const e0 = t.getEpochId()
    t.resetEpoch('drift')
    const e1 = t.getEpochId()
    t.resetEpoch('drift')
    const e2 = t.getEpochId()
    expect(e0).not.toBe(e1)
    expect(e1).not.toBe(e2)
  })
})

// ─── getConfidenceInterval ────────────────────────────────

describe('getConfidenceInterval', () => {
  it('throws RangeError when alpha <= 0', () => {
    const t = new VCGTracker('s17')
    expect(() => t.getConfidenceInterval(0)).toThrow(RangeError)
    expect(() => t.getConfidenceInterval(-0.1)).toThrow(RangeError)
  })

  it('throws RangeError when alpha >= 1', () => {
    const t = new VCGTracker('s18')
    expect(() => t.getConfidenceInterval(1)).toThrow(RangeError)
    expect(() => t.getConfidenceInterval(1.5)).toThrow(RangeError)
  })

  it('returns {lower:0, upper:1} when no samples', () => {
    const t = new VCGTracker('s19')
    const ci = t.getConfidenceInterval(0.05)
    expect(ci.lower).toBe(0)
    expect(ci.upper).toBe(1)
  })

  it('returns valid [0,1]-bounded interval with samples', () => {
    const t = new VCGTracker('s20')
    for (let i = 0; i < 10; i++) {
      t.addResult(output(i % 2 === 0, 0.8), 0.8, TS + i)
    }
    const ci = t.getConfidenceInterval(0.05)
    expect(ci.lower).toBeGreaterThanOrEqual(0)
    expect(ci.upper).toBeLessThanOrEqual(1)
    expect(ci.lower).toBeLessThanOrEqual(ci.upper)
  })
})

// ─── getCalibrationBias ───────────────────────────────────

describe('getCalibrationBias', () => {
  it('returns 0 when no samples', () => {
    const t = new VCGTracker('s21')
    expect(t.getCalibrationBias()).toBe(0)
  })

  it('is positive (overconfident) when claiming high but failing', () => {
    const t = new VCGTracker('s22')
    t.addResult(output(false, 0), 0.9, TS)
    expect(t.getCalibrationBias()).toBeGreaterThan(0)
  })

  it('is negative (underconfident) when claiming low but passing', () => {
    const t = new VCGTracker('s23')
    t.addResult(output(true, 1.0), 0.2, TS)
    expect(t.getCalibrationBias()).toBeLessThan(0)
  })
})

// ─── getBrierScore ────────────────────────────────────────

describe('getBrierScore', () => {
  it('returns 0 when no samples', () => {
    const t = new VCGTracker('s24')
    expect(t.getBrierScore()).toBe(0)
  })

  it('is 0 for perfectly calibrated predictions', () => {
    const t = new VCGTracker('s25')
    t.addResult(output(true, 1.0), 1.0, TS)
    t.addResult(output(false, 0), 0.0, TS + 1)
    expect(t.getBrierScore()).toBeCloseTo(0, 6)
  })

  it('is positive for incorrect predictions', () => {
    const t = new VCGTracker('s26')
    t.addResult(output(false, 0), 0.9, TS)
    expect(t.getBrierScore()).toBeGreaterThan(0)
  })
})

// ─── buildConfidence ──────────────────────────────────────

describe('buildConfidence', () => {
  it('returns heuristic type when insufficient window', () => {
    const t = new VCGTracker('s27')
    t.addResult(output(true, 1.0), 1.0, TS)
    const conf = buildConfidence(t, TS, ['v1'])
    expect(conf.type).toBe('heuristic')
    expect(conf.value).toBe(0.3)
  })

  it('returns verified type when window is sufficient (100+ samples)', () => {
    const t = new VCGTracker('s28')
    for (let i = 0; i < 100; i++) {
      t.addResult(output(true, 1.0), 1.0, TS + i)
    }
    const conf = buildConfidence(t, TS + 100, ['v1', 'v2'])
    expect(conf.type).toBe('verified')
    expect(conf.value).toBeGreaterThanOrEqual(0)
    expect(conf.value).toBeLessThanOrEqual(1)
  })
})
