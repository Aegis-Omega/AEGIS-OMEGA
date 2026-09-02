/**
 * Authorization Inversion Solver.
 *
 * EPISTEMIC TIER: T2 (engineering hypothesis — mechanism is testable, optimality is not claimed)
 *
 * The Authorization Inversion Problem: an agent is technically authorized to
 * *retrieve* from a secure silo, but nothing constrains whether its later
 * output may safely *mutate*. Access leaks into authority because the two are
 * never separately evaluated.
 *
 *     Access is not authority.
 *     Retrieval is not permission to mutate.
 *     Capability is not proportionality.
 *
 * This module is the guard between Boundary and Mutation in the grammar
 * Field -> Boundary -> Verification -> Mutation -> Trace -> Feedback.
 *
 * Authorized(action) =
 *     ValidSVID(agent)
 *   ∧ InScope(action, mutation_operators)
 *   ∧ K(action) <= K_bound
 *   ∧ ClaimLogged(action)
 *   ∧ VerificationPass
 *
 * All five are necessary. A missing input is a rejection, never a default —
 * the observed failure mode is that absent constraints read as permission.
 *
 * This is a pure decision function: it computes a verdict and never performs
 * the action. Acting and verifying stay separable (constitutional rule 2).
 */

export type InversionVerdict = 'pass' | 'reject' | 'escalate'

export type InversionFailureCode =
  | 'svid_missing'
  | 'svid_expired'
  | 'svid_validity_unparsable'
  | 'svid_subject_mismatch'
  | 'operator_undeclared'
  | 'operator_out_of_scope'
  | 'k_bound_exceeded'
  | 'k_bound_unparsable'
  | 'claim_unlogged'
  | 'claim_action_mismatch'
  | 'verification_absent'
  | 'verification_failed'

/** SPIFFE-style verifiable identity for one agent session. */
export interface AgentSVID {
  readonly spiffe_id: string
  readonly session_id: string
  /** Mutation operators this identity may request. Empty = retrieval only. */
  readonly mutation_operators: readonly string[]
  /** Maximum admissible proposal-space complexity. */
  readonly k_bound: number
  /** RFC3339. Compared against `now` supplied by the caller — never a clock read. */
  readonly not_after: string
}

/** Record of what an agent was authorized to do, and under what constraints. */
export interface AAPClaim {
  readonly claim_id: string
  readonly subject_spiffe_id: string
  readonly action: string
  readonly mutation_operator: string
  readonly k_contribution: number
  /** True only once the AGENT_AUTHORIZED event is durably recorded. */
  readonly logged: boolean
}

/** Independent verifier outcome. Absent is not the same as passing. */
export interface VerificationOutcome {
  readonly verifier_id: string
  readonly passed: boolean
  readonly evidence_ref: string | null
}

export interface InversionRequest {
  readonly svid: AgentSVID | null
  readonly claim: AAPClaim | null
  readonly verification: VerificationOutcome | null
  /** The mutation operator the action would actually invoke. */
  readonly requested_operator: string
  readonly action: string
  /** RFC3339, injected by the caller. No ambient time — replay must be stable. */
  readonly now: string
}

export interface InversionDecision {
  readonly verdict: InversionVerdict
  readonly failures: readonly InversionFailureCode[]
  readonly checks: {
    readonly valid_svid: boolean
    readonly in_scope: boolean
    readonly within_k_bound: boolean
    readonly claim_logged: boolean
    readonly verification_pass: boolean
  }
  readonly reason: string
}

/**
 * Escalate rather than reject when identity, scope, budget and log all hold and
 * the only failure is that an independent verifier has not yet run. That is a
 * missing opinion, not a violated constraint, and it is the one case an
 * operator can resolve. Every other failure is a constraint violation and
 * fails closed.
 */
function classify(
  failures: readonly InversionFailureCode[],
  checks: InversionDecision['checks'],
): InversionVerdict {
  const constraints_hold =
    checks.valid_svid && checks.in_scope && checks.within_k_bound && checks.claim_logged

  if (failures.length === 0 && constraints_hold && checks.verification_pass) return 'pass'
  if (failures.length === 1 && failures[0] === 'verification_absent' && constraints_hold) {
    return 'escalate'
  }
  return 'reject'
}

export function checkAuthorizationInversion(request: InversionRequest): InversionDecision {
  const failures: InversionFailureCode[] = []

  const { svid, claim, verification, requested_operator, action, now } = request

  // 1. Identity
  const not_after_ms = svid ? Date.parse(svid.not_after) : Number.NaN
  const now_ms = Date.parse(now)

  let valid_svid = false
  if (!svid) {
    failures.push('svid_missing')
  } else if (Number.isNaN(not_after_ms) || Number.isNaN(now_ms)) {
    // An unparsable bound is not an absent bound. NaN comparisons are false,
    // so without this branch a malformed timestamp would read as still valid.
    failures.push('svid_validity_unparsable')
  } else if (not_after_ms <= now_ms) {
    failures.push('svid_expired')
  } else if (claim && claim.subject_spiffe_id !== svid.spiffe_id) {
    failures.push('svid_subject_mismatch')
  } else {
    valid_svid = true
  }

  // 2. Scope. An undeclared operator is out of scope by construction: a
  //    retrieval-only identity has an empty operator set.
  let in_scope = false
  if (!requested_operator) {
    failures.push('operator_undeclared')
  } else if (!svid) {
    failures.push('operator_out_of_scope')
  } else if (!svid.mutation_operators.includes(requested_operator)) {
    failures.push('operator_out_of_scope')
  } else if (claim && claim.mutation_operator !== requested_operator) {
    failures.push('operator_out_of_scope')
  } else {
    in_scope = true
  }

  // 3. Complexity budget. With no svid or no claim there is no budget to
  //    compare, so the check cannot pass — but it is not an *exceeded* bound
  //    and must not be reported as one. The missing input is already failing
  //    closed under check 1 or check 4.
  //    A non-finite operand fails the comparison rather than the bound: NaN is
  //    not greater than anything, so an unparsable budget would otherwise be
  //    admitted as within bound. Same fail-open shape as the date check above.
  let within_k_bound = false
  if (svid && claim) {
    if (!Number.isFinite(claim.k_contribution) || !Number.isFinite(svid.k_bound)) {
      failures.push('k_bound_unparsable')
    } else if (claim.k_contribution > svid.k_bound) {
      failures.push('k_bound_exceeded')
    } else {
      within_k_bound = true
    }
  }

  // 4. Claim logged
  let claim_logged = false
  if (!claim) {
    failures.push('claim_unlogged')
  } else if (!claim.logged) {
    failures.push('claim_unlogged')
  } else if (claim.action !== action) {
    failures.push('claim_action_mismatch')
  } else {
    claim_logged = true
  }

  // 5. Independent verification. Absent != passed.
  let verification_pass = false
  if (!verification) {
    failures.push('verification_absent')
  } else if (!verification.passed) {
    failures.push('verification_failed')
  } else {
    verification_pass = true
  }

  const checks = { valid_svid, in_scope, within_k_bound, claim_logged, verification_pass }
  const verdict = classify(failures, checks)

  return {
    verdict,
    failures,
    checks,
    reason:
      verdict === 'pass'
        ? 'identity, scope, k-bound, claim log and verification all satisfied'
        : verdict === 'escalate'
          ? 'constraints satisfied; awaiting independent verification'
          : `denied: ${failures.join(', ')}`,
  }
}
