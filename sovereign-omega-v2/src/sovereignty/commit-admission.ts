/**
 * Commit admission — mechanically decidable fragment of the AEGIS OMEGA
 * formal reconstruction (sections 7, 9, 10).
 *
 * EPISTEMIC TIER: T2. The predicates are deterministic and testable; the
 * capacity constants and weight curve are policy choices, not derived results.
 *
 * SCOPE. Only the parts a machine can decide from hashes and enumerations are
 * here. The zero-knowledge obligations of section 6 are represented by the
 * PRESENCE of a proof hash, never by its validity — a present hash means an
 * obligation was declared, not discharged. Verifying pi_eq / pi_adapt requires
 * a proving system this module does not have and must not pretend to have.
 *
 * SPEC AMENDMENTS APPLIED (A1, A2, A3, A6 — reviewer-accepted 2026-07-26):
 *
 *   A1  ValidStrategy joins the section 9.2 admission conjunction. The spec as
 *       first written defined it in 10.3 and consulted it nowhere, which was
 *       fail-open: transform `fork_from_archive` with strategy
 *       `reparent_to_active_sibling` satisfied every listed conjunct. This is
 *       now a normative correction, no longer a deviation.
 *   A2  `archive_required` removed from the enforcement action domain
 *       (Option A). There is no synchronous archive-before-admit path, so a
 *       remediation signal E(N) never returns has no reason to exist.
 *   A3  Genesis anchor introduced. See GENESIS_ANCHOR below.
 *   A7  Genesis uniqueness. Section 9.2 gains
 *         Genesis(v) => NOT EXISTS u in dom(H_ledger) : Genesis(u)
 *       so a ledger holds at most one root. Without it a second root was
 *       admissible and the DAG silently became a forest. Section 9.1's state
 *       vector gains `has_genesis`, since the assertion was unstatable before.
 *
 *       STILL NOT ASSERTED, and out of scope here: section 9.2 never requires
 *       p_v to name a vertex the ledger actually holds, so an orphan whose
 *       parent hash is arbitrary remains admissible. Rootedness needs that
 *       assertion too; uniqueness alone does not give it.
 *   A6  ValidProofs renamed to proofReferencesPresent. It decides whether a
 *       proof REFERENCE is present and well formed. Verification of pi_eq /
 *       pi_adapt is an external obligation this module does not discharge:
 *       ValidProofs = ProofReferencesPresent AND ProofVerificationSucceeds,
 *       and only the left conjunct is computed here.
 *
 * A4 (observable trace equivalence) and A5 (hot-graph vs total memory) are
 * spec-only corrections; nothing in this module encodes either claim.
 */

export type TransformPass =
  | 'normal_commit'
  | 'merge_commit'
  | 'rollback_commit'
  | 'rebase_to_active_sibling'
  | 'fork_from_archive'
  | 'verifier_escalation'
  | 'fail_closed'

export type RebaseStrategy =
  | 'reparent_to_active_sibling'
  | 'fork_from_archived_parent'
  | 'preserve_lineage'
  | 'fail_closed'

export type RebaseMode = 'pure_relocation' | 'state_adaptation'

/** Section 7.2. `archive_required` is in the spec's action domain but E(N) never returns it. */
export type EnforceAction = 'accept' | 'score_branches' | 'expand_cgc' | 'fail_closed'

export const HOT_GRAPH_CAPACITY = 1024
const SCORE_THRESHOLD = 108
const EXPAND_THRESHOLD = 512

/** Section 10.1. */
const SHA256_REF = /^sha256:[0-9a-f]{64}$/

export function isSha256Ref(value: string | null): value is string {
  return value !== null && SHA256_REF.test(value)
}

/**
 * A3. The genesis anchor `g`, deliberately OUTSIDE H so that no hash can ever
 * collide with it and no ordinary vertex can claim to be the root. The domain
 * is H_g = H union {g} for parent and for c0/c1; c2 keeps its own bottom.
 *
 * The root of the DAG has no predecessor. Encoding that as a reserved anchor
 * says so; encoding it as a zero-filled digest would have said the root's
 * parent is a commit whose content hashes to zero, which is a different and
 * false claim.
 */
export const GENESIS_ANCHOR = 'genesis:root'

export function isGenesisAnchor(value: string | null): boolean {
  return value === GENESIS_ANCHOR
}

/** A3. Genesis(v) iff p_v = g and C_v = (g, g, bottom) and the pass is a normal commit. */
export function isGenesis(v: CommitVertex): boolean {
  const [c0, c1, c2] = v.causal_tuple
  return (
    isGenesisAnchor(v.parent) &&
    isGenesisAnchor(c0) &&
    isGenesisAnchor(c1) &&
    c2 === null &&
    v.transform === 'normal_commit' &&
    v.rebase_extension === null
  )
}

export interface ProofBundle {
  readonly equivalence_proof_hash: string | null
  readonly adaptation_proof_hash: string | null
  readonly verification_key_hash: string
  readonly circuit_hash: string
}

export interface RebaseExtension {
  readonly strategy: RebaseStrategy
  readonly mode: RebaseMode
  readonly original_intended_parent_hash: string
  readonly selected_parent_hash: string
  readonly decision_record_hash: string
  readonly proofs: ProofBundle
}

/** Section 1.1, with the spec's own recommended correction: H x H x H_bot. */
export type CausalTuple = readonly [string, string, string | null]

export interface CommitVertex {
  readonly id: string
  readonly parent: string | null
  readonly causal_tuple: CausalTuple
  readonly transform: TransformPass
  readonly rebase_extension: RebaseExtension | null
}

export interface LedgerState {
  readonly active_count: number
  readonly breaker_tripped: boolean
  readonly active_snapshot_hash: string
  readonly known_ids: readonly string[]
  /**
   * A7. Whether this ledger already holds a root. Section 9.1's state vector
   * had no way to express it, so section 9.2 could not assert over existing
   * roots even in principle — the uniqueness gap was a missing state field
   * before it was a missing assertion.
   */
  readonly has_genesis: boolean
}

const REBASE_PASSES: readonly TransformPass[] = ['rebase_to_active_sibling', 'fork_from_archive']

export function isRebase(transform: TransformPass): boolean {
  return REBASE_PASSES.includes(transform)
}

/** Section 7.3. */
export function root9Enforce(activeCount: number): EnforceAction {
  if (activeCount < SCORE_THRESHOLD) return 'accept'
  if (activeCount < EXPAND_THRESHOLD) return 'score_branches'
  if (activeCount < HOT_GRAPH_CAPACITY) return 'expand_cgc'
  return 'fail_closed'
}

/** Section 7.4. Discontinuous at both thresholds — 0 -> 0.2 -> 0.6 are step changes. */
export function cgcWeight(activeCount: number): number {
  if (activeCount < SCORE_THRESHOLD) return 0
  if (activeCount < EXPAND_THRESHOLD) return 0.2
  if (activeCount < HOT_GRAPH_CAPACITY) {
    return 0.6 + (0.4 * (activeCount - EXPAND_THRESHOLD)) / (HOT_GRAPH_CAPACITY - EXPAND_THRESHOLD)
  }
  return 1.0
}

/** Section 10.2, as amended by A3: Genesis OR rebase OR degenerate. */
export function validTuple(v: CommitVertex): boolean {
  if (isGenesis(v)) return true

  const [c0, c1, c2] = v.causal_tuple
  // Outside the genesis branch the anchor is not admissible anywhere, so a
  // non-root vertex cannot borrow the root's exemption.
  if (!isSha256Ref(c0) || !isSha256Ref(c1)) return false
  if (v.parent !== c0) return false

  if (isRebase(v.transform)) {
    const x = v.rebase_extension
    if (!x) return false
    return c0 === x.selected_parent_hash && c1 === x.original_intended_parent_hash && c2 === x.decision_record_hash
  }
  return v.rebase_extension === null && c1 === v.parent && c2 === null
}

/** Section 10.3 — defined by the spec, consulted by nothing in section 9.2. */
export function validStrategy(v: CommitVertex): boolean {
  if (!isRebase(v.transform)) return v.rebase_extension === null
  const strategy = v.rebase_extension?.strategy
  if (v.transform === 'rebase_to_active_sibling') return strategy === 'reparent_to_active_sibling'
  return strategy === 'fork_from_archived_parent'
}

/**
 * Section 10.4 as amended by A6. Decides ProofReferencesPresent only.
 * ValidProofs = ProofReferencesPresent AND ProofVerificationSucceeds; the right
 * conjunct is an external obligation and is NOT computed here.
 */
export function proofReferencesPresent(v: CommitVertex): boolean {
  if (!isRebase(v.transform)) return true
  const x = v.rebase_extension
  if (!x) return false
  if (!isSha256Ref(x.proofs.verification_key_hash) || !isSha256Ref(x.proofs.circuit_hash)) return false
  return x.mode === 'pure_relocation'
    ? isSha256Ref(x.proofs.equivalence_proof_hash)
    : isSha256Ref(x.proofs.adaptation_proof_hash)
}

export type AdmissionFailure =
  | 'breaker_tripped'
  | 'capacity_exhausted'
  | 'duplicate_id'
  | 'duplicate_genesis'
  | 'policy_snapshot_mismatch'
  | 'invalid_tuple'
  | 'invalid_strategy'
  | 'missing_proof_references'

/** Section 9.2. Returns every independent reason, not the first. */
export function admissionFailures(
  v: CommitVertex,
  ledger: LedgerState,
  policySnapshotHash: string,
): readonly AdmissionFailure[] {
  const failures: AdmissionFailure[] = []
  if (ledger.breaker_tripped) failures.push('breaker_tripped')
  if (ledger.active_count + 1 > HOT_GRAPH_CAPACITY) failures.push('capacity_exhausted')
  if (ledger.known_ids.includes(v.id)) failures.push('duplicate_id')
  // A7. Asserted only for a candidate root: a ledger admits at most one.
  if (isGenesis(v) && ledger.has_genesis) failures.push('duplicate_genesis')
  if (ledger.active_snapshot_hash !== policySnapshotHash) failures.push('policy_snapshot_mismatch')
  if (!validTuple(v)) failures.push('invalid_tuple')
  if (!validStrategy(v)) failures.push('invalid_strategy')
  if (!proofReferencesPresent(v)) failures.push('missing_proof_references')
  return failures
}

export function isAdmissible(v: CommitVertex, ledger: LedgerState, policySnapshotHash: string): boolean {
  return admissionFailures(v, ledger, policySnapshotHash).length === 0
}
