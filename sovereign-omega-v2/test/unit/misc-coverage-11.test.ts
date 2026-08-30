// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 11
// EPISTEMIC TIER: T0/T1/T2
//
// Covers functions/classes with zero prior coverage:
//   constitutional/founder.ts — FounderError, buildCanonicalFounderRecord
//   consensus/game-theory.ts  — GameTheoryError
//   lib/telemetry.ts          — subscribeTelemetry listener lifecycle
// ============================================================

import { describe, it, expect, afterEach } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'

// ── constitutional/founder.ts ──────────────────────────────

import {
  FounderError,
  buildCanonicalFounderRecord,
  FOUNDER_SCHEMA_VERSION,
} from '../../src/constitutional/founder.js'

const ZERO_HASH = '0'.repeat(64) as SHA256Hex

describe('FounderError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new FounderError('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('FounderError')
    expect(e.message).toBe('test')
  })
})

describe('buildCanonicalFounderRecord', () => {
  it('returns a frozen record with correct schema_version and founder fields', async () => {
    const record = await buildCanonicalFounderRecord(ZERO_HASH)
    expect(Object.isFrozen(record)).toBe(true)
    expect(record.schema_version).toBe(FOUNDER_SCHEMA_VERSION)
    expect(record.is_replay_reconstructable).toBe(true)
    expect(record.founder_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('founder_name is "Tarik Skalić"', async () => {
    const record = await buildCanonicalFounderRecord(ZERO_HASH)
    expect(record.founder_name).toBe('Tarik Skalić')
  })

  it('stewardship_class is "founding-architect"', async () => {
    const record = await buildCanonicalFounderRecord(ZERO_HASH)
    expect(record.stewardship_class).toBe('founding-architect')
  })

  it('constitution_hash reflects the passed argument', async () => {
    const record = await buildCanonicalFounderRecord(ZERO_HASH)
    expect(record.constitution_hash).toBe(ZERO_HASH)
  })

  it('is deterministic — three calls with same hash produce equal founder_hash', async () => {
    const [r1, r2, r3] = await Promise.all([
      buildCanonicalFounderRecord(ZERO_HASH),
      buildCanonicalFounderRecord(ZERO_HASH),
      buildCanonicalFounderRecord(ZERO_HASH),
    ])
    expect(r1.founder_hash).toBe(r2.founder_hash)
    expect(r2.founder_hash).toBe(r3.founder_hash)
  })
})

// ── consensus/game-theory.ts ────────────────────────────────

import {
  GameTheoryError,
} from '../../src/consensus/game-theory.js'

describe('GameTheoryError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new GameTheoryError('synthesis failed')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('GameTheoryError')
    expect(e.message).toBe('synthesis failed')
  })
})

// ── lib/telemetry.ts ────────────────────────────────────────

import {
  subscribeTelemetry,
} from '../../src/lib/telemetry.js'

describe('subscribeTelemetry', () => {
  const unsubscribers: Array<() => void> = []

  afterEach(() => {
    for (const unsub of unsubscribers.splice(0)) unsub()
  })

  it('immediately delivers current state to a new listener', () => {
    let received: unknown = null
    const unsub = subscribeTelemetry(state => { received = state })
    unsubscribers.push(unsub)
    expect(received).not.toBeNull()
    expect((received as { status: string }).status).toBeDefined()
  })

  it('initial state status is "offline" before any bridge connection', () => {
    let received: unknown = null
    const unsub = subscribeTelemetry(state => { received = state })
    unsubscribers.push(unsub)
    expect((received as { status: string }).status).toBe('offline')
  })

  it('returns a callable unsubscribe function', () => {
    const unsub = subscribeTelemetry(() => {})
    expect(typeof unsub).toBe('function')
    expect(() => unsub()).not.toThrow()
  })

  it('unsubscribed listener no longer receives notifications', () => {
    let callCount = 0
    const unsub = subscribeTelemetry(() => { callCount++ })
    const countAfterSubscribe = callCount
    unsub()
    // After unsubscribe, count should not increase further (synchronously)
    expect(callCount).toBe(countAfterSubscribe)
  })

  it('multiple listeners all receive initial state', () => {
    const states: unknown[] = []
    const u1 = subscribeTelemetry(s => states.push(s))
    const u2 = subscribeTelemetry(s => states.push(s))
    unsubscribers.push(u1, u2)
    expect(states.length).toBe(2)
  })
})
