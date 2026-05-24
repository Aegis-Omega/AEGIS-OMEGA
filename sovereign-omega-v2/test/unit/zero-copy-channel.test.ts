// test/unit/zero-copy-channel.test.ts
// Gate 196 — ZeroCopyChannel (zero-copy inter-fiber communication)
// EPISTEMIC TIER: T2
//
// Constitutional translation of the Dual-Viewport Zero-Copy IMC spec.
// Validates: send/receive/release lifecycle, duplicate guards, auto-release,
// channel audit chain, determinism.

import { describe, it, expect } from 'vitest'
import {
  ZeroCopyChannel,
  ChannelError,
  CHANNEL_SCHEMA_VERSION,
} from '../../src/memory/zero-copy-channel.js'
import { SlabAllocator } from '../../src/memory/slab-allocator.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import type { SlabChunkHandle } from '../../src/memory/slab-allocator.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

async function freshHandle(s = 1): Promise<SlabChunkHandle> {
  const { handle } = await SlabAllocator.empty().allocate('TINY', seq(s))
  return handle
}

describe('Gate 196 — ZeroCopyChannel', () => {

  describe('Constants', () => {
    it('CHANNEL_SCHEMA_VERSION is 1.0.0', () => {
      expect(CHANNEL_SCHEMA_VERSION).toBe('1.0.0')
    })

    it('ChannelError is Error subclass with correct name', () => {
      const err = new ChannelError('x')
      expect(err).toBeInstanceOf(Error)
      expect(err.name).toBe('ChannelError')
    })
  })

  describe('ZeroCopyChannel.create()', () => {
    it('starts with pendingCount=0 and totalSent=0', () => {
      const ch = ZeroCopyChannel.create('universe-A', 'universe-B')
      expect(ch.pendingCount).toBe(0)
      expect(ch.totalSent).toBe(0)
    })

    it('getMessages returns empty array initially', () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      expect(ch.getMessages()).toHaveLength(0)
    })
  })

  describe('send()', () => {
    it('returns a frozen ChannelMessage with correct fields', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      const handle = await freshHandle(1)
      const { message } = await ch.send(handle, seq(1))
      expect(Object.isFrozen(message)).toBe(true)
      expect(message.producer_id).toBe('A')
      expect(message.consumer_id).toBe('B')
      expect(message.is_claimed).toBe(false)
      expect(message.schema_version).toBe(CHANNEL_SCHEMA_VERSION)
      expect(message.is_replay_reconstructable).toBe(true)
    })

    it('message_id is 64-char hex', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      const { message } = await ch.send(await freshHandle(1), seq(1))
      expect(message.message_id).toHaveLength(64)
      expect(/^[0-9a-f]{64}$/.test(message.message_id)).toBe(true)
    })

    it('message_hash is 64-char hex', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      const { message } = await ch.send(await freshHandle(1), seq(1))
      expect(message.message_hash).toHaveLength(64)
      expect(/^[0-9a-f]{64}$/.test(message.message_hash)).toBe(true)
    })

    it('pendingCount=1 and totalSent=1 after send', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      const { channel } = await ch.send(await freshHandle(1), seq(1))
      expect(channel.pendingCount).toBe(1)
      expect(channel.totalSent).toBe(1)
    })

    it('original channel unchanged (immutable pattern)', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      await ch.send(await freshHandle(1), seq(1))
      expect(ch.pendingCount).toBe(0)
      expect(ch.totalSent).toBe(0)
    })

    it('message_id is deterministic x3 for same inputs', async () => {
      const handle = await freshHandle(1)
      const ids = await Promise.all([1, 2, 3].map(async () => {
        const ch = ZeroCopyChannel.create('A', 'B')
        const { message } = await ch.send(handle, seq(1))
        return message.message_id
      }))
      expect(ids[0]).toBe(ids[1])
      expect(ids[1]).toBe(ids[2])
    })

    it('different sequences produce different message_ids', async () => {
      const handle = await freshHandle(1)
      const ch = ZeroCopyChannel.create('A', 'B')
      const { message: m1 } = await ch.send(handle, seq(1))
      const { message: m2 } = await ch.send(handle, seq(2))
        .catch(() => null)
        .then(async () => {
          // handle is same, but sequence differs — use a fresh handle for seq(2)
          const h2 = await freshHandle(2)
          return ch.send(h2, seq(2))
        })
      expect(m1.message_id).not.toBe(m2.message_id)
    })

    it('throws ChannelError on duplicate handle in flight', async () => {
      const handle = await freshHandle(1)
      const ch = ZeroCopyChannel.create('A', 'B')
      const { channel } = await ch.send(handle, seq(1))
      await expect(channel.send(handle, seq(2))).rejects.toThrow(ChannelError)
    })

    it('handle payload is carried by reference (zero-copy: handle_hash preserved)', async () => {
      const handle = await freshHandle(1)
      const ch = ZeroCopyChannel.create('A', 'B')
      const { message } = await ch.send(handle, seq(1))
      expect(message.handle.handle_hash).toBe(handle.handle_hash)
      expect(message.handle.slab_id).toBe(handle.slab_id)
      expect(message.handle.chunk_index).toBe(handle.chunk_index)
    })
  })

  describe('receive()', () => {
    it('marks message as claimed (is_claimed=true)', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      const { channel: ch1, message: m1 } = await ch.send(await freshHandle(1), seq(1))
      const { message: m2 } = await ch1.receive(m1.message_id, seq(2))
      expect(m2.is_claimed).toBe(true)
    })

    it('pendingCount stays 1 after receive (message stays pending until release)', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      const { channel: ch1, message } = await ch.send(await freshHandle(1), seq(1))
      const { channel: ch2 } = await ch1.receive(message.message_id, seq(2))
      expect(ch2.pendingCount).toBe(1)
    })

    it('throws ChannelError on unknown message_id', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      await expect(ch.receive('ab'.repeat(32) as SHA256Hex, seq(1))).rejects.toThrow(ChannelError)
    })

    it('throws ChannelError on already-claimed message', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      const { channel: ch1, message } = await ch.send(await freshHandle(1), seq(1))
      const { channel: ch2 } = await ch1.receive(message.message_id, seq(2))
      await expect(ch2.receive(message.message_id, seq(3))).rejects.toThrow(ChannelError)
    })
  })

  describe('release()', () => {
    it('removes message from pending (pendingCount=0)', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      const { channel: ch1, message } = await ch.send(await freshHandle(1), seq(1))
      const { channel: ch2 } = await ch1.receive(message.message_id, seq(2))
      const { channel: ch3 } = await ch2.release(message.message_id, seq(3))
      expect(ch3.pendingCount).toBe(0)
    })

    it('totalSent remains 1 after release (tracks history)', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      const { channel: ch1, message } = await ch.send(await freshHandle(1), seq(1))
      const { channel: ch2 } = await ch1.receive(message.message_id, seq(2))
      const { channel: ch3 } = await ch2.release(message.message_id, seq(3))
      expect(ch3.totalSent).toBe(1)
    })

    it('throws ChannelError on release without prior claim', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      const { channel: ch1, message } = await ch.send(await freshHandle(1), seq(1))
      await expect(ch1.release(message.message_id, seq(2))).rejects.toThrow(ChannelError)
    })

    it('throws ChannelError on unknown message_id', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      await expect(ch.release('cd'.repeat(32) as SHA256Hex, seq(1))).rejects.toThrow(ChannelError)
    })
  })

  describe('Full lifecycle: send → receive → release', () => {
    it('completes without error and leaves channel empty', async () => {
      let ch = ZeroCopyChannel.create('producer', 'consumer')
      const h1 = await freshHandle(1)
      const h2 = await freshHandle(2)

      const r1 = await ch.send(h1, seq(1)); ch = r1.channel
      const r2 = await ch.send(h2, seq(2)); ch = r2.channel
      expect(ch.pendingCount).toBe(2); expect(ch.totalSent).toBe(2)

      const r3 = await ch.receive(r1.message.message_id, seq(3)); ch = r3.channel
      const r4 = await ch.receive(r2.message.message_id, seq(4)); ch = r4.channel

      const r5 = await ch.release(r3.message.message_id, seq(5)); ch = r5.channel
      const r6 = await ch.release(r4.message.message_id, seq(6)); ch = r6.channel

      expect(ch.pendingCount).toBe(0)
      expect(ch.totalSent).toBe(2)
    })
  })

  describe('autoRelease()', () => {
    it('removes all messages involving the crashed universe', async () => {
      let ch = ZeroCopyChannel.create('A', 'B')
      const h1 = await freshHandle(1)
      const h2 = await freshHandle(2)
      const r1 = await ch.send(h1, seq(1)); ch = r1.channel
      const r2 = await ch.send(h2, seq(2)); ch = r2.channel
      // Claim one
      const r3 = await ch.receive(r1.message.message_id, seq(3)); ch = r3.channel

      // Consumer 'B' crashes
      const { channel: ch2, released_count } = await ch.autoRelease('B', seq(4))
      expect(released_count).toBe(2)  // both messages removed
      expect(ch2.pendingCount).toBe(0)
    })

    it('released_count=0 when no messages involve the crashed universe', async () => {
      let ch = ZeroCopyChannel.create('A', 'B')
      const { channel } = await ch.send(await freshHandle(1), seq(1))
      const { released_count } = await channel.autoRelease('C', seq(2))
      expect(released_count).toBe(0)
      expect(channel.pendingCount).toBe(1)
    })

    it('auto-release is idempotent (second call finds nothing to release)', async () => {
      let ch = ZeroCopyChannel.create('A', 'B')
      const r1 = await ch.send(await freshHandle(1), seq(1)); ch = r1.channel
      const { channel: ch2 } = await ch.autoRelease('A', seq(2))
      const { released_count } = await ch2.autoRelease('A', seq(3))
      expect(released_count).toBe(0)
    })
  })

  describe('certify()', () => {
    it('produces a frozen ChannelCertificate', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      const { channel } = await ch.send(await freshHandle(1), seq(1))
      const cert = await channel.certify(seq(10))
      expect(Object.isFrozen(cert)).toBe(true)
    })

    it('channel_hash is 64-char hex', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      const cert = await ch.certify(seq(10))
      expect(cert.channel_hash).toHaveLength(64)
      expect(/^[0-9a-f]{64}$/.test(cert.channel_hash)).toBe(true)
    })

    it('certificate fields reflect channel state', async () => {
      let ch = ZeroCopyChannel.create('P', 'C')
      const r1 = await ch.send(await freshHandle(1), seq(1)); ch = r1.channel
      const r2 = await ch.send(await freshHandle(2), seq(2)); ch = r2.channel
      // release one
      const r3 = await ch.receive(r1.message.message_id, seq(3)); ch = r3.channel
      const r4 = await ch.release(r3.message.message_id, seq(4)); ch = r4.channel

      const cert = await ch.certify(seq(10))
      expect(cert.pending_count).toBe(1)
      expect(cert.total_sent).toBe(2)
      expect(cert.producer_id).toBe('P')
      expect(cert.consumer_id).toBe('C')
      expect(cert.is_replay_reconstructable).toBe(true)
    })

    it('channel_hash is deterministic x3', async () => {
      const hashes = await Promise.all([1, 2, 3].map(async () => {
        const ch = ZeroCopyChannel.create('A', 'B')
        const { channel } = await ch.send(await freshHandle(1), seq(1))
        return (await channel.certify(seq(10))).channel_hash
      }))
      expect(hashes[0]).toBe(hashes[1])
      expect(hashes[1]).toBe(hashes[2])
    })

    it('different pending states produce different channel_hashes', async () => {
      const ch = ZeroCopyChannel.create('A', 'B')
      const cert0 = await ch.certify(seq(10))
      const { channel } = await ch.send(await freshHandle(1), seq(1))
      const cert1 = await channel.certify(seq(10))
      expect(cert0.channel_hash).not.toBe(cert1.channel_hash)
    })
  })
})
