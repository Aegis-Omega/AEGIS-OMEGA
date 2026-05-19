// ============================================================
// SOVEREIGN OMEGA — Constitutional Governance Surface — Types
// EPISTEMIC TIER: T0 · Gate 13
//
// Defines the verdict lattice, governance decision schema, and
// system health interfaces for the Constitutional Governance Surface.
// ============================================================

import type { SITRState } from '../sitr/types.js'
import type { GlobalState } from '../aoie/types.js'

export const CONSTITUTIONAL_SCHEMA_VERSION = '1.0.0' as const

// ─── Verdict Lattice ───────────────────────────────────────
// ESCALATE > REJECT > DEFER > PERMIT (descending severity)
// A single broken signal elevates the entire verdict.

export type ConstitutionalVerdict = 'PERMIT' | 'DEFER' | 'REJECT' | 'ESCALATE'

// ─── Governance Signal ─────────────────────────────────────

export interface GovernanceSignal {
  readonly sitr_state: SITRState
  readonly aoie_global_state: GlobalState
  readonly invariant_passed: boolean
  readonly has_t0_violation: boolean
  readonly sequence: number
}

// ─── Governance Decision ───────────────────────────────────

export interface GovernanceDecision {
  readonly decision_id: string
  readonly verdict: ConstitutionalVerdict
  readonly sequence: number
  readonly sitr_state: SITRState
  readonly aoie_global_state: GlobalState
  readonly invariant_passed: boolean
  readonly has_t0_violation: boolean
  readonly reason: string
  readonly schema_version: typeof CONSTITUTIONAL_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

// ─── Constitutional Assembly State ─────────────────────────

export interface ConstAssemblyState {
  readonly current_verdict: ConstitutionalVerdict
  readonly decision_count: number
  readonly reject_count: number
  readonly escalation_count: number
  readonly last_sequence: number
  readonly schema_version: typeof CONSTITUTIONAL_SCHEMA_VERSION
}

// ─── System Health Snapshot ────────────────────────────────

export interface SystemHealthSnapshot {
  readonly sitr_state: SITRState
  readonly aoie_global_state: GlobalState
  readonly current_verdict: ConstitutionalVerdict
  readonly convergence_depth: number
  readonly sequence: number
  readonly is_coherent: boolean
}

// ─── Constitutional Telemetry ──────────────────────────────

export interface ConstitutionalTelemetry {
  readonly verdict: ConstitutionalVerdict
  readonly decision_count: number
  readonly reject_count: number
  readonly escalation_count: number
  readonly convergence_depth: number
  readonly governance_throughput: number
  readonly schema_version: typeof CONSTITUTIONAL_SCHEMA_VERSION
}
