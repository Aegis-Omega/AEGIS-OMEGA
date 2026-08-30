// ============================================================
// SOVEREIGN OMEGA — SHP Execution Identity Types
// EPISTEMIC TIER: T0 · Gate 15
//
// Subatomic Holon Particle (SHP): the irreducible deterministic
// execution unit of the AEGIS system. Every component at every
// holonic scale is an instantiation of this identity.
//
// Phase ordering invariant: READ → ASSESS → LOCK → PROPAGATE → HARMONIZE
// Commitment boundary invariant: classification ∉ pre-LOCK phases
//                                constraintResult ∉ post-LOCK phases
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'

export type Phase =
  | 'READ'
  | 'ASSESS'
  | 'LOCK'
  | 'PROPAGATE'
  | 'HARMONIZE'

// Strict phase ordering — the temporal law of SHP execution.
// No phase may be reordered or skipped.
export const SHP_PHASE_ORDER: readonly Phase[] = Object.freeze([
  'READ',
  'ASSESS',
  'LOCK',
  'PROPAGATE',
  'HARMONIZE',
])

export function phaseOrdinal(p: Phase): number {
  const i = SHP_PHASE_ORDER.indexOf(p)
  if (i === -1) throw new RangeError(`Unknown phase: ${p}`)
  return i
}

// ─── Constraint Result (ASSESS phase output) ───────────────
// SITR pre-commit evaluation. Must not exist after LOCK.

export interface SHPConstraintResult {
  readonly violated: boolean
  readonly severity: 'NONE' | 'DEGRADED' | 'UNSTABLE' | 'COMPROMISED'
}

// ─── Classification (PROPAGATE/HARMONIZE phase input) ──────
// AOIE post-commit observation. Must not exist before LOCK.

export interface SHPClassification {
  readonly arbitration: 'RESOLVED' | 'CONTESTED' | 'DEADLOCKED'
  readonly identity: 'CONTINUOUS' | 'DRIFTED' | 'BROKEN'
  readonly drift: 'STABLE' | 'DRIFTING' | 'DIVERGED'
}

// ─── SHP Execution Identity ────────────────────────────────

export interface SHPExecutionIdentity {
  readonly holonId: string
  readonly phase: Phase
  // Immutable snapshot of local state at phase boundary
  readonly state: unknown
  // Causal input slice (E5-aligned; replay-only, no inference)
  readonly eventSlice: readonly unknown[]
  // SITR constraint evaluation result (pre-commit only)
  readonly constraintResult?: SHPConstraintResult
  // AOIE classification result (post-commit only)
  readonly classification?: SHPClassification
  // Enforcement boundary hash — the only cross-phase identifier
  readonly commitHash: SHA256Hex
  // Deterministic lineage pointer (replay anchor)
  readonly parentCommitHash: SHA256Hex | null
  // E5 sequence alignment
  readonly sequence: SequenceNumber
  // Invariant: always true — SHP executions are replay-safe by construction
  readonly isReplaySafe: true
}
