// ============================================================
// AOIE Canonicalization — deterministic snapshot serialization
// EPISTEMIC TIER: T1
// Thin wrappers around canonicalizeJCS (RFC 8785).
// No side effects. No state. No async.
// ============================================================

import { canonicalizeJCS } from '../core/canonicalize.js'
import type { RuntimeSnapshot, PolicyMutation, EpistemicAssertion } from './types.js'

export function canonicalizeSnapshot(s: RuntimeSnapshot): Uint8Array {
  return canonicalizeJCS({
    snapshot_id: s.snapshot_id,
    sequence: s.sequence,
    schema_version: s.schema_version,
    phase: s.phase,
    state_hash: s.state_hash,
    panel_sequence_numbers: [...s.panel_sequence_numbers],
  })
}

export function canonicalizePolicyMutation(m: PolicyMutation): Uint8Array {
  return canonicalizeJCS({
    mutation_id: m.mutation_id,
    sequence: m.sequence,
    policy_type: m.policy_type,
    prior_hash: m.prior_hash,
    next_hash: m.next_hash,
  })
}

export function canonicalizeAssertion(a: EpistemicAssertion): Uint8Array {
  return canonicalizeJCS({
    assertion_id: a.assertion_id,
    sequence: a.sequence,
    subject_id: a.subject_id,
    claimed_tier: String(a.claimed_tier),
    evidence_hash: a.evidence_hash,
  })
}
