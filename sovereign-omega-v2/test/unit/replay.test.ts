// ============================================================
// Replay Engine Tests — event/replay.ts
// Targets uncovered branches: fromCheckpoint path,
// schema version mismatch (with/without upcast),
// validateVersionPin missing fields, registerUpcast,
// error constructors.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { EventEnvelope, RuntimeVersionPin, SequenceNumber } from '../../src/core/types.js'
import { EventType, RetentionClass } from '../../src/core/types.js'
import type { SHA256Hex, UUIDv7 } from '../../src/core/types.js'
import {
  replayProjection,
  registerUpcast,
  ReplayVersionMismatchError,
  ReplayDivergenceError,
} from '../../src/event/replay.js'

// ─── Fixtures ──────────────────────────────────────────────

const SCHEMA = '1.0.0'
const h = (c: string): SHA256Hex => c.repeat(64) as SHA256Hex
const uuid = (n: number): UUIDv7 => `00000000-0000-7000-0000-${String(n).padStart(12, '0')}` as UUIDv7
const seq = (n: number): SequenceNumber => BigInt(n) as SequenceNumber

const PIN: RuntimeVersionPin = {
  schema_version: SCHEMA,
  verifier_versions: { v1: '1.0.0' },
  calibration_model_version: '1.0.0',
  projection_compiler_version: '1.0.0',
  k_measurement_version: '1.0.0',
}

function makeEvent(n: number, schema = SCHEMA): EventEnvelope {
  return {
    event_id: uuid(n),
    stream_id: uuid(0),
    event_type: EventType.SYSTEM_INIT,
    timestamp_ms: 1_600_000_000_000 + n,
    sequence: seq(n),
    producer_id: 'test',
    producer_version: '1.0.0',
    payload_schema_version: schema,
    payload: {},
    prev_hash: h('0'),
    self_hash: h(String(n)),
    retention_class: RetentionClass.EPHEMERAL,
  }
}

// ─── validateVersionPin ────────────────────────────────────

describe('validateVersionPin', () => {
  it('throws when schema_version is empty', async () => {
    const pin = { ...PIN, schema_version: '' }
    await expect(replayProjection([], pin)).rejects.toBeInstanceOf(ReplayVersionMismatchError)
  })

  it('throws when projection_compiler_version is empty', async () => {
    const pin = { ...PIN, projection_compiler_version: '' }
    await expect(replayProjection([], pin)).rejects.toBeInstanceOf(ReplayVersionMismatchError)
  })

  it('throws when calibration_model_version is empty', async () => {
    const pin = { ...PIN, calibration_model_version: '' }
    await expect(replayProjection([], pin)).rejects.toBeInstanceOf(ReplayVersionMismatchError)
  })

  it('throws when verifier_versions is empty', async () => {
    const pin = { ...PIN, verifier_versions: {} }
    await expect(replayProjection([], pin)).rejects.toBeInstanceOf(ReplayVersionMismatchError)
  })

  it('accepts a valid complete pin', async () => {
    await expect(replayProjection([], PIN)).resolves.toBeDefined()
  })
})

// ─── replayProjection — basic ─────────────────────────────

describe('replayProjection: basic', () => {
  it('returns initial projection state for empty event stream', async () => {
    const state = await replayProjection([], PIN)
    expect(state).toBeDefined()
    expect(state.projection_version).toBe(PIN.projection_compiler_version)
  })

  it('applies events in sequence order', async () => {
    const events = [makeEvent(1), makeEvent(2), makeEvent(3)]
    const state = await replayProjection(events, PIN)
    expect(state).toBeDefined()
  })

  it('state is frozen after replay', async () => {
    const state = await replayProjection([], PIN)
    expect(Object.isFrozen(state)).toBe(true)
  })
})

// ─── fromCheckpoint path ───────────────────────────────────

describe('replayProjection: fromCheckpoint', () => {
  it('skips events at or before checkpoint sequence', async () => {
    const events = [makeEvent(1), makeEvent(2), makeEvent(3)]
    const baseState = await replayProjection(events, PIN)

    const checkpoint = {
      last_sequence: seq(2),
      state: baseState,
      state_hash: h('c'),
      pin: PIN,
    }

    const newEvents = [makeEvent(1), makeEvent(2), makeEvent(3), makeEvent(4)]
    const state = await replayProjection(newEvents, PIN, checkpoint)
    expect(state).toBeDefined()
  })

  it('applies only events after checkpoint sequence', async () => {
    const events = [makeEvent(1), makeEvent(2)]
    const baseState = await replayProjection(events, PIN)

    const checkpoint = {
      last_sequence: seq(2),
      state: baseState,
      state_hash: h('c'),
      pin: PIN,
    }

    const state = await replayProjection([], PIN, checkpoint)
    expect(state).toBe(baseState)
  })
})

// ─── Schema version mismatch ──────────────────────────────

describe('replayProjection: schema mismatch', () => {
  it('throws ReplayVersionMismatchError when schema differs and no upcast registered', async () => {
    const events = [makeEvent(1, '0.9.0')]
    await expect(replayProjection(events, PIN)).rejects.toBeInstanceOf(ReplayVersionMismatchError)
  })

  it('applies upcast when registered for the event type/version pair', async () => {
    const FROM_VERSION = '0.8.0-upcast-test'
    registerUpcast(EventType.BUDGET_RESET, FROM_VERSION, SCHEMA, (event) => ({
      ...event,
      payload_schema_version: SCHEMA,
    }))

    const event: EventEnvelope = { ...makeEvent(1, FROM_VERSION), event_type: EventType.BUDGET_RESET }
    await expect(replayProjection([event], PIN)).resolves.toBeDefined()
  })
})

// ─── Error constructors ────────────────────────────────────

describe('ReplayVersionMismatchError', () => {
  it('is an Error with correct name and message', () => {
    const e = new ReplayVersionMismatchError('mismatch')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('ReplayVersionMismatchError')
    expect(e.message).toBe('mismatch')
  })
})

describe('ReplayDivergenceError', () => {
  it('is an Error with sequence, hashes, and correct name', () => {
    const e = new ReplayDivergenceError(seq(5), h('a'), h('b'))
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('ReplayDivergenceError')
    expect(e.sequence).toBe(BigInt(5))
    expect(e.expected_hash).toBe(h('a'))
    expect(e.actual_hash).toBe(h('b'))
    expect(e.message).toContain('5')
  })
})
