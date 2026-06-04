// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 12
// EPISTEMIC TIER: T0/T1/T2
//
// Covers functions/lines with zero prior coverage:
//   core/semantics.ts          — isFiniteNumber
//   gate/risk.ts               — isFrozen(), getBudgetSnapshot()
//   pipeline/schema.ts         — buildConservativeSchema
//   agents/memory/agent-memory.ts — .entries getter
//   sitr/runtime.ts            — telemetry() method
//   verifier/registry.ts       — capacityRegistry.get()
//   projection/compiler.ts     — execute() method body
//   pipeline/e1.ts             — filter on pre-existing ambiguities (line 141)
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber, UUIDv7 } from '../../src/core/types.js'

// ── core/semantics.ts — isFiniteNumber ─────────────────────

import { isFiniteNumber } from '../../src/core/semantics.js'

describe('isFiniteNumber', () => {
  it('returns true for a finite integer', () => {
    expect(isFiniteNumber(42)).toBe(true)
  })

  it('returns true for a finite float', () => {
    expect(isFiniteNumber(3.14)).toBe(true)
  })

  it('returns true for negative finite number', () => {
    expect(isFiniteNumber(-100)).toBe(true)
  })

  it('returns false for NaN', () => {
    expect(isFiniteNumber(NaN)).toBe(false)
  })

  it('returns false for Infinity', () => {
    expect(isFiniteNumber(Infinity)).toBe(false)
  })

  it('returns false for -Infinity', () => {
    expect(isFiniteNumber(-Infinity)).toBe(false)
  })
})

// ── gate/risk.ts — isFrozen(), getBudgetSnapshot() ─────────

import { RiskBudgetManager } from '../../src/gate/risk.js'

const EPOCH_MS = 1_600_000_000_000

describe('RiskBudgetManager.isFrozen()', () => {
  it('is false before freeze()', () => {
    const m = new RiskBudgetManager(EPOCH_MS)
    expect(m.isFrozen()).toBe(false)
  })

  it('is true after freeze()', () => {
    const m = new RiskBudgetManager(EPOCH_MS)
    m.freeze()
    expect(m.isFrozen()).toBe(true)
  })
})

describe('RiskBudgetManager.getBudgetSnapshot()', () => {
  it('returns a frozen RiskBudget with expected fields', () => {
    const m = new RiskBudgetManager(EPOCH_MS, 0.5)
    const snap = m.getBudgetSnapshot()
    expect(snap).toBeDefined()
    expect(snap.global_budget).toBe(0.5)
    expect(snap.spent).toBe(0)
    expect(snap.epoch_start_ms).toBe(EPOCH_MS)
    expect(Object.isFrozen(snap)).toBe(true)
  })
})

// ── pipeline/schema.ts — buildConservativeSchema ────────────

import { buildConservativeSchema } from '../../src/pipeline/schema.js'

const HEURISTIC: import('../../src/core/types.js').Confidence = {
  type: 'heuristic',
  value: 0.1,
  disclaimer: true,
  source: 'TEST',
}

describe('buildConservativeSchema', () => {
  it('returns a frozen schema with score 0', () => {
    const schema = buildConservativeSchema(HEURISTIC)
    expect(Object.isFrozen(schema)).toBe(true)
    expect(schema.score).toBe(0)
  })

  it('uses the default reason in positioning when no reason given', () => {
    const schema = buildConservativeSchema(HEURISTIC)
    expect(schema.positioning).toContain('CONSERVATIVE_FALLBACK')
  })

  it('uses a custom reason in positioning when provided', () => {
    const schema = buildConservativeSchema(HEURISTIC, 'VCG_SUSPENSION')
    expect(schema.positioning).toContain('VCG_SUSPENSION')
  })

  it('passes through the confidence object', () => {
    const schema = buildConservativeSchema(HEURISTIC)
    expect(schema.confidence).toBe(HEURISTIC)
  })

  it('vcg_at_emission is 1.0', () => {
    const schema = buildConservativeSchema(HEURISTIC)
    expect(schema.vcg_at_emission).toBe(1.0)
  })
})

// ── agents/memory/agent-memory.ts — .entries getter ────────

import { AgentMemory } from '../../src/agents/memory/agent-memory.js'
import type { AgentMemoryEntry } from '../../src/agents/types.js'

const ZERO_HASH = '0'.repeat(64) as SHA256Hex

function makeEntry(seq: number): AgentMemoryEntry {
  return {
    entry_id: `entry-${seq}`,
    agent_id: 'test-agent',
    sequence: seq,
    content_hash: ZERO_HASH,
    memory_type: 'observation',
    is_replay_reconstructable: true,
  }
}

describe('AgentMemory.entries getter', () => {
  it('returns empty array on fresh AgentMemory', () => {
    const m = AgentMemory.empty()
    expect(m.entries).toEqual([])
    expect(m.entries.length).toBe(0)
  })

  it('returns stored entries after store()', () => {
    const m = AgentMemory.empty().store(makeEntry(1))
    expect(m.entries).toHaveLength(1)
    expect(m.entries[0]!.entry_id).toBe('entry-1')
  })
})

// ── sitr/runtime.ts — telemetry() ──────────────────────────

import { SITRRuntime } from '../../src/sitr/runtime.js'

describe('SITRRuntime.telemetry()', () => {
  it('returns a telemetry snapshot with expected structure', () => {
    const runtime = SITRRuntime.empty()
    const t = runtime.telemetry()
    expect(t).toBeDefined()
    expect(typeof t.current_state).toBe('string')
    expect(typeof t.intervention_count).toBe('number')
    expect(t.intervention_count).toBe(0)
  })

  it('current_state is "STABLE" for empty runtime', () => {
    const t = SITRRuntime.empty().telemetry()
    expect(t.current_state).toBe('STABLE')
  })
})

// ── verifier/registry.ts — capacityRegistry.get() ──────────

import { capacityRegistry } from '../../src/verifier/registry.js'

describe('capacityRegistry.get()', () => {
  it('returns undefined for an unknown componentId', () => {
    const result = capacityRegistry.get('completely-unknown-component-xyz-cov12')
    expect(result).toBeUndefined()
  })
})

// ── projection/compiler.ts — execute() method body ─────────

import { compileProjection } from '../../src/projection/compiler.js'
import type { RuntimeVersionPin } from '../../src/core/types.js'

const VALID_PIN: RuntimeVersionPin = {
  schema_version: '1.0.0',
  verifier_versions: { 'v-default': '1.0.0' },
  calibration_model_version: '1.0.0',
  projection_compiler_version: '1.0.0',
  k_measurement_version: '1.0.0',
}

describe('compileProjection execute() method', () => {
  it('executes with empty events and returns a ProjectionState', async () => {
    const compiled = compileProjection(VALID_PIN)
    const state = await compiled.execute([])
    expect(state).toBeDefined()
    expect(Object.isFrozen(state)).toBe(true)
    expect(Array.isArray(state.score_accumulator)).toBe(true)
  })
})

// ── pipeline/e1.ts — filter on pre-existing ambiguities ────

import {
  createInitialDialogueState,
  assessAmbiguity,
  updateDialogueState,
} from '../../src/pipeline/e1.js'
import {
  AmbiguityType,
} from '../../src/core/types.js'
import type { AmbiguityFlag } from '../../src/core/types.js'

describe('updateDialogueState with pre-existing ambiguities', () => {
  it('filters existing unresolved ambiguities into the new state', () => {
    const session = 'aaaaaaaa-bbbb-7ccc-8ddd-eeeeeeeeeeee' as UUIDv7
    const base = createInitialDialogueState(session)
    const SEQ1 = BigInt(1) as unknown as SequenceNumber
    const SEQ2 = BigInt(2) as unknown as SequenceNumber

    // Inject a pre-existing unresolved ambiguity manually
    const existingFlag: AmbiguityFlag = {
      id: 'flag-1',
      ambiguity_type: AmbiguityType.INTENT_UNDERSPECIFICATION,
      divergence_score: 0.5,
      introduced_at_sequence: SEQ1,
      resolved: false,
    }

    const stateWithFlag: typeof base = {
      ...base,
      unresolved_ambiguities: [existingFlag],
    }

    const assessment = assessAmbiguity('do it', stateWithFlag, 'v1')
    const updated = updateDialogueState(stateWithFlag, 'do it', assessment, SEQ2)

    // The pre-existing unresolved flag should be carried forward
    expect(updated.unresolved_ambiguities.some(a => a.id === 'flag-1')).toBe(true)
    expect(updated.turn_count).toBe(1)
  })

  it('does not carry resolved ambiguities into new state', () => {
    const session = 'aaaaaaaa-bbbb-7ccc-8ddd-ffffffffffff' as UUIDv7
    const base = createInitialDialogueState(session)
    const SEQ1 = BigInt(1) as unknown as SequenceNumber
    const SEQ2 = BigInt(2) as unknown as SequenceNumber

    const resolvedFlag: AmbiguityFlag = {
      id: 'flag-resolved',
      ambiguity_type: AmbiguityType.REFERENTIAL,
      divergence_score: 0.3,
      introduced_at_sequence: SEQ1,
      resolved: true,
    }

    const stateWithResolved: typeof base = {
      ...base,
      unresolved_ambiguities: [resolvedFlag],
    }

    const assessment = assessAmbiguity('clear statement with no ambiguity at all whatsoever', stateWithResolved, 'v1')
    const updated = updateDialogueState(stateWithResolved, 'clear statement', assessment, SEQ2)

    // The resolved flag should NOT be carried forward
    expect(updated.unresolved_ambiguities.some(a => a.id === 'flag-resolved')).toBe(false)
  })
})
