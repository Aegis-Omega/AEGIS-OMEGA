// ============================================================
// SOVEREIGN OMEGA — Pure Reducer-Driven Projection Machine tests
// EPISTEMIC TIER: T0
//
// Tests for runtime/projection-machine.ts:
//   INITIAL_RUNTIME_STATE — genesis values
//   reduceRuntime         — normal reduce, frozen bypass, sequence guard
//   replayRuntimeState    — empty events, multi-event replay
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  INITIAL_RUNTIME_STATE,
  reduceRuntime,
  replayRuntimeState,
} from '../../src/runtime/projection-machine.js'
import { EventType, RetentionClass } from '../../src/core/types.js'
import type { EventEnvelope, UUIDv7, SHA256Hex, SequenceNumber, RuntimeVersionPin } from '../../src/core/types.js'

const GENESIS = '0'.repeat(64) as SHA256Hex
const H1 = 'a'.repeat(64) as SHA256Hex
const H2 = 'b'.repeat(64) as SHA256Hex
const H3 = 'c'.repeat(64) as SHA256Hex

const PIN: RuntimeVersionPin = {
  schema_version: '1.0.0',
  verifier_versions: { 'v1': '1.0.0' },
  calibration_model_version: '1.0.0',
  projection_compiler_version: '1.0.0',
  k_measurement_version: '1.0.0',
}

function makeEvent(seq: number, hash: SHA256Hex): EventEnvelope {
  return Object.freeze({
    event_id: `evt-${seq}` as UUIDv7,
    stream_id: 'stream-01' as UUIDv7,
    event_type: EventType.RESPONSE_GENERATED,
    timestamp_ms: 1_600_000_000_000 + seq,
    sequence: BigInt(seq) as unknown as SequenceNumber,
    producer_id: 'test',
    producer_version: '1.0.0',
    payload_schema_version: '1.0.0',
    payload: {},
    prev_hash: GENESIS,
    self_hash: hash,
    retention_class: RetentionClass.STANDARD,
  })
}

// ── INITIAL_RUNTIME_STATE ─────────────────────────────────

describe('INITIAL_RUNTIME_STATE', () => {
  it('is frozen', () => {
    expect(Object.isFrozen(INITIAL_RUNTIME_STATE)).toBe(true)
  })

  it('has genesis chain_hash (64 zeros)', () => {
    expect(INITIAL_RUNTIME_STATE.chain_hash).toBe(GENESIS)
  })

  it('has last_sequence of 0n', () => {
    expect(INITIAL_RUNTIME_STATE.last_sequence).toBe(0n)
  })

  it('has empty events, registry, telemetry arrays', () => {
    expect(INITIAL_RUNTIME_STATE.events).toHaveLength(0)
    expect(INITIAL_RUNTIME_STATE.registry).toHaveLength(0)
    expect(INITIAL_RUNTIME_STATE.telemetry).toHaveLength(0)
  })
})

// ── reduceRuntime ─────────────────────────────────────────

describe('reduceRuntime', () => {
  it('returns a new frozen state with the event appended', () => {
    const event = makeEvent(1, H1)
    const next = reduceRuntime(INITIAL_RUNTIME_STATE, event)
    expect(Object.isFrozen(next)).toBe(true)
    expect(next.events).toHaveLength(1)
    expect(next.last_sequence).toBe(1n)
    expect(next.chain_hash).toBe(H1)
  })

  it('does not mutate the previous state', () => {
    const event = makeEvent(1, H1)
    reduceRuntime(INITIAL_RUNTIME_STATE, event)
    expect(INITIAL_RUNTIME_STATE.events).toHaveLength(0)
    expect(INITIAL_RUNTIME_STATE.last_sequence).toBe(0n)
  })

  it('bypasses frozen runtime — returns prev unchanged when freeze_reason is set', () => {
    const frozenState = Object.freeze({
      ...INITIAL_RUNTIME_STATE,
      freeze_reason: 'HALT: T0_ABORT',
    })
    const event = makeEvent(1, H1)
    const result = reduceRuntime(frozenState, event)
    expect(result).toBe(frozenState)  // same reference
    expect(result.events).toHaveLength(0)
  })

  it('returns prev unchanged when event.sequence does not advance (sequence guard)', () => {
    // First advance to sequence 5
    const state1 = reduceRuntime(INITIAL_RUNTIME_STATE, makeEvent(5, H1))
    // Try to apply event with sequence 3 (< current 5)
    const state2 = reduceRuntime(state1, makeEvent(3, H2))
    expect(state2).toBe(state1)  // no change
  })

  it('returns prev unchanged when event.sequence equals last_sequence', () => {
    const state1 = reduceRuntime(INITIAL_RUNTIME_STATE, makeEvent(1, H1))
    const state2 = reduceRuntime(state1, makeEvent(1, H2))
    expect(state2).toBe(state1)
  })

  it('processes sequential events correctly across 3 steps', () => {
    const s1 = reduceRuntime(INITIAL_RUNTIME_STATE, makeEvent(1, H1))
    const s2 = reduceRuntime(s1, makeEvent(2, H2))
    const s3 = reduceRuntime(s2, makeEvent(3, H3))
    expect(s3.events).toHaveLength(3)
    expect(s3.last_sequence).toBe(3n)
    expect(s3.chain_hash).toBe(H3)
  })
})

// ── replayRuntimeState ────────────────────────────────────

describe('replayRuntimeState', () => {
  it('returns initial state for empty event list', () => {
    const result = replayRuntimeState([], PIN)
    expect(result.events).toHaveLength(0)
    expect(result.chain_hash).toBe(GENESIS)
    expect(result.last_sequence).toBe(0n)
  })

  it('replays 3 events and produces correct final state', () => {
    const events = [makeEvent(1, H1), makeEvent(2, H2), makeEvent(3, H3)]
    const result = replayRuntimeState(events, PIN)
    expect(result.events).toHaveLength(3)
    expect(result.last_sequence).toBe(3n)
    expect(result.chain_hash).toBe(H3)
  })

  it('result is frozen', () => {
    const result = replayRuntimeState([makeEvent(1, H1)], PIN)
    expect(Object.isFrozen(result)).toBe(true)
  })
})
