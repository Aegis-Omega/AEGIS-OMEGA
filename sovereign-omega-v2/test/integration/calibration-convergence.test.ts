// ============================================================
// Gate 97 — Calibration Convergence (Integration)
// ~18 tests: VCG calibration → ConvergenceSurface pipeline;
//   depth bounded; convergence hash stable; T0 violation
//   detection via convergence surface.
// ============================================================

import { describe, it, expect } from 'vitest'
import { VCGTracker, buildConfidence } from '../../src/calibration/vcg.js'
import { ConvergenceSurface } from '../../src/constitutional/convergence.js'
import { CalibrationDomain } from '../../src/core/types.js'
import { checkInvariants } from '../../src/core/invariant-checker.js'
import type { InvariantCheckResult } from '../../src/core/invariant-checker.js'
import type { VerifierOutput } from '../../src/verifier/types.js'

const TS = 1_600_000_000_000

const CLEAN_SNAPSHOT = {
  vcg_error: 0.05,
  drift_index: 0.0,
  corruption_count: 0,
  pgcs_passes: true,
  calibrator_passes: true,
  failsafe_state: 'OPERATIONAL',
  sequence: 1,
  gate_acceptance_rate: 0.95,
  gate_sealed: true,
}

function cleanInv(seqN: number): InvariantCheckResult {
  return checkInvariants({ ...CLEAN_SNAPSHOT, sequence: seqN })
}

function violationInv(seqN: number): InvariantCheckResult {
  return checkInvariants({ ...CLEAN_SNAPSHOT, vcg_error: 2.0, corruption_count: 1, sequence: seqN })
}

function makeOutput(passed: boolean, domain: CalibrationDomain, id: string): VerifierOutput {
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

// ─── VCG → ConvergenceSurface pipeline ───────────────────

describe('Calibration → Convergence: PASS pipeline', () => {
  it('10 cycles of good calibration → convergenceDepth=10', () => {
    const surface = ConvergenceSurface.create(0.95)
    const inv = cleanInv(1)
    for (let i = 1; i <= 10; i++) {
      surface.recordCycle({
        sitr_state: 'STABLE',
        aoie_global_state: 'SECURE',
        invariant_result: inv,
        sequence: i,
        gate_result: 'PASS',
      })
    }
    expect(surface.convergenceDepth()).toBe(10)
  })

  it('FAIL cycle resets convergenceDepth to 0', () => {
    const surface = ConvergenceSurface.create(0.9)
    const inv = cleanInv(1)
    for (let i = 1; i <= 5; i++) {
      surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: inv, sequence: i, gate_result: 'PASS' })
    }
    expect(surface.convergenceDepth()).toBe(5)
    surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: inv, sequence: 6, gate_result: 'FAIL' })
    expect(surface.convergenceDepth()).toBe(0)
  })

  it('VCG high error → FAIL, convergenceDepth resets', () => {
    const tracker = new VCGTracker('err-stream')
    // All failed samples with high claimed confidence = high error
    for (let i = 0; i < 20; i++) {
      tracker.addResult(makeOutput(false, CalibrationDomain.GROUND_TRUTH, `g${i}`), 0.99, TS + i)
    }
    const metric = tracker.compute(TS + 20)
    expect(metric.weighted_error).toBeGreaterThan(0.5)

    const surface = ConvergenceSurface.create(0.9)
    const inv = cleanInv(1)
    for (let i = 1; i <= 3; i++) {
      surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: inv, sequence: i, gate_result: 'PASS' })
    }
    const gate = metric.weighted_error > 0.5 ? 'FAIL' : 'PASS'
    surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: inv, sequence: 4, gate_result: gate })
    expect(surface.convergenceDepth()).toBe(0)
  })
})

// ─── Calibration convergence bounds ───────────────────────

describe('Calibration: convergence bounds', () => {
  it('buildConfidence value in [0,1] after 50 samples', () => {
    const tracker = new VCGTracker('bounds')
    for (let i = 0; i < 50; i++) {
      tracker.addResult(makeOutput(i % 3 !== 0, CalibrationDomain.GROUND_TRUTH, `g${i}`), 0.75, TS + i)
    }
    const conf = buildConfidence(tracker, TS + 50, ['v1'])
    expect(conf.value).toBeGreaterThanOrEqual(0)
    expect(conf.value).toBeLessThanOrEqual(1)
  })

  it('perfect calibration (claimed=actual) → weighted_error < 0.05', () => {
    const tracker = new VCGTracker('perfect')
    for (let i = 0; i < 50; i++) {
      tracker.addResult(makeOutput(true, CalibrationDomain.GROUND_TRUTH, `g${i}`), 1.0, TS + i)
    }
    const metric = tracker.compute(TS + 50)
    expect(metric.weighted_error).toBeLessThan(0.05)
  })

  it('50-sample tracker → sample_count=50', () => {
    const tracker = new VCGTracker('count')
    for (let i = 0; i < 50; i++) {
      tracker.addResult(makeOutput(true, CalibrationDomain.GROUND_TRUTH, `g${i}`), 0.9, TS + i)
    }
    expect(tracker.compute(TS + 50).sample_count).toBe(50)
  })

  it('buildConfidence is deterministic ×3 at 50 samples', () => {
    const tracker = new VCGTracker('det')
    for (let i = 0; i < 50; i++) {
      tracker.addResult(makeOutput(i % 2 === 0, CalibrationDomain.GROUND_TRUTH, `g${i}`), 0.8, TS + i)
    }
    const c1 = buildConfidence(tracker, TS + 100, ['v1'])
    const c2 = buildConfidence(tracker, TS + 100, ['v1'])
    const c3 = buildConfidence(tracker, TS + 100, ['v1'])
    expect(c1.value).toBe(c2.value)
    expect(c2.value).toBe(c3.value)
  })
})

// ─── T0 violation → is_coherent=false ────────────────────

describe('Calibration Convergence: T0 violation detection', () => {
  it('T0 violation (corruption_count=1) → is_coherent=false', () => {
    const surface = ConvergenceSurface.create(0.9)
    const inv = violationInv(1)
    surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: inv, sequence: 1, gate_result: 'FAIL' })
    expect(surface.systemHealth(1).is_coherent).toBe(false)
  })

  it('systemHealth is frozen object', () => {
    const surface = ConvergenceSurface.create(0.95)
    const inv = cleanInv(1)
    surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: inv, sequence: 1, gate_result: 'PASS' })
    expect(Object.isFrozen(surface.systemHealth(1))).toBe(true)
  })

  it('DEGRADED SITR → is_coherent=false', () => {
    const surface = ConvergenceSurface.create(0.9)
    const inv = cleanInv(1)
    surface.recordCycle({ sitr_state: 'DEGRADED', aoie_global_state: 'SECURE', invariant_result: inv, sequence: 1, gate_result: 'PASS' })
    expect(surface.systemHealth(1).is_coherent).toBe(false)
  })

  it('stable system → is_coherent=true', () => {
    const surface = ConvergenceSurface.create(0.9)
    const inv = cleanInv(1)
    surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: inv, sequence: 1, gate_result: 'PASS' })
    expect(surface.systemHealth(1).is_coherent).toBe(true)
  })

  it('convergence depth idempotency: convergenceDepth called ×3 → same value', () => {
    const surface = ConvergenceSurface.create(0.9)
    for (let i = 1; i <= 7; i++) {
      surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: cleanInv(i), sequence: i, gate_result: 'PASS' })
    }
    const d1 = surface.convergenceDepth()
    const d2 = surface.convergenceDepth()
    const d3 = surface.convergenceDepth()
    expect(d1).toBe(7)
    expect(d1).toBe(d2)
    expect(d2).toBe(d3)
  })
})
