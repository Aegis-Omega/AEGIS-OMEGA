// ============================================================
// SOVEREIGN OMEGA — SITRState Join Semilattice
// EPISTEMIC TIER: T2 · Gate 20
//
// SITRState is a total order: STABLE < DEGRADED < UNSTABLE <
// CONSTITUTIONAL_RISK < CONTAINED < COMPROMISED.
// join(a, b) = max(a, b) — monotonic escalation wins.
// This reuses the existing lattice.ts ordinal, ensuring the
// CRDT join is consistent with the SITR runtime's escalate().
// ============================================================

import { stateOrdinal } from '../sitr/lattice.js'
import type { SITRState } from '../sitr/types.js'

/**
 * Semilattice join for SITRState: returns the more-escalated state.
 * Commutative, associative, idempotent, monotonic.
 */
export function joinSITRState(a: SITRState, b: SITRState): SITRState {
  return stateOrdinal(a) >= stateOrdinal(b) ? a : b
}

/**
 * Fold an array of SITRState values to their least upper bound.
 * Returns 'STABLE' for an empty array (the lattice bottom element).
 */
export function foldSITRStates(states: readonly SITRState[]): SITRState {
  return states.reduce<SITRState>((acc, s) => joinSITRState(acc, s), 'STABLE')
}

/** True iff a ≤ b in the escalation order. */
export function sitrLeq(a: SITRState, b: SITRState): boolean {
  return stateOrdinal(a) <= stateOrdinal(b)
}
