import { describe, it, expect } from 'vitest'
import { VCGTracker } from '../../src/calibration/vcg'
import { CalibrationDomain } from '../../src/core/types'
import type { VerifierOutput } from '../../src/verifier/types'
import { SHA256Hex } from '../../src/core/types'

function makeOutput(passed: boolean, confidence: number, trust: CalibrationDomain): VerifierOutput {
  return {
    verifier_id: `v-${trust}`,
    claim_id: 'test-claim',
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

describe('VCG Calibration Tracker', () => {
  it('computes VCG of 0 for perfectly calibrated samples', () => {
    const tracker = new VCGTracker('stream-1')
    const ts = 1000
    tracker.addResult(makeOutput(true, 1.0, CalibrationDomain.GROUND_TRUTH), 1.0, ts)
    tracker.addResult(makeOutput(false, 0.0, CalibrationDomain.GROUND_TRUTH), 0.0, ts)
    const metric = tracker.compute(ts)
    expect(metric.weighted_error).toBeCloseTo(0, 5)
  })

  it('computes VCG of 1 for maximally miscalibrated samples', () => {
    const tracker = new VCGTracker('stream-2')
    const ts = 1000
    tracker.addResult(makeOutput(false, 1.0, CalibrationDomain.GROUND_TRUTH), 1.0, ts)
    tracker.addResult(makeOutput(true, 0.0, CalibrationDomain.GROUND_TRUTH), 0.0, ts)
    const metric = tracker.compute(ts)
    expect(metric.weighted_error).toBeCloseTo(1, 5)
  })

  it('ignores Advisory-Excluded verifiers', () => {
    const tracker = new VCGTracker('stream-3')
    const ts = 1000
    // Advisory-excluded — should not contribute
    tracker.addResult(makeOutput(false, 1.0, CalibrationDomain.ADVISORY_EXCLUDED), 1.0, ts)
    const metric = tracker.compute(ts)
    expect(metric.sample_count).toBe(0)
  })

  it('applies 0.5 weight to Retrieval-Assisted verifiers', () => {
    const tracker1 = new VCGTracker('stream-4a')
    const tracker2 = new VCGTracker('stream-4b')
    const ts = 1000
    // Ground truth: full weight
    tracker1.addResult(makeOutput(false, 1.0, CalibrationDomain.GROUND_TRUTH), 1.0, ts)
    // Retrieval-assisted: half weight — should produce same error magnitude but lower effective weight
    tracker2.addResult(makeOutput(false, 1.0, CalibrationDomain.RETRIEVAL_ASSISTED), 1.0, ts)
    const m1 = tracker1.compute(ts)
    const m2 = tracker2.compute(ts)
    expect(m1.weighted_error).toBeCloseTo(m2.weighted_error, 5) // same error magnitude
    expect(m1.effective_sample_size).toBeGreaterThan(m2.effective_sample_size) // but different ESS
  })

  it('does not emit verified confidence below minimum window', () => {
    const tracker = new VCGTracker('stream-5')
    const ts = 1000
    // Add only 5 samples (below 100 minimum)
    for (let i = 0; i < 5; i++) {
      tracker.addResult(makeOutput(true, 0.9, CalibrationDomain.GROUND_TRUTH), 0.9, ts + i)
    }
    expect(tracker.canEmitVerifiedConfidence(ts + 5)).toBe(false)
  })

  it('produces deterministic bootstrap CI for same seed', () => {
    const ts = 1_600_000_000_000
    const tracker1 = new VCGTracker('stream-det')
    const tracker2 = new VCGTracker('stream-det')
    for (let i = 0; i < 50; i++) {
      const output = makeOutput(i % 2 === 0, 0.6, CalibrationDomain.GROUND_TRUTH)
      tracker1.addResult(output, 0.6, ts + i * 1000)
      tracker2.addResult(output, 0.6, ts + i * 1000)
    }
    const m1 = tracker1.compute(ts + 50_000)
    const m2 = tracker2.compute(ts + 50_000)
    expect(m1.bootstrap_ci_95[0]).toBeCloseTo(m2.bootstrap_ci_95[0], 10)
    expect(m1.bootstrap_ci_95[1]).toBeCloseTo(m2.bootstrap_ci_95[1], 10)
  })

  it('trims to window size', () => {
    const tracker = new VCGTracker('stream-6', 10)
    const ts = 1000
    for (let i = 0; i < 20; i++) {
      tracker.addResult(makeOutput(true, 0.9, CalibrationDomain.GROUND_TRUTH), 0.9, ts + i)
    }
    const metric = tracker.compute(ts + 20)
    expect(metric.sample_count).toBe(10)
  })
})
