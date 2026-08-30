// ============================================================
// AOIE — Arbitration & Ontological Identity Engine Types
// EPISTEMIC TIER: T1
// HOLONIC SCALE: FIELD (observation layer above SITR)
// Pure classification oracle. No mutations. No side effects.
// classifyRuntime accepts ONLY post_enforcement snapshots.
// ============================================================

import type { SHA256Hex, EpistemicTier } from '../core/types.js'

export const AOIE_SCHEMA_VERSION = '1.0.0' as const

export type GlobalState = 'SECURE' | 'ALERT' | 'COMPROMISED'
export type ArbitrationState = 'RESOLVED' | 'CONTESTED' | 'DEADLOCKED'
export type IdentityContinuityState = 'CONTINUOUS' | 'DRIFTED' | 'BROKEN'
export type ConstitutionalDriftState = 'STABLE' | 'DRIFTING' | 'DIVERGED'

// Phase in the 7-step deterministic frame execution contract.
// AOIE classifyRuntime rejects all phases except 'post_enforcement'.
export type SnapshotPhase = 'pre_commit' | 'post_commit' | 'post_enforcement'

export interface RuntimeSnapshot {
  readonly snapshot_id: string
  readonly sequence: number
  readonly schema_version: typeof AOIE_SCHEMA_VERSION
  readonly phase: SnapshotPhase
  readonly state_hash: SHA256Hex
  readonly panel_sequence_numbers: readonly number[]
}

export interface PolicyMutation {
  readonly mutation_id: string
  readonly sequence: number
  readonly policy_type: string
  readonly prior_hash: SHA256Hex
  readonly next_hash: SHA256Hex
}

export interface EpistemicAssertion {
  readonly assertion_id: string
  readonly sequence: number
  readonly subject_id: string
  readonly claimed_tier: EpistemicTier
  readonly evidence_hash: SHA256Hex
}

export interface AOIEClassification {
  readonly global_state: GlobalState
  readonly arbitration: ArbitrationState
  readonly identity_continuity: IdentityContinuityState
  readonly constitutional_drift: ConstitutionalDriftState
  readonly classified_at_sequence: number
  readonly is_replay_reconstructable: true
  readonly schema_version: typeof AOIE_SCHEMA_VERSION
}
