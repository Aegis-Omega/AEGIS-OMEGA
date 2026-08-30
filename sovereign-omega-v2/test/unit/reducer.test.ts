// ============================================================
// SOVEREIGN OMEGA — Projection Reducer Tests (Gate 4)
// ============================================================

import { describe, it, expect } from 'vitest'
import { applyEvent, createProjectionState } from '../../src/projection/reducer'
import { deepFreeze } from '../../src/core/immutable'
import { EventType as ET, RetentionClass as RC } from '../../src/core/types'
import type { EventEnvelope, SequenceNumber } from '../../src/core/types'
import type { SHA256Hex } from '../../src/core/types'

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
    prev_hash: '0'.repeat(64) as SHA256Hex,
    self_hash: '0'.repeat(64) as SHA256Hex,
    retention_class: RC.REGULATED,
  })
}

describe('Projection Reducer — Gate 4', () => {
  it('initial state is frozen', () => {
    const state = createProjectionState('1.0.0')
    expect(Object.isFrozen(state)).toBe(true)
  })

  it('applies CONFIDENCE_CLAIMED event', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent(ET.CONFIDENCE_CLAIMED, 1, { confidence_type: 'verified' })
    const next = applyEvent(state, event)
    expect(next.confidence_type).toBe('verified')
  })

  it('applies VCG_COMPUTED event', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent(ET.VCG_COMPUTED, 1, { vcg_epoch_id: 'epoch-1', weighted_error: 0.1 })
    const next = applyEvent(state, event)
    expect(next.vcg_epoch_id).toBe('epoch-1')
  })

  it('applies SYSTEM_OUTPUT event accumulating score', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent(ET.SYSTEM_OUTPUT, 1, {
      score: 80,
      strengths: ['strong'],
      risks: ['weak'],
      output_hash: 'abc',
    })
    const next = applyEvent(state, event)
    expect(next.score_accumulator).toContain(80)
    expect(next.strengths).toContain('strong')
  })

  it('returns frozen state after every apply', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent(ET.CONFIDENCE_CLAIMED, 1, { confidence_type: 'verified' })
    const next = applyEvent(state, event)
    expect(Object.isFrozen(next)).toBe(true)
  })

  it('is deterministic: same input always produces same output', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent(ET.SYSTEM_OUTPUT, 1, { score: 75, strengths: ['a', 'b'], risks: ['x'] })
    const next1 = applyEvent(state, event)
    const next2 = applyEvent(state, event)
    expect(JSON.stringify(next1)).toBe(JSON.stringify(next2))
  })

  it('freezes on GATE_FROZEN event', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent(ET.GATE_FROZEN, 1, {})
    const next = applyEvent(state, event)
    expect(next.freeze_reason).toBe('gate_frozen')
  })

  it('ignores events after freeze', () => {
    const state = createProjectionState('1.0.0')
    const frozen = applyEvent(state, makeEvent(ET.GATE_FROZEN, 1, {}))
    const after = applyEvent(frozen, makeEvent(ET.CONFIDENCE_CLAIMED, 2, { confidence_type: 'verified' }))
    expect(after.confidence_type).toBe('heuristic') // unchanged
    expect(after.freeze_reason).toBe('gate_frozen')
  })

  it('does not share references between input and output', () => {
    const state = createProjectionState('1.0.0')
    const event = makeEvent(ET.SYSTEM_OUTPUT, 1, { score: 50, strengths: ['s1'] })
    const next = applyEvent(state, event)
    expect(next).not.toBe(state)
    expect(next.score_accumulator).not.toBe(state.score_accumulator)
  })
})
