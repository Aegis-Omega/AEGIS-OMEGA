// ============================================================
// SOVEREIGN OMEGA — Post-Enforcement Snapshot Factory
// EPISTEMIC TIER: T0 · Gate 14
//
// Bridges phase 4 (enforcement) → phase 5 (AOIE projection).
// Produces a RuntimeSnapshot with phase='post_enforcement',
// which is the ONLY valid input for classifyRuntime().
// The state_hash is computed deterministically via FNV-1a over
// a canonical state descriptor (sitr_state + directives + seq).
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { AOIE_SCHEMA_VERSION } from '../aoie/types.js'
import type { RuntimeSnapshot } from '../aoie/types.js'
import type { SITRState } from '../sitr/types.js'
import type { EnforcementResult } from '../enforcement/types.js'

function fnv1a32(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619) >>> 0
  }
  return h >>> 0
}

/**
 * Capture the post-enforcement system state as an AOIE-compatible snapshot.
 * The state_hash encodes: sitr_state, directives applied, and frame sequence.
 * Deterministic: same parameters always produce the same snapshot.
 */
export function capturePostEnforcementSnapshot(params: {
  readonly enforcement_result: EnforcementResult
  readonly sitr_state: SITRState
  readonly panel_sequence_numbers: readonly number[]
  readonly sequence: number
}): RuntimeSnapshot {
  const stateKey = [
    params.sitr_state,
    params.enforcement_result.directives_applied,
    params.sequence,
  ].join(':')

  const hashNum = fnv1a32(stateKey)
  const stateHash = hashNum.toString(16).padStart(64, '0') as SHA256Hex

  return Object.freeze<RuntimeSnapshot>({
    snapshot_id: `snap-${params.sequence}`,
    sequence: params.sequence,
    schema_version: AOIE_SCHEMA_VERSION,
    phase: 'post_enforcement',
    state_hash: stateHash,
    panel_sequence_numbers: Object.freeze([...params.panel_sequence_numbers]),
  })
}
