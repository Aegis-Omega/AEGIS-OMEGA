// ============================================================
// SOVEREIGN OMEGA — Replay Lineage Certifier
// EPISTEMIC TIER: T0 · Gate 30
//
// TopologyLineage: an append-only chain of GovernanceTopology
// snapshots where each link's previous_topology_hash equals the
// prior epoch's topology_hash. Provides the full causal history
// of constitutional state transitions.
//
// Lineage laws:
//   - First entry: previous_topology_hash = GENESIS_TOPOLOGY_HASH
//   - Entry[n].previous_topology_hash = Entry[n-1].topology_hash
//   - Sequence is strictly monotone across entries
//   - certifyLineage() verifies every link independently
//
// The lineage_hash of a LineageEntry is:
//   hashValue({topology_hash, previous_topology_hash, sequence})
// forming a tamper-evident chain of constitutional epochs.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { hashValue } from '../core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import type { GovernanceTopology } from '../frame/topology.js'

export const LINEAGE_SCHEMA_VERSION = '1.0.0' as const

/** Zero-hash anchor for the first lineage entry's previous_topology_hash. */
export const GENESIS_TOPOLOGY_HASH: SHA256Hex = '0'.repeat(64) as SHA256Hex

// ─── Error ─────────────────────────────────────────────────

export class LineageError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'LineageError'
  }
}

// ─── Types ─────────────────────────────────────────────────

/**
 * One certified link in the topology lineage chain.
 * lineage_hash chains from previous_topology_hash — tamper-evident.
 */
export interface LineageEntry {
  readonly topology_hash: SHA256Hex
  readonly previous_topology_hash: SHA256Hex
  readonly sequence: SequenceNumber
  readonly lineage_hash: SHA256Hex
  readonly schema_version: typeof LINEAGE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

/** Result of certifyLineage() over a complete chain. */
export interface LineageCertificate {
  readonly is_valid: boolean
  readonly entry_count: number
  readonly terminal_hash: SHA256Hex | null
  readonly certificate_hash: SHA256Hex
  readonly is_replay_reconstructable: true
}

// ─── Lineage Entry construction ────────────────────────────

/**
 * Compute the lineage_hash for an entry given its fields.
 * lineage_hash = hashValue({topology_hash, previous_topology_hash, sequence})
 */
export async function computeLineageHash(
  topologyHash: SHA256Hex,
  previousTopologyHash: SHA256Hex,
  sequence: SequenceNumber,
): Promise<SHA256Hex> {
  return hashValue({ topology_hash: topologyHash, previous_topology_hash: previousTopologyHash, sequence })
}

/**
 * Build a LineageEntry from a GovernanceTopology and its predecessor hash.
 * Throws LineageError if sequence is not strictly greater than prevSequence.
 */
export async function buildLineageEntry(
  topology: GovernanceTopology,
  previousTopologyHash: SHA256Hex,
  prevSequence: SequenceNumber | null,
): Promise<LineageEntry> {
  if (prevSequence !== null && topology.sequence <= prevSequence) {
    throw new LineageError(
      `Lineage sequence ${topology.sequence} must be > previous ${prevSequence}`
    )
  }
  const lineage_hash = await computeLineageHash(
    topology.topology_hash,
    previousTopologyHash,
    topology.sequence,
  )
  return deepFreeze<LineageEntry>({
    topology_hash: topology.topology_hash,
    previous_topology_hash: previousTopologyHash,
    sequence: topology.sequence,
    lineage_hash,
    schema_version: LINEAGE_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

// ─── TopologyLineage ───────────────────────────────────────

/** Append-only chain of LineageEntry records. Immutable functional update. */
export class TopologyLineage {
  private readonly _entries: readonly LineageEntry[]
  private readonly _lastSeq: SequenceNumber | null
  private readonly _lastHash: SHA256Hex

  private constructor(
    entries: readonly LineageEntry[],
    lastSeq: SequenceNumber | null,
    lastHash: SHA256Hex,
  ) {
    this._entries = entries
    this._lastSeq = lastSeq
    this._lastHash = lastHash
  }

  static empty(): TopologyLineage {
    return new TopologyLineage(deepFreeze([]), null, GENESIS_TOPOLOGY_HASH)
  }

  /**
   * Append a topology snapshot. Throws LineageError on non-monotonic sequence.
   * Returns a new TopologyLineage — does not mutate this instance.
   */
  async append(topology: GovernanceTopology): Promise<TopologyLineage> {
    const entry = await buildLineageEntry(topology, this._lastHash, this._lastSeq)
    return new TopologyLineage(
      deepFreeze([...this._entries, entry]),
      topology.sequence,
      topology.topology_hash,
    )
  }

  getAll(): readonly LineageEntry[] { return this._entries }
  get length(): number { return this._entries.length }
  get lastHash(): SHA256Hex { return this._lastHash }
  get lastSequence(): SequenceNumber | null { return this._lastSeq }
}

// ─── Certification ─────────────────────────────────────────

/**
 * Verify a complete lineage chain:
 *   1. First entry's previous_topology_hash = GENESIS_TOPOLOGY_HASH
 *   2. Each entry[n].previous_topology_hash = entry[n-1].topology_hash
 *   3. Each lineage_hash is re-derived from fields
 *   4. Sequence is strictly monotone
 */
export async function certifyLineage(
  entries: readonly LineageEntry[],
): Promise<LineageCertificate> {
  if (entries.length === 0) {
    const certHash = await hashValue({ valid: true, entry_count: 0 }) as SHA256Hex
    return deepFreeze<LineageCertificate>({
      is_valid: true, entry_count: 0, terminal_hash: null,
      certificate_hash: certHash, is_replay_reconstructable: true,
    })
  }

  let prevHash: SHA256Hex = GENESIS_TOPOLOGY_HASH
  let prevSeq: SequenceNumber | null = null

  for (const entry of entries) {
    if (entry.previous_topology_hash !== prevHash) {
      const certHash = await hashValue({ valid: false, reason: 'hash_chain_broken' }) as SHA256Hex
      return deepFreeze<LineageCertificate>({
        is_valid: false, entry_count: entries.length, terminal_hash: null,
        certificate_hash: certHash, is_replay_reconstructable: true,
      })
    }
    if (prevSeq !== null && entry.sequence <= prevSeq) {
      const certHash = await hashValue({ valid: false, reason: 'sequence_non_monotone' }) as SHA256Hex
      return deepFreeze<LineageCertificate>({
        is_valid: false, entry_count: entries.length, terminal_hash: null,
        certificate_hash: certHash, is_replay_reconstructable: true,
      })
    }
    const expected = await computeLineageHash(
      entry.topology_hash, entry.previous_topology_hash, entry.sequence,
    )
    if (entry.lineage_hash !== expected) {
      const certHash = await hashValue({ valid: false, reason: 'lineage_hash_invalid' }) as SHA256Hex
      return deepFreeze<LineageCertificate>({
        is_valid: false, entry_count: entries.length, terminal_hash: null,
        certificate_hash: certHash, is_replay_reconstructable: true,
      })
    }
    prevHash = entry.topology_hash
    prevSeq = entry.sequence
  }

  const terminal = entries[entries.length - 1]!.lineage_hash
  const certHash = await hashValue({ valid: true, terminal_hash: terminal, entry_count: entries.length }) as SHA256Hex
  return deepFreeze<LineageCertificate>({
    is_valid: true, entry_count: entries.length, terminal_hash: terminal,
    certificate_hash: certHash, is_replay_reconstructable: true,
  })
}
