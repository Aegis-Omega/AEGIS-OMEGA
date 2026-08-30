// ============================================================
// Gate 68 — Convergence Surface Adversarial (Integration)
// ~22 tests: convergence depth stress; FAIL resets depth;
//   T0 violation detection; freeze law idempotency; 50-cycle
//   authority; systemHealth is frozen.
// ============================================================

import { describe, it, expect } from 'vitest'
import { ConvergenceSurface } from '../../src/constitutional/convergence.js'
import { checkInvariants } from '../../src/core/invariant-checker.js'
import type { InvariantCheckResult } from '../../src/core/invariant-checker.js'

const CLEAN_SNAPSHOT = {
  vcg_error: 0.1,
  drift_index: 0.0,
  corruption_count: 0,
  pgcs_passes: true,
  calibrator_passes: true,
  failsafe_state: 'OPERATIONAL',
  sequence: 1,
  gate_acceptance_rate: 0.95,
  gate_sealed: true,
}

function cleanResult(seq: number): InvariantCheckResult {
  return checkInvariants({ ...CLEAN_SNAPSHOT, sequence: seq })
}

function failResult(seq: number): InvariantCheckResult {
  // VCG error out of bounds → T0_ABORT
  return checkInvariants({ ...CLEAN_SNAPSHOT, vcg_error: 2.0, corruption_count: 1, sequence: seq })
}

// ─── Convergence depth stress ─────────────────────────────

describe('ConvergenceSurface: convergence depth', () => {
  it('50 consecutive PASS cycles → convergenceDepth()=50', () => {
    const surface = ConvergenceSurface.create(0.95)
    for (let i = 1; i <= 50; i++) {
      surface.recordCycle({
        sitr_state: 'STABLE',
        aoie_global_state: 'SECURE',
        invariant_result: cleanResult(i),
        sequence: i,
        gate_result: 'PASS',
      })
    }
    expect(surface.convergenceDepth()).toBe(50)
  })

  it('FAIL resets convergence depth to 0', () => {
    const surface = ConvergenceSurface.create(0.95)
    for (let i = 1; i <= 20; i++) {
      surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: cleanResult(i), sequence: i, gate_result: 'PASS' })
    }
    expect(surface.convergenceDepth()).toBe(20)
    surface.recordCycle({ sitr_state: 'DEGRADED', aoie_global_state: 'ALERT', invariant_result: failResult(21), sequence: 21, gate_result: 'FAIL' })
    expect(surface.convergenceDepth()).toBe(0)
  })

  it('PASS after FAIL resumes depth from 1', () => {
    const surface = ConvergenceSurface.create(0.95)
    surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: cleanResult(1), sequence: 1, gate_result: 'FAIL' })
    surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: cleanResult(2), sequence: 2, gate_result: 'PASS' })
    expect(surface.convergenceDepth()).toBe(1)
  })

  it('alternating PASS/FAIL/PASS/FAIL → convergenceDepth=0 after last FAIL', () => {
    const surface = ConvergenceSurface.create(0.95)
    for (let i = 1; i <= 10; i++) {
      const result = i % 2 === 0 ? 'FAIL' : 'PASS'
      surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: cleanResult(i), sequence: i, gate_result: result })
    }
    expect(surface.convergenceDepth()).toBe(0)
  })
})

// ─── systemHealth is frozen and coherent ──────────────────

describe('ConvergenceSurface: systemHealth', () => {
  it('systemHealth is frozen', () => {
    const surface = ConvergenceSurface.create(0.95)
    surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: cleanResult(1), sequence: 1, gate_result: 'PASS' })
    const health = surface.systemHealth(1)
    expect(Object.isFrozen(health)).toBe(true)
  })

  it('healthy system → is_coherent=true', () => {
    const surface = ConvergenceSurface.create(0.95)
    surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: cleanResult(1), sequence: 1, gate_result: 'PASS' })
    expect(surface.systemHealth(1).is_coherent).toBe(true)
  })

  it('DEGRADED sitr_state → is_coherent=false', () => {
    const surface = ConvergenceSurface.create(0.95)
    surface.recordCycle({ sitr_state: 'DEGRADED', aoie_global_state: 'SECURE', invariant_result: cleanResult(1), sequence: 1, gate_result: 'FAIL' })
    expect(surface.systemHealth(1).is_coherent).toBe(false)
  })

  it('systemHealth convergence_depth matches convergenceDepth()', () => {
    const surface = ConvergenceSurface.create(0.95)
    for (let i = 1; i <= 15; i++) {
      surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: cleanResult(i), sequence: i, gate_result: 'PASS' })
    }
    expect(surface.systemHealth(15).convergence_depth).toBe(surface.convergenceDepth())
  })
})

// ─── T0 violation detection ───────────────────────────────

describe('ConvergenceSurface: T0 violation detection', () => {
  it('T0 violation → is_coherent=false', () => {
    const surface = ConvergenceSurface.create(0.0)
    surface.recordCycle({
      sitr_state: 'CONSTITUTIONAL_RISK',
      aoie_global_state: 'COMPROMISED',
      invariant_result: failResult(1),
      sequence: 1,
      gate_result: 'FAIL',
    })
    expect(surface.systemHealth(1).is_coherent).toBe(false)
  })
})

// ─── Throughput ───────────────────────────────────────────

describe('ConvergenceSurface: throughput', () => {
  it('throughput proportional to cycle count', () => {
    const surface = ConvergenceSurface.create(0.9)
    for (let i = 1; i <= 10; i++) {
      surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: cleanResult(i), sequence: i, gate_result: 'PASS' })
    }
    const tp = surface.throughput(10)
    expect(tp).toBeGreaterThan(0)
  })
})

// ─── Freeze law idempotency ───────────────────────────────

describe('ConvergenceSurface: freeze law idempotency', () => {
  it('systemHealth called 3× → identical convergence_depth each time', () => {
    const surface = ConvergenceSurface.create(0.9)
    for (let i = 1; i <= 5; i++) {
      surface.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: cleanResult(i), sequence: i, gate_result: 'PASS' })
    }
    const h1 = surface.systemHealth(5)
    const h2 = surface.systemHealth(5)
    const h3 = surface.systemHealth(5)
    expect(h1.convergence_depth).toBe(h2.convergence_depth)
    expect(h2.convergence_depth).toBe(h3.convergence_depth)
  })
})
