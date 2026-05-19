// ============================================================
// AOIE Identity Continuity — snapshot sequence coherence
// EPISTEMIC TIER: T1
// Pure functions only. No global state.
// ============================================================

import type { RuntimeSnapshot, IdentityContinuityState } from './types.js'
import { computeIdentityDrift } from './hash.js'

const DRIFT_THRESHOLD_BROKEN = 0.3

export function classifyIdentityContinuity(
  snapshots: readonly RuntimeSnapshot[]
): IdentityContinuityState {
  if (snapshots.length <= 1) return 'CONTINUOUS'
  const drift = computeIdentityDrift(snapshots)
  if (drift === 0) return 'CONTINUOUS'
  if (drift <= DRIFT_THRESHOLD_BROKEN) return 'DRIFTED'
  return 'BROKEN'
}
