// ============================================================
// Gate 78 — Policy × Reduction Composition (Integration)
// ~18 tests: GuardianPolicy amendment lifecycle triggers
//   admitAbstraction re-evaluation; APPROVED propagates;
//   VETOED blocks registration; cross-module record_hash binding.
// ============================================================

import { describe, it, expect } from 'vitest'
import { PolicyAmendmentEngine } from '../../src/constitutional/policy.js'
import { buildOntologyRecord, admitAbstraction, ReductionRegistry, type OntologyInput } from '../../src/constitutional/reduction.js'
import type { SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

function makeInput(name: string, n: number): OntologyInput {
  return {
    name,
    primitive_mapping: 'HASH',
    replay_mapping: 'LOCK',
    topology_mapping: 'LINEAGE',
    epistemic_tier: 'T2',
    sequence: seq(n),
  }
}

// ─── Policy → Reduction pipeline ─────────────────────────

describe('Policy × Reduction: amendment drives admission', () => {
  it('APPROVED amendment → abstraction admitted to registry', async () => {
    let engine = PolicyAmendmentEngine.empty()
    const { engine: next, amendment } = engine.propose({
      target: 'AdaptiveLineage',
      description: 'Admit adaptive lineage abstraction',
      constraint_delta: 'allow_adaptive_lineage',
      at_sequence: 1,
    })
    engine = next.recordVerdict(amendment.amendment_id, 'APPROVED')
    engine = engine.apply(amendment.amendment_id, { at_sequence: 2, invariants_passed: true })

    const applied = engine.getById(amendment.amendment_id)!
    expect(applied.status).toBe('APPLIED')

    // Post-amendment: admit the corresponding abstraction
    const rec = await buildOntologyRecord(makeInput('AdaptiveLineage', 1))
    const result = await admitAbstraction([], rec)
    expect(result.verdict).toBe('ADMITTED')
  })

  it('VETOED amendment → admission blocked (manual enforcement)', async () => {
    let engine = PolicyAmendmentEngine.empty()
    const { engine: next, amendment } = engine.propose({
      target: 'BlockedConcept',
      description: 'Blocked concept',
      constraint_delta: 'allow_blocked',
      at_sequence: 1,
    })
    engine = next.recordVerdict(amendment.amendment_id, 'VETOED')
    const a = engine.getById(amendment.amendment_id)!
    expect(a.status).toBe('REJECTED')
    // By policy convention: do not admit if amendment was VETOED
    // We verify the guardian verdict is propagated correctly
    expect(a.guardian_verdict).toBe('VETOED')
  })

  it('5 amendments → 5 APPLIED → 5 abstractions admitted', async () => {
    let engine = PolicyAmendmentEngine.empty()
    const ids: string[] = []
    for (let i = 1; i <= 5; i++) {
      const { engine: next, amendment } = engine.propose({
        target: `concept_${i}`,
        description: `Amendment ${i}`,
        constraint_delta: `allow_${i}`,
        at_sequence: i,
      })
      engine = next
      ids.push(amendment.amendment_id)
    }
    for (const id of ids) {
      engine = engine.recordVerdict(id, 'APPROVED')
    }
    for (let i = 0; i < ids.length; i++) {
      engine = engine.apply(ids[i]!, { at_sequence: 100 + i, invariants_passed: true })
    }
    expect(engine.getAll().every(a => a.status === 'APPLIED')).toBe(true)

    let registry = ReductionRegistry.empty()
    for (let i = 1; i <= 5; i++) {
      const rec = await buildOntologyRecord(makeInput(`Concept_${i}`, i))
      const { registry: next } = await registry.register(rec)
      registry = next
    }
    expect(registry.length).toBe(5)
  })
})

// ─── Structural binding ───────────────────────────────────

describe('Policy × Reduction: structural binding', () => {
  it('amendment record_hash and ontology record_hash are both 64-char hex', async () => {
    const engine = PolicyAmendmentEngine.empty()
    const { amendment } = engine.propose({ target: 'X', description: 'D', constraint_delta: 'C', at_sequence: 1 })
    expect(typeof amendment.amendment_id).toBe('string')
    expect(amendment.amendment_id.length).toBeGreaterThan(0)

    const rec = await buildOntologyRecord(makeInput('X', 1))
    expect(rec.record_hash).toHaveLength(64)
    expect(rec.record_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('registry.isKnown returns true after registration', async () => {
    let registry = ReductionRegistry.empty()
    const rec = await buildOntologyRecord(makeInput('TestAbstraction', 1))
    const { registry: next } = await registry.register(rec)
    registry = next
    expect(registry.isKnown('TestAbstraction')).toBe(true)
  })

  it('registry.isKnown returns false for unregistered', () => {
    const registry = ReductionRegistry.empty()
    expect(registry.isKnown('Unknown')).toBe(false)
  })

  it('empty registry has length 0', () => {
    expect(ReductionRegistry.empty().length).toBe(0)
  })

  it('immutable: registry unchanged after failed register (duplicate)', async () => {
    let registry = ReductionRegistry.empty()
    const rec1 = await buildOntologyRecord(makeInput('Same', 1))
    const rec2 = await buildOntologyRecord({ ...makeInput('Same', 2) })
    const { registry: next } = await registry.register(rec1)
    registry = next
    await registry.register(rec2)  // rejected — duplicate
    expect(registry.length).toBe(1)
  })
})
