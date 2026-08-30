// ============================================================
// SOVEREIGN OMEGA — Enforcement Engine Types
// EPISTEMIC TIER: T0 · Gate 14
//
// Schema for enforcement decisions and results produced by
// applyDirectives(). These are E5-appendable audit records —
// the enforcement engine is an event producer, not a state mutator.
// ============================================================

import type { ContainmentAction } from '../sitr/types.js'

export const ENFORCEMENT_SCHEMA_VERSION = '1.0.0' as const

// APPLIED: directive was matched to an active target and executed
// SKIPPED: target not found in active set; directive has no effect
// BLOCKED: directive rejected (future extension — currently unused)
export type EnforcementOutcome = 'APPLIED' | 'SKIPPED' | 'BLOCKED'

export interface EnforcementDecision {
  readonly directive_id: string
  readonly action: ContainmentAction
  readonly outcome: EnforcementOutcome
  readonly target_id: string
  readonly applied_at_sequence: number
  readonly is_replay_reconstructable: true
}

export interface EnforcementResult {
  readonly decisions: readonly EnforcementDecision[]
  readonly directives_applied: number
  readonly directives_skipped: number
  readonly sequence: number
  readonly is_replay_reconstructable: true
  readonly schema_version: typeof ENFORCEMENT_SCHEMA_VERSION
}
