// ============================================================
// AOIE Arbitration — policy mutation + assertion classification
// EPISTEMIC TIER: T1
// Pure functions only. No side effects. No global state.
// ============================================================

import type { PolicyMutation, EpistemicAssertion, ArbitrationState } from './types.js'

const ZERO_HASH_PREFIX = '00000000'

function hasConflictingMutations(mutations: readonly PolicyMutation[]): boolean {
  const seen = new Map<string, number>()
  for (const m of mutations) {
    const prev = seen.get(m.policy_type)
    if (prev !== undefined && prev !== m.sequence) {
      return true
    }
    seen.set(m.policy_type, m.sequence)
  }
  return false
}

function hasUnverifiedAssertions(assertions: readonly EpistemicAssertion[]): boolean {
  return assertions.some(a => a.evidence_hash.startsWith(ZERO_HASH_PREFIX))
}

export function classifyArbitration(
  mutations: readonly PolicyMutation[],
  assertions: readonly EpistemicAssertion[]
): ArbitrationState {
  if (hasConflictingMutations(mutations)) return 'DEADLOCKED'
  if (hasUnverifiedAssertions(assertions)) return 'CONTESTED'
  return 'RESOLVED'
}
