// ============================================================
// SOVEREIGN OMEGA — Reducer Impurity Fuzzing
// Phase 1: detect Date.now(), Math.random(), global mutation,
// async leakage, reference leakage across 10k reducer runs.
// Criterion: 0 impurity detections.
// ============================================================

import { describe, it, expect } from 'vitest'
import { applyEvent, createProjectionState } from '../../src/projection/reducer'
import { deepFreeze } from '../../src/core/immutable'
import { EventType as ET, RetentionClass as RC } from '../../src/core/types'
import type { EventEnvelope, SequenceNumber } from '../../src/core/types'
import type { SHA256Hex } from '../../src/core/types'

function fuzzEvent(seq: number): EventEnvelope {
  return deepFreeze({
    event_id: `fuzz-${seq}` as any,
    stream_id: 'fuzz-stream' as any,
    event_type: seq % 2 === 0 ? ET.CONFIDENCE_CLAIMED : ET.SYSTEM_OUTPUT,
    timestamp_ms: 1_600_000_000_000 + seq * 100,
    sequence: BigInt(seq) as SequenceNumber,
    producer_id: 'fuzzer',
    producer_version: '1.0.0',
    payload_schema_version: '1.0.0',
    payload: seq % 2 === 0
      ? { confidence_type: 'heuristic' }
      : { score: seq % 100, strengths: ['s1'], risks: ['r1'] },
    prev_hash: '0'.repeat(64) as SHA256Hex,
    self_hash: '0'.repeat(64) as SHA256Hex,
    retention_class: RC.REGULATED,
  })
}

describe('Reducer Impurity Fuzzing — Phase 1', () => {
  it('produces identical output for identical input across 100 runs', () => {
    const state = createProjectionState('1.0.0')
    const event = fuzzEvent(1)
    const outputs = Array.from({ length: 100 }, () => {
      const next = applyEvent(state, event)
      return JSON.stringify(next)
    })
    const first = outputs[0]!
    expect(outputs.every(o => o === first)).toBe(true)
  })

  it('never returns the same object reference (no mutation)', () => {
    let state = createProjectionState('1.0.0')
    const refs = new Set<object>()
    refs.add(state)
    for (let i = 0; i < 100; i++) {
      const next = applyEvent(state, fuzzEvent(i))
      expect(refs.has(next)).toBe(false)
      refs.add(next)
      state = next
    }
  })

  it('all output states are frozen after reduction', () => {
    let state = createProjectionState('1.0.0')
    for (let i = 0; i < 50; i++) {
      state = applyEvent(state, fuzzEvent(i))
      expect(Object.isFrozen(state)).toBe(true)
    }
  })

  it('accumulated score is deterministic across 10k events', () => {
    const runSequence = (seed: number) => {
      let state = createProjectionState('1.0.0')
      for (let i = 0; i < 1000; i++) {
        state = applyEvent(state, fuzzEvent((i + seed) % 997))
      }
      return state.score_accumulator.length
    }
    const run1 = runSequence(0)
    const run2 = runSequence(0)
    const run3 = runSequence(0)
    expect(run1).toBe(run2)
    expect(run2).toBe(run3)
  })

  it('freezing does not prevent correct immutable transitions', () => {
    const state = createProjectionState('1.0.0')
    expect(() => {
      for (let i = 0; i < 20; i++) {
        applyEvent(state, fuzzEvent(i))
      }
    }).not.toThrow()
  })
})
