// ============================================================
// SOVEREIGN OMEGA — Constitutional Capsule VM Types
// EPISTEMIC TIER: T0 (type grammar) / T2 (execution semantics)
// Gate 32
//
// A Capsule is the only admissible extensibility boundary.
// Every capsule execution is replay-certifiable:
//   manifest → capability check → entropy evaluation
//   → event commit → lineage attestation
//
// Constitutional requirements (invariants):
//   - is_rollback_safe: true is mandatory in every manifest
//   - entropy_budget: max canonical payload bytes; 0 = read-only
//   - capsule_id: hashValue(manifest without capsule_id) — deterministic
//   - No hidden mutable state; all outputs are pure function values
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'

export const CAPSULE_SCHEMA_VERSION = '1.0.0' as const

// ─── Capability grammar ────────────────────────────────────

/**
 * Admissible capability types. These are the only operations a
 * capsule may declare. Any unlisted operation is constitutionally
 * forbidden regardless of runtime context.
 */
export type CapsuleCapabilityType =
  | 'READ_STATE'       // observe topology/ledger state (read-only)
  | 'EMIT_EVENT'       // append one event to the E5 substrate
  | 'QUERY_TOPOLOGY'   // query GovernanceTopology fields
  | 'OBSERVE_LINEAGE'  // read lineage entries (read-only)

export interface CapsuleCapability {
  readonly type: CapsuleCapabilityType
  readonly target: string          // subsystem or resource identifier
  readonly is_read_only: boolean   // EMIT_EVENT sets this to false
}

// ─── Manifest ──────────────────────────────────────────────

/**
 * The canonical, frozen declaration of a capsule's constitutional contract.
 * capsule_id is hashValue(all fields except capsule_id) — content-addressed.
 */
export interface CapsuleManifest {
  readonly capsule_id: string
  readonly capabilities: readonly CapsuleCapability[]
  /** Max allowed entropy units (canonical payload bytes). 0 = read-only. */
  readonly entropy_budget: number
  readonly is_rollback_safe: true   // constitutional requirement — must always be true
  readonly schema_version: typeof CAPSULE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

// ─── Execution result ──────────────────────────────────────

export type CapsuleOutcome = 'COMMITTED' | 'REJECTED' | 'ROLLED_BACK'

/**
 * Immutable result of one capsule execution.
 * event_hash = hashValue({capsule_id, payload, sequence})
 * attestation_hash chains from parent_lineage_hash — lineage-linked.
 */
export interface CapsuleResult {
  readonly capsule_id: string
  readonly outcome: CapsuleOutcome
  readonly entropy_consumed: number
  readonly event_hash: SHA256Hex
  readonly attestation_hash: SHA256Hex
  readonly sequence: SequenceNumber
  readonly reason?: string
  readonly is_replay_reconstructable: true
}

// ─── Error ─────────────────────────────────────────────────

export class CapsuleError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'CapsuleError'
  }
}
