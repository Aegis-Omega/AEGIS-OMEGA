// ============================================================
// Gate 33 — Ontology Reduction Enforcement Tests
// ~27 tests: buildOntologyRecord, admitAbstraction, ReductionRegistry,
//   T4/T5 blocking, dedup, sequence monotonicity, determinism.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SequenceNumber } from '../../src/core/types.js'
import {
  buildOntologyRecord,
  admitAbstraction,
  ReductionRegistry,
  ReductionError,
  REDUCTION_SCHEMA_VERSION,
  type OntologyInput,
} from '../../src/constitutional/reduction.js'

// ─── Helpers ───────────────────────────────────────────────

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const VALID: OntologyInput = {
  name: 'TopologyHashEngine',
  primitive_mapping: 'HASH',
  replay_mapping: 'HARMONIZE',
  topology_mapping: 'LEDGER',
  epistemic_tier: 'T0',
  sequence: seq(1),
}

// ─── buildOntologyRecord ───────────────────────────────────

describe('buildOntologyRecord', () => {
  it('produces a frozen record with all fields', async () => {
    const r = await buildOntologyRecord(VALID)
    expect(Object.isFrozen(r)).toBe(true)
    expect(r.name).toBe('TopologyHashEngine')
    expect(r.primitive_mapping).toBe('HASH')
    expect(r.replay_mapping).toBe('HARMONIZE')
    expect(r.topology_mapping).toBe('LEDGER')
    expect(r.epistemic_tier).toBe('T0')
    expect(r.is_replay_reconstructable).toBe(true)
  })

  it('abstraction_id is 64-char hex', async () => {
    const r = await buildOntologyRecord(VALID)
    expect(r.abstraction_id).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(r.abstraction_id)).toBe(true)
  })

  it('record_hash is 64-char hex', async () => {
    const r = await buildOntologyRecord(VALID)
    expect(r.record_hash).toHaveLength(64)
  })

  it('abstraction_id is deterministic × 3', async () => {
    const id1 = (await buildOntologyRecord(VALID)).abstraction_id
    const id2 = (await buildOntologyRecord(VALID)).abstraction_id
    const id3 = (await buildOntologyRecord(VALID)).abstraction_id
    expect(id1).toBe(id2)
    expect(id2).toBe(id3)
  })

  it('different name → different abstraction_id', async () => {
    const r1 = await buildOntologyRecord(VALID)
    const r2 = await buildOntologyRecord({ ...VALID, name: 'LineageCertifier' })
    expect(r1.abstraction_id).not.toBe(r2.abstraction_id)
  })
})

// ─── admitAbstraction ─────────────────────────────────────

describe('admitAbstraction — ADMITTED', () => {
  it('valid T0 abstraction with all four mappings → ADMITTED', async () => {
    const r = await buildOntologyRecord(VALID)
    const result = await admitAbstraction([], r)
    expect(result.verdict).toBe('ADMITTED')
    expect(result.is_replay_reconstructable).toBe(true)
  })

  it('result is frozen', async () => {
    const r = await buildOntologyRecord(VALID)
    const result = await admitAbstraction([], r)
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('result_hash is 64-char hex', async () => {
    const r = await buildOntologyRecord(VALID)
    const result = await admitAbstraction([], r)
    expect(result.result_hash).toHaveLength(64)
  })

  it('T1, T2, T3 abstractions are admitted', async () => {
    for (const tier of ['T1', 'T2', 'T3'] as const) {
      const r = await buildOntologyRecord({ ...VALID, epistemic_tier: tier, name: `Test_${tier}`, sequence: seq(1) })
      const result = await admitAbstraction([], r)
      expect(result.verdict).toBe('ADMITTED')
    }
  })
})

describe('admitAbstraction — REJECTED', () => {
  it('T4 tier → REJECTED (constitutionally blocked)', async () => {
    const r = await buildOntologyRecord({ ...VALID, epistemic_tier: 'T0' })
    const tampered = Object.freeze({ ...r, epistemic_tier: 'T4' as 'T0' })
    const result = await admitAbstraction([], tampered)
    expect(result.verdict).toBe('REJECTED')
    expect(result.reason).toContain('T4')
  })

  it('T5 tier → REJECTED', async () => {
    const r = await buildOntologyRecord({ ...VALID, epistemic_tier: 'T0' })
    const tampered = Object.freeze({ ...r, epistemic_tier: 'T5' as 'T0' })
    const result = await admitAbstraction([], tampered)
    expect(result.verdict).toBe('REJECTED')
  })

  it('duplicate name → REJECTED', async () => {
    const r1 = await buildOntologyRecord(VALID)
    const r2 = await buildOntologyRecord({ ...VALID, sequence: seq(2) })
    const result = await admitAbstraction([r1], r2)
    expect(result.verdict).toBe('REJECTED')
    expect(result.reason).toContain('already registered')
  })
})

// ─── ReductionRegistry ─────────────────────────────────────

describe('ReductionRegistry', () => {
  it('starts empty', () => {
    const reg = ReductionRegistry.empty()
    expect(reg.length).toBe(0)
    expect(reg.isKnown('anything')).toBe(false)
  })

  it('admitted record appears in registry', async () => {
    let reg = ReductionRegistry.empty()
    const r = await buildOntologyRecord(VALID)
    const { registry, result } = await reg.register(r)
    expect(result.verdict).toBe('ADMITTED')
    expect(registry.length).toBe(1)
    expect(registry.isKnown('TopologyHashEngine')).toBe(true)
  })

  it('rejected record does not mutate registry', async () => {
    let reg = ReductionRegistry.empty()
    const r1 = await buildOntologyRecord(VALID)
    const { registry: reg2 } = await reg.register(r1)
    const r2 = await buildOntologyRecord({ ...VALID, sequence: seq(2) })
    const { registry: reg3, result } = await reg2.register(r2)
    expect(result.verdict).toBe('REJECTED')
    expect(reg3.length).toBe(1)
  })

  it('register is immutable — original unchanged', async () => {
    const reg = ReductionRegistry.empty()
    const r = await buildOntologyRecord(VALID)
    await reg.register(r)
    expect(reg.length).toBe(0)
  })

  it('throws ReductionError on non-monotonic sequence', async () => {
    let reg = ReductionRegistry.empty()
    const r1 = await buildOntologyRecord({ ...VALID, sequence: seq(5) })
    const { registry } = await reg.register(r1)
    const r2 = await buildOntologyRecord({ ...VALID, name: 'Other', sequence: seq(3) })
    await expect(registry.register(r2)).rejects.toThrow(ReductionError)
  })

  it('multi-record chain: 3 distinct abstractions admitted', async () => {
    let reg = ReductionRegistry.empty()
    const names = ['Alpha', 'Beta', 'Gamma']
    for (let i = 0; i < names.length; i++) {
      const r = await buildOntologyRecord({ ...VALID, name: names[i]!, sequence: seq(i + 1) })
      const { registry, result } = await reg.register(r)
      expect(result.verdict).toBe('ADMITTED')
      reg = registry
    }
    expect(reg.length).toBe(3)
    for (const name of names) expect(reg.isKnown(name)).toBe(true)
  })

  it('REDUCTION_SCHEMA_VERSION is 1.0.0', () => {
    expect(REDUCTION_SCHEMA_VERSION).toBe('1.0.0')
  })
})
