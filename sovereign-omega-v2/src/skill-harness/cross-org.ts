// ============================================================
// Skill Harness — Phase 6 Cross-Organizational Cognition Seam
// EPISTEMIC TIER: T2 · Gate 168
//
// Seam declaration for opt-in cross-org skill sharing.
// Implementation is deferred pending multi-tenant infrastructure
// and organizational consent architecture (T2→T1 migration
// requires live deployment evidence).
//
// Constitutional constraint: all cross-org transfers flow through
// the same AdaptivePower(T) ≤ ReplayVerifiability(T) invariant.
// No direct org-to-org skill propagation permitted; all transfers
// must produce replay-certifiable SkillTransferProposal records.
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'

export const CROSS_ORG_SCHEMA_VERSION = '1.0.0' as const

// Consent model for cross-org skill sharing.
export type CrossOrgConsentLevel =
  | 'none'           // no sharing permitted (default)
  | 'opt-in-read'    // can read external org skills (no write)
  | 'opt-in-mutual'  // bidirectional consensual sharing

export interface OrgSkillManifest {
  readonly org_id: string
  readonly consent_level: CrossOrgConsentLevel
  readonly published_skill_ids: readonly string[]
  readonly manifest_hash: SHA256Hex          // hashValue({org_id, consent_level, published_skill_ids[]})
  readonly sequence: SequenceNumber
  readonly schema_version: typeof CROSS_ORG_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

// Cross-org transfer request seam — not yet implemented.
// When implemented, this will wrap proposeSkillTransfer with
// inter-org consent verification and audit trail binding.
export interface CrossOrgTransferRequest {
  readonly source_org_id: string
  readonly target_org_id: string
  readonly skill_id: string
  readonly requires_consent: true
  readonly schema_version: typeof CROSS_ORG_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class CrossOrgError extends Error {
  override readonly name = 'CrossOrgError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

// Phase 6 is not yet implemented. This stub documents the seam.
// Calling this function throws CrossOrgError with a clear message.
export function crossOrgTransfer(_request: CrossOrgTransferRequest): never {
  throw new CrossOrgError(
    'Cross-org skill transfer is not yet implemented (Phase 6 seam). ' +
    'Use collaboration.proposeSkillTransfer() for intra-org transfers.',
  )
}
