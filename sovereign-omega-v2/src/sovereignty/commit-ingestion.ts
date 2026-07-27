/**
 * Atomic ingestion — section 9.3 of the AEGIS OMEGA formal reconstruction.
 *
 * EPISTEMIC TIER: T2.
 *
 *   Gamma(v, S_ledger, Omega) = S'_ledger  if Admissible(v, S_ledger, Omega)
 *                             = bottom     otherwise
 *
 * This is the seam that makes the other modules compose. `admitCommit` computes
 * V_hash and runs the decision; `applyIngestion` produces the successor ledger
 * state. Deciding and applying stay separate functions, so a denial cannot
 * accidentally advance the ledger.
 *
 * WHY admitCommit EXISTS. `admissionFailures` takes `hashVerified` as a
 * required boolean. That defends against a fail-open default but not against a
 * caller passing `true` without checking. `admitCommit` closes the normal path:
 * it computes the hash itself, so the only way to hand it a lie is to bypass it
 * deliberately.
 *
 * WHAT THIS DOES NOT CLAIM. Section 9.3 also requires strict serializability —
 * that every successful transition appears to occur at a single linearization
 * point. That is a property of the store that persists these states, not of a
 * pure function over an immutable value. Nothing here establishes it, and a
 * caller that applies two transitions concurrently against the same prior state
 * will lose one. The atomicity has to come from the substrate.
 */

import {
  admissionFailures,
  isGenesis,
  type AdmissionFailure,
  type LedgerState,
} from './commit-admission.js'
import { verifySemanticHash, type SemanticVertex } from './semantic-hash.js'

export interface AdmissionDecision {
  readonly admitted: boolean
  readonly failures: readonly AdmissionFailure[]
  /** The hash recomputed from content, not the one the vertex claimed. */
  readonly computed_hash_verified: boolean
}

/** Section 9.2, with V_hash computed rather than asserted by the caller. */
export async function admitCommit(
  v: SemanticVertex,
  ledger: LedgerState,
  policySnapshotHash: string,
): Promise<AdmissionDecision> {
  const hashVerified = await verifySemanticHash(v)
  const failures = admissionFailures(v, ledger, policySnapshotHash, hashVerified)
  return { admitted: failures.length === 0, failures, computed_hash_verified: hashVerified }
}

/**
 * Section 9.3. Returns the successor ledger state, or null for bottom.
 *
 * The prior state is never mutated: a denied ingestion leaves the caller
 * holding exactly the state it started with.
 */
export function applyIngestion(
  v: SemanticVertex,
  ledger: LedgerState,
  decision: AdmissionDecision,
): LedgerState | null {
  if (!decision.admitted) return null

  return Object.freeze({
    active_count: ledger.active_count + 1,
    breaker_tripped: ledger.breaker_tripped,
    active_snapshot_hash: ledger.active_snapshot_hash,
    known_ids: Object.freeze([...ledger.known_ids, v.id]),
    has_genesis: ledger.has_genesis || isGenesis(v),
    known_vertex_hashes: Object.freeze([...ledger.known_vertex_hashes, v.semantic_hash]),
  })
}

/** Decide then apply. Returns the successor state, or null if denied. */
export async function ingest(
  v: SemanticVertex,
  ledger: LedgerState,
  policySnapshotHash: string,
): Promise<{ readonly decision: AdmissionDecision; readonly next: LedgerState | null }> {
  const decision = await admitCommit(v, ledger, policySnapshotHash)
  return { decision, next: applyIngestion(v, ledger, decision) }
}
