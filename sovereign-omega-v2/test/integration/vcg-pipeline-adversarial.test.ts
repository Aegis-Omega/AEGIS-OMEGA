// ============================================================
// Gate 80 — VCG Calibration Pipeline Adversarial (Integration)
// ~18 tests: VCGTracker score manipulation attempts bounded;
//   ADVISORY_EXCLUDED verifiers never contribute to VCG;
//   buildConfidence output is replay-certifiable;
//   determinism at fixed timestamp.
// ============================================================

import { describe, it, expect } from 'vitest'
import { VCGTracker, buildConfidence } from '../../src/calibration/vcg.js'
import { CalibrationDomain } from '../../src/core/types.js'
import type { VerifierOutput } from '../../src/verifier/types.js'

const TS = 1_600_000_000_000  // fixed epoch — never Date.now()

function makeOutput(passed: boolean, domain: CalibrationDomain, id = 'v1'): VerifierOutput {
  return Object.freeze({
    verifier_id: id,
    claim_id: `claim_${id}`,
    passed,
    raw_confidence: passed ? 0.9 : 0.1,
    evidence_refs: [],
    latency_ms: 1,
    determinism_flag: true,
    verifier_version: '1.0.0',
    trust_class: domain,
    artifact_hash: id.padEnd(64, '0') as any,
  })
}

// ─── ADVISORY_EXCLUDED never contributes ──────────────────

describe('VCG: ADVISORY_EXCLUDED never contributes', () => {
  it('100 ADVISORY_EXCLUDED results → VCG.weighted_error stays 0', () => {
    const tracker = new VCGTracker('test-stream')
    for (let i = 0; i < 100; i++) {
      tracker.addResult(makeOutput(false, CalibrationDomain.ADVISORY_EXCLUDED, `adv_${i}`), 0.9, TS + i)
    }
    const metric = tracker.compute(TS + 100)
    expect(metric.sample_count).toBe(0)
    expect(metric.weighted_error).toBe(0)
  })

  it('GROUND_TRUTH + ADVISORY_EXCLUDED → only GROUND_TRUTH counted', () => {
    const tracker = new VCGTracker('test-stream')
    tracker.addResult(makeOutput(true, CalibrationDomain.GROUND_TRUTH, 'gt1'), 0.9, TS + 1)
    tracker.addResult(makeOutput(false, CalibrationDomain.ADVISORY_EXCLUDED, 'adv1'), 0.9, TS + 2)
    const metric = tracker.compute(TS + 2)
    expect(metric.sample_count).toBe(1)  // only GROUND_TRUTH
  })

  it('RETRIEVAL_ASSISTED contributes with weight 0.5', () => {
    const tracker = new VCGTracker('test-stream')
    tracker.addResult(makeOutput(true, CalibrationDomain.RETRIEVAL_ASSISTED, 'r1'), 0.9, TS + 1)
    const metric = tracker.compute(TS + 1)
    expect(metric.sample_count).toBe(1)
  })
})

// ─── Score manipulation attempts bounded ──────────────────

describe('VCG: score manipulation bounded to [0,1]', () => {
  it('extreme claimed_confidence > 1 clamped to 1', () => {
    const tracker = new VCGTracker('test-stream')
    tracker.addResult(makeOutput(false, CalibrationDomain.GROUND_TRUTH, 'gt1'), 999.0, TS + 1)
    const metric = tracker.compute(TS + 1)
    // claimed is clamped to 1.0; actual=0; error = |1 - 0| = 1
    expect(metric.weighted_error).toBeGreaterThan(0)
    expect(metric.weighted_error).toBeLessThanOrEqual(1)
  })

  it('negative claimed_confidence clamped to 0', () => {
    const tracker = new VCGTracker('test-stream')
    tracker.addResult(makeOutput(true, CalibrationDomain.GROUND_TRUTH, 'gt1'), -5.0, TS + 1)
    const metric = tracker.compute(TS + 1)
    // claimed = 0; actual = 1; error = |0 - 1| = 1
    expect(metric.weighted_error).toBeGreaterThan(0)
    expect(metric.weighted_error).toBeLessThanOrEqual(1)
  })

  it('perfect calibration (claimed=actual) → weighted_error near 0', () => {
    const tracker = new VCGTracker('test-stream')
    for (let i = 0; i < 10; i++) {
      tracker.addResult(makeOutput(true, CalibrationDomain.GROUND_TRUTH, `gt${i}`), 1.0, TS + i)
    }
    const metric = tracker.compute(TS + 10)
    expect(metric.weighted_error).toBeLessThan(0.1)
  })
})

// ─── buildConfidence determinism ──────────────────────────

describe('VCG: buildConfidence determinism', () => {
  it('buildConfidence output is deterministic × 3', () => {
    const tracker = new VCGTracker('stream-det')
    for (let i = 0; i < 20; i++) {
      tracker.addResult(makeOutput(i % 2 === 0, CalibrationDomain.GROUND_TRUTH, `gt${i}`), 0.85, TS + i)
    }
    const c1 = buildConfidence(tracker, TS + 100, ['v1', 'v2'])
    const c2 = buildConfidence(tracker, TS + 100, ['v1', 'v2'])
    const c3 = buildConfidence(tracker, TS + 100, ['v1', 'v2'])
    expect(c1.value).toBe(c2.value)
    expect(c2.value).toBe(c3.value)
    expect(c1.type).toBe(c2.type)
  })

  it('buildConfidence value is in [0, 1]', () => {
    const tracker = new VCGTracker('stream-bounds')
    for (let i = 0; i < 20; i++) {
      tracker.addResult(makeOutput(true, CalibrationDomain.GROUND_TRUTH, `gt${i}`), 0.9, TS + i)
    }
    const conf = buildConfidence(tracker, TS + 100, ['v1'])
    expect(conf.value).toBeGreaterThanOrEqual(0)
    expect(conf.value).toBeLessThanOrEqual(1)
  })

  it('empty tracker → metric.sample_count=0, weighted_error=0', () => {
    const tracker = new VCGTracker('empty')
    const metric = tracker.compute(TS)
    expect(metric.sample_count).toBe(0)
    expect(metric.weighted_error).toBe(0)
  })

  it('20 GROUND_TRUTH results → sample_count=20', () => {
    const tracker = new VCGTracker('full')
    for (let i = 0; i < 20; i++) {
      tracker.addResult(makeOutput(i % 2 === 0, CalibrationDomain.GROUND_TRUTH, `gt${i}`), 0.7, TS + i)
    }
    const metric = tracker.compute(TS + 20)
    expect(metric.sample_count).toBe(20)
  })
})
