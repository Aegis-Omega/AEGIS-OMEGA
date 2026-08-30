// ============================================================
// SOVEREIGN OMEGA — Topology Hash Engine
// EPISTEMIC TIER: T0 · Gate 29
//
// Implements the constitutional identity law:
//   ConstitutionalIdentity(T) = TopologyHash(T)
//
// A GovernanceTopology is the complete fingerprint of a governance
// epoch: SITR state + AOIE verdict + constitutional verdict +
// ledger Merkle root + consensus QC hash + DFA certificate.
//
// Two nodes are in the same constitutional state iff their
// topology_hash values are equal — enabling replay equivalence
// voting without full state transfer.
//
// Invariants:
//   - topology_hash = hashValue(all fields except topology_hash)
//   - null consensus_qc_hash = single-node or pre-quorum epoch
//   - All fields are frozen; topology object is deepFreeze-d
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { hashValue } from '../core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import type { SITRState } from '../sitr/types.js'
import type { GlobalState } from '../aoie/types.js'
import type { ConstitutionalVerdict } from '../constitutional/types.js'

export const TOPOLOGY_SCHEMA_VERSION = '1.0.0' as const

// ─── Error ─────────────────────────────────────────────────

export class TopologyError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'TopologyError'
  }
}

// ─── Types ─────────────────────────────────────────────────

/**
 * Complete constitutional identity for one governance epoch.
 * topology_hash is the canonical SHA-256 fingerprint of the epoch —
 * identical topologies across nodes proves replay equivalence.
 */
export interface GovernanceTopology {
  readonly sitr_state: SITRState
  readonly aoie_global_state: GlobalState
  readonly constitutional_verdict: ConstitutionalVerdict
  readonly ledger_root: SHA256Hex
  /** null iff no quorum has been established yet (single-node or pre-consensus). */
  readonly consensus_qc_hash: SHA256Hex | null
  readonly dfa_certificate_hash: SHA256Hex
  readonly sequence: SequenceNumber
  readonly topology_hash: SHA256Hex
  readonly schema_version: typeof TOPOLOGY_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

/** All inputs required to build a GovernanceTopology. */
export interface TopologyInput {
  readonly sitr_state: SITRState
  readonly aoie_global_state: GlobalState
  readonly constitutional_verdict: ConstitutionalVerdict
  readonly ledger_root: SHA256Hex
  readonly consensus_qc_hash: SHA256Hex | null
  readonly dfa_certificate_hash: SHA256Hex
  readonly sequence: SequenceNumber
}

// ─── Canonical payload ─────────────────────────────────────

/** The exact object that is hashed to produce topology_hash. */
function topologyPayload(input: TopologyInput): Record<string, unknown> {
  return {
    aoie_global_state: input.aoie_global_state,
    consensus_qc_hash: input.consensus_qc_hash,
    constitutional_verdict: input.constitutional_verdict,
    dfa_certificate_hash: input.dfa_certificate_hash,
    ledger_root: input.ledger_root,
    schema_version: TOPOLOGY_SCHEMA_VERSION,
    sequence: input.sequence,
    sitr_state: input.sitr_state,
  }
}

// ─── Core functions ────────────────────────────────────────

/**
 * Compute only the topology_hash for the given input.
 * Deterministic: same input → same SHA-256 hash.
 */
export async function computeTopologyHash(input: TopologyInput): Promise<SHA256Hex> {
  return hashValue(topologyPayload(input))
}

/**
 * Build a complete frozen GovernanceTopology for a governance epoch.
 * topology_hash is computed from all other fields — tamper-evident.
 */
export async function buildTopology(input: TopologyInput): Promise<GovernanceTopology> {
  const topology_hash = await computeTopologyHash(input)
  return deepFreeze<GovernanceTopology>({
    sitr_state: input.sitr_state,
    aoie_global_state: input.aoie_global_state,
    constitutional_verdict: input.constitutional_verdict,
    ledger_root: input.ledger_root,
    consensus_qc_hash: input.consensus_qc_hash,
    dfa_certificate_hash: input.dfa_certificate_hash,
    sequence: input.sequence,
    topology_hash,
    schema_version: TOPOLOGY_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

/**
 * True iff both topologies have byte-identical topology_hash values.
 * This is the constitutional convergence test: two nodes with the
 * same topology_hash are provably in the same governance state.
 */
export function topologiesConverge(a: GovernanceTopology, b: GovernanceTopology): boolean {
  return a.topology_hash === b.topology_hash
}

/**
 * Verify that a GovernanceTopology's topology_hash is self-consistent —
 * re-derives the hash from its own fields and checks for equality.
 * Returns false if the topology has been tampered with.
 */
export async function verifyTopology(topology: GovernanceTopology): Promise<boolean> {
  const expected = await computeTopologyHash(topology)
  return topology.topology_hash === expected
}
