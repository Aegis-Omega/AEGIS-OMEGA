// ============================================================
// SOVEREIGN OMEGA — Forensic Divergence Localisation
// EPISTEMIC TIER: T0
// Ω-P2: Replay mismatches become byte-localised, deterministic,
// and forensically reconstructable. Corruption is always observable.
// ============================================================

import type { SHA256Hex } from '../core/types.js'

export interface DivergenceReport {
  readonly event_index: number
  readonly projection_key: string
  readonly reducer_hash: string
  readonly expected_hash: SHA256Hex
  readonly actual_hash: SHA256Hex
  readonly byte_offset: number
  readonly context_window: string // hex of 8 bytes around divergence
}

/**
 * Locate the first byte position where two Uint8Arrays diverge.
 * Returns -1 if identical.
 */
export function locateFirstDivergence(
  expected: Uint8Array,
  actual: Uint8Array
): number {
  const len = Math.min(expected.length, actual.length)
  for (let i = 0; i < len; i++) {
    if (expected[i] !== actual[i]) return i
  }
  return expected.length === actual.length ? -1 : len
}

/**
 * Build a DivergenceReport from two projection outputs.
 * Used by the replay harness when a mismatch is detected.
 */
export function buildDivergenceReport(
  event_index: number,
  projection_key: string,
  reducer_hash: string,
  expected: Uint8Array,
  actual: Uint8Array,
  expected_hash: SHA256Hex,
  actual_hash: SHA256Hex
): DivergenceReport {
  const byte_offset = locateFirstDivergence(expected, actual)

  // Extract 8-byte window around divergence for context
  const windowStart = Math.max(0, byte_offset - 4)
  const windowEnd = Math.min(expected.length, byte_offset + 4)
  const contextBytes = expected.slice(windowStart, windowEnd)
  const context_window = Array.from(contextBytes)
    .map(b => b.toString(16).padStart(2, '0'))
    .join(' ')

  return Object.freeze({
    event_index,
    projection_key,
    reducer_hash,
    expected_hash,
    actual_hash,
    byte_offset,
    context_window,
  })
}

/**
 * Terminal system event types. All failures become events.
 * Terminal events are appended to the substrate and excluded
 * from recursive projection to prevent cascading corruption.
 */
export type TerminalEventType =
  | 'FREEZE_TRIGGERED'
  | 'DETERMINISM_VIOLATION'
  | 'REPLAY_MISMATCH'
  | 'VERIFIER_QUARANTINE'
  | 'MANIFEST_DIVERGENCE'
  | 'STATISTICAL_BOUND_FAILURE'
  | 'IMMUTABILITY_ESCAPE'

export const TERMINAL_EVENT_TYPES: ReadonlySet<TerminalEventType> = new Set([
  'FREEZE_TRIGGERED',
  'DETERMINISM_VIOLATION',
  'REPLAY_MISMATCH',
  'VERIFIER_QUARANTINE',
  'MANIFEST_DIVERGENCE',
  'STATISTICAL_BOUND_FAILURE',
  'IMMUTABILITY_ESCAPE',
])

export interface TerminalEvent {
  readonly type: TerminalEventType
  readonly terminal: true
  readonly sequence: number
  readonly reason: string
  readonly byte_offset?: number
}

export function isTerminalEvent(type: string): type is TerminalEventType {
  return TERMINAL_EVENT_TYPES.has(type as TerminalEventType)
}
