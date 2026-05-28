// ============================================================
// Slot Registry Extended Tests — memory/slot-registry.ts
// Targets:
//   L131 arm 0: relocate on a deallocated (slot_live=false) slot → throws
//   deallocate() happy path and double-deallocate guard
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  ExclusiveSlotMap,
  SlotRegistryError,
} from '../../src/memory/slot-registry.js'
import type { SequenceNumber } from '../../src/core/types.js'

const S1 = 1n as SequenceNumber
const S2 = 2n as SequenceNumber
const S3 = 3n as SequenceNumber

describe('ExclusiveSlotMap.deallocate: happy path', () => {
  it('deallocate sets slot_live to false', async () => {
    const { registry: r1 } = await ExclusiveSlotMap.empty().register(0, 1000, 64, S1)
    const { registry: r2, fragment } = await r1.deallocate(0, S2)
    expect(fragment.slot_state.slot_live).toBe(false)
    expect(r2.size).toBe(1)
  })

  it('deallocated slot is visible in getAll()', async () => {
    const { registry: r1 } = await ExclusiveSlotMap.empty().register(0, 1000, 64, S1)
    const { registry: r2 } = await r1.deallocate(0, S2)
    const all = r2.getAll()
    expect(all).toHaveLength(1)
    expect(all[0]?.slot_state.slot_live).toBe(false)
  })

  it('generation is not advanced on deallocate', async () => {
    const { registry: r1, fragment: f1 } = await ExclusiveSlotMap.empty().register(0, 1000, 64, S1)
    const { fragment: f2 } = await r1.deallocate(0, S2)
    expect(f2.slot_state.slot_gen).toBe(f1.slot_state.slot_gen)
  })
})

describe('ExclusiveSlotMap.deallocate: error paths', () => {
  it('throws when slot_index not found', async () => {
    await expect(
      ExclusiveSlotMap.empty().deallocate(99, S1)
    ).rejects.toThrow(SlotRegistryError)
  })

  it('throws when slot already deallocated (double-deallocate)', async () => {
    const { registry: r1 } = await ExclusiveSlotMap.empty().register(0, 1000, 64, S1)
    const { registry: r2 } = await r1.deallocate(0, S2)
    await expect(r2.deallocate(0, S3)).rejects.toThrow(/already deallocated/)
  })
})

describe('ExclusiveSlotMap.relocate on deallocated slot (L131 arm 0)', () => {
  it('throws SlotRegistryError when slot is not live', async () => {
    const { registry: r1 } = await ExclusiveSlotMap.empty().register(0, 1000, 64, S1)
    const { registry: r2 } = await r1.deallocate(0, S2)
    // relocate on a non-live slot → L131 arm 0
    await expect(r2.relocate(0, 2000, S3)).rejects.toThrow(SlotRegistryError)
    await expect(r2.relocate(0, 2000, S3)).rejects.toThrow(/not live/)
  })
})
