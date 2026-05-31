// ============================================================
// SOVEREIGN OMEGA — Verifier Independence Monitor tests
// EPISTEMIC TIER: T1
//
// Tests for verifier/independence.ts:
//   VerifierIndependenceMonitor — pairwise agreement tracking,
//   Q32.32 weight penalties, snapshot fields, hasAlerts thresholds
// ============================================================

import { describe, it, expect } from 'vitest'
import { VerifierIndependenceMonitor } from '../../src/verifier/independence.js'
import { CalibrationDomain } from '../../src/core/types.js'
import { Q_ONE, fromQ32 } from '../../src/core/fixedpoint.js'
import type { SHA256Hex } from '../../src/core/types.js'
import type { VerifierOutput } from '../../src/verifier/types.js'

const H = '0'.repeat(64) as SHA256Hex

function makeOutput(
  id: string,
  passed: boolean,
  trust: CalibrationDomain = CalibrationDomain.GROUND_TRUTH,
): VerifierOutput {
  return {
    verifier_id: id,
    claim_id: 'c1',
    passed,
    raw_confidence: 1.0,
    evidence_refs: [],
    latency_ms: 10,
    determinism_flag: true,
    verifier_version: '1.0.0',
    trust_class: trust,
    artifact_hash: H,
  }
}

// ── Initial state ─────────────────────────────────────────

describe('VerifierIndependenceMonitor initial state', () => {
  it('getWeight returns Q_ONE for unknown verifier', () => {
    const mon = new VerifierIndependenceMonitor()
    expect(mon.getWeight('unknown')).toBe(Q_ONE)
  })

  it('getSnapshot returns empty array', () => {
    const mon = new VerifierIndependenceMonitor()
    expect(mon.getSnapshot()).toHaveLength(0)
  })

  it('hasAlerts returns false', () => {
    const mon = new VerifierIndependenceMonitor()
    expect(mon.hasAlerts()).toBe(false)
  })
})

// ── update — filtering ────────────────────────────────────

describe('VerifierIndependenceMonitor.update filtering', () => {
  it('ignores ADVISORY_EXCLUDED outputs — no pair records created', () => {
    const mon = new VerifierIndependenceMonitor()
    mon.update([
      makeOutput('ae-a', true, CalibrationDomain.ADVISORY_EXCLUDED),
      makeOutput('ae-b', true, CalibrationDomain.ADVISORY_EXCLUDED),
    ])
    expect(mon.getSnapshot()).toHaveLength(0)
  })

  it('ignores a single calibration-eligible output (no pair to form)', () => {
    const mon = new VerifierIndependenceMonitor()
    mon.update([makeOutput('solo', true)])
    expect(mon.getSnapshot()).toHaveLength(0)
  })
})

// ── update — pairwise tracking ────────────────────────────

describe('VerifierIndependenceMonitor.update pairwise tracking', () => {
  it('creates one pair record after first update with two GT verifiers', () => {
    const mon = new VerifierIndependenceMonitor()
    mon.update([makeOutput('v1', true), makeOutput('v2', true)])
    const snap = mon.getSnapshot()
    expect(snap).toHaveLength(1)
    expect(snap[0]!.samples).toBe(1)
    expect(snap[0]!.agreement_rate).toBe(1.0)
  })

  it('pair key is sorted verifier IDs joined with ::', () => {
    const mon = new VerifierIndependenceMonitor()
    mon.update([makeOutput('z-beta', true), makeOutput('a-alpha', true)])
    const snap = mon.getSnapshot()
    expect(snap[0]!.pair).toBe('a-alpha::z-beta')
  })

  it('agreement_rate accumulates correctly across multiple updates', () => {
    const mon = new VerifierIndependenceMonitor()
    // 3 agree + 2 disagree = 3/5 = 0.6
    for (let i = 0; i < 3; i++) mon.update([makeOutput('p', true), makeOutput('q', true)])
    for (let i = 0; i < 2; i++) mon.update([makeOutput('p', true), makeOutput('q', false)])
    const snap = mon.getSnapshot()
    expect(snap[0]!.samples).toBe(5)
    expect(snap[0]!.agreement_rate).toBeCloseTo(0.6)
  })

  it('agreement_rate is 0.0 when verifiers never agree', () => {
    const mon = new VerifierIndependenceMonitor()
    for (let i = 0; i < 5; i++) {
      mon.update([makeOutput('va', true), makeOutput('vb', false)])
    }
    expect(mon.getSnapshot()[0]!.agreement_rate).toBe(0.0)
  })
})

// ── Weight penalty below threshold ───────────────────────

describe('VerifierIndependenceMonitor weight penalty — below MIN_SAMPLES (20)', () => {
  it('weight stays Q_ONE with 19 agreeing samples (one short of threshold)', () => {
    const mon = new VerifierIndependenceMonitor()
    for (let i = 0; i < 19; i++) {
      mon.update([makeOutput('pen-a', true), makeOutput('pen-b', true)])
    }
    expect(fromQ32(mon.getWeight('pen-a'))).toBe(1.0)
    expect(fromQ32(mon.getWeight('pen-b'))).toBe(1.0)
  })

  it('snapshot penalty field is 1.0 below threshold', () => {
    const mon = new VerifierIndependenceMonitor()
    mon.update([makeOutput('snap-a', true), makeOutput('snap-b', true)])
    expect(mon.getSnapshot()[0]!.penalty).toBe(1.0)
  })
})

// ── Weight penalty at threshold ───────────────────────────

describe('VerifierIndependenceMonitor weight penalty — at MIN_SAMPLES (20)', () => {
  it('weight drops below 1.0 once 20 fully-agreeing samples are recorded', () => {
    const mon = new VerifierIndependenceMonitor()
    for (let i = 0; i < 20; i++) {
      mon.update([makeOutput('w-a', true), makeOutput('w-b', true)])
    }
    expect(fromQ32(mon.getWeight('w-a'))).toBeLessThan(1.0)
    expect(fromQ32(mon.getWeight('w-b'))).toBeLessThan(1.0)
  })

  it('weight does not drop below the floor (0.25) under maximum agreement', () => {
    const mon = new VerifierIndependenceMonitor()
    for (let i = 0; i < 50; i++) {
      mon.update([makeOutput('floor-a', true), makeOutput('floor-b', true)])
    }
    expect(fromQ32(mon.getWeight('floor-a'))).toBeGreaterThanOrEqual(0.25)
  })
})

// ── hasAlerts ─────────────────────────────────────────────

describe('VerifierIndependenceMonitor.hasAlerts', () => {
  it('is true after 20+ samples with agreement_rate > 0.90', () => {
    const mon = new VerifierIndependenceMonitor()
    for (let i = 0; i < 20; i++) {
      mon.update([makeOutput('ha-a', true), makeOutput('ha-b', true)])
    }
    expect(mon.hasAlerts()).toBe(true)
  })

  it('is false with 20+ samples but agreement_rate ≤ 0.90', () => {
    const mon = new VerifierIndependenceMonitor()
    // 9 agree + 11 disagree → 9/20 = 0.45 ≤ 0.90
    for (let i = 0; i < 9; i++) mon.update([makeOutput('low-a', true), makeOutput('low-b', true)])
    for (let i = 0; i < 11; i++) mon.update([makeOutput('low-a', true), makeOutput('low-b', false)])
    expect(mon.getSnapshot()[0]!.agreement_rate).toBeCloseTo(0.45)
    expect(mon.hasAlerts()).toBe(false)
  })

  it('is false with high agreement_rate but fewer than 20 samples', () => {
    const mon = new VerifierIndependenceMonitor()
    for (let i = 0; i < 19; i++) {
      mon.update([makeOutput('few-a', true), makeOutput('few-b', true)])
    }
    expect(mon.hasAlerts()).toBe(false)
  })
})
