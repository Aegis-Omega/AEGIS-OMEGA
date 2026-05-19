// ============================================================
// SOVEREIGN OMEGA — Policy Amendment Types
// EPISTEMIC TIER: T0 · Gate 21
//
// Models bounded policy amendments that flow through E5 as
// constitutional events. Amendments never modify constitutional
// primitives directly — all changes are E5 events consumed by
// the enforcement engine (Phase 4 of runFrame).
// ============================================================

import { CONSTITUTIONAL_SCHEMA_VERSION } from './types.js'

// ─── Amendment Lifecycle ───────────────────────────────────

export type AmendmentStatus =
  | 'PROPOSED'
  | 'UNDER_REVIEW'
  | 'APPROVED'
  | 'REJECTED'
  | 'APPLIED'

// ─── Core Type ─────────────────────────────────────────────

export interface PolicyAmendment {
  readonly amendment_id: string
  readonly proposed_at_sequence: number
  readonly target: string
  readonly description: string
  /** Machine-parseable constraint delta (e.g. "allow X when Y"). */
  readonly constraint_delta: string
  readonly status: AmendmentStatus
  readonly guardian_verdict?: 'APPROVED' | 'VETOED'
  readonly applied_at_sequence?: number
  readonly is_replay_reconstructable: true
  readonly schema_version: typeof CONSTITUTIONAL_SCHEMA_VERSION
}

// ─── Error ─────────────────────────────────────────────────

export class PolicyAmendmentError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'PolicyAmendmentError'
  }
}
