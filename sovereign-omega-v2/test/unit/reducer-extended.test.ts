// ============================================================
// Reducer Extended Tests — projection/reducer.ts
// Targets uncovered branches:
//   switch arm 4: VERIFIER_EVALUATED event type
//   L65 arm 1: SYSTEM_OUTPUT without score (score undefined)
//   L82 arm 0,1: VERIFIER_EVALUATED with and without artifact_hash
//   default arm: unknown event type passes through
// ============================================================

import { describe, it, expect } from 'vitest'
import { applyEvent, createProjectionState } from '../../src/projection/reducer.js'
import { deepFreeze } from '../../src/core/immutable.js'
import { EventType as ET, RetentionClass as RC } from '../../src/core/types.js'
import type { EventEnvelope, SequenceNumber } from '../../src/core/types.js'
import type { SHA256Hex } from '../../src/core/types.js'

function makeEvent(type: ET | string, seq: number, payload: unknown = {}): EventEnvelope {
  return deepFreeze({
    event_id: `event-${seq}` as never,
    stream_id: 'test-stream' as never,
    event_type: type as ET,
    timestamp_ms: 1_600_000_000_000 + seq * 1000,
    sequence: BigInt(seq) as SequenceNumber,
    producer_id: 'test',
    producer_version: '1.0.0',
    payload_schema_version: '1.0.0',
    payload,
    prev_hash: '0'.repeat(64) as SHA256Hex,
    self_hash: '0'.repeat(64) as SHA256Hex,
    retention_class: RC.REGULATED,
  })
}

// ─── VERIFIER_EVALUATED event ─────────────────────────────────

describe('applyEvent: VERIFIER_EVALUATED with artifact_hash', () => {
  it('pushes artifact_hash into retrieval_context_hashes', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent(ET.VERIFIER_EVALUATED, 1, { artifact_hash: 'abc123' })
    const next = applyEvent(state, event)
    expect(next.retrieval_context_hashes).toContain('abc123')
  })

  it('updates last_updated_sequence', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent(ET.VERIFIER_EVALUATED, 7, { artifact_hash: 'hash7' })
    const next = applyEvent(state, event)
    expect(next.last_updated_sequence).toBe(7n)
  })
})

describe('applyEvent: VERIFIER_EVALUATED without artifact_hash', () => {
  it('does not push to retrieval_context_hashes when artifact_hash absent', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent(ET.VERIFIER_EVALUATED, 2, {})
    const next = applyEvent(state, event)
    expect(next.retrieval_context_hashes).toHaveLength(0)
  })

  it('still updates last_updated_sequence', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent(ET.VERIFIER_EVALUATED, 3, {})
    const next = applyEvent(state, event)
    expect(next.last_updated_sequence).toBe(3n)
  })
})

// ─── SYSTEM_OUTPUT without score ────────────────────────────

describe('applyEvent: SYSTEM_OUTPUT without score field', () => {
  it('does not push to score_accumulator when score is undefined', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent(ET.SYSTEM_OUTPUT, 1, { strengths: ['good'] })
    const next = applyEvent(state, event)
    expect(next.score_accumulator).toHaveLength(0)
    expect(next.strengths).toContain('good')
  })

  it('does not push positioning when positioning absent', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent(ET.SYSTEM_OUTPUT, 1, { score: 90 })
    const next = applyEvent(state, event)
    expect(next.positioning_candidates).toHaveLength(0)
  })
})

// ─── Default (unknown) event type ────────────────────────────

describe('applyEvent: unknown event type uses default branch', () => {
  it('returns state with updated last_updated_sequence', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent('UNKNOWN_EVENT_TYPE', 5)
    const next = applyEvent(state, event)
    expect(next.last_updated_sequence).toBe(5n)
  })

  it('does not change other state fields', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent('BOGUS', 9)
    const next = applyEvent(state, event)
    expect(next.score_accumulator).toHaveLength(0)
    expect(next.retrieval_context_hashes).toHaveLength(0)
  })
})
