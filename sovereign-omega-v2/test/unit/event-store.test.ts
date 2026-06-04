// ============================================================
// SOVEREIGN OMEGA — EventStore tests
// EPISTEMIC TIER: T2
//
// Tests for src/event/store.ts
//
// Uses fake-indexeddb/auto to polyfill IndexedDB globals
// so tests can run in the jsdom environment.
// Each test uses a unique stream ID for isolation.
// ============================================================

// Polyfill IndexedDB globals before any test code runs
import 'fake-indexeddb/auto'

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { EventStore, EventStoreError } from '../../src/event/store.js'
import { EventType, RetentionClass } from '../../src/core/types.js'
import type { UUIDv7, SHA256Hex } from '../../src/core/types.js'

const FIXED_TS = 1_600_000_000_000

// Generate a unique stream ID per test to avoid cross-test IndexedDB contamination
let testCounter = 0
function uniqueStreamId(): UUIDv7 {
  testCounter++
  return `01900000-0000-7000-8000-${String(testCounter).padStart(12, '0')}` as UUIDv7
}

// ── EventStoreError ───────────────────────────────────────

describe('EventStoreError', () => {
  it('is an Error subclass with name=EventStoreError', () => {
    const err = new EventStoreError('test message')
    expect(err).toBeInstanceOf(Error)
    expect(err.name).toBe('EventStoreError')
    expect(err.message).toBe('test message')
  })
})

// ── EventStore.requireDB ──────────────────────────────────

describe('EventStore — requireDB guard', () => {
  it('throws EventStoreError when append() called before open()', async () => {
    const store = new EventStore(uniqueStreamId())
    await expect(
      store.append(EventType.AMBIGUITY_ROUTED, { test: true }, 'p', '1', '1', RetentionClass.STANDARD, FIXED_TS)
    ).rejects.toThrow(EventStoreError)
    await expect(
      store.append(EventType.AMBIGUITY_ROUTED, { test: true }, 'p', '1', '1', RetentionClass.STANDARD, FIXED_TS)
    ).rejects.toThrow('not opened')
  })

  it('throws when getAll() called before open()', async () => {
    const store = new EventStore(uniqueStreamId())
    await expect(store.getAll()).rejects.toThrow(EventStoreError)
  })

  it('throws when getSince() called before open()', async () => {
    const store = new EventStore(uniqueStreamId())
    await expect(store.getSince(1n as any)).rejects.toThrow(EventStoreError)
  })

  it('throws when verifyChain() called before open()', async () => {
    const store = new EventStore(uniqueStreamId())
    await expect(store.verifyChain()).rejects.toThrow(EventStoreError)
  })
})

// ── EventStore.open ───────────────────────────────────────

describe('EventStore.open', () => {
  it('opens without error', async () => {
    const store = new EventStore(uniqueStreamId())
    await expect(store.open()).resolves.toBeUndefined()
  })

  it('can be opened multiple times (idempotent)', async () => {
    const store = new EventStore(uniqueStreamId())
    await store.open()
    await expect(store.open()).resolves.toBeUndefined()
  })
})

// ── EventStore.append ─────────────────────────────────────

describe('EventStore.append', () => {
  let store: EventStore

  beforeEach(async () => {
    store = new EventStore(uniqueStreamId())
    await store.open()
  })

  it('returns a frozen EventEnvelope with correct fields', async () => {
    const envelope = await store.append(
      EventType.AMBIGUITY_ROUTED,
      { test: 'payload' },
      'producer-1',
      'v1.0.0',
      '1.0.0',
      RetentionClass.STANDARD,
      FIXED_TS
    )

    expect(Object.isFrozen(envelope)).toBe(true)
    expect(envelope.event_type).toBe(EventType.AMBIGUITY_ROUTED)
    expect(envelope.producer_id).toBe('producer-1')
    expect(envelope.timestamp_ms).toBe(FIXED_TS)
    expect(envelope.retention_class).toBe(RetentionClass.STANDARD)
    expect(typeof envelope.event_id).toBe('string')
  })

  it('assigns sequence=1 to the first event (0-indexed counter starts at -1)', async () => {
    const envelope = await store.append(
      EventType.GATE_EVALUATED,
      {},
      'p', 'v1', '1', RetentionClass.REGULATED, FIXED_TS
    )
    expect(Number(envelope.sequence)).toBe(0)
  })

  it('generates a 64-char hex self_hash', async () => {
    const envelope = await store.append(
      EventType.VCG_COMPUTED,
      { value: 42 },
      'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS
    )
    expect(envelope.self_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('sets prev_hash=genesis on the first event', async () => {
    const envelope = await store.append(
      EventType.SYSTEM_OUTPUT,
      {},
      'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS
    )
    expect(envelope.prev_hash).toBe('0'.repeat(64))
  })

  it('chains prev_hash to previous event self_hash', async () => {
    const first = await store.append(
      EventType.AMBIGUITY_ROUTED, { n: 1 }, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS
    )
    const second = await store.append(
      EventType.GATE_EVALUATED, { n: 2 }, 'p', 'v1', '1', RetentionClass.REGULATED, FIXED_TS + 1
    )
    expect(second.prev_hash).toBe(first.self_hash)
  })

  it('increments sequence for each appended event', async () => {
    const e1 = await store.append(EventType.AMBIGUITY_ROUTED, {}, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS)
    const e2 = await store.append(EventType.GATE_EVALUATED,   {}, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS)
    expect(Number(e2.sequence) - Number(e1.sequence)).toBe(1)
  })

  it('freezes the payload object in the returned envelope', async () => {
    const payload = { mutable: 'value' }
    const envelope = await store.append(
      EventType.VCG_COMPUTED, payload, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS
    )
    expect(Object.isFrozen(envelope.payload)).toBe(true)
  })
})

// ── EventStore.getAll ─────────────────────────────────────

describe('EventStore.getAll', () => {
  it('returns empty frozen array for a new stream', async () => {
    const store = new EventStore(uniqueStreamId())
    await store.open()
    const events = await store.getAll()
    expect(events).toHaveLength(0)
    expect(Object.isFrozen(events)).toBe(true)
  })

  it('returns all appended events in sequence order', async () => {
    const store = new EventStore(uniqueStreamId())
    await store.open()
    await store.append(EventType.AMBIGUITY_ROUTED, { n: 1 }, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS)
    await store.append(EventType.GATE_EVALUATED,   { n: 2 }, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS + 1)
    await store.append(EventType.VCG_COMPUTED,     { n: 3 }, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS + 2)

    const events = await store.getAll()
    expect(events).toHaveLength(3)
    expect(events[0]!.event_type).toBe(EventType.AMBIGUITY_ROUTED)
    expect(events[2]!.event_type).toBe(EventType.VCG_COMPUTED)
  })

  it('returns events with BigInt sequence numbers', async () => {
    const store = new EventStore(uniqueStreamId())
    await store.open()
    await store.append(EventType.SYSTEM_OUTPUT, {}, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS)
    const events = await store.getAll()
    expect(typeof events[0]!.sequence).toBe('bigint')
  })
})

// ── EventStore.getSince ───────────────────────────────────

describe('EventStore.getSince', () => {
  it('returns events at or after the given sequence', async () => {
    const store = new EventStore(uniqueStreamId())
    await store.open()
    const e1 = await store.append(EventType.AMBIGUITY_ROUTED, { n: 1 }, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS)
    await store.append(EventType.GATE_EVALUATED, { n: 2 }, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS + 1)
    await store.append(EventType.VCG_COMPUTED,   { n: 3 }, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS + 2)

    // Skip the first event
    const since = await store.getSince((e1.sequence + 1n) as any)
    expect(since).toHaveLength(2)
    expect(since[0]!.event_type).toBe(EventType.GATE_EVALUATED)
  })

  it('returns empty array when fromSequence is beyond all events', async () => {
    const store = new EventStore(uniqueStreamId())
    await store.open()
    await store.append(EventType.SYSTEM_OUTPUT, {}, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS)
    const since = await store.getSince(999n as any)
    expect(since).toHaveLength(0)
  })
})

// ── EventStore.verifyChain ────────────────────────────────

describe('EventStore.verifyChain', () => {
  it('returns null for an empty chain', async () => {
    const store = new EventStore(uniqueStreamId())
    await store.open()
    expect(await store.verifyChain()).toBeNull()
  })

  it('returns null when chain is intact', async () => {
    const store = new EventStore(uniqueStreamId())
    await store.open()
    await store.append(EventType.AMBIGUITY_ROUTED, {}, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS)
    await store.append(EventType.GATE_EVALUATED,   {}, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS + 1)
    expect(await store.verifyChain()).toBeNull()
  })

  it('returns broken-at-sequence when prev_hash does not match previous event self_hash', async () => {
    const store = new EventStore(uniqueStreamId())
    await store.open()
    const first  = await store.append(EventType.AMBIGUITY_ROUTED, {}, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS)
    const second = await store.append(EventType.GATE_EVALUATED,   {}, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS + 1)

    // Spy on getAll to return a tampered second event with wrong prev_hash
    vi.spyOn(store, 'getAll').mockResolvedValueOnce(
      Object.freeze([first, { ...second, prev_hash: 'f'.repeat(64) as SHA256Hex }])
    )
    const result = await store.verifyChain()
    expect(result).not.toBeNull()
    expect(result?.broken_at_sequence).toBe(Number(second.sequence))
    expect(result?.expected).toBe(first.self_hash)
    expect(result?.got).toBe('f'.repeat(64))
  })

  it('detects broken genesis hash (first event with wrong prev_hash)', async () => {
    const store = new EventStore(uniqueStreamId())
    await store.open()
    const first = await store.append(EventType.SYSTEM_OUTPUT, {}, 'p', 'v1', '1', RetentionClass.STANDARD, FIXED_TS)

    vi.spyOn(store, 'getAll').mockResolvedValueOnce(
      Object.freeze([{ ...first, prev_hash: 'a'.repeat(64) as SHA256Hex }])
    )
    const result = await store.verifyChain()
    expect(result).not.toBeNull()
    expect(result?.expected).toBe('0'.repeat(64))
    expect(result?.got).toBe('a'.repeat(64))
  })
})

afterEach(() => vi.restoreAllMocks())
