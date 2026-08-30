// ============================================================
// Gate 24 — Byzantine Transport Interface Tests (~20 tests)
// EPISTEMIC TIER: T2
//
// Tests cover:
//   - DeterministicMessageQueue: enqueue, drain, dedup, anti-equivocation
//   - ByzantineSimulation: safe/unsafe outcomes, drops, BFT quorum guard
//   - NetworkKernel: broadcastVote, computeMessageId determinism
//
// Fixed timestamp: 1_600_000_000_000 — never Date.now()
// All state objects are verified to be frozen.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import {
  type PeerId,
  type MessageId,
  type ReplayMessage,
  type NetworkConfig,
  NetworkError,
} from '../../src/network/types.js'
import { DeterministicMessageQueue } from '../../src/network/queue.js'
import { simulate } from '../../src/network/simulation.js'
import { computeMessageId, broadcastVote } from '../../src/network/kernel.js'

// ─── Helpers ───────────────────────────────────────────────

const TS = 1_600_000_000_000

function peer(name: string): PeerId {
  return name as PeerId
}

function hash(hex: string): SHA256Hex {
  return hex.padStart(64, '0') as SHA256Hex
}

function seq(n: bigint): SequenceNumber {
  return n as SequenceNumber
}

function msgId(s: string): MessageId {
  return s as MessageId
}

function makeMsg(
  id: string,
  sender: string,
  recipient: string,
  payloadHex: string,
  sequence: bigint,
): ReplayMessage {
  return Object.freeze({
    message_id: msgId(id),
    sender: peer(sender),
    recipient: peer(recipient),
    payload_hash: hash(payloadHex),
    sequence: seq(sequence),
    timestamp_ms: TS,
  })
}

function makeConfig(peerNames: string[], f: number): NetworkConfig {
  return Object.freeze({
    peers: peerNames.map(peer),
    max_byzantine_peers: f,
    message_ttl_sequence: 10,
  })
}

// ─── DeterministicMessageQueue ─────────────────────────────

describe('DeterministicMessageQueue', () => {
  it('starts empty with size 0', () => {
    const q = DeterministicMessageQueue.create()
    expect(q.size).toBe(0)
  })

  it('enqueues a single message as DELIVERED', () => {
    const q = DeterministicMessageQueue.create()
    const msg = makeMsg('msg-b', 'A', 'B', 'aabb', 1n)
    const [q2, result] = q.enqueue(msg)
    expect(result.status).toBe('DELIVERED')
    expect(q2.size).toBe(1)
  })

  it('drains messages in lexicographic message_id order', () => {
    let q = DeterministicMessageQueue.create()
    // Enqueue in reverse lexicographic order
    ;[
      makeMsg('msg-c', 'A', 'C', 'cccc', 3n),
      makeMsg('msg-a', 'A', 'A', 'aaaa', 1n),
      makeMsg('msg-b', 'A', 'B', 'bbbb', 2n),
    ].forEach(m => {
      const [next] = q.enqueue(m)
      q = next
    })
    const [empty, msgs] = q.drain()
    expect(msgs.map(m => m.message_id)).toEqual(['msg-a', 'msg-b', 'msg-c'])
    expect(empty.size).toBe(0)
  })

  it('returns DUPLICATE for re-enqueuing the same message_id', () => {
    const msg = makeMsg('dup-msg', 'X', 'Y', 'deadbeef', 5n)
    let q = DeterministicMessageQueue.create()
    const [q2] = q.enqueue(msg)
    q = q2
    const [q3, result] = q.enqueue(msg)
    expect(result.status).toBe('DUPLICATE')
    expect(q3.size).toBe(1) // still 1, not 2
  })

  it('allows retransmit of same (sender, seq, payload_hash) without error', () => {
    // Same payload_hash for same (sender, sequence) is a retransmit, not equivocation
    const msg1 = makeMsg('id-1', 'P', 'Q', 'cafebabe', 7n)
    const msg2 = makeMsg('id-2', 'P', 'Q', 'cafebabe', 7n) // different message_id, same key
    let q = DeterministicMessageQueue.create()
    const [q2] = q.enqueue(msg1)
    q = q2
    expect(() => q.enqueue(msg2)).not.toThrow()
  })

  it('throws NetworkError on anti-equivocation violation', () => {
    // Same (sender, sequence) but different payload_hash — Byzantine equivocation
    const msg1 = makeMsg('id-1', 'Byzantine', 'R', 'aaaaaa', 3n)
    const msg2 = makeMsg('id-2', 'Byzantine', 'R', 'bbbbbb', 3n) // same sender+seq, different hash
    let q = DeterministicMessageQueue.create()
    const [q2] = q.enqueue(msg1)
    q = q2
    expect(() => q.enqueue(msg2)).toThrowError(NetworkError)
  })

  it('drain returns empty array from empty queue', () => {
    const q = DeterministicMessageQueue.create()
    const [, msgs] = q.drain()
    expect(msgs).toHaveLength(0)
  })

  it('queue is immutable — original queue unchanged after enqueue', () => {
    const q = DeterministicMessageQueue.create()
    const msg = makeMsg('im-msg', 'A', 'B', '1234', 1n)
    const [q2] = q.enqueue(msg)
    expect(q.size).toBe(0)   // original unchanged
    expect(q2.size).toBe(1)
  })

  it('multiple messages from same sender with different sequences are allowed', () => {
    let q = DeterministicMessageQueue.create()
    for (let i = 0n; i < 5n; i++) {
      const msg = makeMsg(`msg-${i}`, 'sender', 'recv', `hash${i}`, i)
      const [next, result] = q.enqueue(msg)
      q = next
      expect(result.status).toBe('DELIVERED')
    }
    expect(q.size).toBe(5)
  })
})

// ─── ByzantineSimulation ───────────────────────────────────

describe('ByzantineSimulation', () => {
  it('all honest peers → is_safe=true, all delivered', () => {
    const config = makeConfig(['A', 'B', 'C', 'D'], 1) // n=4 >= 3*1+1=4
    const messages = [
      makeMsg('m1', 'A', 'B', 'hash1', 1n),
      makeMsg('m2', 'A', 'C', 'hash1', 1n),
      makeMsg('m3', 'A', 'D', 'hash1', 1n),
    ]
    const result = simulate(config, messages)
    expect(result.is_safe).toBe(true)
    expect(result.equivocations).toBe(0)
    expect(result.delivered).toHaveLength(3)
    expect(result.dropped).toHaveLength(0)
  })

  it('equivocation by Byzantine peer → is_safe=false', () => {
    const config = makeConfig(['A', 'B', 'C', 'D'], 1)
    const messages = [
      makeMsg('m1', 'A', 'B', 'hash-honest', 1n),
      // Byzantine: same sender 'A', same sequence 1, different payload_hash
      makeMsg('m2', 'A', 'C', 'hash-byzantine', 1n),
    ]
    const result = simulate(config, messages)
    expect(result.is_safe).toBe(false)
    expect(result.equivocations).toBeGreaterThan(0)
  })

  it('message to unknown peer is dropped', () => {
    const config = makeConfig(['A', 'B', 'C', 'D'], 1)
    const messages = [
      makeMsg('m-known', 'A', 'B', 'hash1', 1n),
      makeMsg('m-unknown', 'A', 'UNKNOWN', 'hash1', 2n),
    ]
    const result = simulate(config, messages)
    expect(result.dropped).toHaveLength(1)
    expect(result.dropped[0]?.message_id).toBe('m-unknown')
    expect(result.delivered).toHaveLength(1)
  })

  it('rejects BFT config violating n >= 3f+1', () => {
    // n=3, f=1: 3 < 3*1+1=4 → should throw
    const config = makeConfig(['A', 'B', 'C'], 1)
    expect(() => simulate(config, [])).toThrowError(NetworkError)
  })

  it('empty message list produces empty result', () => {
    const config = makeConfig(['A', 'B', 'C', 'D'], 1)
    const result = simulate(config, [])
    expect(result.delivered).toHaveLength(0)
    expect(result.dropped).toHaveLength(0)
    expect(result.equivocations).toBe(0)
    expect(result.is_safe).toBe(true)
  })

  it('result object is frozen', () => {
    const config = makeConfig(['A', 'B', 'C', 'D'], 1)
    const result = simulate(config, [])
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('duplicate message_id counted once in delivered', () => {
    const config = makeConfig(['A', 'B', 'C', 'D'], 1)
    const msg = makeMsg('dup', 'A', 'B', 'hash1', 1n)
    const result = simulate(config, [msg, msg])
    // Duplicate is silently ignored, not dropped
    expect(result.delivered).toHaveLength(1)
  })

  it('same inputs produce same output (pure function)', () => {
    const config = makeConfig(['A', 'B', 'C', 'D'], 1)
    const messages = [
      makeMsg('m1', 'A', 'B', 'hash1', 1n),
      makeMsg('m2', 'B', 'C', 'hash2', 2n),
    ]
    const r1 = simulate(config, messages)
    const r2 = simulate(config, messages)
    expect(r1.delivered.map(m => m.message_id)).toEqual(r2.delivered.map(m => m.message_id))
    expect(r1.equivocations).toBe(r2.equivocations)
    expect(r1.is_safe).toBe(r2.is_safe)
  })
})

// ─── NetworkKernel ─────────────────────────────────────────

describe('NetworkKernel — computeMessageId', () => {
  it('returns a deterministic MessageId', () => {
    const id1 = computeMessageId(peer('A'), peer('B'), hash('aabb'), seq(1n))
    const id2 = computeMessageId(peer('A'), peer('B'), hash('aabb'), seq(1n))
    expect(id1).toBe(id2)
  })

  it('different recipients produce different ids', () => {
    const id1 = computeMessageId(peer('A'), peer('B'), hash('aabb'), seq(1n))
    const id2 = computeMessageId(peer('A'), peer('C'), hash('aabb'), seq(1n))
    expect(id1).not.toBe(id2)
  })

  it('different sequences produce different ids', () => {
    const id1 = computeMessageId(peer('A'), peer('B'), hash('aabb'), seq(1n))
    const id2 = computeMessageId(peer('A'), peer('B'), hash('aabb'), seq(2n))
    expect(id1).not.toBe(id2)
  })

  it('different payload hashes produce different ids', () => {
    const id1 = computeMessageId(peer('A'), peer('B'), hash('aabb'), seq(1n))
    const id2 = computeMessageId(peer('A'), peer('B'), hash('ccdd'), seq(1n))
    expect(id1).not.toBe(id2)
  })
})

describe('NetworkKernel — broadcastVote', () => {
  it('produces one message per non-sender peer', () => {
    const config = makeConfig(['A', 'B', 'C', 'D'], 1)
    const msgs = broadcastVote(peer('A'), hash('vote1'), seq(1n), TS, config)
    // A is the sender, so 3 recipients: B, C, D
    expect(msgs).toHaveLength(3)
  })

  it('no message sent to the sender itself', () => {
    const config = makeConfig(['A', 'B', 'C', 'D'], 1)
    const msgs = broadcastVote(peer('A'), hash('vote1'), seq(1n), TS, config)
    expect(msgs.every(m => m.sender !== m.recipient)).toBe(true)
    expect(msgs.every(m => m.recipient !== peer('A'))).toBe(true)
  })

  it('all messages carry the correct sender and payload_hash', () => {
    const config = makeConfig(['A', 'B', 'C', 'D'], 1)
    const ph = hash('deadbeef')
    const msgs = broadcastVote(peer('A'), ph, seq(5n), TS, config)
    msgs.forEach(m => {
      expect(m.sender).toBe('A')
      expect(m.payload_hash).toBe(ph)
      expect(m.sequence).toBe(5n)
      expect(m.timestamp_ms).toBe(TS)
    })
  })

  it('message_ids are deterministic across identical calls', () => {
    const config = makeConfig(['A', 'B', 'C', 'D'], 1)
    const msgs1 = broadcastVote(peer('A'), hash('v1'), seq(1n), TS, config)
    const msgs2 = broadcastVote(peer('A'), hash('v1'), seq(1n), TS, config)
    expect(msgs1.map(m => m.message_id)).toEqual(msgs2.map(m => m.message_id))
  })

  it('all output messages are frozen', () => {
    const config = makeConfig(['A', 'B', 'C', 'D'], 1)
    const msgs = broadcastVote(peer('A'), hash('v1'), seq(1n), TS, config)
    msgs.forEach(m => expect(Object.isFrozen(m)).toBe(true))
  })

  it('output array is sorted by recipient peer id (deterministic ordering)', () => {
    // Use makeConfig with unordered list including sender 'X'
    const config = makeConfig(['D', 'B', 'A', 'C', 'X'], 1) // intentionally unordered, n=5 >= 3*1+1=4
    const msgs = broadcastVote(peer('X'), hash('v1'), seq(1n), TS, config)
    const recipients = msgs.map(m => m.recipient)
    const sorted = [...recipients].sort()
    expect(recipients).toEqual(sorted)
  })
})
