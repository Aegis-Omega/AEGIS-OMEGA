// ============================================================
// SOVEREIGN OMEGA — Adaptive Lineage
// EPISTEMIC TIER: T2 · Gate 38
//
// Unified causal chain: topology transitions AND capability
// evolution records linked by hash. The full SHP cycle is
// expressed in the chain's event types.
// primitive_mapping: HASH+SEQUENCE · replay_mapping: full cycle
// topology_mapping: LINEAGE
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import type { EvolutionVerdict } from '../capsule/evolution.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import { GENESIS_TOPOLOGY_HASH } from './lineage.js'

export { GENESIS_TOPOLOGY_HASH }
export const ADAPTIVE_LINEAGE_SCHEMA_VERSION = '1.0.0' as const

export type AdaptiveEvent =
  | { readonly kind: 'TOPOLOGY_TRANSITION'; readonly topology_hash: SHA256Hex }
  | { readonly kind: 'CAPABILITY_EVOLUTION'; readonly proposal_id: SHA256Hex; readonly verdict: EvolutionVerdict }

export interface AdaptiveLineageEntry {
  readonly event: AdaptiveEvent
  readonly previous_entry_hash: SHA256Hex
  readonly sequence: SequenceNumber
  readonly entry_hash: SHA256Hex
  readonly schema_version: typeof ADAPTIVE_LINEAGE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface AdaptiveLineageCertificate {
  readonly is_valid: boolean
  readonly entry_count: number
  readonly terminal_hash: SHA256Hex | null
  readonly certificate_hash: SHA256Hex
  readonly is_replay_reconstructable: true
}

export class AdaptiveLineageError extends Error {
  override readonly name = 'AdaptiveLineageError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

async function buildEntry(
  event: AdaptiveEvent,
  previous_entry_hash: SHA256Hex,
  sequence: SequenceNumber,
): Promise<AdaptiveLineageEntry> {
  const entry_hash = await hashValue({ event, previous_entry_hash, sequence: sequence.toString() })
  return deepFreeze<AdaptiveLineageEntry>({
    event,
    previous_entry_hash,
    sequence,
    entry_hash,
    schema_version: ADAPTIVE_LINEAGE_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

export class AdaptiveLineage {
  private constructor(
    private readonly _entries: readonly AdaptiveLineageEntry[],
    private readonly _lastSequence: SequenceNumber | null,
  ) {}

  static empty(): AdaptiveLineage {
    return new AdaptiveLineage([], null)
  }

  get length(): number { return this._entries.length }
  get lastHash(): SHA256Hex {
    return this._entries.length === 0
      ? GENESIS_TOPOLOGY_HASH
      : this._entries[this._entries.length - 1]!.entry_hash
  }
  get lastSequence(): SequenceNumber | null { return this._lastSequence }

  async append(
    event: AdaptiveEvent,
    sequence: SequenceNumber,
  ): Promise<{ lineage: AdaptiveLineage; entry: AdaptiveLineageEntry }> {
    if (this._lastSequence !== null && sequence <= this._lastSequence) {
      throw new AdaptiveLineageError(
        `Non-monotonic sequence: ${sequence} ≤ ${this._lastSequence}`,
      )
    }
    const entry = await buildEntry(event, this.lastHash, sequence)
    const lineage = new AdaptiveLineage(
      Object.freeze([...this._entries, entry]),
      sequence,
    )
    return { lineage, entry }
  }

  getAll(): readonly AdaptiveLineageEntry[] { return this._entries }
}

export async function certifyAdaptiveLineage(
  entries: readonly AdaptiveLineageEntry[],
): Promise<AdaptiveLineageCertificate> {
  let is_valid = true

  for (let i = 0; i < entries.length; i++) {
    const expected_prev = i === 0 ? GENESIS_TOPOLOGY_HASH : entries[i - 1]!.entry_hash
    if (entries[i]!.previous_entry_hash !== expected_prev) { is_valid = false; break }
    const recomputed = await hashValue({
      event: entries[i]!.event,
      previous_entry_hash: entries[i]!.previous_entry_hash,
      sequence: entries[i]!.sequence.toString(),
    })
    if (recomputed !== entries[i]!.entry_hash) { is_valid = false; break }
  }

  const terminal_hash = entries.length === 0 ? null : entries[entries.length - 1]!.entry_hash
  const certificate_hash = await hashValue(entries.map(e => e.entry_hash))

  return deepFreeze<AdaptiveLineageCertificate>({
    is_valid,
    entry_count: entries.length,
    terminal_hash,
    certificate_hash,
    is_replay_reconstructable: true,
  })
}
