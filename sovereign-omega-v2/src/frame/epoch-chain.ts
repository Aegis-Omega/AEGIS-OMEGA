// ============================================================
// SOVEREIGN OMEGA — Epoch Chain
// EPISTEMIC TIER: T2 · Gate 40
//
// Append-only hash chain of EpochRecords. Links successive
// epochs via previous_epoch_hash. certifyEpochChain() verifies
// the full chain integrity and recomputes each link_hash.
// primitive_mapping: HASH · replay_mapping: PROPAGATE
// topology_mapping: LINEAGE
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import type { EpochRecord } from './epoch.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const EPOCH_CHAIN_SCHEMA_VERSION = '1.0.0' as const
export const EPOCH_GENESIS_HASH: SHA256Hex = '0'.repeat(64) as SHA256Hex

export interface EpochLink {
  readonly epoch_hash: SHA256Hex
  readonly previous_epoch_hash: SHA256Hex
  readonly sequence: SequenceNumber
  readonly link_hash: SHA256Hex  // hashValue({epoch_hash, previous_epoch_hash, sequence})
  readonly schema_version: typeof EPOCH_CHAIN_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface EpochChainCertificate {
  readonly is_valid: boolean
  readonly link_count: number
  readonly terminal_hash: SHA256Hex | null
  readonly certificate_hash: SHA256Hex
  readonly is_replay_reconstructable: true
}

export class EpochChainError extends Error {
  override readonly name = 'EpochChainError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

async function buildLink(
  epoch: EpochRecord,
  previous_epoch_hash: SHA256Hex,
): Promise<EpochLink> {
  const link_hash = await hashValue({
    epoch_hash: epoch.epoch_hash,
    previous_epoch_hash,
    sequence: epoch.sequence.toString(),
  })
  return deepFreeze<EpochLink>({
    epoch_hash: epoch.epoch_hash,
    previous_epoch_hash,
    sequence: epoch.sequence,
    link_hash,
    schema_version: EPOCH_CHAIN_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

export class EpochChain {
  private constructor(
    private readonly _links: readonly EpochLink[],
    private readonly _lastSequence: SequenceNumber | null,
  ) {}

  static empty(): EpochChain {
    return new EpochChain([], null)
  }

  get length(): number { return this._links.length }
  get lastHash(): SHA256Hex {
    return this._links.length === 0
      ? EPOCH_GENESIS_HASH
      : this._links[this._links.length - 1]!.link_hash
  }
  get lastSequence(): SequenceNumber | null { return this._lastSequence }

  async append(epoch: EpochRecord): Promise<{ chain: EpochChain; link: EpochLink }> {
    if (this._lastSequence !== null && epoch.sequence <= this._lastSequence) {
      throw new EpochChainError(
        `Non-monotonic sequence: ${epoch.sequence} ≤ ${this._lastSequence}`,
      )
    }
    const link = await buildLink(epoch, this.lastHash)
    const chain = new EpochChain(
      Object.freeze([...this._links, link]),
      epoch.sequence,
    )
    return { chain, link }
  }

  getAll(): readonly EpochLink[] { return this._links }
}

export async function certifyEpochChain(
  links: readonly EpochLink[],
): Promise<EpochChainCertificate> {
  let is_valid = true

  for (let i = 0; i < links.length; i++) {
    const expected_prev = i === 0 ? EPOCH_GENESIS_HASH : links[i - 1]!.link_hash
    if (links[i]!.previous_epoch_hash !== expected_prev) { is_valid = false; break }
    const recomputed = await hashValue({
      epoch_hash: links[i]!.epoch_hash,
      previous_epoch_hash: links[i]!.previous_epoch_hash,
      sequence: links[i]!.sequence.toString(),
    })
    if (recomputed !== links[i]!.link_hash) { is_valid = false; break }
  }

  const terminal_hash = links.length === 0 ? null : links[links.length - 1]!.link_hash
  const certificate_hash = await hashValue(links.map(l => l.link_hash))

  return deepFreeze<EpochChainCertificate>({
    is_valid,
    link_count: links.length,
    terminal_hash,
    certificate_hash,
    is_replay_reconstructable: true,
  })
}
