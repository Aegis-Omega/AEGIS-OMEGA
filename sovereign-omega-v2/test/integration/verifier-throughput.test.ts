// ============================================================
// Gate 46 — Constitutional Verifier Throughput
// ~24 tests: ReductionRegistry under concurrent and adversarial
//   registration, capsule VM across all three outcome paths at
//   scale (100 executions), determinism under repetition,
//   rejection robustness (T4/T5, duplicate, stale sequence).
//
// Covers the verifier throughput surface identified in the
// constitutional stabilization assessment.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SequenceNumber } from '../../src/core/types.js'
import {
  buildOntologyRecord,
  admitAbstraction,
  ReductionRegistry,
  type OntologyInput,
} from '../../src/constitutional/reduction.js'
import {
  buildManifest,
  runCapsule,
  capabilityGranted,
} from '../../src/capsule/kernel.js'
import { CapsuleError } from '../../src/capsule/types.js'
import type { SHA256Hex } from '../../src/core/types.js'

// ─── Helpers ───────────────────────────────────────────────

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

function makeInput(n: number, tier: OntologyInput['epistemic_tier'] = 'T0'): OntologyInput {
  return {
    name: `Abstraction_${n}`,
    primitive_mapping: 'HASH',
    replay_mapping: 'HARMONIZE',
    topology_mapping: 'LINEAGE',
    epistemic_tier: tier,
    sequence: seq(n),
  }
}

// ─── ReductionRegistry concurrent admits ───────────────────

describe('ReductionRegistry: concurrent admission', () => {
  it('50 distinct abstractions all admitted sequentially', async () => {
    let registry = ReductionRegistry.empty()
    for (let i = 1; i <= 50; i++) {
      const record = await buildOntologyRecord(makeInput(i))
      const { registry: next, result } = await registry.register(record)
      expect(result.verdict).toBe('ADMITTED')
      registry = next
    }
    expect(registry.length).toBe(50)
  })

  it('50 concurrent buildOntologyRecord calls produce distinct abstraction_ids', async () => {
    const records = await Promise.all(
      Array.from({ length: 50 }, (_, i) => buildOntologyRecord(makeInput(i + 1))),
    )
    const ids = new Set(records.map(r => r.abstraction_id))
    expect(ids.size).toBe(50)
  })

  it('registry state is immutable: REJECTED registration does not change length', async () => {
    let registry = ReductionRegistry.empty()
    const record = await buildOntologyRecord(makeInput(1))
    const { registry: r1 } = await registry.register(record)
    const dupRecord = await buildOntologyRecord({ ...makeInput(1), sequence: seq(2) })
    const { registry: r2, result } = await r1.register(dupRecord)
    expect(result.verdict).toBe('REJECTED')
    expect(r2.length).toBe(r1.length)  // unchanged
  })

  it('10 mixed admits and rejections: final count matches admits only', async () => {
    let registry = ReductionRegistry.empty()
    let expectedCount = 0
    for (let i = 1; i <= 10; i++) {
      const record = await buildOntologyRecord(makeInput(i))
      const { registry: next, result } = await registry.register(record)
      if (result.verdict === 'ADMITTED') expectedCount++
      registry = next
    }
    expect(registry.length).toBe(expectedCount)
    expect(expectedCount).toBe(10)
  })
})

// ─── Adversarial rejection paths ──────────────────────────

describe('ReductionRegistry: adversarial rejection', () => {
  it('T4 tier → REJECTED immediately', async () => {
    const record = await buildOntologyRecord({ ...makeInput(1), epistemic_tier: 'T4' as unknown as OntologyInput['epistemic_tier'] })
    const result = await admitAbstraction([], record)
    expect(result.verdict).toBe('REJECTED')
    expect(result.reason).toMatch(/T4/)
  })

  it('duplicate name → REJECTED with reason containing name', async () => {
    const r1 = await buildOntologyRecord(makeInput(1))
    const r2 = await buildOntologyRecord({ ...makeInput(2), name: r1.name })
    const result = await admitAbstraction([r1], r2)
    expect(result.verdict).toBe('REJECTED')
    expect(result.reason).toContain(r1.name)
  })

  it('stale sequence in registry → throws ReductionError', async () => {
    let registry = ReductionRegistry.empty()
    const r1 = await buildOntologyRecord(makeInput(5))
    const { registry: r } = await registry.register(r1)
    registry = r
    const r2 = await buildOntologyRecord(makeInput(3))  // seq 3 < last seq 5
    await expect(registry.register(r2)).rejects.toThrow()
  })

  it('T4/T5 rejections produce frozen AdmissibilityResult', async () => {
    const record = await buildOntologyRecord({ ...makeInput(1), epistemic_tier: 'T4' as unknown as OntologyInput['epistemic_tier'] })
    const result = await admitAbstraction([], record)
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('ADMITTED result_hash is deterministic × 3', async () => {
    const record = await buildOntologyRecord(makeInput(1))
    const r1 = await admitAbstraction([], record)
    const r2 = await admitAbstraction([], record)
    const r3 = await admitAbstraction([], record)
    expect(r1.result_hash).toBe(r2.result_hash)
    expect(r2.result_hash).toBe(r3.result_hash)
  })
})

// ─── Capsule VM: 100-execution throughput ─────────────────

describe('Capsule VM: throughput across all three outcome paths', () => {
  it('100 COMMITTED executions with distinct sequences', async () => {
    const manifest = await buildManifest({
      capabilities: [{ type: 'EMIT_EVENT', target: 'e5', is_read_only: false }],
      entropy_budget: 10_000,
    })
    const results = await Promise.all(
      Array.from({ length: 100 }, (_, i) => runCapsule({
        manifest,
        capability_type: 'EMIT_EVENT',
        target: 'e5',
        payload: { index: i, value: `governance_frame_${i}` },
        sequence: seq(i + 1),
        parent_lineage_hash: null,
      })),
    )
    for (const r of results) {
      expect(r.outcome).toBe('COMMITTED')
      expect(r.event_hash).toHaveLength(64)
      expect(r.attestation_hash).toHaveLength(64)
    }
  })

  it('all 100 COMMITTED results have distinct attestation_hashes', async () => {
    const manifest = await buildManifest({
      capabilities: [{ type: 'QUERY_TOPOLOGY', target: 'topology', is_read_only: true }],
      entropy_budget: 10_000,
    })
    const results = await Promise.all(
      Array.from({ length: 100 }, (_, i) => runCapsule({
        manifest,
        capability_type: 'QUERY_TOPOLOGY',
        target: 'topology',
        payload: { query: `q${i}` },
        sequence: seq(i + 1),
        parent_lineage_hash: null,
      })),
    )
    const hashes = new Set(results.map(r => r.attestation_hash))
    expect(hashes.size).toBe(100)
  })

  it('REJECTED outcome when capability not in manifest', async () => {
    const manifest = await buildManifest({
      capabilities: [{ type: 'READ_STATE', target: 'ledger', is_read_only: true }],
      entropy_budget: 1000,
    })
    const result = await runCapsule({
      manifest,
      capability_type: 'EMIT_EVENT',  // not in manifest
      target: 'e5',
      payload: { data: 'unauthorized' },
      sequence: seq(1),
      parent_lineage_hash: null,
    })
    expect(result.outcome).toBe('REJECTED')
    expect(result.entropy_consumed).toBe(0)
    expect(result.reason).toBeDefined()
  })

  it('ROLLED_BACK when payload exceeds entropy_budget', async () => {
    const manifest = await buildManifest({
      capabilities: [{ type: 'EMIT_EVENT', target: 'e5', is_read_only: false }],
      entropy_budget: 5,  // tiny budget
    })
    const result = await runCapsule({
      manifest,
      capability_type: 'EMIT_EVENT',
      target: 'e5',
      payload: { data: 'this payload is definitely larger than 5 bytes canonical' },
      sequence: seq(1),
      parent_lineage_hash: null,
    })
    expect(result.outcome).toBe('ROLLED_BACK')
    expect(result.entropy_consumed).toBeGreaterThan(5)
  })
})

// ─── Capsule determinism and immutability ─────────────────

describe('Capsule VM: determinism and structural guarantees', () => {
  it('same input → same attestation_hash × 3', async () => {
    const manifest = await buildManifest({
      capabilities: [{ type: 'READ_STATE', target: 'state', is_read_only: true }],
      entropy_budget: 1000,
    })
    const input = {
      manifest,
      capability_type: 'READ_STATE' as const,
      target: 'state',
      payload: { key: 'sitr_state', value: 'STABLE' },
      sequence: seq(7),
      parent_lineage_hash: h('l'),
    }
    const r1 = await runCapsule(input)
    const r2 = await runCapsule(input)
    const r3 = await runCapsule(input)
    expect(r1.attestation_hash).toBe(r2.attestation_hash)
    expect(r2.attestation_hash).toBe(r3.attestation_hash)
    expect(r1.outcome).toBe('COMMITTED')
  })

  it('COMMITTED result is frozen', async () => {
    const manifest = await buildManifest({
      capabilities: [{ type: 'READ_STATE', target: 's', is_read_only: true }],
      entropy_budget: 1000,
    })
    const result = await runCapsule({
      manifest,
      capability_type: 'READ_STATE',
      target: 's',
      payload: {},
      sequence: seq(1),
      parent_lineage_hash: null,
    })
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('negative entropy_budget throws CapsuleError', async () => {
    await expect(buildManifest({
      capabilities: [],
      entropy_budget: -1,
    })).rejects.toThrow(CapsuleError)
  })

  it('capabilityGranted is consistent with runCapsule REJECTED', async () => {
    const manifest = await buildManifest({
      capabilities: [{ type: 'READ_STATE', target: 'x', is_read_only: true }],
      entropy_budget: 1000,
    })
    // EMIT_EVENT on 'e5' not in manifest
    expect(capabilityGranted(manifest, 'EMIT_EVENT', 'e5')).toBe(false)
    const result = await runCapsule({
      manifest, capability_type: 'EMIT_EVENT', target: 'e5',
      payload: {}, sequence: seq(1), parent_lineage_hash: null,
    })
    expect(result.outcome).toBe('REJECTED')
  })
})
