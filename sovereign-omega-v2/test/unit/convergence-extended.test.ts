// ============================================================
// Convergence Extended Tests — constitutional/convergence.ts
// Targets uncovered branches:
//   systemHealth() before any recordCycle (inv=null → 'PERMIT', t0=false)
//   recordCycle findings: T1_ALERT → 'important' severity
//   recordCycle findings: T2_WARN → 'informational' severity
// ============================================================

import { describe, it, expect } from 'vitest'
import { ConvergenceSurface } from '../../src/constitutional/convergence.js'
import type { InvariantCheckResult, InvariantViolation } from '../../src/core/invariant-checker.js'
import { HolonicScale, EpistemicTier } from '../../src/core/types.js'

// ─── Fixture helpers ──────────────────────────────────────

function makeResult(violations: readonly InvariantViolation[]): InvariantCheckResult {
  return {
    passed: violations.length === 0,
    violations,
    checked_at_sequence: 1,
  }
}

function makeViolation(severity: 'T0_ABORT' | 'T1_ALERT' | 'T2_WARN'): InvariantViolation {
  return {
    invariant_id: `INV-${severity}`,
    description: `Test ${severity} violation`,
    severity,
    observed_value: 'test',
    expected: 'ok',
    holonic_scale: HolonicScale.CELLULAR,
    tier: EpistemicTier.T1,
  }
}

// ─── systemHealth before any recordCycle ─────────────────

describe('ConvergenceSurface: systemHealth with no prior recordCycle', () => {
  it('systemHealth before any cycle uses PERMIT verdict (inv=null)', () => {
    const surface = ConvergenceSurface.create(0.9)
    const health = surface.systemHealth(0)
    expect(health.current_verdict).toBe('PERMIT')
  })

  it('systemHealth before any cycle has t0=false → is_coherent=true', () => {
    const surface = ConvergenceSurface.create(0.9)
    const health = surface.systemHealth(0)
    // default _lastSitrState='STABLE', _lastAoieGlobal='SECURE', no T0
    expect(health.is_coherent).toBe(true)
  })

  it('systemHealth before any cycle is frozen', () => {
    const surface = ConvergenceSurface.create(0.9)
    expect(Object.isFrozen(surface.systemHealth(0))).toBe(true)
  })

  it('convergenceDepth is 0 before any cycle', () => {
    const surface = ConvergenceSurface.create(0.9)
    expect(surface.convergenceDepth()).toBe(0)
  })
})

// ─── T1_ALERT violation → 'important' severity ───────────

describe('ConvergenceSurface: recordCycle with T1_ALERT violation', () => {
  it('accepts cycle with T1_ALERT violation without throwing', () => {
    const surface = ConvergenceSurface.create(0.9)
    expect(() => surface.recordCycle({
      sitr_state: 'DEGRADED',
      aoie_global_state: 'ALERT',
      invariant_result: makeResult([makeViolation('T1_ALERT')]),
      sequence: 1,
      gate_result: 'FAIL',
    })).not.toThrow()
  })

  it('T1_ALERT violation still resets consecutivePassCount on FAIL', () => {
    const surface = ConvergenceSurface.create(0.9)
    surface.recordCycle({
      sitr_state: 'STABLE',
      aoie_global_state: 'SECURE',
      invariant_result: makeResult([]),
      sequence: 1,
      gate_result: 'PASS',
    })
    surface.recordCycle({
      sitr_state: 'DEGRADED',
      aoie_global_state: 'ALERT',
      invariant_result: makeResult([makeViolation('T1_ALERT')]),
      sequence: 2,
      gate_result: 'FAIL',
    })
    expect(surface.convergenceDepth()).toBe(0)
  })
})

// ─── T2_WARN violation → 'informational' severity ────────

describe('ConvergenceSurface: recordCycle with T2_WARN violation', () => {
  it('accepts cycle with T2_WARN violation without throwing', () => {
    const surface = ConvergenceSurface.create(0.9)
    expect(() => surface.recordCycle({
      sitr_state: 'STABLE',
      aoie_global_state: 'SECURE',
      invariant_result: makeResult([makeViolation('T2_WARN')]),
      sequence: 1,
      gate_result: 'PASS',
    })).not.toThrow()
  })

  it('T2_WARN on PASS still increments consecutivePassCount', () => {
    const surface = ConvergenceSurface.create(0.9)
    surface.recordCycle({
      sitr_state: 'STABLE',
      aoie_global_state: 'SECURE',
      invariant_result: makeResult([makeViolation('T2_WARN')]),
      sequence: 1,
      gate_result: 'PASS',
    })
    expect(surface.convergenceDepth()).toBe(1)
  })

  it('multiple violation severities in one cycle does not throw', () => {
    const surface = ConvergenceSurface.create(0.9)
    expect(() => surface.recordCycle({
      sitr_state: 'DEGRADED',
      aoie_global_state: 'ALERT',
      invariant_result: makeResult([
        makeViolation('T0_ABORT'),
        makeViolation('T1_ALERT'),
        makeViolation('T2_WARN'),
      ]),
      sequence: 1,
      gate_result: 'FAIL',
    })).not.toThrow()
  })
})
