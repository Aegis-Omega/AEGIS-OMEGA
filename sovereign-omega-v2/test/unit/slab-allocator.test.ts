// test/unit/slab-allocator.test.ts
// Gate 194 — SlabAllocator (multi-tiered epoch-based slab allocator)
// EPISTEMIC TIER: T2
//
// Constitutional translation of the Slab-Oriented Multi-Tiered Epoch Allocator spec.
// Validates: tier isolation, bitmap mechanics, epoch-based decommission, audit chain.

import { describe, it, expect } from 'vitest'
import {
  SlabAllocator,
  SlabAllocatorError,
  SLAB_SCHEMA_VERSION,
  SLAB_TIER_SIZES,
  CHUNKS_PER_SLAB,
  SLAB_DECOMMISSION_THRESHOLD,
  MAX_SLABS_PER_TIER,
} from '../../src/memory/slab-allocator.js'
import type { SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

describe('Gate 194 — SlabAllocator', () => {

  describe('Constants', () => {
    it('SLAB_SCHEMA_VERSION is 1.0.0', () => {
      expect(SLAB_SCHEMA_VERSION).toBe('1.0.0')
    })

    it('CHUNKS_PER_SLAB is 64 (matches the 64-bit bitmap)', () => {
      expect(CHUNKS_PER_SLAB).toBe(64)
    })

    it('SLAB_DECOMMISSION_THRESHOLD is 8 (F_6)', () => {
      expect(SLAB_DECOMMISSION_THRESHOLD).toBe(8)
    })

    it('MAX_SLABS_PER_TIER is 8 (holonic ecology bound)', () => {
      expect(MAX_SLABS_PER_TIER).toBe(8)
    })

    it('SLAB_TIER_SIZES are correct power-of-2 values', () => {
      expect(SLAB_TIER_SIZES.TINY).toBe(4 * 1024)
      expect(SLAB_TIER_SIZES.SMALL).toBe(16 * 1024)
      expect(SLAB_TIER_SIZES.MEDIUM).toBe(64 * 1024)
      expect(SLAB_TIER_SIZES.LARGE).toBe(1024 * 1024)
    })

    it('SlabAllocatorError is Error subclass with correct name', () => {
      const err = new SlabAllocatorError('x')
      expect(err).toBeInstanceOf(Error)
      expect(err.name).toBe('SlabAllocatorError')
    })
  })

  describe('SlabAllocator.empty()', () => {
    it('starts with slabCount=0 and totalAllocated=0', () => {
      const a = SlabAllocator.empty()
      expect(a.slabCount).toBe(0)
      expect(a.totalAllocated).toBe(0)
    })

    it('getSlabs returns empty for all tiers', () => {
      const a = SlabAllocator.empty()
      expect(a.getSlabs('TINY')).toHaveLength(0)
      expect(a.getSlabs('LARGE')).toHaveLength(0)
    })
  })

  describe('allocate() — basic', () => {
    it('creates a slab and returns a frozen handle', async () => {
      const a = SlabAllocator.empty()
      const { handle } = await a.allocate('TINY', seq(1))
      expect(Object.isFrozen(handle)).toBe(true)
      expect(handle.tier).toBe('TINY')
      expect(handle.is_replay_reconstructable).toBe(true)
      expect(handle.schema_version).toBe(SLAB_SCHEMA_VERSION)
    })

    it('handle_hash is 64-char hex', async () => {
      const a = SlabAllocator.empty()
      const { handle } = await a.allocate('TINY', seq(1))
      expect(handle.handle_hash).toHaveLength(64)
      expect(/^[0-9a-f]{64}$/.test(handle.handle_hash)).toBe(true)
    })

    it('slabCount and totalAllocated increment', async () => {
      const a = SlabAllocator.empty()
      const { allocator: a1 } = await a.allocate('TINY', seq(1))
      expect(a1.slabCount).toBe(1)
      expect(a1.totalAllocated).toBe(1)
    })

    it('original allocator unchanged (immutable pattern)', async () => {
      const a = SlabAllocator.empty()
      await a.allocate('TINY', seq(1))
      expect(a.slabCount).toBe(0)
      expect(a.totalAllocated).toBe(0)
    })

    it('chunk_index=0 for first allocation in a new slab', async () => {
      const a = SlabAllocator.empty()
      const { handle } = await a.allocate('MEDIUM', seq(1))
      expect(handle.chunk_index).toBe(0)
    })

    it('second allocation in same slab gets chunk_index=1', async () => {
      let a = SlabAllocator.empty()
      const r1 = await a.allocate('SMALL', seq(1))
      a = r1.allocator
      const { handle: h2 } = await a.allocate('SMALL', seq(2))
      expect(h2.chunk_index).toBe(1)
      expect(h2.slab_id).toBe(r1.handle.slab_id)
    })

    it('handle_hash deterministic x3 for same inputs', async () => {
      const hashes = await Promise.all([1, 2, 3].map(async () => {
        const a = SlabAllocator.empty()
        const { handle } = await a.allocate('TINY', seq(1))
        return handle.handle_hash
      }))
      expect(hashes[0]).toBe(hashes[1])
      expect(hashes[1]).toBe(hashes[2])
    })

    it('different tiers allocate independently', async () => {
      let a = SlabAllocator.empty()
      const rt = await a.allocate('TINY', seq(1))
      a = rt.allocator
      const rl = await a.allocate('LARGE', seq(2))
      a = rl.allocator
      expect(a.slabCount).toBe(2)
      expect(a.getSlabs('TINY')).toHaveLength(1)
      expect(a.getSlabs('LARGE')).toHaveLength(1)
    })

    it('fills first slab and overflows to second slab after 64 allocations', async () => {
      let a = SlabAllocator.empty()
      let lastHandle = null
      for (let i = 0; i < CHUNKS_PER_SLAB + 1; i++) {
        const { allocator, handle } = await a.allocate('TINY', seq(i + 1))
        a = allocator
        lastHandle = handle
      }
      expect(a.slabCount).toBe(2)
      expect(a.totalAllocated).toBe(CHUNKS_PER_SLAB + 1)
      // 65th handle is in the second slab
      expect(lastHandle!.chunk_index).toBe(0)
    }, 30_000)

    it('throws SlabAllocatorError when MAX_SLABS_PER_TIER exceeded', async () => {
      let a = SlabAllocator.empty()
      // Fill all 8 slabs × 64 chunks = 512 allocations
      for (let i = 0; i < MAX_SLABS_PER_TIER * CHUNKS_PER_SLAB; i++) {
        const { allocator } = await a.allocate('TINY', seq(i + 1))
        a = allocator
      }
      await expect(a.allocate('TINY', seq(9999))).rejects.toThrow(SlabAllocatorError)
    }, 60_000)
  })

  describe('release()', () => {
    it('releases a chunk and decrements totalAllocated', async () => {
      let a = SlabAllocator.empty()
      const { allocator: a1, handle } = await a.allocate('TINY', seq(1))
      const { allocator: a2 } = await a1.release(handle, seq(2))
      expect(a2.totalAllocated).toBe(0)
    })

    it('released chunk can be re-allocated', async () => {
      let a = SlabAllocator.empty()
      const r1 = await a.allocate('TINY', seq(1))
      a = r1.allocator
      const r2 = await a.release(r1.handle, seq(2))
      a = r2.allocator
      const r3 = await a.allocate('TINY', seq(3))
      expect(r3.handle.chunk_index).toBe(0)
      expect(r3.handle.slab_id).toBe(r1.handle.slab_id)
    })

    it('double-release throws SlabAllocatorError', async () => {
      let a = SlabAllocator.empty()
      const { allocator: a1, handle } = await a.allocate('TINY', seq(1))
      const { allocator: a2 } = await a1.release(handle, seq(2))
      await expect(a2.release(handle, seq(3))).rejects.toThrow(SlabAllocatorError)
    })

    it('release of unknown slab throws SlabAllocatorError', async () => {
      const a = SlabAllocator.empty()
      const { handle } = await a.allocate('TINY', seq(1))
      // Use the handle on the empty allocator (slab not registered there)
      await expect(a.release(handle, seq(2))).rejects.toThrow(SlabAllocatorError)
    })

    it('sets last_release_epoch on the slab', async () => {
      let a = SlabAllocator.empty()
      const { allocator: a1, handle } = await a.allocate('TINY', seq(1))
      const { allocator: a2 } = await a1.release(handle, seq(5))
      const slab = a2.getSlabs('TINY')[0]!
      expect(slab.last_release_epoch).toBe(seq(5))
    })
  })

  describe('decommissionEmpty()', () => {
    it('does not decommission a slab still within threshold', async () => {
      let a = SlabAllocator.empty()
      const { allocator: a1, handle } = await a.allocate('TINY', seq(1))
      const { allocator: a2 } = await a1.release(handle, seq(2))
      // epoch diff = 5 < SLAB_DECOMMISSION_THRESHOLD=8
      const { allocator: a3, decommissioned_count } = await a2.decommissionEmpty(seq(7))
      expect(decommissioned_count).toBe(0)
      expect(a3.getSlabs('TINY')[0]!.is_decommissioned).toBe(false)
    })

    it('decommissions an empty slab at exactly the threshold epoch', async () => {
      let a = SlabAllocator.empty()
      const { allocator: a1, handle } = await a.allocate('TINY', seq(1))
      const { allocator: a2 } = await a1.release(handle, seq(1))
      // epoch diff = 8 = SLAB_DECOMMISSION_THRESHOLD
      const { allocator: a3, decommissioned_count } = await a2.decommissionEmpty(seq(9))
      expect(decommissioned_count).toBe(1)
      expect(a3.getSlabs('TINY')[0]!.is_decommissioned).toBe(true)
    })

    it('does not decommission a slab that still has allocated chunks', async () => {
      let a = SlabAllocator.empty()
      const { allocator: a1, handle: h1 } = await a.allocate('TINY', seq(1))
      const { allocator: a2 } = await a1.allocate('TINY', seq(2))
      // Only release h1; h2 (chunk_index=1) still allocated
      const { allocator: a3 } = await a2.release(h1, seq(2))
      const { allocator: a4, decommissioned_count } = await a3.decommissionEmpty(seq(100))
      expect(decommissioned_count).toBe(0)
      expect(a4.getSlabs('TINY')[0]!.is_decommissioned).toBe(false)
    })

    it('never decommissions a slab with null last_release_epoch (never released)', async () => {
      const a = SlabAllocator.empty()
      const { allocator: a1 } = await a.allocate('TINY', seq(1))
      // Don't release — last_release_epoch stays null
      const { decommissioned_count } = await a1.decommissionEmpty(seq(1000))
      expect(decommissioned_count).toBe(0)
    })
  })

  describe('certify()', () => {
    it('produces a frozen SlabCertificate', async () => {
      const a = SlabAllocator.empty()
      const { allocator: a1 } = await a.allocate('TINY', seq(1))
      const cert = await a1.certify(seq(10))
      expect(Object.isFrozen(cert)).toBe(true)
    })

    it('allocator_hash is 64-char hex', async () => {
      const a = SlabAllocator.empty()
      const { allocator: a1 } = await a.allocate('TINY', seq(1))
      const cert = await a1.certify(seq(10))
      expect(cert.allocator_hash).toHaveLength(64)
      expect(/^[0-9a-f]{64}$/.test(cert.allocator_hash)).toBe(true)
    })

    it('certificate fields reflect allocator state', async () => {
      let a = SlabAllocator.empty()
      const { allocator: a1, handle: h1 } = await a.allocate('TINY', seq(1))
      const { allocator: a2 } = await a1.allocate('TINY', seq(2))
      const { allocator: a3 } = await a2.release(h1, seq(2))
      const { allocator: a4 } = await a3.decommissionEmpty(seq(100))
      const cert = await a4.certify(seq(10))
      expect(cert.slab_count).toBe(1)
      expect(cert.total_allocated).toBe(1)
      expect(cert.is_replay_reconstructable).toBe(true)
      expect(cert.schema_version).toBe(SLAB_SCHEMA_VERSION)
    })

    it('allocator_hash is deterministic x3', async () => {
      const hashes = await Promise.all([1, 2, 3].map(async () => {
        const a = SlabAllocator.empty()
        const { allocator: a1 } = await a.allocate('SMALL', seq(1))
        const cert = await a1.certify(seq(10))
        return cert.allocator_hash
      }))
      expect(hashes[0]).toBe(hashes[1])
      expect(hashes[1]).toBe(hashes[2])
    })

    it('different allocation states produce different allocator_hashes', async () => {
      const a = SlabAllocator.empty()
      const cert0 = await a.certify(seq(10))
      const { allocator: a1 } = await a.allocate('TINY', seq(1))
      const cert1 = await a1.certify(seq(10))
      expect(cert0.allocator_hash).not.toBe(cert1.allocator_hash)
    })
  })
})
