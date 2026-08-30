// EPISTEMIC TIER: T2 (engineering hypothesis)
// Constitutional mapping:
//   primitive_mapping: HASH+SEQUENCE — slab_hash + handle_hash chain every allocation event
//   replay_mapping:    PROPAGATE     — allocator state propagates via immutable snapshot returns
//   topology_mapping:  LINEAGE       — allocation history is auditable via certify()
//
// SlabAllocator — multi-tiered epoch-based slab allocator.
//
// Constitutional translation of the Slab-Oriented Multi-Tiered Epoch Allocator spec:
//   "Fixed-size slabs"           → SLAB_TIER_SIZES (TINY/SMALL/MEDIUM/LARGE, power-of-2)
//   "64-bit availability bitmap" → bigint bitmask; bit i=1 means chunk i allocated
//   "CAS atomic update"          → synchronous bigint ops (single-threaded; deterministic)
//   "Thread-local free-lists"    → per-operation allocation (immutable pattern provides this)
//   "Epoch-based reclamation"    → decommissionEmpty(current_epoch) at SequenceNumber threshold
//   "Slab decommission"          → is_decommissioned=true when empty for SLAB_DECOMMISSION_THRESHOLD epochs
//
// Ecology bound: MAX_SLABS_PER_TIER = 8 = MAX_UNIVERSES (same holonic constant).
// Decommission window: 8 epochs = F_6 (Fibonacci-capped, same as MAX_SIMULATION_DEPTH).

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'

export const SLAB_SCHEMA_VERSION = '1.0.0' as const
export const CHUNKS_PER_SLAB = 64 as const
export const SLAB_DECOMMISSION_THRESHOLD = 8   // F_6 — Fibonacci epoch window
export const MAX_SLABS_PER_TIER = 8            // holonic ecology bound

export const SLAB_TIER_SIZES = {
  TINY:   4 * 1024,
  SMALL:  16 * 1024,
  MEDIUM: 64 * 1024,
  LARGE:  1024 * 1024,
} as const

export type SlabTier = keyof typeof SLAB_TIER_SIZES

const FULL_MASK = (1n << 64n) - 1n  // 0xFFFF_FFFF_FFFF_FFFF

function firstFreeBit(bitmap: bigint): number | null {
  const b = bitmap & FULL_MASK
  if (b === FULL_MASK) return null
  for (let i = 0; i < CHUNKS_PER_SLAB; i++) {
    if ((b & (1n << BigInt(i))) === 0n) return i
  }
  /* c8 ignore next -- FULL_MASK check above guarantees a free bit exists; loop always returns early */
  return null
}

function popcount(bitmap: bigint): number {
  let n = 0; let b = bitmap & FULL_MASK
  while (b > 0n) { n += Number(b & 1n); b >>= 1n }
  return n
}

export interface SlabChunkHandle {
  readonly slab_id:     string
  readonly tier:        SlabTier
  readonly chunk_index: number
  readonly epoch:       SequenceNumber
  readonly handle_hash: SHA256Hex
  readonly schema_version: typeof SLAB_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface SlabRecord {
  readonly slab_id:            string
  readonly tier:               SlabTier
  readonly chunk_size_bytes:   number
  readonly allocated_bitmap:   bigint     // bit i=1: chunk i allocated
  readonly allocated_count:    number     // popcount(allocated_bitmap)
  readonly last_release_epoch: SequenceNumber | null
  readonly is_decommissioned:  boolean
  readonly epoch:              SequenceNumber
  readonly slab_hash:          SHA256Hex  // hashValue({slab_id, allocated_bitmap, epoch})
  readonly schema_version:     typeof SLAB_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface SlabCertificate {
  readonly slab_count:           number
  readonly total_allocated:      number
  readonly decommissioned_count: number
  readonly allocator_hash:       SHA256Hex
  readonly sequence:             SequenceNumber
  readonly schema_version:       typeof SLAB_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class SlabAllocatorError extends Error {
  override readonly name = 'SlabAllocatorError'
}

async function slabHash(slab_id: string, bitmap: bigint, epoch: SequenceNumber): Promise<SHA256Hex> {
  return await hashValue({ slab_id, allocated_bitmap: bitmap.toString(), epoch: epoch.toString() }) as SHA256Hex
}

export class SlabAllocator {
  readonly #slabs: ReadonlyMap<string, SlabRecord>
  readonly #tiers: ReadonlyMap<SlabTier, readonly string[]>  // tier → ordered slab_ids

  private constructor(slabs: ReadonlyMap<string, SlabRecord>, tiers: ReadonlyMap<SlabTier, readonly string[]>) {
    this.#slabs = slabs; this.#tiers = tiers
  }

  static empty(): SlabAllocator { return new SlabAllocator(new Map(), new Map()) }

  get slabCount(): number { return this.#slabs.size }
  get totalAllocated(): number {
    let n = 0; for (const s of this.#slabs.values()) n += s.allocated_count; return n
  }

  getSlabs(tier: SlabTier): readonly SlabRecord[] {
    return Object.freeze((this.#tiers.get(tier) ?? []).map(id => this.#slabs.get(id)!))
  }

  async allocate(tier: SlabTier, sequence: SequenceNumber): Promise<{ allocator: SlabAllocator; handle: SlabChunkHandle }> {
    const tier_ids = this.#tiers.get(tier) ?? []
    let target: SlabRecord | null = null
    let ci = -1

    for (const id of tier_ids) {
      const s = this.#slabs.get(id)!
      if (s.is_decommissioned) continue
      const fi = firstFreeBit(s.allocated_bitmap)
      if (fi !== null) { target = s; ci = fi; break }
    }

    if (target === null) {
      const active = tier_ids.filter(id => !this.#slabs.get(id)!.is_decommissioned).length
      if (active >= MAX_SLABS_PER_TIER) throw new SlabAllocatorError(
        `[SLAB_REJECT] ecology overflow: MAX_SLABS_PER_TIER=${MAX_SLABS_PER_TIER} reached for tier ${tier}`,
      )
      const slab_id = await hashValue({ tier, slab_index: tier_ids.length, sequence: sequence.toString() }) as string
      target = deepFreeze<SlabRecord>({
        slab_id, tier, chunk_size_bytes: SLAB_TIER_SIZES[tier],
        allocated_bitmap: 0n, allocated_count: 0, last_release_epoch: null,
        is_decommissioned: false, epoch: sequence,
        slab_hash: await slabHash(slab_id, 0n, sequence),
        schema_version: SLAB_SCHEMA_VERSION, is_replay_reconstructable: true,
      })
      ci = 0
    }

    const new_bitmap = target.allocated_bitmap | (1n << BigInt(ci))
    const updated = deepFreeze<SlabRecord>({
      ...target,
      allocated_bitmap: new_bitmap, allocated_count: popcount(new_bitmap),
      epoch: sequence, slab_hash: await slabHash(target.slab_id, new_bitmap, sequence),
    })

    const handle = deepFreeze<SlabChunkHandle>({
      slab_id: updated.slab_id, tier, chunk_index: ci, epoch: sequence,
      handle_hash: await hashValue({ slab_id: updated.slab_id, chunk_index: ci, epoch: sequence.toString() }) as SHA256Hex,
      schema_version: SLAB_SCHEMA_VERSION, is_replay_reconstructable: true,
    })

    const ns = new Map(this.#slabs); ns.set(updated.slab_id, updated)
    const ids = [...tier_ids]; if (!ids.includes(updated.slab_id)) ids.push(updated.slab_id)
    const nt = new Map(this.#tiers); nt.set(tier, Object.freeze(ids))
    return { allocator: new SlabAllocator(ns, nt), handle }
  }

  async release(handle: SlabChunkHandle, sequence: SequenceNumber): Promise<{ allocator: SlabAllocator }> {
    const slab = this.#slabs.get(handle.slab_id)
    if (!slab) throw new SlabAllocatorError(`[SLAB_REJECT] slab_id '${handle.slab_id}' not found`)
    const bit = 1n << BigInt(handle.chunk_index)
    if ((slab.allocated_bitmap & bit) === 0n) throw new SlabAllocatorError(
      `[SLAB_REJECT] chunk ${handle.chunk_index} already free — double-release`,
    )
    const new_bitmap = slab.allocated_bitmap & ~bit
    const updated = deepFreeze<SlabRecord>({
      ...slab,
      allocated_bitmap: new_bitmap, allocated_count: popcount(new_bitmap),
      last_release_epoch: sequence, epoch: sequence,
      slab_hash: await slabHash(slab.slab_id, new_bitmap, sequence),
    })
    const ns = new Map(this.#slabs); ns.set(slab.slab_id, updated)
    return { allocator: new SlabAllocator(ns, this.#tiers) }
  }

  async decommissionEmpty(current_epoch: SequenceNumber): Promise<{ allocator: SlabAllocator; decommissioned_count: number }> {
    const threshold = BigInt(SLAB_DECOMMISSION_THRESHOLD)
    const ns = new Map(this.#slabs); let count = 0
    for (const [id, slab] of this.#slabs) {
      if (!slab.is_decommissioned && slab.allocated_count === 0 &&
          slab.last_release_epoch !== null && current_epoch - slab.last_release_epoch >= threshold) {
        ns.set(id, deepFreeze({ ...slab, is_decommissioned: true })); count++
      }
    }
    return { allocator: new SlabAllocator(ns, this.#tiers), decommissioned_count: count }
  }

  async certify(sequence: SequenceNumber): Promise<SlabCertificate> {
    const sorted = [...this.#slabs.values()].sort((a, b) => a.slab_id.localeCompare(b.slab_id))
    return deepFreeze<SlabCertificate>({
      slab_count:           sorted.length,
      total_allocated:      sorted.reduce((n, s) => n + s.allocated_count, 0),
      decommissioned_count: sorted.filter(s => s.is_decommissioned).length,
      allocator_hash:       await hashValue({ slab_hashes: sorted.map(s => s.slab_hash), sequence: sequence.toString() }) as SHA256Hex,
      sequence, schema_version: SLAB_SCHEMA_VERSION, is_replay_reconstructable: true,
    })
  }
}
