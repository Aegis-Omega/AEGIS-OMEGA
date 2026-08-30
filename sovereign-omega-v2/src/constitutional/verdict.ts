// ============================================================
// SOVEREIGN OMEGA — Constitutional Verdict Engine
// EPISTEMIC TIER: T0 · Gate 13
//
// Pure functions. Same inputs always produce the same verdict.
// Verdict lattice: ESCALATE > REJECT > DEFER > PERMIT
// ============================================================

import type { SITRState } from '../sitr/types.js'
import type { GlobalState } from '../aoie/types.js'
import type { InvariantCheckResult } from '../core/invariant-checker.js'
import { hasT0Violation } from '../core/invariant-checker.js'
import type { ConstitutionalVerdict } from './types.js'

// Severity ordering mirrors SITRState escalation lattice
const SITR_ESCALATE: readonly SITRState[] = ['COMPROMISED']
const SITR_REJECT: readonly SITRState[] = ['CONSTITUTIONAL_RISK', 'CONTAINED']
const SITR_DEFER: readonly SITRState[] = ['UNSTABLE', 'DEGRADED']

/**
 * Compute constitutional verdict from the three convergent signals:
 * SITR constitutional state, AOIE global classification, and invariant
 * check result. ESCALATE takes priority over REJECT over DEFER over PERMIT.
 */
export function computeVerdict(
  sitrState: SITRState,
  aoieGlobalState: GlobalState,
  invariantResult: InvariantCheckResult,
): ConstitutionalVerdict {
  const t0 = hasT0Violation(invariantResult)

  if (t0 || SITR_ESCALATE.includes(sitrState) || aoieGlobalState === 'COMPROMISED') {
    return 'ESCALATE'
  }
  if (SITR_REJECT.includes(sitrState)) {
    return 'REJECT'
  }
  if (SITR_DEFER.includes(sitrState) || aoieGlobalState === 'ALERT') {
    return 'DEFER'
  }
  return 'PERMIT'
}

/**
 * Human-readable explanation of the verdict. Deterministic — same inputs,
 * same string. Used in GovernanceDecision.reason and Guardian payloads.
 */
export function verdictReason(
  sitrState: SITRState,
  aoieGlobalState: GlobalState,
  invariantResult: InvariantCheckResult,
): string {
  const t0 = hasT0Violation(invariantResult)
  if (t0) {
    const ids = invariantResult.violations
      .filter(v => v.severity === 'T0_ABORT')
      .map(v => v.invariant_id)
      .join(', ')
    return `T0 violation at seq ${invariantResult.checked_at_sequence}: ${ids}`
  }
  if (sitrState === 'COMPROMISED') return 'SITR reached COMPROMISED terminal state'
  if (aoieGlobalState === 'COMPROMISED') return 'AOIE classified runtime as COMPROMISED'
  if (sitrState === 'CONSTITUTIONAL_RISK') return 'SITR: constitutional risk — non-replay-safe frame detected'
  if (sitrState === 'CONTAINED') return 'SITR: active containment directive in force'
  if (sitrState === 'UNSTABLE') return 'SITR: unstable — workflow invariant failures recorded'
  if (sitrState === 'DEGRADED') return 'SITR: degraded — orchestration pressure or replay integrity low'
  if (aoieGlobalState === 'ALERT') return 'AOIE: structural alert — contested or drifting signals present'
  return `All signals clean — SITR ${sitrState}, AOIE ${aoieGlobalState}, invariants passed`
}
