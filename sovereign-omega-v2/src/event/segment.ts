// ============================================================
// SOVEREIGN OMEGA — Event Segment & Merkle Anchoring
// EPISTEMIC TIER: T0
// Segments provide sublinear integrity verification at scale.
// Encoding: 'byte-concat-arity-2-v1' (pinned in header).
// ============================================================

import type { EventEnvelope, EventSegment, UUIDv7, SHA256Hex } from '../core/types.js'
import { computeMerkleRootFromValues } from '../core/hashing.js'
import { canonicalizeJCS } from '../core/canonicalize.js'
import { generateUUIDv7 } from './uuid.js'

const DEFAULT_SEGMENT_SIZE = 1000

/**
 * Build an EventSegment from a slice of the event log.
 * The Merkle root covers all events in the segment using
 * byte-concat-arity-2-v1 encoding (never string concatenation).
 */
export async function buildSegment(
  streamId: UUIDv7,
  events: readonly EventEnvelope[]
): Promise<EventSegment> {
  if (events.length === 0) throw new Error('Cannot build segment from empty event list')

  const first = events[0]!
  const last = events[events.length - 1]!

  // Compute Merkle root over canonical form of each event
  // Uses byte-concat-arity-2-v1: each leaf is the canonical bytes of the event
  const leaves = events.map(e => canonicalizeJCS({
    event_id: e.event_id,
    sequence: String(e.sequence),
    self_hash: e.self_hash,
  }))

  const merkle_root = await computeMerkleRootFromValues(
    leaves.map(l => new TextDecoder().decode(l))
  )

  return Object.freeze({
    segment_id: generateUUIDv7(),
    stream_id: streamId,
    start_sequence: first.sequence,
    end_sequence: last.sequence,
    event_count: events.length,
    merkle_root,
    compressed_blob_ref: `segment:${String(first.sequence)}-${String(last.sequence)}`,
    compression_codec: 'none' as const,
    codec_config_hash: '0'.repeat(64) as SHA256Hex,
    merkle_encoding: 'byte-concat-arity-2-v1' as const,
  })
}

/**
 * Verify a segment's Merkle root against a list of events.
 * Returns true if the root matches, false if tampered.
 */
export async function verifySegment(
  segment: EventSegment,
  events: readonly EventEnvelope[]
): Promise<boolean> {
  if (events.length !== segment.event_count) return false

  const leaves = events.map(e => canonicalizeJCS({
    event_id: e.event_id,
    sequence: String(e.sequence),
    self_hash: e.self_hash,
  }))

  const computed_root = await computeMerkleRootFromValues(
    leaves.map(l => new TextDecoder().decode(l))
  )

  return computed_root === segment.merkle_root
}

/**
 * Partition an event list into segments of the given size.
 */
export function partitionIntoSegments(
  events: readonly EventEnvelope[],
  segmentSize = DEFAULT_SEGMENT_SIZE
): readonly (readonly EventEnvelope[])[] {
  const segments: (readonly EventEnvelope[])[] = []
  for (let i = 0; i < events.length; i += segmentSize) {
    segments.push(Object.freeze(events.slice(i, i + segmentSize)))
  }
  return Object.freeze(segments)
}
