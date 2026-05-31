// ============================================================
// SOVEREIGN OMEGA — SHP Invariant Guard
// EPISTEMIC TIER: T0 · Gate 15
//
// Runtime enforcement of the 8 SHP execution invariants.
// checkSHPInvariants() validates the structural constraints of a
// single SHPExecutionIdentity — field presence rules (INV-SHP-06,
// INV-SHP-07) and cross-phase identifier rule (INV-SHP-08).
// validatePhaseTransition() enforces ordering rule (INV-SHP-05).
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import type { Phase, SHPExecutionIdentity } from './types.js'
import { phaseOrdinal, SHP_PHASE_ORDER } from './types.js'
import type { SHPInvariantId } from './execution.js'

export interface SHPInvariantViolation {
  readonly rule: SHPInvariantId
  readonly description: string
  readonly phase: Phase
}

export interface SHPInvariantResult {
  readonly valid: boolean
  readonly violations: readonly SHPInvariantViolation[]
  readonly checked_phase: Phase
}

const PRE_LOCK: readonly Phase[] = Object.freeze(['READ', 'ASSESS'])
const POST_LOCK: readonly Phase[] = Object.freeze(['PROPAGATE', 'HARMONIZE'])

/**
 * Validate structural invariants of a single SHPExecutionIdentity.
 * Checks field-presence constraints derived from temporal separation:
 *   INV-SHP-06  classification must not exist in pre-LOCK phases
 *   INV-SHP-07  constraintResult must not exist in post-LOCK phases
 *   INV-SHP-08  commitHash must be a non-empty string
 * Pure function — same identity always produces the same result.
 */
export function checkSHPInvariants(identity: SHPExecutionIdentity): SHPInvariantResult {
  const violations: SHPInvariantViolation[] = []
  const p = identity.phase

  if (PRE_LOCK.includes(p) && identity.classification !== undefined) {
    violations.push(deepFreeze({
      rule: 'INV-SHP-06' as const,
      description: `Phase ${p}: classification must not exist before LOCK`,
      phase: p,
    }))
  }

  if (POST_LOCK.includes(p) && identity.constraintResult !== undefined) {
    violations.push(deepFreeze({
      rule: 'INV-SHP-07' as const,
      description: `Phase ${p}: constraintResult must not exist after LOCK`,
      phase: p,
    }))
  }

  /* c8 ignore next -- identity.commitHash.length===0 is dead: any truthy string has length>0; empty string is falsy so caught by !identity.commitHash */
  if (!identity.commitHash || identity.commitHash.length === 0) {
    violations.push(deepFreeze({
      rule: 'INV-SHP-08' as const,
      description: 'commitHash must be a non-empty string — it is the only cross-phase identifier',
      phase: p,
    }))
  }

  return deepFreeze<SHPInvariantResult>({
    valid: violations.length === 0,
    violations: Object.freeze(violations),
    checked_phase: p,
  })
}

/**
 * Validate that a phase transition is legal under INV-SHP-05.
 * Returns true if `to` is the immediate successor of `from`
 * in the SHP_PHASE_ORDER; false otherwise.
 */
export function validatePhaseTransition(from: Phase, to: Phase): boolean {
  return phaseOrdinal(to) === phaseOrdinal(from) + 1
}

/**
 * Validate that a sequence of phases forms a valid (possibly partial)
 * SHP execution prefix — no gaps, no repetitions, correct ordering.
 */
export function validatePhaseSequence(phases: readonly Phase[]): boolean {
  if (phases.length === 0) return true
  for (let i = 0; i < phases.length; i++) {
    if (phases[i] !== SHP_PHASE_ORDER[i]) return false
  }
  return true
}
