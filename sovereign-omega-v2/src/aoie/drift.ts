// ============================================================
// AOIE Constitutional Drift — policy mutation rate classifier
// EPISTEMIC TIER: T1
// Pure functions only. No global state.
// ============================================================

import type { RuntimeSnapshot, PolicyMutation, ConstitutionalDriftState } from './types.js'

const DRIFT_THRESHOLD_DRIFTING = 0.1  // > 0.1 mutations per snapshot
const DRIFT_THRESHOLD_DIVERGED = 0.5  // > 0.5 mutations per snapshot

export function classifyConstitutionalDrift(
  snapshots: readonly RuntimeSnapshot[],
  mutations: readonly PolicyMutation[]
): ConstitutionalDriftState {
  if (mutations.length === 0) return 'STABLE'
  const snapshotCount = Math.max(1, snapshots.length)
  const rate = mutations.length / snapshotCount
  if (rate > DRIFT_THRESHOLD_DIVERGED) return 'DIVERGED'
  if (rate > DRIFT_THRESHOLD_DRIFTING) return 'DRIFTING'
  return 'STABLE'
}
