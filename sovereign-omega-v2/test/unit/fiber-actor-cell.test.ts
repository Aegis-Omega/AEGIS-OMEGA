// test/unit/fiber-actor-cell.test.ts
// Gate 198 — FiberActorCell (isolated fiber execution unit with Grace Loop)
// EPISTEMIC TIER: T2
//
// Constitutional translation of the Fiber Actor Cell with Grace Loop spec.
// Validates: ACTIVE→TERMINATED lifecycle, deposit/consume/terminate, Grace Loop
// autoRelease, joint FiberCertificate, determinism, immutable pattern.

import { describe, it, expect } from 'vitest'
import {
  FiberActorCell,
  FiberError,
  FIBER_SCHEMA_VERSION,
} from '../../src/memory/fiber-actor-cell.js'
import { SlabAllocator } from '../../src/memory/slab-allocator.js'
import { ChannelError } from '../../src/memory/zero-copy-channel.js'
import type { SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

async function producerHandle(s = 1, tier: 'TINY' | 'SMALL' | 'MEDIUM' | 'LARGE' = 'TINY') {
  const { handle } = await SlabAllocator.empty().allocate(tier, seq(s))
  return handle
}

describe('Gate 198 — FiberActorCell', () => {

  describe('Constants', () => {
    it('FIBER_SCHEMA_VERSION is 1.0.0', () => {
      expect(FIBER_SCHEMA_VERSION).toBe('1.0.0')
    })

    it('FiberError is Error subclass', () => {
      expect(new FiberError('x')).toBeInstanceOf(Error)
    })

    it('FiberError name is FiberError', () => {
      expect(new FiberError('x').name).toBe('FiberError')
    })
  })

  describe('FiberActorCell.create()', () => {
    it('starts with pendingMessages=0', () => {
      const cell = FiberActorCell.create('fiber-A', 'producer-P')
      expect(cell.pendingMessages).toBe(0)
    })

    it('starts with allocatedChunks=0', () => {
      const cell = FiberActorCell.create('fiber-A', 'producer-P')
      expect(cell.allocatedChunks).toBe(0)
    })

    it('starts with isTerminated=false', () => {
      const cell = FiberActorCell.create('fiber-A', 'producer-P')
      expect(cell.isTerminated).toBe(false)
    })

    it('actorId matches constructor argument', () => {
      const cell = FiberActorCell.create('my-fiber', 'my-producer')
      expect(cell.actorId).toBe('my-fiber')
    })
  })

  describe('deposit()', () => {
    it('pendingMessages increments to 1 after deposit', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h = await producerHandle(1)
      const { cell: c1 } = await cell.deposit(h, seq(1)); cell = c1
      expect(cell.pendingMessages).toBe(1)
    })

    it('returns a 64-char hex message_id', async () => {
      const cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h = await producerHandle(1)
      const { message_id } = await cell.deposit(h, seq(1))
      expect(message_id).toHaveLength(64)
      expect(/^[0-9a-f]{64}$/.test(message_id)).toBe(true)
    })

    it('original cell unchanged (immutable pattern)', async () => {
      const cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h = await producerHandle(1)
      await cell.deposit(h, seq(1))
      expect(cell.pendingMessages).toBe(0)
    })

    it('two deposits: pendingMessages=2', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h1 = await producerHandle(1)
      const h2 = await producerHandle(2)
      const { cell: c1 } = await cell.deposit(h1, seq(1)); cell = c1
      const { cell: c2 } = await cell.deposit(h2, seq(2)); cell = c2
      expect(cell.pendingMessages).toBe(2)
    })

    it('throws FiberError when fiber is TERMINATED', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const { cell: c1 } = await cell.terminate(seq(1)); cell = c1
      const h = await producerHandle(2)
      await expect(cell.deposit(h, seq(2))).rejects.toThrow(FiberError)
    })

    it('throws ChannelError on duplicate handle in flight', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h = await producerHandle(1)
      const { cell: c1 } = await cell.deposit(h, seq(1)); cell = c1
      await expect(cell.deposit(h, seq(2))).rejects.toThrow(ChannelError)
    })
  })

  describe('consume()', () => {
    it('pendingMessages=0 after consume (receive+release completes cycle)', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h = await producerHandle(1)
      const { cell: c1, message_id } = await cell.deposit(h, seq(1)); cell = c1
      const { cell: c2 } = await cell.consume(message_id, 'TINY', seq(2)); cell = c2
      expect(cell.pendingMessages).toBe(0)
    })

    it('allocatedChunks=1 after consume (fiber allocates work chunk)', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h = await producerHandle(1)
      const { cell: c1, message_id } = await cell.deposit(h, seq(1)); cell = c1
      const { cell: c2 } = await cell.consume(message_id, 'TINY', seq(2)); cell = c2
      expect(cell.allocatedChunks).toBe(1)
    })

    it('work_handle has the requested tier', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h = await producerHandle(1)
      const { cell: c1, message_id } = await cell.deposit(h, seq(1)); cell = c1
      const { work_handle } = await cell.consume(message_id, 'MEDIUM', seq(2))
      expect(work_handle.tier).toBe('MEDIUM')
    })

    it('work_handle handle_hash is 64-char hex', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h = await producerHandle(1)
      const { cell: c1, message_id } = await cell.deposit(h, seq(1)); cell = c1
      const { work_handle } = await cell.consume(message_id, 'SMALL', seq(2))
      expect(work_handle.handle_hash).toHaveLength(64)
    })

    it('original cell unchanged after consume (immutable pattern)', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h = await producerHandle(1)
      const { cell: c1, message_id } = await cell.deposit(h, seq(1)); cell = c1
      await cell.consume(message_id, 'TINY', seq(2))
      expect(cell.pendingMessages).toBe(1) // original still has the message
      expect(cell.allocatedChunks).toBe(0) // original has no work chunks
    })

    it('throws FiberError when fiber is TERMINATED', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h = await producerHandle(1)
      const { cell: c1, message_id } = await cell.deposit(h, seq(1)); cell = c1
      const { cell: c2 } = await cell.terminate(seq(2)); cell = c2
      await expect(cell.consume(message_id, 'TINY', seq(3))).rejects.toThrow(FiberError)
    })

    it('throws ChannelError on unknown message_id', async () => {
      const cell = FiberActorCell.create('fiber-A', 'prod-P')
      const fakeId = 'ab'.repeat(32) as any
      await expect(cell.consume(fakeId, 'TINY', seq(1))).rejects.toThrow(ChannelError)
    })
  })

  describe('Full deposit → consume lifecycle', () => {
    it('complete single message cycle leaves pendingMessages=0, allocatedChunks=1', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h = await producerHandle(1)
      const { cell: c1, message_id } = await cell.deposit(h, seq(1)); cell = c1
      const { cell: c2 } = await cell.consume(message_id, 'TINY', seq(2)); cell = c2
      expect(cell.pendingMessages).toBe(0)
      expect(cell.allocatedChunks).toBe(1)
      expect(cell.isTerminated).toBe(false)
    })

    it('two messages processed sequentially: pendingMessages=0, allocatedChunks=2', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h1 = await producerHandle(1)
      const h2 = await producerHandle(2)

      const { cell: c1, message_id: id1 } = await cell.deposit(h1, seq(1)); cell = c1
      const { cell: c2, message_id: id2 } = await cell.deposit(h2, seq(2)); cell = c2
      const { cell: c3 } = await cell.consume(id1, 'TINY', seq(3)); cell = c3
      const { cell: c4 } = await cell.consume(id2, 'SMALL', seq(4)); cell = c4

      expect(cell.pendingMessages).toBe(0)
      expect(cell.allocatedChunks).toBe(2)
    })
  })

  describe('terminate() — Grace Loop', () => {
    it('released_count equals number of pending messages', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h1 = await producerHandle(1)
      const h2 = await producerHandle(2)
      const { cell: c1 } = await cell.deposit(h1, seq(1)); cell = c1
      const { cell: c2 } = await cell.deposit(h2, seq(2)); cell = c2
      const { released_count } = await cell.terminate(seq(3))
      expect(released_count).toBe(2)
    })

    it('isTerminated=true after terminate', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const { cell: c1 } = await cell.terminate(seq(1)); cell = c1
      expect(cell.isTerminated).toBe(true)
    })

    it('pendingMessages=0 after terminate', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h = await producerHandle(1)
      const { cell: c1 } = await cell.deposit(h, seq(1)); cell = c1
      const { cell: c2 } = await cell.terminate(seq(2)); cell = c2
      expect(cell.pendingMessages).toBe(0)
    })

    it('terminate is idempotent (second call: released_count=0, still TERMINATED)', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h = await producerHandle(1)
      const { cell: c1 } = await cell.deposit(h, seq(1)); cell = c1
      const { cell: c2 } = await cell.terminate(seq(2)); cell = c2
      const { cell: c3, released_count } = await cell.terminate(seq(3)); cell = c3
      expect(released_count).toBe(0)
      expect(cell.isTerminated).toBe(true)
    })

    it('released_count=0 when no messages in flight', async () => {
      const cell = FiberActorCell.create('fiber-A', 'prod-P')
      const { released_count } = await cell.terminate(seq(1))
      expect(released_count).toBe(0)
    })
  })

  describe('certify()', () => {
    it('produces a frozen FiberCertificate', async () => {
      const cell = FiberActorCell.create('fiber-A', 'prod-P')
      const cert = await cell.certify(seq(10))
      expect(Object.isFrozen(cert)).toBe(true)
    })

    it('fiber_hash is 64-char hex', async () => {
      const cell = FiberActorCell.create('fiber-A', 'prod-P')
      const cert = await cell.certify(seq(10))
      expect(cert.fiber_hash).toHaveLength(64)
      expect(/^[0-9a-f]{64}$/.test(cert.fiber_hash)).toBe(true)
    })

    it('fields reflect cell state (after deposit+consume)', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const h = await producerHandle(1)
      const { cell: c1, message_id } = await cell.deposit(h, seq(1)); cell = c1
      const { cell: c2 } = await cell.consume(message_id, 'SMALL', seq(2)); cell = c2
      const cert = await cell.certify(seq(10))
      expect(cert.actor_id).toBe('fiber-A')
      expect(cert.channel_pending).toBe(0)
      expect(cert.channel_total_sent).toBe(1)
      expect(cert.slab_allocated).toBe(1)
      expect(cert.is_terminated).toBe(false)
      expect(cert.is_replay_reconstructable).toBe(true)
      expect(cert.schema_version).toBe(FIBER_SCHEMA_VERSION)
    })

    it('is_terminated=true reflected in certificate after terminate', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const { cell: c1 } = await cell.terminate(seq(1)); cell = c1
      const cert = await cell.certify(seq(10))
      expect(cert.is_terminated).toBe(true)
    })

    it('fiber_hash is deterministic ×3 for same cell state', async () => {
      const hashes = await Promise.all([1, 2, 3].map(async () => {
        const cell = FiberActorCell.create('fiber-A', 'prod-P')
        return (await cell.certify(seq(10))).fiber_hash
      }))
      expect(hashes[0]).toBe(hashes[1])
      expect(hashes[1]).toBe(hashes[2])
    })

    it('different actor_ids produce different fiber_hashes', async () => {
      const c1 = FiberActorCell.create('fiber-A', 'prod-P')
      const c2 = FiberActorCell.create('fiber-B', 'prod-P')
      const cert1 = await c1.certify(seq(10))
      const cert2 = await c2.certify(seq(10))
      expect(cert1.fiber_hash).not.toBe(cert2.fiber_hash)
    })

    it('pre-terminate and post-terminate produce different fiber_hashes', async () => {
      let cell = FiberActorCell.create('fiber-A', 'prod-P')
      const certBefore = await cell.certify(seq(10))
      const { cell: c1 } = await cell.terminate(seq(1)); cell = c1
      const certAfter = await cell.certify(seq(10))
      expect(certBefore.fiber_hash).not.toBe(certAfter.fiber_hash)
    })
  })
})
