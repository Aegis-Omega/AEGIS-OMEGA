// ============================================================
// SOVEREIGN OMEGA — Forensic Divergence tests
// EPISTEMIC TIER: T0
//
// Tests for forensics/divergence.ts:
//   locateFirstDivergence — byte-exact divergence detection
//   buildDivergenceReport — forensic context window construction
//   isTerminalEvent — terminal event type guard
//   TERMINAL_EVENT_TYPES — exhaustive membership check
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  locateFirstDivergence,
  buildDivergenceReport,
  isTerminalEvent,
  TERMINAL_EVENT_TYPES,
} from '../../src/forensics/divergence.js'
import type { SHA256Hex } from '../../src/core/types.js'

const HASH_A = ('a'.repeat(64)) as SHA256Hex
const HASH_B = ('b'.repeat(64)) as SHA256Hex

// ── locateFirstDivergence ─────────────────────────────────

describe('locateFirstDivergence', () => {
  it('returns -1 for two identical arrays', () => {
    const a = new Uint8Array([1, 2, 3, 4])
    const b = new Uint8Array([1, 2, 3, 4])
    expect(locateFirstDivergence(a, b)).toBe(-1)
  })

  it('returns -1 for two empty arrays', () => {
    expect(locateFirstDivergence(new Uint8Array(), new Uint8Array())).toBe(-1)
  })

  it('returns 0 when first bytes differ', () => {
    const a = new Uint8Array([1, 2, 3])
    const b = new Uint8Array([9, 2, 3])
    expect(locateFirstDivergence(a, b)).toBe(0)
  })

  it('returns 2 when third bytes differ', () => {
    const a = new Uint8Array([1, 2, 3, 4])
    const b = new Uint8Array([1, 2, 9, 4])
    expect(locateFirstDivergence(a, b)).toBe(2)
  })

  it('returns last-matching index when one array is a prefix of the other', () => {
    // expected=[1,2,3,4], actual=[1,2,3] → len=3, all match → return len=3
    const expected = new Uint8Array([1, 2, 3, 4])
    const actual   = new Uint8Array([1, 2, 3])
    expect(locateFirstDivergence(expected, actual)).toBe(3)
  })

  it('returns len when actual is longer but prefix matches expected', () => {
    const expected = new Uint8Array([1, 2])
    const actual   = new Uint8Array([1, 2, 3])
    expect(locateFirstDivergence(expected, actual)).toBe(2)
  })

  it('returns 0 when both arrays start differently and actual is shorter', () => {
    const expected = new Uint8Array([5, 6, 7])
    const actual   = new Uint8Array([0])
    expect(locateFirstDivergence(expected, actual)).toBe(0)
  })

  it('detects divergence at last position', () => {
    const a = new Uint8Array([1, 2, 3, 4])
    const b = new Uint8Array([1, 2, 3, 5])
    expect(locateFirstDivergence(a, b)).toBe(3)
  })
})

// ── buildDivergenceReport ─────────────────────────────────

describe('buildDivergenceReport', () => {
  it('produces a frozen report with correct fields', () => {
    const expected = new Uint8Array([1, 2, 3, 4, 5])
    const actual   = new Uint8Array([1, 2, 9, 4, 5])
    const report   = buildDivergenceReport(
      7, 'state.count', 'reducer-hash-abc', expected, actual, HASH_A, HASH_B,
    )
    expect(Object.isFrozen(report)).toBe(true)
    expect(report.event_index).toBe(7)
    expect(report.projection_key).toBe('state.count')
    expect(report.reducer_hash).toBe('reducer-hash-abc')
    expect(report.expected_hash).toBe(HASH_A)
    expect(report.actual_hash).toBe(HASH_B)
    expect(report.byte_offset).toBe(2)
  })

  it('context_window is hex-encoded bytes around divergence point', () => {
    // expected=[0x00..0x09], actual=[0x00..0x04,0xFF,0x06..0x09]
    const expected = new Uint8Array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    const actual   = new Uint8Array([0, 1, 2, 3, 4, 0xff, 6, 7, 8, 9])
    const report   = buildDivergenceReport(0, 'k', 'r', expected, actual, HASH_A, HASH_B)
    // Divergence at index 5; window is expected.slice(max(0,5-4)=1, min(10,5+4)=9) = [1..8]
    expect(report.byte_offset).toBe(5)
    // context_window should be the hex of bytes 1..8 (windowStart=1, windowEnd=9)
    expect(report.context_window).toBe('01 02 03 04 05 06 07 08')
  })

  it('context_window clamps to start of array when divergence is near beginning', () => {
    const expected = new Uint8Array([0, 1, 2, 3, 4, 5])
    const actual   = new Uint8Array([9, 1, 2, 3, 4, 5])
    const report   = buildDivergenceReport(0, 'k', 'r', expected, actual, HASH_A, HASH_B)
    // Divergence at 0; windowStart = max(0, 0-4) = 0, windowEnd = min(6, 0+4) = 4
    expect(report.byte_offset).toBe(0)
    expect(report.context_window).toBe('00 01 02 03')
  })

  it('context_window clamps to end of array when divergence is near end', () => {
    const expected = new Uint8Array([0, 1, 2, 3, 0xfe])
    const actual   = new Uint8Array([0, 1, 2, 3, 0xff])
    const report   = buildDivergenceReport(0, 'k', 'r', expected, actual, HASH_A, HASH_B)
    // Divergence at 4; windowStart = max(0, 4-4) = 0, windowEnd = min(5, 4+4) = 5
    expect(report.byte_offset).toBe(4)
    expect(report.context_window).toBe('00 01 02 03 fe')
  })

  it('byte_offset is -1 for identical arrays', () => {
    const buf    = new Uint8Array([1, 2, 3])
    const report = buildDivergenceReport(0, 'k', 'r', buf, buf, HASH_A, HASH_B)
    expect(report.byte_offset).toBe(-1)
  })
})

// ── isTerminalEvent ───────────────────────────────────────

describe('isTerminalEvent', () => {
  it('returns true for each known terminal event type', () => {
    const known = [
      'FREEZE_TRIGGERED',
      'DETERMINISM_VIOLATION',
      'REPLAY_MISMATCH',
      'VERIFIER_QUARANTINE',
      'MANIFEST_DIVERGENCE',
      'STATISTICAL_BOUND_FAILURE',
      'IMMUTABILITY_ESCAPE',
    ]
    for (const t of known) {
      expect(isTerminalEvent(t)).toBe(true)
    }
  })

  it('returns false for non-terminal strings', () => {
    expect(isTerminalEvent('UNKNOWN')).toBe(false)
    expect(isTerminalEvent('')).toBe(false)
    expect(isTerminalEvent('freeze_triggered')).toBe(false)  // case-sensitive
    expect(isTerminalEvent('SKILL_VALIDATED')).toBe(false)
  })

  it('TERMINAL_EVENT_TYPES set has exactly 7 members', () => {
    expect(TERMINAL_EVENT_TYPES.size).toBe(7)
  })
})
