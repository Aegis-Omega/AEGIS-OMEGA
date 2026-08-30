// ============================================================
// SOVEREIGN OMEGA — Gate Mutation Governance Registry tests
// EPISTEMIC TIER: T0
//
// Tests for gate/mutation-governance.ts:
//   MutationGovernanceRegistry — registerCapacity, register, seal,
//   validateKBound, markApplied, findPath
// ============================================================

import { describe, it, expect } from 'vitest'
import { MutationGovernanceRegistry } from '../../src/gate/mutation-governance.js'
import type { MigrationContract } from '../../src/gate/mutation-governance.js'
import { CapabilityClass } from '../../src/core/types.js'
import type { SHA256Hex } from '../../src/core/types.js'

const H = '0'.repeat(64) as SHA256Hex

function makeCapacity(id: string, kBound: number) {
  return {
    component_id: id,
    k_bound: kBound,
    mutation_operators: [] as string[],
    dependency_graph_hash: H,
    capability_class: CapabilityClass.INFERENCE,
    epoch_duration_ms: 1000,
    k_measurement_version: '1.0.0',
  }
}

function makeMigration(id: string, fromId: string, fromVer: string, toId: string, toVer: string, deltaK = 1): MigrationContract {
  return {
    migration_id: id,
    from_schema_id: fromId,
    from_version: fromVer,
    to_schema_id: toId,
    to_version: toVer,
    transform: (p) => p,
    transform_source_hash: H,
    delta_k: deltaK,
  }
}

// ── registerCapacity ──────────────────────────────────────

describe('MutationGovernanceRegistry.registerCapacity', () => {
  it('accepts a valid capacity declaration', () => {
    const reg = new MutationGovernanceRegistry()
    expect(() => reg.registerCapacity(makeCapacity('comp-ok', 10))).not.toThrow()
  })

  it('throws INVALID_K_BOUND for negative k_bound', () => {
    const reg = new MutationGovernanceRegistry()
    expect(() => reg.registerCapacity(makeCapacity('comp-neg', -1))).toThrow('INVALID_K_BOUND')
  })

  it('throws REGISTRY_SEALED after seal()', () => {
    const reg = new MutationGovernanceRegistry()
    reg.seal()
    expect(() => reg.registerCapacity(makeCapacity('comp-sealed', 5))).toThrow('REGISTRY_SEALED')
  })
})

// ── register ──────────────────────────────────────────────

describe('MutationGovernanceRegistry.register', () => {
  it('accepts a valid migration + rollback pair', () => {
    const reg = new MutationGovernanceRegistry()
    expect(() => reg.register(
      makeMigration('m1', 's', '1.0', 's', '2.0'),
      { migration_id: 'm1', rollback_supported: false },
    )).not.toThrow()
  })

  it('throws NEGATIVE_DELTA_K_FORBIDDEN for negative delta_k', () => {
    const reg = new MutationGovernanceRegistry()
    expect(() => reg.register(
      makeMigration('m-neg', 's', '1.0', 's', '2.0', -1),
      { migration_id: 'm-neg', rollback_supported: false },
    )).toThrow('NEGATIVE_DELTA_K_FORBIDDEN')
  })

  it('throws REGISTRY_SEALED after seal()', () => {
    const reg = new MutationGovernanceRegistry()
    reg.seal()
    expect(() => reg.register(
      makeMigration('m-sealed', 's', '1.0', 's', '2.0'),
      { migration_id: 'm-sealed', rollback_supported: false },
    )).toThrow('REGISTRY_SEALED')
  })
})

// ── validateKBound ────────────────────────────────────────

describe('MutationGovernanceRegistry.validateKBound', () => {
  it('throws NO_CAPACITY when component is not registered', () => {
    const reg = new MutationGovernanceRegistry()
    expect(() => reg.validateKBound('no-comp', 1)).toThrow('NO_CAPACITY_FOR_no-comp')
  })

  it('passes when cumulative delta is within k_bound', () => {
    const reg = new MutationGovernanceRegistry()
    reg.registerCapacity(makeCapacity('c1', 5))
    expect(() => reg.validateKBound('c1', 3)).not.toThrow()
  })

  it('throws K_BOUND_EXCEEDED when delta exceeds k_bound', () => {
    const reg = new MutationGovernanceRegistry()
    reg.registerCapacity(makeCapacity('c2', 3))
    expect(() => reg.validateKBound('c2', 4)).toThrow('K_BOUND_EXCEEDED_c2')
  })

  it('accounts for previously applied migrations in cumulative total', () => {
    const reg = new MutationGovernanceRegistry()
    reg.registerCapacity(makeCapacity('c3', 3))
    reg.register(makeMigration('applied-m', 'x', '1.0', 'x', '2.0', 2), { migration_id: 'applied-m', rollback_supported: false })
    reg.markApplied('c3', 'applied-m')
    // current k = 2 (from applied-m), delta = 2 → total = 4 > k_bound 3
    expect(() => reg.validateKBound('c3', 2)).toThrow('K_BOUND_EXCEEDED_c3')
  })

  it('passes when applied migrations + delta is exactly at k_bound', () => {
    const reg = new MutationGovernanceRegistry()
    reg.registerCapacity(makeCapacity('c4', 3))
    reg.register(makeMigration('m-exact', 'x', '1.0', 'x', '2.0', 1), { migration_id: 'm-exact', rollback_supported: false })
    reg.markApplied('c4', 'm-exact')
    // current k = 1, delta = 2 → total = 3 === k_bound 3 → should pass (not exceed)
    expect(() => reg.validateKBound('c4', 2)).not.toThrow()
  })
})

// ── findPath ──────────────────────────────────────────────

describe('MutationGovernanceRegistry.findPath', () => {
  it('returns empty array when from and to are identical', () => {
    const reg = new MutationGovernanceRegistry()
    expect(reg.findPath('schema', '1.0', 'schema', '1.0')).toEqual([])
  })

  it('returns null when no migration registered for the path', () => {
    const reg = new MutationGovernanceRegistry()
    expect(reg.findPath('a', '1.0', 'b', '2.0')).toBeNull()
  })

  it('finds a direct single-step migration', () => {
    const reg = new MutationGovernanceRegistry()
    const m = makeMigration('direct', 'schema', '1.0', 'schema', '2.0')
    reg.register(m, { migration_id: 'direct', rollback_supported: false })
    const path = reg.findPath('schema', '1.0', 'schema', '2.0')
    expect(path).toHaveLength(1)
    expect(path![0]!.migration_id).toBe('direct')
  })

  it('finds a two-step migration chain', () => {
    const reg = new MutationGovernanceRegistry()
    const m1 = makeMigration('hop1', 'schema', '1.0', 'schema', '2.0')
    const m2 = makeMigration('hop2', 'schema', '2.0', 'schema', '3.0')
    reg.register(m1, { migration_id: 'hop1', rollback_supported: false })
    reg.register(m2, { migration_id: 'hop2', rollback_supported: false })
    const path = reg.findPath('schema', '1.0', 'schema', '3.0')
    expect(path).toHaveLength(2)
    expect(path![0]!.migration_id).toBe('hop1')
    expect(path![1]!.migration_id).toBe('hop2')
  })
})
