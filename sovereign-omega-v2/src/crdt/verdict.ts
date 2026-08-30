// ============================================================
// SOVEREIGN OMEGA — ConstitutionalVerdict Join Semilattice
// EPISTEMIC TIER: T2 · Gate 20
//
// Verdict total order (most to least restrictive):
//   ESCALATE > REJECT > DEFER > PERMIT
// join(a, b) = max(a, b) — most-restrictive verdict wins.
// Commutative, associative, idempotent, monotonic.
// ============================================================

import type { ConstitutionalVerdict } from '../constitutional/types.js'

export const VERDICT_ORDER: readonly ConstitutionalVerdict[] = Object.freeze([
  'PERMIT',
  'DEFER',
  'REJECT',
  'ESCALATE',
])

export function verdictOrdinal(v: ConstitutionalVerdict): number {
  const idx = VERDICT_ORDER.indexOf(v)
  return idx === -1 ? 0 : idx
}

/**
 * Semilattice join for ConstitutionalVerdict: most-restrictive wins.
 * Commutative, associative, idempotent, monotonic.
 */
export function joinVerdict(a: ConstitutionalVerdict, b: ConstitutionalVerdict): ConstitutionalVerdict {
  return verdictOrdinal(a) >= verdictOrdinal(b) ? a : b
}

/**
 * Fold an array of verdicts to their least upper bound.
 * Returns 'PERMIT' for an empty array (lattice bottom).
 */
export function foldVerdicts(verdicts: readonly ConstitutionalVerdict[]): ConstitutionalVerdict {
  return verdicts.reduce<ConstitutionalVerdict>((acc, v) => joinVerdict(acc, v), 'PERMIT')
}

/** True iff a ≤ b in the verdict restriction order. */
export function verdictLeq(a: ConstitutionalVerdict, b: ConstitutionalVerdict): boolean {
  return verdictOrdinal(a) <= verdictOrdinal(b)
}
