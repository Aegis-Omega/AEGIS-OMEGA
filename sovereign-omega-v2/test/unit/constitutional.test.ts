// ============================================================
// Gate 13 — Constitutional Governance Surface Tests
// ~20 tests: verdict lattice, guardian payloads, assembly,
//   convergence, runtime composition, determinism
// ============================================================

import { describe, it, expect } from 'vitest'
import { HolonicScale, EpistemicTier } from '../../src/core/types'
import type { InvariantCheckResult, InvariantViolation } from '../../src/core/invariant-checker'
import type { RuntimeSnapshot as InvariantRuntimeSnapshot } from '../../src/core/invariant-checker'
import type { AOIEClassification } from '../../src/aoie/types'
import { AOIE_SCHEMA_VERSION } from '../../src/aoie/types.js'
import { SITRRuntime } from '../../src/sitr/runtime.js'
import { computeVerdict, verdictReason } from '../../src/constitutional/verdict.js'
import {
  buildGuardianInvokedPayload,
  buildGuardianVerdictPayload,
  verdictToGuardianOutcome,
} from '../../src/constitutional/guardian.js'
import { ConstitutionalAssembly } from '../../src/constitutional/assembly.js'
import { ConvergenceSurface } from '../../src/constitutional/convergence.js'
import { ConstitutionalRuntime } from '../../src/constitutional/runtime.js'
import type { UUIDv7 } from '../../src/core/types'

// ─── Test helpers ──────────────────────────────────────────

const CLEAN_INVARIANT_RESULT: InvariantCheckResult = Object.freeze({
  passed: true,
  violations: Object.freeze([]),
  checked_at_sequence: 1,
})

function makeT0Violation(): InvariantViolation {
  return Object.freeze({
    invariant_id: 'INV-02',
    description: 'Corruption count must be zero',
    severity: 'T0_ABORT' as const,
    observed_value: 1,
    expected: 'corruption_count = 0',
    holonic_scale: HolonicScale.CELLULAR,
    tier: EpistemicTier.T0,
  })
}


const T0_INVARIANT_RESULT: InvariantCheckResult = Object.freeze({
  passed: false,
  violations: Object.freeze([makeT0Violation()]),
  checked_at_sequence: 1,
})

const CLEAN_INVARIANT_SNAPSHOT: InvariantRuntimeSnapshot = {
  vcg_error: 0,
  drift_index: 0,
  corruption_count: 0,
  pgcs_passes: true,
  calibrator_passes: true,
  failsafe_state: 'healthy',
  sequence: 1,
  gate_sealed: true,
}

const T0_INVARIANT_SNAPSHOT: InvariantRuntimeSnapshot = {
  ...CLEAN_INVARIANT_SNAPSHOT,
  corruption_count: 1,
}

function makeAoie(overrides: Partial<AOIEClassification> = {}): AOIEClassification {
  return Object.freeze({
    global_state: 'SECURE' as const,
    arbitration: 'RESOLVED' as const,
    identity_continuity: 'CONTINUOUS' as const,
    constitutional_drift: 'STABLE' as const,
    classified_at_sequence: 1,
    is_replay_reconstructable: true as const,
    schema_version: AOIE_SCHEMA_VERSION,
    ...overrides,
  })
}

const MOCK_UUID = 'a'.repeat(36) as UUIDv7

// ─── Verdict ───────────────────────────────────────────────

describe('computeVerdict', () => {
  it('PERMIT for STABLE + SECURE + clean invariants', () => {
    expect(computeVerdict('STABLE', 'SECURE', CLEAN_INVARIANT_RESULT)).toBe('PERMIT')
  })

  it('DEFER for SITR=DEGRADED', () => {
    expect(computeVerdict('DEGRADED', 'SECURE', CLEAN_INVARIANT_RESULT)).toBe('DEFER')
  })

  it('DEFER for SITR=UNSTABLE', () => {
    expect(computeVerdict('UNSTABLE', 'SECURE', CLEAN_INVARIANT_RESULT)).toBe('DEFER')
  })

  it('DEFER for AOIE=ALERT', () => {
    expect(computeVerdict('STABLE', 'ALERT', CLEAN_INVARIANT_RESULT)).toBe('DEFER')
  })

  it('REJECT for SITR=CONSTITUTIONAL_RISK', () => {
    expect(computeVerdict('CONSTITUTIONAL_RISK', 'SECURE', CLEAN_INVARIANT_RESULT)).toBe('REJECT')
  })

  it('REJECT for SITR=CONTAINED', () => {
    expect(computeVerdict('CONTAINED', 'SECURE', CLEAN_INVARIANT_RESULT)).toBe('REJECT')
  })

  it('ESCALATE for T0 violation (overrides all)', () => {
    expect(computeVerdict('STABLE', 'SECURE', T0_INVARIANT_RESULT)).toBe('ESCALATE')
  })

  it('ESCALATE for SITR=COMPROMISED', () => {
    expect(computeVerdict('COMPROMISED', 'SECURE', CLEAN_INVARIANT_RESULT)).toBe('ESCALATE')
  })

  it('ESCALATE for AOIE=COMPROMISED', () => {
    expect(computeVerdict('STABLE', 'COMPROMISED', CLEAN_INVARIANT_RESULT)).toBe('ESCALATE')
  })

  it('T0 violation escalates even when SITR and AOIE are clean', () => {
    expect(computeVerdict('STABLE', 'SECURE', T0_INVARIANT_RESULT)).toBe('ESCALATE')
  })

  it('verdictReason returns non-empty string for all branches', () => {
    const cases: Parameters<typeof verdictReason>[] = [
      ['STABLE', 'SECURE', CLEAN_INVARIANT_RESULT],
      ['STABLE', 'SECURE', T0_INVARIANT_RESULT],
      ['COMPROMISED', 'SECURE', CLEAN_INVARIANT_RESULT],
      ['STABLE', 'COMPROMISED', CLEAN_INVARIANT_RESULT],
      ['CONSTITUTIONAL_RISK', 'SECURE', CLEAN_INVARIANT_RESULT],
      ['CONTAINED', 'SECURE', CLEAN_INVARIANT_RESULT],
      ['UNSTABLE', 'SECURE', CLEAN_INVARIANT_RESULT],
      ['DEGRADED', 'SECURE', CLEAN_INVARIANT_RESULT],
      ['STABLE', 'ALERT', CLEAN_INVARIANT_RESULT],
    ]
    for (const args of cases) {
      const r = verdictReason(...args)
      expect(typeof r).toBe('string')
      expect(r.length).toBeGreaterThan(0)
    }
  })
})

// ─── Guardian ──────────────────────────────────────────────

describe('guardian payloads', () => {
  it('verdictToGuardianOutcome: PERMIT → APPROVED', () => {
    expect(verdictToGuardianOutcome('PERMIT')).toBe('APPROVED')
  })

  it('verdictToGuardianOutcome: DEFER → APPROVED', () => {
    expect(verdictToGuardianOutcome('DEFER')).toBe('APPROVED')
  })

  it('verdictToGuardianOutcome: REJECT → VETOED', () => {
    expect(verdictToGuardianOutcome('REJECT')).toBe('VETOED')
  })

  it('verdictToGuardianOutcome: ESCALATE → VETOED', () => {
    expect(verdictToGuardianOutcome('ESCALATE')).toBe('VETOED')
  })

  it('buildGuardianInvokedPayload returns frozen object with correct fields', () => {
    const p = buildGuardianInvokedPayload({
      invoked_by: 'constitutional-runtime',
      check_reason: 'gate transition check',
      files_under_review: ['src/sitr/runtime.ts'],
    })
    expect(Object.isFrozen(p)).toBe(true)
    expect(p.invoked_by).toBe('constitutional-runtime')
    expect(p.files_under_review).toContain('src/sitr/runtime.ts')
  })

  it('buildGuardianVerdictPayload: PERMIT → APPROVED, check_performed set', () => {
    const p = buildGuardianVerdictPayload({
      verdict: 'PERMIT',
      location: 'src/constitutional/runtime.ts',
      reason: 'clean signals',
      invocation_event_id: MOCK_UUID,
    })
    expect(p.verdict).toBe('APPROVED')
    expect(p.check_performed).toBe('GATE_PROTOCOL_CHECK')
    expect(Object.isFrozen(p)).toBe(true)
  })

  it('buildGuardianVerdictPayload: ESCALATE → VETOED', () => {
    const p = buildGuardianVerdictPayload({
      verdict: 'ESCALATE',
      location: 'src/constitutional/runtime.ts',
      reason: 'T0 violation',
      invocation_event_id: MOCK_UUID,
    })
    expect(p.verdict).toBe('VETOED')
  })
})

// ─── ConstitutionalAssembly ────────────────────────────────

describe('ConstitutionalAssembly', () => {
  it('starts with PERMIT (no decisions)', () => {
    expect(ConstitutionalAssembly.empty().currentVerdict()).toBe('PERMIT')
  })

  it('observe returns new instance; source unchanged', () => {
    const a0 = ConstitutionalAssembly.empty()
    const a1 = a0.observe({
      sitr_state: 'STABLE',
      aoie_global_state: 'SECURE',
      invariant_result: CLEAN_INVARIANT_RESULT,
      sequence: 1,
      decision_id: 'd-001',
    })
    expect(a0.decisions()).toHaveLength(0)
    expect(a1.decisions()).toHaveLength(1)
  })

  it('verdict updates when signals degrade', () => {
    const a1 = ConstitutionalAssembly.empty().observe({
      sitr_state: 'CONSTITUTIONAL_RISK',
      aoie_global_state: 'SECURE',
      invariant_result: CLEAN_INVARIANT_RESULT,
      sequence: 1,
      decision_id: 'd-001',
    })
    expect(a1.currentVerdict()).toBe('REJECT')
  })

  it('reject_count and escalation_count increment correctly', () => {
    const a = ConstitutionalAssembly.empty()
      .observe({ sitr_state: 'CONSTITUTIONAL_RISK', aoie_global_state: 'SECURE', invariant_result: CLEAN_INVARIANT_RESULT, sequence: 1, decision_id: 'r1' })
      .observe({ sitr_state: 'STABLE', aoie_global_state: 'COMPROMISED', invariant_result: CLEAN_INVARIANT_RESULT, sequence: 2, decision_id: 'e1' })
    const s = a.getState()
    expect(s.reject_count).toBe(1)
    expect(s.escalation_count).toBe(1)
    expect(s.decision_count).toBe(2)
  })

  it('getState() returns frozen object', () => {
    const s = ConstitutionalAssembly.empty().getState()
    expect(Object.isFrozen(s)).toBe(true)
  })
})

// ─── ConvergenceSurface ────────────────────────────────────

describe('ConvergenceSurface', () => {
  it('convergenceDepth=0 before any cycles', () => {
    expect(ConvergenceSurface.create(1.0).convergenceDepth()).toBe(0)
  })

  it('convergenceDepth increases with PASS cycles', () => {
    const cs = ConvergenceSurface.create(1.0)
    cs.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: CLEAN_INVARIANT_RESULT, sequence: 1, gate_result: 'PASS' })
    cs.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: CLEAN_INVARIANT_RESULT, sequence: 2, gate_result: 'PASS' })
    expect(cs.convergenceDepth()).toBe(2)
  })

  it('convergenceDepth resets on FAIL', () => {
    const cs = ConvergenceSurface.create(1.0)
    cs.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: CLEAN_INVARIANT_RESULT, sequence: 1, gate_result: 'PASS' })
    cs.recordCycle({ sitr_state: 'DEGRADED', aoie_global_state: 'SECURE', invariant_result: CLEAN_INVARIANT_RESULT, sequence: 2, gate_result: 'FAIL' })
    expect(cs.convergenceDepth()).toBe(0)
  })

  it('systemHealth is_coherent for clean signals', () => {
    const cs = ConvergenceSurface.create(1.0)
    cs.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: CLEAN_INVARIANT_RESULT, sequence: 1, gate_result: 'PASS' })
    const h = cs.systemHealth(1)
    expect(h.is_coherent).toBe(true)
    expect(h.current_verdict).toBe('PERMIT')
    expect(Object.isFrozen(h)).toBe(true)
  })

  it('systemHealth is_coherent=false when T0 violation present', () => {
    const cs = ConvergenceSurface.create(1.0)
    cs.recordCycle({ sitr_state: 'STABLE', aoie_global_state: 'SECURE', invariant_result: T0_INVARIANT_RESULT, sequence: 1, gate_result: 'FAIL' })
    expect(cs.systemHealth(1).is_coherent).toBe(false)
  })

  it('throughput returns 0 when sequenceSpan=0', () => {
    expect(ConvergenceSurface.create(1.0).throughput(0)).toBe(0)
  })
})

// ─── ConstitutionalRuntime ─────────────────────────────────

describe('ConstitutionalRuntime', () => {
  it('empty() starts with PERMIT', () => {
    expect(ConstitutionalRuntime.empty().currentVerdict()).toBe('PERMIT')
  })

  it('evaluate() with clean signals → PERMIT', () => {
    const r = ConstitutionalRuntime.empty().evaluate({
      sitr: SITRRuntime.empty(),
      aoie: makeAoie(),
      invariantSnapshot: CLEAN_INVARIANT_SNAPSHOT,
      sequence: 1,
      decision_id: 'd-001',
    })
    expect(r.currentVerdict()).toBe('PERMIT')
  })

  it('evaluate() with T0 violation snapshot → ESCALATE', () => {
    const r = ConstitutionalRuntime.empty().evaluate({
      sitr: SITRRuntime.empty(),
      aoie: makeAoie(),
      invariantSnapshot: T0_INVARIANT_SNAPSHOT,
      sequence: 1,
      decision_id: 'd-001',
    })
    expect(r.currentVerdict()).toBe('ESCALATE')
  })

  it('evaluate() is functional — source unchanged', () => {
    const r0 = ConstitutionalRuntime.empty()
    const r1 = r0.evaluate({
      sitr: SITRRuntime.empty(),
      aoie: makeAoie(),
      invariantSnapshot: CLEAN_INVARIANT_SNAPSHOT,
      sequence: 1,
      decision_id: 'd-001',
    })
    expect(r0.decisions()).toHaveLength(0)
    expect(r1.decisions()).toHaveLength(1)
  })

  it('guardianInvokedPayload returns correct shape', () => {
    const r = ConstitutionalRuntime.empty().evaluate({
      sitr: SITRRuntime.empty(),
      aoie: makeAoie(),
      invariantSnapshot: CLEAN_INVARIANT_SNAPSHOT,
      sequence: 1,
      decision_id: 'd-001',
    })
    const p = r.guardianInvokedPayload({
      invoked_by: 'operator',
      files_under_review: ['src/constitutional/runtime.ts'],
    })
    expect(p.invoked_by).toBe('operator')
    expect(typeof p.check_reason).toBe('string')
  })

  it('guardianVerdictPayload: PERMIT verdict → APPROVED', () => {
    const r = ConstitutionalRuntime.empty().evaluate({
      sitr: SITRRuntime.empty(),
      aoie: makeAoie(),
      invariantSnapshot: CLEAN_INVARIANT_SNAPSHOT,
      sequence: 1,
      decision_id: 'd-001',
    })
    const p = r.guardianVerdictPayload({
      location: 'src/constitutional',
      invocation_event_id: MOCK_UUID,
    })
    expect(p.verdict).toBe('APPROVED')
  })

  it('telemetry returns all expected fields', () => {
    const r = ConstitutionalRuntime.empty().evaluate({
      sitr: SITRRuntime.empty(),
      aoie: makeAoie(),
      invariantSnapshot: CLEAN_INVARIANT_SNAPSHOT,
      sequence: 1,
      decision_id: 'd-001',
    })
    const t = r.telemetry(10)
    expect(t.verdict).toBe('PERMIT')
    expect(t.decision_count).toBe(1)
    expect(typeof t.governance_throughput).toBe('number')
    expect(typeof t.convergence_depth).toBe('number')
  })
})
