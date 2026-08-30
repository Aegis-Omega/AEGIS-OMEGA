// ============================================================
// SOVEREIGN OMEGA — Runtime Constitutional Invariant Checker tests
// EPISTEMIC TIER: T0
//
// Tests for core/invariant-checker.ts:
//   checkInvariants — all 10 invariants (pass + violation cases)
//   hasT0Violation  — severity filter
//   isCycleCoherent — gate + T0 combined gate
//   formatReport    — human-readable summary
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  checkInvariants,
  hasT0Violation,
  isCycleCoherent,
  formatReport,
} from '../../src/core/invariant-checker.js'
import type { RuntimeSnapshot, InvariantCheckResult } from '../../src/core/invariant-checker.js'
import { HolonicScale, RalphPhase } from '../../src/core/types.js'
import type { RalphCycle, UUIDv7, SequenceNumber } from '../../src/core/types.js'

function goodSnapshot(overrides: Partial<RuntimeSnapshot> = {}): RuntimeSnapshot {
  return {
    vcg_error: 0.5,
    drift_index: 0,
    corruption_count: 0,
    pgcs_passes: true,
    calibrator_passes: true,
    failsafe_state: 'ok',
    sequence: 10,
    gate_sealed: true,
    ...overrides,
  }
}

function makePassingResult(): InvariantCheckResult {
  return checkInvariants(goodSnapshot())
}

// ── checkInvariants — happy path ──────────────────────────

describe('checkInvariants — happy path', () => {
  it('passes all invariants with a clean snapshot', () => {
    const result = checkInvariants(goodSnapshot())
    expect(result.passed).toBe(true)
    expect(result.violations).toHaveLength(0)
    expect(result.checked_at_sequence).toBe(10)
  })

  it('vacuously passes INV-07 when gate_acceptance_rate is absent', () => {
    const result = checkInvariants(goodSnapshot())
    expect(result.violations.find(v => v.invariant_id === 'INV-07')).toBeUndefined()
  })

  it('vacuously passes INV-09 when afse_r2 is absent', () => {
    const result = checkInvariants(goodSnapshot())
    expect(result.violations.find(v => v.invariant_id === 'INV-09')).toBeUndefined()
  })

  it('vacuously passes INV-09 when pgcs_passes=false even if afse_r2 < 0.98', () => {
    const result = checkInvariants(goodSnapshot({ pgcs_passes: false, afse_r2: 0.50 }))
    expect(result.violations.find(v => v.invariant_id === 'INV-09')).toBeUndefined()
  })

  it('vacuously passes INV-10 when tgcs_variance is absent', () => {
    const result = checkInvariants(goodSnapshot())
    expect(result.violations.find(v => v.invariant_id === 'INV-10')).toBeUndefined()
  })
})

// ── checkInvariants — individual violations ───────────────

describe('checkInvariants — individual violations', () => {
  it('INV-01: vcg_error > 1 produces T0_ABORT violation', () => {
    const result = checkInvariants(goodSnapshot({ vcg_error: 1.1 }))
    const v = result.violations.find(v => v.invariant_id === 'INV-01')
    expect(v).toBeDefined()
    expect(v!.severity).toBe('T0_ABORT')
    expect(result.passed).toBe(false)
  })

  it('INV-01: vcg_error < 0 produces T0_ABORT violation', () => {
    const result = checkInvariants(goodSnapshot({ vcg_error: -0.1 }))
    expect(result.violations.find(v => v.invariant_id === 'INV-01')).toBeDefined()
  })

  it('INV-02: corruption_count > 0 produces T0_ABORT violation', () => {
    const result = checkInvariants(goodSnapshot({ corruption_count: 1 }))
    const v = result.violations.find(v => v.invariant_id === 'INV-02')
    expect(v).toBeDefined()
    expect(v!.severity).toBe('T0_ABORT')
  })

  it('INV-03: pgcs_passes=false produces T1_ALERT violation', () => {
    const result = checkInvariants(goodSnapshot({ pgcs_passes: false }))
    const v = result.violations.find(v => v.invariant_id === 'INV-03')
    expect(v).toBeDefined()
    expect(v!.severity).toBe('T1_ALERT')
  })

  it('INV-04: drift_index < 0 produces T1_ALERT violation', () => {
    const result = checkInvariants(goodSnapshot({ drift_index: -1 }))
    const v = result.violations.find(v => v.invariant_id === 'INV-04')
    expect(v).toBeDefined()
    expect(v!.severity).toBe('T1_ALERT')
  })

  it('INV-05: gate_sealed=false produces T0_ABORT violation', () => {
    const result = checkInvariants(goodSnapshot({ gate_sealed: false }))
    const v = result.violations.find(v => v.invariant_id === 'INV-05')
    expect(v).toBeDefined()
    expect(v!.severity).toBe('T0_ABORT')
  })

  it('INV-06: failsafe_state=frozen produces T0_ABORT violation', () => {
    const result = checkInvariants(goodSnapshot({ failsafe_state: 'frozen' }))
    const v = result.violations.find(v => v.invariant_id === 'INV-06')
    expect(v).toBeDefined()
    expect(v!.severity).toBe('T0_ABORT')
  })

  it('INV-07: gate_acceptance_rate=1.5 produces T1_ALERT violation', () => {
    const result = checkInvariants(goodSnapshot({ gate_acceptance_rate: 1.5 }))
    const v = result.violations.find(v => v.invariant_id === 'INV-07')
    expect(v).toBeDefined()
    expect(v!.severity).toBe('T1_ALERT')
  })

  it('INV-08: sequence=-1 produces T0_ABORT violation', () => {
    const result = checkInvariants(goodSnapshot({ sequence: -1 }))
    const v = result.violations.find(v => v.invariant_id === 'INV-08')
    expect(v).toBeDefined()
    expect(v!.severity).toBe('T0_ABORT')
  })

  it('INV-09: afse_r2=0.97 when pgcs_passes=true produces T1_ALERT violation', () => {
    const result = checkInvariants(goodSnapshot({ pgcs_passes: true, afse_r2: 0.97 }))
    const v = result.violations.find(v => v.invariant_id === 'INV-09')
    expect(v).toBeDefined()
    expect(v!.severity).toBe('T1_ALERT')
  })

  it('INV-10: tgcs_variance=1 produces T1_ALERT violation', () => {
    const result = checkInvariants(goodSnapshot({ tgcs_variance: 1 }))
    const v = result.violations.find(v => v.invariant_id === 'INV-10')
    expect(v).toBeDefined()
    expect(v!.severity).toBe('T1_ALERT')
  })

  it('multiple violations accumulate — all reported', () => {
    const result = checkInvariants(goodSnapshot({
      vcg_error: 2.0,
      corruption_count: 3,
      failsafe_state: 'frozen',
    }))
    expect(result.violations.length).toBeGreaterThanOrEqual(3)
    expect(result.passed).toBe(false)
  })
})

// ── hasT0Violation ────────────────────────────────────────

describe('hasT0Violation', () => {
  it('returns false for a passed result', () => {
    expect(hasT0Violation(makePassingResult())).toBe(false)
  })

  it('returns true when a T0_ABORT violation exists', () => {
    const result = checkInvariants(goodSnapshot({ corruption_count: 1 }))
    expect(hasT0Violation(result)).toBe(true)
  })

  it('returns false when only T1_ALERT violations exist', () => {
    const result = checkInvariants(goodSnapshot({ pgcs_passes: false }))
    expect(result.violations.some(v => v.severity === 'T1_ALERT')).toBe(true)
    expect(hasT0Violation(result)).toBe(false)
  })
})

// ── isCycleCoherent ───────────────────────────────────────

describe('isCycleCoherent', () => {
  const passCycle: RalphCycle = {
    cycle_id: 'c1' as unknown as UUIDv7,
    cycle_number: 1,
    target_scale: HolonicScale.ATOMIC,
    phase: RalphPhase.HARMONIZE,
    findings: [],
    analysis_notes: [],
    links_established: [],
    patches_applied: [],
    harmonization_result: 'COHERENT',
    gate_result: 'PASS',
    sequence: 1n as unknown as SequenceNumber,
  }
  const failCycle: RalphCycle = { ...passCycle, gate_result: 'FAIL' }

  it('returns true when gate passes and no T0 violation', () => {
    expect(isCycleCoherent(passCycle, makePassingResult())).toBe(true)
  })

  it('returns false when gate fails even with no T0 violation', () => {
    expect(isCycleCoherent(failCycle, makePassingResult())).toBe(false)
  })

  it('returns false when gate passes but T0 violation exists', () => {
    const t0result = checkInvariants(goodSnapshot({ corruption_count: 1 }))
    expect(isCycleCoherent(passCycle, t0result)).toBe(false)
  })

  it('returns false when both gate fails and T0 violation exists', () => {
    const t0result = checkInvariants(goodSnapshot({ corruption_count: 1 }))
    expect(isCycleCoherent(failCycle, t0result)).toBe(false)
  })
})

// ── formatReport ─────────────────────────────────────────

describe('formatReport', () => {
  it('returns ALL CLEAR line when passed', () => {
    const report = formatReport(makePassingResult())
    expect(report).toMatch(/^ALL CLEAR/)
    expect(report).toContain('seq 10')
  })

  it('includes invariant ID and severity in violation report', () => {
    const result = checkInvariants(goodSnapshot({ corruption_count: 1 }))
    const report = formatReport(result)
    expect(report).toContain('T0_ABORT')
    expect(report).toContain('INV-02')
  })

  it('one line per violation in multi-violation report', () => {
    const result = checkInvariants(goodSnapshot({
      vcg_error: 2.0,
      corruption_count: 1,
    }))
    const lines = formatReport(result).split('\n')
    expect(lines.length).toBeGreaterThanOrEqual(2)
  })
})
