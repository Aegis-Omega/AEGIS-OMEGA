// ============================================================
// Misc Coverage Batch 3
// Targets:
//   frame/dfa.ts: phase_mismatch return (L185 arm 0),
//     terminal_phase_wrong return (L211 arm 0)
//   core/invariant-checker.ts: formatReport passed=true + passed=false (L195 arms 0,1)
//   core/schema-registry.ts: null field value (L82 branch 8 arm 0),
//     array field value (L82 branches 9 arm 0, 10 arm 1)
//   pipeline/schema.ts: deriveActions score in [40,69] (L85 arm 0)
// ============================================================

import { describe, it, expect } from 'vitest'

// ─── DFA: phase_mismatch (L185 arm 0) ─────────────────────

import {
  initialMachine,
  transition,
  certifyExecution,
} from '../../src/frame/dfa.js'
import { hashValue } from '../../src/core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import type { FrameTransitionRecord, DFAState } from '../../src/frame/dfa.js'
import type { Phase } from '../../src/shp/types.js'

const ZERO_HASH = '0'.repeat(64) as SHA256Hex
const SEQ = 1n as SequenceNumber

describe('certifyExecution: phase_mismatch (L185 arm 0)', () => {
  it('returns is_valid=false when records[0].from_phase does not match IDLE', async () => {
    // First record starts from READ (not IDLE) → phase_mismatch
    const badRecord: FrameTransitionRecord = Object.freeze({
      from_phase: 'READ' as DFAState,
      to_phase: 'ASSESS' as Phase,
      state_hash: ZERO_HASH,
      transition_hash: ZERO_HASH,
      sequence: SEQ,
      is_replay_reconstructable: true as const,
    })
    const records = Array(5).fill(badRecord) as FrameTransitionRecord[]
    const cert = await certifyExecution(records, SEQ)
    expect(cert.is_valid).toBe(false)
  })
})

describe('certifyExecution: terminal_phase_wrong (L211 arm 0)', () => {
  it('returns is_valid=false when final to_phase is not HARMONIZE', async () => {
    // Build 4 valid transitions: IDLE→READ→ASSESS→LOCK→PROPAGATE
    let machine = initialMachine(SEQ)
    const records: FrameTransitionRecord[] = []
    const phases: Phase[] = ['READ', 'ASSESS', 'LOCK', 'PROPAGATE']
    for (const phase of phases) {
      const r = await transition(machine, phase, ZERO_HASH)
      machine = r.machine
      records.push(r.record)
    }

    // Build fake 5th record: PROPAGATE→READ (wrong terminal, not HARMONIZE)
    // Must compute the correct hash so hash_mismatch check passes
    const wrongTo: Phase = 'READ'
    const fakeTransitionHash = await hashValue({
      from_phase: 'PROPAGATE',
      to_phase: wrongTo,
      state_hash: ZERO_HASH,
      prev_transition_hash: machine.last_transition_hash,
      sequence: machine.sequence,
    }) as SHA256Hex

    records.push(Object.freeze({
      from_phase: 'PROPAGATE' as DFAState,
      to_phase: wrongTo,
      state_hash: ZERO_HASH,
      transition_hash: fakeTransitionHash,
      sequence: SEQ,
      is_replay_reconstructable: true as const,
    }))

    const cert = await certifyExecution(records, SEQ)
    expect(cert.is_valid).toBe(false)
  })
})

// ─── InvariantChecker: formatReport both arms ─────────────

import {
  formatReport,
  checkInvariants,
} from '../../src/core/invariant-checker.js'
import type { InvariantCheckResult } from '../../src/core/invariant-checker.js'
import { HolonicScale, EpistemicTier } from '../../src/core/types.js'

describe('formatReport: passed=true returns ALL CLEAR (L195 arm 0)', () => {
  it('returns ALL CLEAR string when result.passed is true', () => {
    const result: InvariantCheckResult = {
      passed: true,
      violations: [],
      checked_at_sequence: 5,
    }
    const report = formatReport(result)
    expect(report).toContain('ALL CLEAR')
    expect(report).toContain('seq 5')
  })
})

describe('formatReport: passed=false returns violations (L195 arm 1)', () => {
  it('returns violation lines when result.passed is false', () => {
    const result: InvariantCheckResult = {
      passed: false,
      violations: [
        {
          invariant_id: 'INV-TEST',
          description: 'test violation description',
          severity: 'T0_ABORT' as const,
          observed_value: 0.3,
          expected: '>= 0.9',
          holonic_scale: HolonicScale.CELLULAR,
          tier: EpistemicTier.T0,
        },
      ],
      checked_at_sequence: 10,
    }
    const report = formatReport(result)
    expect(report).toContain('[T0_ABORT]')
    expect(report).toContain('INV-TEST')
  })

  it('via checkInvariants: vcg_error=1 triggers violation → formatReport returns violations', () => {
    const snapshot = {
      vcg_error: 1.5,       // > 1 → triggers INV-01 (vcg_error must be in [0,1])
      drift_index: 0,
      sequence: 1,
      pgcs_passes: true,
      afse_r2: 0.99,
      corruption_count: 0,
      calibrator_passes: true,
      failsafe_state: 'normal',
    }
    const result = checkInvariants(snapshot)
    expect(result.passed).toBe(false)
    const report = formatReport(result)
    expect(report.length).toBeGreaterThan(0)
    expect(report).not.toContain('ALL CLEAR')
  })
})

// ─── SchemaRegistry: null and array field values ──────────

import { SchemaRegistry } from '../../src/core/schema-registry.js'

function buildRegistry(): SchemaRegistry {
  const reg = new SchemaRegistry()
  reg.register({
    schema_id: 'test-schema',
    version: '1.0.0',
    fields: [
      { name: 'nullField', type: 'null', required: false },
      { name: 'arrayField', type: 'array', required: false },
      { name: 'stringField', type: 'string', required: false },
    ],
  })
  return reg
}

describe('SchemaRegistry: null field value (L82 branch 8 arm 0)', () => {
  it('correctly identifies null value as type "null"', () => {
    const reg = buildRegistry()
    const result = reg.validate({ nullField: null }, 'test-schema', '1.0.0')
    // null should match type 'null' → no error
    expect(result.valid).toBe(true)
    expect(result.errors).toHaveLength(0)
  })

  it('reports mismatch when null value is given for a non-null field', () => {
    const reg = new SchemaRegistry()
    reg.register({
      schema_id: 'strict-schema',
      version: '1.0.0',
      fields: [{ name: 'name', type: 'string', required: false }],
    })
    const result = reg.validate({ name: null }, 'strict-schema', '1.0.0')
    expect(result.valid).toBe(false)
    expect(result.errors[0]).toContain('null')
  })
})

describe('SchemaRegistry: array field value (L82 branch 9 arm 0, branch 10 arm 1)', () => {
  it('correctly identifies array value as type "array"', () => {
    const reg = buildRegistry()
    const result = reg.validate({ arrayField: [1, 2, 3] }, 'test-schema', '1.0.0')
    // array should match type 'array' → no error
    expect(result.valid).toBe(true)
    expect(result.errors).toHaveLength(0)
  })

  it('reports mismatch when array is given for a non-array field', () => {
    const reg = buildRegistry()
    const result = reg.validate({ stringField: [1, 2] }, 'test-schema', '1.0.0')
    expect(result.valid).toBe(false)
    expect(result.errors[0]).toContain('array')
  })
})

// ─── Pipeline Schema: deriveActions score in [40, 69] ──────

import {
  buildDecisionSchema,
} from '../../src/pipeline/schema.js'
import { createProjectionState, applyEvent } from '../../src/projection/reducer.js'
import { EventType as ET, RetentionClass as RC } from '../../src/core/types.js'
import type { EventEnvelope, Confidence } from '../../src/core/types.js'
import type { UUIDv7 } from '../../src/core/types.js'

function makeSystemOutputEvent(seq: number, score: number): EventEnvelope {
  return Object.freeze({
    event_id: `ev-${seq}` as UUIDv7,
    stream_id: 'pipeline-test' as never,
    event_type: ET.SYSTEM_OUTPUT,
    timestamp_ms: 1_600_000_000_000 + seq * 1000,
    sequence: BigInt(seq) as SequenceNumber,
    producer_id: 'test',
    producer_version: '1.0.0',
    payload_schema_version: '1.0.0',
    payload: { score },
    prev_hash: ZERO_HASH,
    self_hash: ZERO_HASH,
    retention_class: RC.REGULATED,
  })
}

const HEURISTIC_CONFIDENCE: Confidence = {
  type: 'heuristic',
  value: 0.75,
  disclaimer: true,
  source: 'test',
}

describe('buildDecisionSchema: score in [40, 69] hits deriveActions middle tier (L85 arm 0)', () => {
  it('actions contain medium-tier text when score is 50', () => {
    const state0 = createProjectionState('1.0.0')
    const state1 = applyEvent(state0, makeSystemOutputEvent(1, 50))
    const schema = buildDecisionSchema(state1, HEURISTIC_CONFIDENCE, 0.99)
    // score = 50, which is in [40, 69] → middle-tier actions
    expect(schema.score).toBe(50)
    expect(schema.actions[0]).toContain('Validate')
  })

  it('actions contain low-tier text when score is 30', () => {
    const state0 = createProjectionState('1.0.0')
    const state1 = applyEvent(state0, makeSystemOutputEvent(1, 30))
    const schema = buildDecisionSchema(state1, HEURISTIC_CONFIDENCE, 0.99)
    // score = 30 < 40 → lowest tier
    expect(schema.score).toBe(30)
    expect(schema.actions[0]).toContain('Pause')
  })
})
