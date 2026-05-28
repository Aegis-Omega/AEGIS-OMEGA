// EPISTEMIC TIER: T2 (engineering hypothesis)
// Constitutional mapping:
//   primitive_mapping: HASH      — slot_hash = hashValue(slot_index, slot_state, sequence)
//   replay_mapping:    PROPAGATE — slot transitions are PROPAGATE-phase updates
//   topology_mapping:  CONSENSUS — authoritative map = consensus ground truth for slot state
//
// Translation of the Coq/Iris AllocatorR CMRA:
//   authR (gmapUR nat (exclR slot_stateO))
//
// Exclusivity law: two registrations targeting the same slot_index cannot coexist.
// Their composition is ⊥ (SlotRegistryError), mirroring:
//   Excl(σ) ⊗ Excl(σ') = ⊥ for any σ, σ'
//
// Relocation invariant (from Coq Step 3 — linearized ghost update):
// When slot_addr changes, slot_gen MUST advance atomically. A relocation that
// fails to increment the generation produces a stale handle — rejected by
// isGenerationFresh(). Saturation (gen → ⊥) permanently invalidates the slot.
//
// Immutable pattern: every mutating operation returns a new ExclusiveSlotMap.
// The original is unchanged. No Set/Map in exported state objects — arrays only.

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import {
  makeGeneration,
  incrementGeneration,
  type BoundedGeneration,
} from './bounded-generation.js'

export const SLOT_REGISTRY_SCHEMA_VERSION = '1.0.0' as const

export interface SlotState {
  readonly slot_gen:  BoundedGeneration  // generation — advances on every relocation
  readonly slot_addr: number             // physical base address
  readonly slot_size: number             // allocation size in bytes (> 0)
  readonly slot_live: boolean            // false = deallocated, pending reclaim
}

export interface SlotFragment {
  readonly slot_index: number
  readonly slot_state: SlotState
  readonly slot_hash:  SHA256Hex   // hashValue({slot_index, slot_state, sequence})
  readonly schema_version: typeof SLOT_REGISTRY_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface RegistryCertificate {
  readonly slot_count:    number
  readonly live_count:    number
  readonly registry_hash: SHA256Hex  // hashValue over all slot_hashes sorted by slot_index
  readonly sequence:      SequenceNumber
  readonly schema_version: typeof SLOT_REGISTRY_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class SlotRegistryError extends Error {
  override readonly name = 'SlotRegistryError'
}

export class ExclusiveSlotMap {
  readonly #slots: ReadonlyMap<number, SlotFragment>

  private constructor(slots: ReadonlyMap<number, SlotFragment>) {
    this.#slots = slots
  }

  static empty(): ExclusiveSlotMap {
    return new ExclusiveSlotMap(new Map())
  }

  get size(): number { return this.#slots.size }

  // Register a new slot. Throws if slot_index already present (exclusivity law).
  async register(
    slot_index: number,
    slot_addr: number,
    slot_size: number,
    sequence: SequenceNumber,
  ): Promise<{ registry: ExclusiveSlotMap; fragment: SlotFragment }> {
    if (this.#slots.has(slot_index)) {
      throw new SlotRegistryError(
        `[REGISTRY_EXCLUSIVE] slot_index ${slot_index} already registered — exclusivity violation`,
      )
    }
    if (slot_size === 0) {
      throw new SlotRegistryError(`[REGISTRY_REJECT] slot_size must be > 0`)
    }
    const slot_state: SlotState = {
      slot_gen:  makeGeneration(0),
      slot_addr,
      slot_size,
      slot_live: true,
    }
    const slot_hash = await hashValue({
      slot_index,
      slot_state: {
        slot_gen: slot_state.slot_gen,
        slot_addr: slot_state.slot_addr,
        slot_size: slot_state.slot_size,
        slot_live: slot_state.slot_live,
      },
      sequence: sequence.toString(),
    }) as SHA256Hex
    const fragment = deepFreeze<SlotFragment>({
      slot_index,
      slot_state,
      slot_hash,
      schema_version: SLOT_REGISTRY_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })
    const next = new Map(this.#slots)
    next.set(slot_index, fragment)
    return { registry: new ExclusiveSlotMap(next), fragment }
  }

  // Relocate a live slot to a new physical address, atomically advancing its generation.
  // Mirrors Coq proof Step 3: linearized ghost update of the indirection table.
  // Throws if slot not found, not live, or generation saturated (⊥).
  async relocate(
    slot_index: number,
    new_addr: number,
    sequence: SequenceNumber,
  ): Promise<{ registry: ExclusiveSlotMap; fragment: SlotFragment }> {
    const existing = this.#slots.get(slot_index)
    if (!existing) {
      throw new SlotRegistryError(
        `[REGISTRY_REJECT] slot_index ${slot_index} not found`,
      )
    }
    if (!existing.slot_state.slot_live) {
      throw new SlotRegistryError(
        `[REGISTRY_REJECT] slot_index ${slot_index} is not live`,
      )
    }
    const next_gen = incrementGeneration(existing.slot_state.slot_gen)
    /* c8 ignore next -- generation reaches null only after 2^32-1 relocations; unreachable in practice */
    if (next_gen === null) {
      throw new SlotRegistryError(
        `[REGISTRY_SATURATED] slot_index ${slot_index} generation saturated — handle permanently invalid`,
      )
    }
    const slot_state: SlotState = {
      slot_gen:  next_gen,
      slot_addr: new_addr,
      slot_size: existing.slot_state.slot_size,
      slot_live: true,
    }
    const slot_hash = await hashValue({
      slot_index,
      slot_state: {
        slot_gen: slot_state.slot_gen,
        slot_addr: slot_state.slot_addr,
        slot_size: slot_state.slot_size,
        slot_live: slot_state.slot_live,
      },
      sequence: sequence.toString(),
    }) as SHA256Hex
    const fragment = deepFreeze<SlotFragment>({
      slot_index,
      slot_state,
      slot_hash,
      schema_version: SLOT_REGISTRY_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })
    const next = new Map(this.#slots)
    next.set(slot_index, fragment)
    return { registry: new ExclusiveSlotMap(next), fragment }
  }

  // Mark a live slot as deallocated (slot_live → false), pending physical reclaim.
  // Generation is not advanced — deallocation is a logical state change, not relocation.
  // Throws if slot not found or already deallocated.
  async deallocate(
    slot_index: number,
    sequence: SequenceNumber,
  ): Promise<{ registry: ExclusiveSlotMap; fragment: SlotFragment }> {
    const existing = this.#slots.get(slot_index)
    if (!existing) {
      throw new SlotRegistryError(
        `[REGISTRY_REJECT] slot_index ${slot_index} not found`,
      )
    }
    if (!existing.slot_state.slot_live) {
      throw new SlotRegistryError(
        `[REGISTRY_REJECT] slot_index ${slot_index} already deallocated`,
      )
    }
    const slot_state: SlotState = {
      slot_gen:  existing.slot_state.slot_gen,
      slot_addr: existing.slot_state.slot_addr,
      slot_size: existing.slot_state.slot_size,
      slot_live: false,
    }
    const slot_hash = await hashValue({
      slot_index,
      slot_state: {
        slot_gen: slot_state.slot_gen,
        slot_addr: slot_state.slot_addr,
        slot_size: slot_state.slot_size,
        slot_live: slot_state.slot_live,
      },
      sequence: sequence.toString(),
    }) as SHA256Hex
    const fragment = deepFreeze<SlotFragment>({
      slot_index,
      slot_state,
      slot_hash,
      schema_version: SLOT_REGISTRY_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })
    const next = new Map(this.#slots)
    next.set(slot_index, fragment)
    return { registry: new ExclusiveSlotMap(next), fragment }
  }

  lookup(slot_index: number): SlotFragment | null {
    return this.#slots.get(slot_index) ?? null
  }

  // Returns all fragments sorted by slot_index (deterministic, no Map iteration order).
  getAll(): readonly SlotFragment[] {
    return [...this.#slots.values()].sort((a, b) => a.slot_index - b.slot_index)
  }

  async certify(sequence: SequenceNumber): Promise<RegistryCertificate> {
    const all = this.getAll()
    const live_count = all.filter(f => f.slot_state.slot_live).length
    const registry_hash = await hashValue({
      slot_hashes: all.map(f => f.slot_hash),
      sequence: sequence.toString(),
    }) as SHA256Hex
    return deepFreeze<RegistryCertificate>({
      slot_count: all.length,
      live_count,
      registry_hash,
      sequence,
      schema_version: SLOT_REGISTRY_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })
  }
}
