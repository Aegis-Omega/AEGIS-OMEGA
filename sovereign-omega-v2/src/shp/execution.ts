// ============================================================
// SOVEREIGN OMEGA — SHP Kernel Interface
// EPISTEMIC TIER: T0 · Gate 15
//
// SHPKernel is the abstract execution contract for any holonic
// component at any scale. runFrame() is the ORGANISM-scale
// instantiation. Any Agent, Workflow, or IDE panel is a
// smaller-grain instantiation of the same interface.
//
// Eight invariants of the SHP execution lattice (formal):
//   INV-SHP-01  ASSESS must occur before LOCK
//   INV-SHP-02  LOCK is a single immutable commit point
//   INV-SHP-03  PROPAGATE may only use commitHash + frozen state
//   INV-SHP-04  HARMONIZE is purely observational feedback
//   INV-SHP-05  No phase may be reordered or skipped
//   INV-SHP-06  classification must not exist before LOCK
//   INV-SHP-07  constraintResult must not exist after LOCK
//   INV-SHP-08  commitHash is the only cross-phase identifier
// ============================================================

import type { SHPExecutionIdentity, SHPClassification } from './types.js'
import type { SHA256Hex } from '../core/types.js'

export interface SHPKernel {
  /** R — Deterministic event intake. No inference, no derived memory. */
  read(input: unknown): readonly unknown[]

  /** A — SITR constraint evaluation. Pre-commit. Produces EnforcementPlan. */
  assess(eventSlice: readonly unknown[]): SHPExecutionIdentity['constraintResult']

  /** L — Irreversible state commitment. Causal boundary point. */
  lock(state: unknown): { readonly commitHash: SHA256Hex; readonly frozenState: unknown }

  /** P — AOIE structural observation. Post-commit. Pure function of commitHash. */
  propagate(commitHash: SHA256Hex, state: unknown): void

  /** H — Constitutional verdict. Purely observational feedback into E5. */
  harmonize(commitHash: SHA256Hex, classification: SHPClassification | undefined): void
}

// Formal invariant registry — machine-readable SHP execution rules
export const SHP_EXECUTION_INVARIANTS = Object.freeze([
  { id: 'INV-SHP-01', rule: 'ASSESS must occur before LOCK', phase: 'ASSESS' },
  { id: 'INV-SHP-02', rule: 'LOCK is a single immutable commit point', phase: 'LOCK' },
  { id: 'INV-SHP-03', rule: 'PROPAGATE may only use commitHash + frozen state', phase: 'PROPAGATE' },
  { id: 'INV-SHP-04', rule: 'HARMONIZE is purely observational feedback', phase: 'HARMONIZE' },
  { id: 'INV-SHP-05', rule: 'No phase may be reordered or skipped', phase: null },
  { id: 'INV-SHP-06', rule: 'classification must not exist before LOCK', phase: 'LOCK' },
  { id: 'INV-SHP-07', rule: 'constraintResult must not exist after LOCK', phase: 'LOCK' },
  { id: 'INV-SHP-08', rule: 'commitHash is the only cross-phase identifier', phase: null },
] as const)

export type SHPInvariantId = typeof SHP_EXECUTION_INVARIANTS[number]['id']
