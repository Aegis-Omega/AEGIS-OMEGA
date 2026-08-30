// ============================================================
// Federation Type Seams — CRGM §7
// EPISTEMIC TIER: T2 (engineering hypothesis — seam only, Gate 145)
// Status: SEAMS DECLARED — network transport NOT implemented.
// Implementation requires Phase 2+ (live infrastructure).
// Pattern: identical to src/ledger/persistence.ts (Gate 23).
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const FEDERATION_SCHEMA_VERSION = '1.0.0' as const

export type FederationRole =
  | 'sovereign-node'         // Holds authoritative replay lineage
  | 'constitutional-witness' // Verifies lineage without holding authority
  | 'federation-relay'       // Routes EventEnvelope cross-node (Law of Silence)

export interface SovereignNodeManifest {
  readonly node_id: string
  readonly role: FederationRole
  readonly public_key_fingerprint: string  // stub — awaiting PKI (Gate 22 generateKeypair)
  readonly lineage_root_hash: SHA256Hex
  readonly schema_version: typeof FEDERATION_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface FederationSyncRecord {
  readonly source_node_id: string
  readonly target_node_id: string
  readonly lineage_terminal_hash: SHA256Hex
  readonly sync_hash: SHA256Hex  // hashValue({source, target, lineage_terminal_hash, sequence})
  readonly sequence: SequenceNumber
  readonly schema_version: typeof FEDERATION_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class FederationError extends Error {
  override readonly name = 'FederationError'
}

export async function buildSyncRecord(input: {
  source_node_id: string
  target_node_id: string
  lineage_terminal_hash: SHA256Hex
  sequence: SequenceNumber
}): Promise<FederationSyncRecord> {
  if (!input.source_node_id) throw new FederationError('source_node_id must be non-empty')
  if (!input.target_node_id) throw new FederationError('target_node_id must be non-empty')
  const sync_hash = await hashValue({
    source: input.source_node_id,
    target: input.target_node_id,
    lineage_terminal_hash: input.lineage_terminal_hash,
    sequence: input.sequence.toString(),
  }) as SHA256Hex
  return deepFreeze<FederationSyncRecord>({
    source_node_id: input.source_node_id,
    target_node_id: input.target_node_id,
    lineage_terminal_hash: input.lineage_terminal_hash,
    sync_hash,
    sequence: input.sequence,
    schema_version: FEDERATION_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

export async function buildNodeManifest(input: {
  node_id: string
  role: FederationRole
  public_key_fingerprint: string
  lineage_root_hash: SHA256Hex
}): Promise<SovereignNodeManifest> {
  if (!input.node_id) throw new FederationError('node_id must be non-empty')
  return deepFreeze<SovereignNodeManifest>({
    node_id: input.node_id,
    role: input.role,
    public_key_fingerprint: input.public_key_fingerprint,
    lineage_root_hash: input.lineage_root_hash,
    schema_version: FEDERATION_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}
