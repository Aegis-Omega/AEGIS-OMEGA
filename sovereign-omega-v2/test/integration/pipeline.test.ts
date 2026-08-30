// ============================================================
// SOVEREIGN OMEGA — Pipeline Integration Tests (Gate 7)
// Verifies: conservative fallback on gate failure,
// correct event logging, schema structure compliance.
// ============================================================

import { describe, it, expect } from 'vitest'
import { buildDecisionSchema, buildConservativeSchema } from '../../src/pipeline/schema'
import { createProjectionState } from '../../src/projection/reducer'
import { applyEvent } from '../../src/projection/reducer'
import { EventType as ET, RetentionClass as RC } from '../../src/core/types'
import { deepFreeze } from '../../src/core/immutable'
import type { EventEnvelope, SequenceNumber, SHA256Hex, Confidence } from '../../src/core/types'

const VERIFIED_CONFIDENCE: Confidence = {
  type: 'verified',
  value: 0.85,
  verifier_ids: ['v1', 'v2'],
  vcg_epoch: 'epoch-1',
}

const HEURISTIC_CONFIDENCE: Confidence = {
  type: 'heuristic',
  value: 0.3,
  disclaimer: true,
  source: 'FALLBACK',
}

function makeEvent(type: ET, seq: number, payload: unknown): EventEnvelope {
  return deepFreeze({
    event_id: `evt-${seq}` as any,
    stream_id: 'test' as any,
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

describe('DecisionSchema Construction — Gate 7', () => {
  it('builds schema from populated projection state', () => {
    let state = createProjectionState('1.0.0')
    state = applyEvent(state, makeEvent(ET.SYSTEM_OUTPUT, 1, {
      score: 80,
      strengths: ['Market leader', 'Strong brand', 'Loyal customers'],
      risks: ['New entrant', 'Cost pressure', 'Regulatory risk'],
      positioning: 'Premium segment leader',
      output_hash: 'abc123',
    }))

    const schema = buildDecisionSchema(state, VERIFIED_CONFIDENCE, 0.12)

    expect(schema.score).toBeGreaterThanOrEqual(0)
    expect(schema.score).toBeLessThanOrEqual(100)
    expect(schema.strengths).toHaveLength(3)
    expect(schema.risks).toHaveLength(3)
    expect(schema.actions).toHaveLength(3)
    expect(schema.positioning).toBeTruthy()
    expect(schema.confidence.type).toBe('verified')
    expect(schema.audit_trace_id).toBeTruthy()
    expect(schema.schema_version).toBe('1.0.0')
  })

  it('builds conservative schema with correct structure', () => {
    const schema = buildConservativeSchema(HEURISTIC_CONFIDENCE)
    expect(schema.score).toBe(0)
    expect(schema.strengths).toHaveLength(3)
    expect(schema.risks).toHaveLength(3)
    expect(schema.actions).toHaveLength(3)
    expect(schema.confidence.type).toBe('heuristic')
  })

  it('schema is frozen (immutable)', () => {
    const state = createProjectionState('1.0.0')
    const schema = buildDecisionSchema(state, HEURISTIC_CONFIDENCE, 0.5)
    expect(Object.isFrozen(schema)).toBe(true)
  })

  it('each schema has a unique audit_trace_id', () => {
    const state = createProjectionState('1.0.0')
    const s1 = buildDecisionSchema(state, HEURISTIC_CONFIDENCE, 0.5)
    const s2 = buildDecisionSchema(state, HEURISTIC_CONFIDENCE, 0.5)
    expect(s1.audit_trace_id).not.toBe(s2.audit_trace_id)
  })

  it('vcg_at_emission reflects passed-in VCG value', () => {
    const state = createProjectionState('1.0.0')
    const schema = buildDecisionSchema(state, VERIFIED_CONFIDENCE, 0.17)
    expect(schema.vcg_at_emission).toBeCloseTo(0.17, 5)
  })

  it('conservative fallback includes reason in positioning', () => {
    const schema = buildConservativeSchema(HEURISTIC_CONFIDENCE, 'GATE_REJECTED')
    expect(schema.positioning).toContain('GATE_REJECTED')
  })

  it('score is bounded 0-100 even for extreme accumulators', () => {
    let state = createProjectionState('1.0.0')
    for (let i = 0; i < 5; i++) {
      state = applyEvent(state, makeEvent(ET.SYSTEM_OUTPUT, i + 1, { score: 150 }))
    }
    const schema = buildDecisionSchema(state, HEURISTIC_CONFIDENCE, 0.3)
    expect(schema.score).toBeLessThanOrEqual(100)
    expect(schema.score).toBeGreaterThanOrEqual(0)
  })
})
