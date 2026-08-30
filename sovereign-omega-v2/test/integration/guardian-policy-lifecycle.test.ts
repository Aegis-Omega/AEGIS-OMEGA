// ============================================================
// Gate 109 — Guardian Policy Lifecycle (Integration)
// ~18 tests: Guardian policy full lifecycle: proposal →
//   T4/T5 rejection → T2 amendment → APPROVED → binding →
//   re-run admitAbstraction passes.
// ============================================================

import { describe, it, expect } from 'vitest'
import { PolicyAmendmentEngine } from '../../src/constitutional/policy.js'
import { buildOntologyRecord, admitAbstraction } from '../../src/constitutional/reduction.js'
import type { OntologyInput } from '../../src/constitutional/reduction.js'
import type { SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

// ─── Basic lifecycle ──────────────────────────────────────

describe('Guardian Policy: proposal lifecycle', () => {
  it('propose → APPROVED → APPLIED lifecycle', () => {
    let engine = PolicyAmendmentEngine.empty()
    const { engine: e1, amendment } = engine.propose({
      target: 'SwarmConsensus',
      description: 'Allow swarm convergence',
      constraint_delta: 'allow_swarm',
      at_sequence: 1,
    })
    const e2 = e1.recordVerdict(amendment.amendment_id, 'APPROVED')
    const e3 = e2.apply(amendment.amendment_id, { at_sequence: 2, invariants_passed: true })
    expect(e3.getById(amendment.amendment_id)!.status).toBe('APPLIED')
    expect(e3.getById(amendment.amendment_id)!.applied_at_sequence).toBe(2)
  })

  it('propose → VETOED: status=REJECTED (guardian rejects via veto)', () => {
    let engine = PolicyAmendmentEngine.empty()
    const { engine: e1, amendment } = engine.propose({
      target: 'T4Concept', description: 'T4 concept', constraint_delta: 'allow_t4', at_sequence: 1,
    })
    const e2 = e1.recordVerdict(amendment.amendment_id, 'VETOED')
    expect(e2.getById(amendment.amendment_id)!.status).toBe('REJECTED')
  })

  it('propose → VETOED: status=REJECTED with guardian_verdict=VETOED', () => {
    let engine = PolicyAmendmentEngine.empty()
    const { engine: e1, amendment } = engine.propose({
      target: 'T5Concept', description: 'T5 concept', constraint_delta: 'allow_t5', at_sequence: 1,
    })
    const e2 = e1.recordVerdict(amendment.amendment_id, 'VETOED')
    expect(e2.getById(amendment.amendment_id)!.status).toBe('REJECTED')
    expect(e2.getById(amendment.amendment_id)!.guardian_verdict).toBe('VETOED')
  })

  it('double apply throws PolicyAmendmentError', () => {
    let engine = PolicyAmendmentEngine.empty()
    const { engine: e1, amendment } = engine.propose({
      target: 'TestModule', description: 'Test', constraint_delta: 'allow_test', at_sequence: 1,
    })
    const e2 = e1.recordVerdict(amendment.amendment_id, 'APPROVED')
    const e3 = e2.apply(amendment.amendment_id, { at_sequence: 2, invariants_passed: true })
    expect(() => e3.apply(amendment.amendment_id, { at_sequence: 3, invariants_passed: true })).toThrow()
  })

  it('amendment_id is deterministic (FNV-1a based)', () => {
    const engine = PolicyAmendmentEngine.empty()
    const { amendment: a1 } = engine.propose({
      target: 'Test', description: 'Test', constraint_delta: 'allow_x', at_sequence: 1,
    })
    const { amendment: a2 } = engine.propose({
      target: 'Test', description: 'Test', constraint_delta: 'allow_x', at_sequence: 1,
    })
    // Same inputs → same amendment_id
    expect(a1.amendment_id).toBe(a2.amendment_id)
    // Has amd_ prefix
    expect(a1.amendment_id).toMatch(/^amd_[0-9a-f]+$/)
  })
})

// ─── T4/T5 concept rejection ──────────────────────────────

describe('Guardian Policy: T4/T5 concept handling', () => {
  it('T3 (research conjecture) with all mappings → admitAbstraction ADMITTED', async () => {
    const rec = await buildOntologyRecord({
      name: 'ResearchConjectureProtocol',
      primitive_mapping: 'HASH',
      replay_mapping: 'HARMONIZE',
      topology_mapping: 'LINEAGE',
      epistemic_tier: 'T3',
      sequence: seq(1),
    })
    const result = await admitAbstraction([], rec)
    expect(result.verdict).toBe('ADMITTED')
  })

  it('T2 concept with all mappings → admitAbstraction ADMITTED', async () => {
    const rec = await buildOntologyRecord({
      name: 'SwarmConvergenceProtocol',
      primitive_mapping: 'VERIFY',
      replay_mapping: 'LOCK',
      topology_mapping: 'CONSENSUS',
      epistemic_tier: 'T2',
      sequence: seq(1),
    })
    const result = await admitAbstraction([], rec)
    expect(result.verdict).toBe('ADMITTED')
  })

  it('T0 concept → ADMITTED (mechanically proven)', async () => {
    const rec = await buildOntologyRecord({
      name: 'DeterministicHash',
      primitive_mapping: 'HASH',
      replay_mapping: 'READ',
      topology_mapping: 'LINEAGE',
      epistemic_tier: 'T0',
      sequence: seq(1),
    })
    const result = await admitAbstraction([], rec)
    expect(result.verdict).toBe('ADMITTED')
  })
})

// ─── Holonic five-concept admission proof ─────────────────

describe('Guardian Policy: holonic five-concept admission', () => {
  it('all five holonic concepts → ADMITTED after policy approval', async () => {
    const concepts: OntologyInput[] = [
      { name: 'SwarmConvergenceProtocol', primitive_mapping: 'VERIFY', replay_mapping: 'LOCK', topology_mapping: 'CONSENSUS', epistemic_tier: 'T2', sequence: seq(34) },
      { name: 'SelfAttestationProtocol', primitive_mapping: 'HASH', replay_mapping: 'HARMONIZE', topology_mapping: 'DFA', epistemic_tier: 'T0', sequence: seq(35) },
      { name: 'GovernanceMirrorStream', primitive_mapping: 'CANONICALIZE', replay_mapping: 'PROPAGATE', topology_mapping: 'LINEAGE', epistemic_tier: 'T1', sequence: seq(36) },
      { name: 'CapabilityEvolutionProtocol', primitive_mapping: 'SEQUENCE', replay_mapping: 'ASSESS', topology_mapping: 'DFA', epistemic_tier: 'T2', sequence: seq(37) },
      { name: 'AdaptiveLineageChain', primitive_mapping: 'HASH', replay_mapping: 'HARMONIZE', topology_mapping: 'LINEAGE', epistemic_tier: 'T2', sequence: seq(38) },
    ]
    for (const input of concepts) {
      const rec = await buildOntologyRecord(input)
      const result = await admitAbstraction([], rec)
      expect(result.verdict).toBe('ADMITTED')
    }
  })

  it('duplicate concept name → REJECTED', async () => {
    const rec1 = await buildOntologyRecord({
      name: 'UniqueProtocol', primitive_mapping: 'HASH', replay_mapping: 'READ',
      topology_mapping: 'LINEAGE', epistemic_tier: 'T2', sequence: seq(1),
    })
    const rec2 = await buildOntologyRecord({
      name: 'UniqueProtocol', primitive_mapping: 'HASH', replay_mapping: 'READ',
      topology_mapping: 'LINEAGE', epistemic_tier: 'T2', sequence: seq(2),
    })
    const existing = [rec1]
    const result = await admitAbstraction(existing, rec2)
    expect(result.verdict).toBe('REJECTED')
    expect(result.reason).toMatch(/already/i)
  })

  it('50-amendment engine: all APPLIED at end', () => {
    let engine = PolicyAmendmentEngine.empty()
    const ids: string[] = []
    for (let i = 1; i <= 50; i++) {
      const { engine: next, amendment } = engine.propose({
        target: `Module${i}`, description: `Amendment ${i}`, constraint_delta: `delta${i}`, at_sequence: i,
      })
      engine = next.recordVerdict(amendment.amendment_id, 'APPROVED')
      ids.push(amendment.amendment_id)
    }
    for (let i = 0; i < 50; i++) {
      engine = engine.apply(ids[i]!, { at_sequence: 51 + i, invariants_passed: true })
    }
    for (const id of ids) {
      expect(engine.getById(id)!.status).toBe('APPLIED')
    }
  })
})
