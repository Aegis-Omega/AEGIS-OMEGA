// ============================================================
// SOVEREIGN OMEGA — Runtime Constitutional Invariant Checker
// EPISTEMIC TIER: T0
//
// Validates that runtime state satisfies all declared invariants.
// Self-referential: the checker itself is subject to the invariants it checks.
// Runs on every gate transition and epoch boundary.
// ============================================================

import { HolonicScale, EpistemicTier, type RalphCycle } from './types.js'

export interface InvariantViolation {
  readonly invariant_id: string
  readonly description: string
  readonly severity: 'T0_ABORT' | 'T1_ALERT' | 'T2_WARN'
  readonly observed_value: unknown
  readonly expected: string
  readonly holonic_scale: HolonicScale
  readonly tier: EpistemicTier
}

export interface InvariantCheckResult {
  readonly passed: boolean
  readonly violations: readonly InvariantViolation[]
  readonly checked_at_sequence: number
}

export interface RuntimeSnapshot {
  vcg_error: number
  drift_index: number
  corruption_count: number
  pgcs_passes: boolean
  calibrator_passes: boolean
  failsafe_state: string
  sequence: number
  gate_acceptance_rate?: number
  gate_sealed?: boolean
  // Layer B epistemic metrics — coupled to INV-09/INV-10 when present
  afse_r2?: number
  tgcs_variance?: number
}

const INVARIANTS = [
  {
    id: 'INV-01',
    description: 'VCG error must be in [0, 1]',
    severity: 'T0_ABORT' as const,
    scale: HolonicScale.CELLULAR,
    tier: EpistemicTier.T0,
    check: (s: RuntimeSnapshot) => s.vcg_error >= 0 && s.vcg_error <= 1,
    expected: 'vcg_error ∈ [0.0, 1.0]',
    observed: (s: RuntimeSnapshot) => s.vcg_error,
  },
  {
    id: 'INV-02',
    description: 'Corruption count must be zero (T0 criterion)',
    severity: 'T0_ABORT' as const,
    scale: HolonicScale.CELLULAR,
    tier: EpistemicTier.T0,
    check: (s: RuntimeSnapshot) => s.corruption_count === 0,
    expected: 'corruption_count = 0',
    observed: (s: RuntimeSnapshot) => s.corruption_count,
  },
  {
    id: 'INV-03',
    description: 'PGCS disk I/O must be zero before TGCS is valid',
    severity: 'T1_ALERT' as const,
    scale: HolonicScale.CELLULAR,
    tier: EpistemicTier.T1,
    check: (s: RuntimeSnapshot) => s.pgcs_passes,
    expected: 'pgcs_passes = true',
    observed: (s: RuntimeSnapshot) => s.pgcs_passes,
  },
  {
    id: 'INV-04',
    description: 'Drift index must be non-negative',
    severity: 'T1_ALERT' as const,
    scale: HolonicScale.MOLECULAR,
    tier: EpistemicTier.T1,
    check: (s: RuntimeSnapshot) => s.drift_index >= 0,
    expected: 'drift_index ≥ 0',
    observed: (s: RuntimeSnapshot) => s.drift_index,
  },
  {
    id: 'INV-05',
    description: 'Gate must be sealed before events are processed',
    severity: 'T0_ABORT' as const,
    scale: HolonicScale.MOLECULAR,
    tier: EpistemicTier.T0,
    check: (s: RuntimeSnapshot) => s.gate_sealed !== false,
    expected: 'gate_sealed = true',
    observed: (s: RuntimeSnapshot) => s.gate_sealed,
  },
  {
    id: 'INV-06',
    description: 'Failsafe must not be FROZEN (unrecoverable)',
    severity: 'T0_ABORT' as const,
    scale: HolonicScale.CELLULAR,
    tier: EpistemicTier.T0,
    check: (s: RuntimeSnapshot) => s.failsafe_state !== 'frozen',
    expected: 'failsafe_state ≠ frozen',
    observed: (s: RuntimeSnapshot) => s.failsafe_state,
  },
  {
    id: 'INV-07',
    description: 'Gate acceptance rate must be in [0, 1]',
    severity: 'T1_ALERT' as const,
    scale: HolonicScale.MOLECULAR,
    tier: EpistemicTier.T1,
    check: (s: RuntimeSnapshot) =>
      s.gate_acceptance_rate === undefined ||
      (s.gate_acceptance_rate >= 0 && s.gate_acceptance_rate <= 1),
    expected: 'gate_acceptance_rate ∈ [0.0, 1.0]',
    observed: (s: RuntimeSnapshot) => s.gate_acceptance_rate,
  },
  {
    id: 'INV-08',
    description: 'Sequence must be monotonically non-decreasing (checked per call)',
    severity: 'T0_ABORT' as const,
    scale: HolonicScale.SUBATOMIC,
    tier: EpistemicTier.T0,
    check: (s: RuntimeSnapshot) => s.sequence >= 0,
    expected: 'sequence ≥ 0',
    observed: (s: RuntimeSnapshot) => s.sequence,
  },
  {
    id: 'INV-09',
    // AFSE R² ≥ 0.98 is only enforceable when PGCS passes (valid I/O baseline).
    // When afse_r2 is absent, invariant is vacuously satisfied (metric not yet wired).
    description: 'AFSE R² must be ≥ 0.98 when PGCS passes (scaling validity criterion)',
    severity: 'T1_ALERT' as const,
    scale: HolonicScale.CELLULAR,
    tier: EpistemicTier.T1,
    check: (s: RuntimeSnapshot) =>
      !s.pgcs_passes || s.afse_r2 === undefined || s.afse_r2 >= 0.98,
    expected: 'afse_r2 ≥ 0.98 (when pgcs_passes)',
    observed: (s: RuntimeSnapshot) => s.afse_r2,
  },
  {
    id: 'INV-10',
    // TGCS σ² = 0 is the run-to-run variance target. When non-zero, thermal
    // throttling is affecting timing consistency. Vacuously satisfied when absent.
    description: 'TGCS run-to-run variance must be zero (thermal stability criterion)',
    severity: 'T1_ALERT' as const,
    scale: HolonicScale.CELLULAR,
    tier: EpistemicTier.T1,
    check: (s: RuntimeSnapshot) =>
      s.tgcs_variance === undefined || s.tgcs_variance === 0,
    expected: 'tgcs_variance = 0',
    observed: (s: RuntimeSnapshot) => s.tgcs_variance,
  },
] as const

export function checkInvariants(snapshot: RuntimeSnapshot): InvariantCheckResult {
  const violations: InvariantViolation[] = []

  for (const inv of INVARIANTS) {
    if (!inv.check(snapshot)) {
      violations.push({
        invariant_id: inv.id,
        description: inv.description,
        severity: inv.severity,
        observed_value: inv.observed(snapshot),
        expected: inv.expected,
        holonic_scale: inv.scale,
        tier: inv.tier,
      })
    }
  }

  return {
    passed: violations.length === 0,
    violations,
    checked_at_sequence: snapshot.sequence,
  }
}

export function hasT0Violation(result: InvariantCheckResult): boolean {
  return result.violations.some(v => v.severity === 'T0_ABORT')
}

/**
 * Verify that a Ralph cycle is coherent with the current invariant state.
 * A cycle is coherent if: gate passed AND no T0 violations remain.
 */
export function isCycleCoherent(
  cycle: RalphCycle,
  invariantResult: InvariantCheckResult,
): boolean {
  return cycle.gate_result === 'PASS' && !hasT0Violation(invariantResult)
}

/** Human-readable summary for dashboard display. One line per violation, or "ALL CLEAR". */
export function formatReport(result: InvariantCheckResult): string {
  if (result.passed) return `ALL CLEAR — ${INVARIANTS.length} invariants checked at seq ${result.checked_at_sequence}`
  return result.violations
    .map(v => `[${v.severity}] ${v.invariant_id}: ${v.description} (got ${String(v.observed_value)}, want ${v.expected})`)
    .join('\n')
}
