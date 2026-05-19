// ============================================================
// AOIE Runtime — pure structural classification oracle
// EPISTEMIC TIER: T1
// No class. No state. Stateless pure function only.
// Accepts ONLY post_enforcement snapshots (phase guard enforced).
// AOIE never influences SITR, agents, or workflows.
// ============================================================

import { AOIE_SCHEMA_VERSION } from './types.js'
import type { RuntimeSnapshot, PolicyMutation, EpistemicAssertion, AOIEClassification } from './types.js'
import { SITRConstraintError } from '../sitr/types.js'
import { classifyArbitration } from './arbitration.js'
import { classifyIdentityContinuity } from './identity.js'
import { classifyConstitutionalDrift } from './drift.js'
import { classifyGlobalState } from './lattice.js'
import { freezeClassification } from './freeze.js'

export function classifyRuntime(params: {
  snapshots: readonly RuntimeSnapshot[]
  mutations: readonly PolicyMutation[]
  assertions: readonly EpistemicAssertion[]
  sequence: number
}): AOIEClassification {
  // Phase guard: AOIE only accepts post_enforcement snapshots.
  for (const s of params.snapshots) {
    if (s.phase !== 'post_enforcement') {
      throw new SITRConstraintError(
        `AOIE phase guard: snapshot ${s.snapshot_id} has phase '${s.phase}', expected 'post_enforcement'`
      )
    }
  }

  const arbitration = classifyArbitration(params.mutations, params.assertions)
  const identity = classifyIdentityContinuity(params.snapshots)
  const drift = classifyConstitutionalDrift(params.snapshots, params.mutations)
  const global_state = classifyGlobalState(arbitration, identity, drift)

  return freezeClassification({
    global_state,
    arbitration,
    identity_continuity: identity,
    constitutional_drift: drift,
    classified_at_sequence: params.sequence,
    is_replay_reconstructable: true,
    schema_version: AOIE_SCHEMA_VERSION,
  })
}
