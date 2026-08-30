// Ralph Loop state machine unit tests — Cycles 81–90, extended Cycles 91–100
import { describe, it, expect } from 'vitest'
import { RalphLoop, estimateSystemEntropy, governanceThroughput } from '../../src/core/ralph-loop.js'
import { HolonicScale, RalphPhase, EpistemicTier, CYCLE_ARCHIVE_SCHEMA_VERSION, type RalphCycle, type SequenceNumber } from '../../src/core/types.js'
import {
  checkInvariants,
  hasT0Violation,
  isCycleCoherent,
  type RuntimeSnapshot,
} from '../../src/core/invariant-checker.js'
import { generateUUIDv7 } from '../../src/event/uuid.js'

const SEQ = BigInt(1_000_000) as ReturnType<typeof BigInt> & { readonly __brand: 'SequenceNumber' }

// ─── Ralph Loop ──────────────────────────────────────────────────────────────

describe('RalphLoop', () => {
  it('begins at cycle 0 with zero convergence depth', () => {
    const loop = new RalphLoop(HolonicScale.ATOMIC, 0.5)
    expect(loop.getState().total_cycles).toBe(0)
    expect(loop.convergenceDepth()).toBe(0)
  })

  it('records a PASS cycle correctly', () => {
    const loop = new RalphLoop(HolonicScale.MOLECULAR, 0.8)
    const cycle = loop
      .beginCycle(SEQ)
      .addFinding({ description: 'missing test', severity: 'informational', scale: HolonicScale.ATOMIC, tier: EpistemicTier.T1 })
      .addAnalysisNote('Add coverage for ralph-loop module')
      .addLink('ralph-loop.ts ↔ types.ts via RalphCycle interface')
      .addPatch({ description: 'add unit tests', file: 'test/unit/ralph-loop.test.ts', type: 'create', tier_before: EpistemicTier.T2, tier_after: EpistemicTier.T1 })
      .harmonize('PASS')

    expect(cycle.cycle_number).toBe(1)
    expect(cycle.target_scale).toBe(HolonicScale.MOLECULAR)
    expect(cycle.harmonization_result).toBe('COHERENT')
    expect(cycle.gate_result).toBe('PASS')
    expect(cycle.phase).toBe(RalphPhase.HARMONIZE)
    expect(cycle.findings).toHaveLength(1)
    expect(cycle.patches_applied).toHaveLength(1)
  })

  it('records a FAIL cycle as INCOHERENT', () => {
    const loop = new RalphLoop(HolonicScale.CELLULAR, 1.0)
    const cycle = loop.beginCycle(SEQ).harmonize('FAIL')
    expect(cycle.harmonization_result).toBe('INCOHERENT')
  })

  it('convergence depth counts consecutive PASS cycles', () => {
    const loop = new RalphLoop(HolonicScale.ORGANISM, 0.6)
    loop.beginCycle(SEQ).harmonize('PASS')
    loop.beginCycle(SEQ).harmonize('PASS')
    loop.beginCycle(SEQ).harmonize('FAIL')
    loop.beginCycle(SEQ).harmonize('PASS')
    // After FAIL then PASS, only 1 consecutive PASS at the end
    expect(loop.convergenceDepth()).toBe(1)
  })

  it('full 100-cycle loop completes with monotonically increasing cycle numbers', () => {
    const loop = new RalphLoop(HolonicScale.FIELD, 0.0)
    for (let i = 0; i < 100; i++) {
      const cycle = loop.beginCycle(SEQ).harmonize('PASS')
      expect(cycle.cycle_number).toBe(i + 1)
    }
    expect(loop.getState().total_cycles).toBe(100)
    expect(loop.convergenceDepth()).toBe(100)
  })

  it('getState includes entropy_at_end when provided', () => {
    const loop = new RalphLoop(HolonicScale.SUBATOMIC, 1.0)
    loop.beginCycle(SEQ).harmonize('PASS')
    const state = loop.getState(0.1)
    expect(state.entropy_at_start).toBe(1.0)
    expect(state.entropy_at_end).toBe(0.1)
  })

  it('exportArchive produces versioned CycleArchive', () => {
    const loop = new RalphLoop(HolonicScale.CELLULAR, 0.9)
    loop.beginCycle(SEQ).harmonize('PASS')
    loop.beginCycle(SEQ).harmonize('PASS')
    const archive = loop.exportArchive(999, 0.3)
    expect(archive.schema_version).toBe(CYCLE_ARCHIVE_SCHEMA_VERSION)
    expect(archive.archived_at_sequence).toBe(999)
    expect(archive.cycles).toHaveLength(2)
    expect(archive.total_cycles).toBe(2)
    expect(archive.convergence_depth).toBe(2)
    expect(archive.entropy_at_start).toBe(0.9)
    expect(archive.entropy_at_end).toBe(0.3)
  })

  it('exportArchive omits entropy_at_end when not provided', () => {
    const loop = new RalphLoop(HolonicScale.ATOMIC, 0.5)
    loop.beginCycle(SEQ).harmonize('PASS')
    const archive = loop.exportArchive(100)
    expect('entropy_at_end' in archive).toBe(false)
  })
})

// ─── estimateSystemEntropy ────────────────────────────────────────────────────

describe('estimateSystemEntropy', () => {
  it('returns 0 for perfect acceptance (rate=1)', () => {
    expect(estimateSystemEntropy(1.0)).toBe(0)
  })

  it('returns 0 for zero acceptance (rate=0)', () => {
    expect(estimateSystemEntropy(0.0)).toBe(0)
  })

  it('returns max entropy at rate=0.5', () => {
    const h = estimateSystemEntropy(0.5)
    expect(h).toBeCloseTo(1.0, 10)
  })

  it('is symmetric around 0.5', () => {
    expect(estimateSystemEntropy(0.3)).toBeCloseTo(estimateSystemEntropy(0.7), 10)
  })

  it('clamps out-of-range inputs', () => {
    expect(estimateSystemEntropy(-1)).toBe(0)
    expect(estimateSystemEntropy(2)).toBe(0)
  })
})

// ─── governanceThroughput ─────────────────────────────────────────────────────

describe('governanceThroughput', () => {
  it('returns cycles-per-sequence-unit', () => {
    // 10 cycles over 10000 sequence events = 0.001 cycles/seq
    expect(governanceThroughput(10, 10_000)).toBeCloseTo(0.001, 6)
  })

  it('returns 0 for zero span', () => {
    expect(governanceThroughput(5, 0)).toBe(0)
  })

  it('returns 0 for negative span', () => {
    expect(governanceThroughput(3, -1)).toBe(0)
  })

  it('increases linearly with cycle count', () => {
    expect(governanceThroughput(100, 1000)).toBeCloseTo(0.1, 6)
    expect(governanceThroughput(200, 1000)).toBeCloseTo(0.2, 6)
  })
})

// ─── InvariantChecker ─────────────────────────────────────────────────────────

describe('checkInvariants', () => {
  const nominal: RuntimeSnapshot = {
    vcg_error: 0.05,
    drift_index: 0.0,
    corruption_count: 0,
    pgcs_passes: true,
    calibrator_passes: true,
    failsafe_state: 'active',
    sequence: 42,
    gate_acceptance_rate: 0.87,
    gate_sealed: true,
  }

  it('passes on nominal state', () => {
    const result = checkInvariants(nominal)
    expect(result.passed).toBe(true)
    expect(result.violations).toHaveLength(0)
  })

  it('fails INV-02 when corruption_count > 0', () => {
    const result = checkInvariants({ ...nominal, corruption_count: 1 })
    expect(result.passed).toBe(false)
    expect(result.violations.some(v => v.invariant_id === 'INV-02')).toBe(true)
    expect(hasT0Violation(result)).toBe(true)
  })

  it('fails INV-01 when vcg_error > 1', () => {
    const result = checkInvariants({ ...nominal, vcg_error: 1.5 })
    expect(result.violations.some(v => v.invariant_id === 'INV-01')).toBe(true)
  })

  it('fails INV-06 when failsafe_state = frozen', () => {
    const result = checkInvariants({ ...nominal, failsafe_state: 'frozen' })
    expect(result.violations.some(v => v.invariant_id === 'INV-06')).toBe(true)
    expect(hasT0Violation(result)).toBe(true)
  })

  it('does not fail INV-07 when gate_acceptance_rate is undefined', () => {
    const { gate_acceptance_rate: _, ...rest } = nominal
    const result = checkInvariants({ ...rest } as RuntimeSnapshot)
    expect(result.violations.some(v => v.invariant_id === 'INV-07')).toBe(false)
  })

  it('fails INV-05 when gate_sealed = false', () => {
    const result = checkInvariants({ ...nominal, gate_sealed: false })
    expect(result.violations.some(v => v.invariant_id === 'INV-05')).toBe(true)
  })

  it('INV-09: passes when afse_r2 absent (vacuously satisfied)', () => {
    const result = checkInvariants(nominal)
    expect(result.violations.some(v => v.invariant_id === 'INV-09')).toBe(false)
  })

  it('INV-09: passes when afse_r2 ≥ 0.98', () => {
    const result = checkInvariants({ ...nominal, afse_r2: 0.9976 })
    expect(result.violations.some(v => v.invariant_id === 'INV-09')).toBe(false)
  })

  it('INV-09: fails when pgcs_passes and afse_r2 < 0.98', () => {
    const result = checkInvariants({ ...nominal, pgcs_passes: true, afse_r2: 0.95 })
    expect(result.violations.some(v => v.invariant_id === 'INV-09')).toBe(true)
    expect(hasT0Violation(result)).toBe(false) // T1_ALERT, not T0
  })

  it('INV-09: passes when afse_r2 < 0.98 but pgcs does not pass', () => {
    const result = checkInvariants({ ...nominal, pgcs_passes: false, afse_r2: 0.5 })
    expect(result.violations.some(v => v.invariant_id === 'INV-09')).toBe(false)
  })

  it('INV-10: passes when tgcs_variance absent (vacuously satisfied)', () => {
    const result = checkInvariants(nominal)
    expect(result.violations.some(v => v.invariant_id === 'INV-10')).toBe(false)
  })

  it('INV-10: passes when tgcs_variance = 0', () => {
    const result = checkInvariants({ ...nominal, tgcs_variance: 0 })
    expect(result.violations.some(v => v.invariant_id === 'INV-10')).toBe(false)
  })

  it('INV-10: fails when tgcs_variance > 0 (thermal instability)', () => {
    const result = checkInvariants({ ...nominal, tgcs_variance: 0.0001 })
    expect(result.violations.some(v => v.invariant_id === 'INV-10')).toBe(true)
    expect(hasT0Violation(result)).toBe(false) // T1_ALERT, not T0
  })

  it('isCycleCoherent requires PASS gate AND no T0 violations', () => {
    const cycle: RalphCycle = {
      cycle_id: generateUUIDv7(),
      cycle_number: 1,
      target_scale: HolonicScale.MOLECULAR,
      phase: RalphPhase.HARMONIZE,
      findings: [],
      analysis_notes: [],
      links_established: [],
      patches_applied: [],
      harmonization_result: 'COHERENT',
      gate_result: 'PASS',
      sequence: BigInt(0) as SequenceNumber,
    }
    const nominalResult = checkInvariants(nominal)
    expect(isCycleCoherent(cycle, nominalResult)).toBe(true)

    const corruptResult = checkInvariants({ ...nominal, corruption_count: 1 })
    expect(isCycleCoherent(cycle, corruptResult)).toBe(false)
  })
})
