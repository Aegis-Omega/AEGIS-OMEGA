// ============================================================
// SOVEREIGN OMEGA — Event Segment & Merkle Anchoring tests
// EPISTEMIC TIER: T0
//
// Tests for event/segment.ts:
//   buildSegment          — fields, merkle_root, empty-throws
//   verifySegment         — valid, count-mismatch, tamper detection
//   partitionIntoSegments — chunking, default size, empty input
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  buildSegment,
  verifySegment,
  partitionIntoSegments,
} from '../../src/event/segment.js'
import { EventType, RetentionClass } from '../../src/core/types.js'
import type { EventEnvelope, UUIDv7, SHA256Hex, SequenceNumber } from '../../src/core/types.js'

const H = '0'.repeat(64) as SHA256Hex
const STREAM = 'stream-01' as UUIDv7

function makeEnvelope(seq: number): EventEnvelope {
  return Object.freeze({
    event_id: `evt-${seq}` as UUIDv7,
    stream_id: STREAM,
    event_type: EventType.RESPONSE_GENERATED,
    timestamp_ms: 1_600_000_000_000 + seq,
    sequence: BigInt(seq) as unknown as SequenceNumber,
    producer_id: 'test',
    producer_version: '1.0.0',
    payload_schema_version: '1.0.0',
    payload: { seq },
    prev_hash: H,
    self_hash: `${'a'.repeat(63)}${seq % 10}` as SHA256Hex,
    retention_class: RetentionClass.STANDARD,
  })
}

// ── buildSegment ──────────────────────────────────────────

describe('buildSegment', () => {
  it('throws when events list is empty', async () => {
    await expect(buildSegment(STREAM, [])).rejects.toThrow()
  })

  it('returns a frozen segment with correct field values', async () => {
    const events = [makeEnvelope(1), makeEnvelope(2), makeEnvelope(3)]
    const seg = await buildSegment(STREAM, events)
    expect(Object.isFrozen(seg)).toBe(true)
    expect(seg.stream_id).toBe(STREAM)
    expect(seg.event_count).toBe(3)
    expect(seg.start_sequence).toBe(events[0]!.sequence)
    expect(seg.end_sequence).toBe(events[2]!.sequence)
    expect(seg.compression_codec).toBe('none')
    expect(seg.merkle_encoding).toBe('byte-concat-arity-2-v1')
  })

  it('merkle_root is a 64-char hex string', async () => {
    const seg = await buildSegment(STREAM, [makeEnvelope(10)])
    expect(seg.merkle_root).toMatch(/^[0-9a-f]{64}$/)
  })

  it('generates a unique segment_id each call', async () => {
    const events = [makeEnvelope(1)]
    const s1 = await buildSegment(STREAM, events)
    const s2 = await buildSegment(STREAM, events)
    expect(s1.segment_id).not.toBe(s2.segment_id)
  })

  it('merkle_root is deterministic for the same events', async () => {
    const events = [makeEnvelope(1), makeEnvelope(2)]
    const r1 = (await buildSegment(STREAM, events)).merkle_root
    const r2 = (await buildSegment(STREAM, events)).merkle_root
    expect(r1).toBe(r2)
  })
})

// ── verifySegment ─────────────────────────────────────────

describe('verifySegment', () => {
  it('returns true when events match the segment', async () => {
    const events = [makeEnvelope(1), makeEnvelope(2), makeEnvelope(3)]
    const seg = await buildSegment(STREAM, events)
    expect(await verifySegment(seg, events)).toBe(true)
  })

  it('returns false when event count differs from segment.event_count', async () => {
    const events = [makeEnvelope(1), makeEnvelope(2)]
    const seg = await buildSegment(STREAM, events)
    // Pass only one event (count mismatch)
    expect(await verifySegment(seg, [makeEnvelope(1)])).toBe(false)
  })

  it('returns false when an event self_hash is tampered', async () => {
    const events = [makeEnvelope(1), makeEnvelope(2)]
    const seg = await buildSegment(STREAM, events)
    // Tamper the first event's self_hash
    const tampered = [
      Object.freeze({ ...events[0]!, self_hash: 'b'.repeat(64) as SHA256Hex }),
      events[1]!,
    ]
    expect(await verifySegment(seg, tampered)).toBe(false)
  })
})

// ── partitionIntoSegments ─────────────────────────────────

describe('partitionIntoSegments', () => {
  it('returns empty array for empty event list', () => {
    const parts = partitionIntoSegments([])
    expect(parts).toHaveLength(0)
  })

  it('returns one partition when events fit in one segment', () => {
    const events = [makeEnvelope(1), makeEnvelope(2), makeEnvelope(3)]
    const parts = partitionIntoSegments(events, 5)
    expect(parts).toHaveLength(1)
    expect(parts[0]).toHaveLength(3)
  })

  it('partitions into correct chunk sizes', () => {
    const events = Array.from({ length: 7 }, (_, i) => makeEnvelope(i + 1))
    const parts = partitionIntoSegments(events, 3)
    expect(parts).toHaveLength(3)
    expect(parts[0]).toHaveLength(3)
    expect(parts[1]).toHaveLength(3)
    expect(parts[2]).toHaveLength(1)
  })

  it('result and partitions are frozen', () => {
    const events = [makeEnvelope(1), makeEnvelope(2)]
    const parts = partitionIntoSegments(events, 2)
    expect(Object.isFrozen(parts)).toBe(true)
    expect(Object.isFrozen(parts[0])).toBe(true)
  })
})
