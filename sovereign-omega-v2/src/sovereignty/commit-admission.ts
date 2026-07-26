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
 * DELIBERATE DEVIATION FROM THE SPEC AS WRITTEN. Section 9.2 lists the
 * admission conjunction as V_hash, ValidTuple, ValidProofs, ValidSignature —
 * it omits ValidStrategy, which section 10.3 defines and nothing then consults.
 * That omission is fail-open: a vertex with transform `fork_from_archive` and
 * strategy `reparent_to_active_sibling` satisfies every listed conjunct. This
 * module CONSULTS ValidStrategy. The deviation is intentional and is pinned by
 * a test, so it is reviewable rather than silent.
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

/** Section 10.2. */
export function validTuple(v: CommitVertex): boolean {
  const [c0, c1, c2] = v.causal_tuple
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

/** Section 10.4. Presence of an obligation, not discharge of it. */
export function validProofs(v: CommitVertex): boolean {
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
  | 'policy_snapshot_mismatch'
  | 'invalid_tuple'
  | 'invalid_strategy'
  | 'invalid_proofs'

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
  if (ledger.active_snapshot_hash !== policySnapshotHash) failures.push('policy_snapshot_mismatch')
  if (!validTuple(v)) failures.push('invalid_tuple')
  if (!validStrategy(v)) failures.push('invalid_strategy')
  if (!validProofs(v)) failures.push('invalid_proofs')
  return failures
}

export function isAdmissible(v: CommitVertex, ledger: LedgerState, policySnapshotHash: string): boolean {
  return admissionFailures(v, ledger, policySnapshotHash).length === 0
}
