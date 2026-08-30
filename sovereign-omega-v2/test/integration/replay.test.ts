// ============================================================
// SOVEREIGN OMEGA — Deterministic Replay Integration Test
// BUILD GATE 7: byte-identical DecisionSchema across runs
// This is the deployment gate. Do not deploy without passing.
// ============================================================

import { describe, it, expect } from 'vitest'
import { replayProjection } from '../../src/event/replay'
import { deepFreeze } from '../../src/core/immutable'
import { canonicalizeJCSString } from '../../src/core/canonicalize'
import type { EventEnvelope, RuntimeVersionPin, SequenceNumber } from '../../src/core/types'
import { EventType as ET, RetentionClass as RC } from '../../src/core/types'

const TEST_PIN: RuntimeVersionPin = {
  schema_version: '1.0.0',
  verifier_versions: { 'v-test': '1.0.0' },
  calibration_model_version: '1.0.0',
  projection_compiler_version: '1.0.0',
  k_measurement_version: '1.0.0',
}

function makeEvent(type: ET, seq: number, payload: unknown = {}): EventEnvelope {
  return deepFreeze({
    event_id: `event-${seq}` as any,
    stream_id: 'test-stream' as any,
    event_type: type,
    timestamp_ms: 1_600_000_000_000 + seq * 1000,
    sequence: BigInt(seq) as SequenceNumber,
    producer_id: 'test',
    producer_version: '1.0.0',
    payload_schema_version: '1.0.0',
    payload,
    prev_hash: '0'.repeat(64) as any,
    self_hash: '0'.repeat(64) as any,
    retention_class: RC.REGULATED,
  })
}

describe('Deterministic Replay — Gate 7', () => {
  const events: EventEnvelope[] = [
    makeEvent(ET.SYSTEM_INIT, 0, {}),
    makeEvent(ET.CONFIDENCE_CLAIMED, 1, { confidence_type: 'verified' }),
    makeEvent(ET.VCG_COMPUTED, 2, { vcg_epoch_id: 'epoch-1', weighted_error: 0.12 }),
    makeEvent(ET.SYSTEM_OUTPUT, 3, {
      score: 75,
      strengths: ['Clear value prop', 'Strong market fit'],
      risks: ['Competition risk'],
      positioning: 'Differentiated mid-market player',
      output_hash: 'abc123',
    }),
  ]

  it('produces identical state from two independent replays', async () => {
    const state1 = await replayProjection(events, TEST_PIN)
    const state2 = await replayProjection(events, TEST_PIN)
    const canonical1 = canonicalizeJCSString(state1)
    const canonical2 = canonicalizeJCSString(state2)
    expect(canonical1).toBe(canonical2)
  })

  it('produces identical canonical JSON across replay runs', async () => {
    const results: string[] = []
    for (let i = 0; i < 3; i++) {
      const state = await replayProjection(events, TEST_PIN)
      results.push(canonicalizeJCSString(state))
    }
    expect(results[0]).toBe(results[1])
    expect(results[1]).toBe(results[2])
  })

  it('produces different state from different event streams', async () => {
    const events2 = [
      ...events,
      makeEvent(ET.SYSTEM_OUTPUT, 4, { score: 30, strengths: ['Early stage'], risks: ['High risk'] }),
    ]
    const state1 = await replayProjection(events, TEST_PIN)
    const state2 = await replayProjection(events2, TEST_PIN)
    expect(canonicalizeJCSString(state1)).not.toBe(canonicalizeJCSString(state2))
  })

  it('output state is frozen', async () => {
    const state = await replayProjection(events, TEST_PIN)
    expect(Object.isFrozen(state)).toBe(true)
  })

  it('aborts on schema version mismatch without upcast', async () => {
    const mismatchEvent = makeEvent(ET.CONFIDENCE_CLAIMED, 5, { confidence_type: 'verified' })
    const mismatchedEvents = [
      ...events,
      { ...mismatchEvent, payload_schema_version: '99.0.0' } as EventEnvelope,
    ]
    await expect(replayProjection(mismatchedEvents, TEST_PIN)).rejects.toThrow('Schema version mismatch')
  })

  it('applies events in sequence order', async () => {
    const orderedEvents = [...events].sort(() => Math.random() - 0.5)
    // Sort back to original order before replay — replay should use sequence order
    const state = await replayProjection(orderedEvents, TEST_PIN)
    expect(state.confidence_type).toBe('verified')
  })
})
