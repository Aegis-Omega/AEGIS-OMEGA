// ============================================================
// SOVEREIGN OMEGA — Mutation Governance Registry tests
// EPISTEMIC TIER: T0
//
// Tests for event/mutation-registry.ts:
//   MutationGovernanceError   — error subclass
//   findMigrationPath          — same-version, no-path, multi-hop
//   applyMigrationPath         — empty path passthrough, transform chain
//   checkPinCompatibility      — same version, missing path
//   getMigration / getRollback — unregistered → undefined
//   seal()                     — post-seal register throws (runs last)
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  mutationGovernanceRegistry,
  MutationGovernanceError,
} from '../../src/event/mutation-registry.js'
import type { MigrationContract } from '../../src/event/mutation-registry.js'
import type { SHA256Hex } from '../../src/core/types.js'

const H = '0'.repeat(64) as SHA256Hex

function makeMigration(
  id: string,
  fromSchema: string,
  fromVer: string,
  toSchema: string,
  toVer: string,
  transform: (p: unknown) => unknown = (p) => p,
): MigrationContract {
  return {
    migration_id: id,
    from_schema_id: fromSchema,
    from_version: fromVer,
    to_schema_id: toSchema,
    to_version: toVer,
    description: `migrate ${fromSchema}:${fromVer} → ${toSchema}:${toVer}`,
    transform,
    transform_hash: H,
  }
}

// ── MutationGovernanceError ───────────────────────────────

describe('MutationGovernanceError', () => {
  it('is an Error subclass with correct name and message', () => {
    const e = new MutationGovernanceError('test error')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('MutationGovernanceError')
    expect(e.message).toBe('test error')
  })
})

// ── findMigrationPath ─────────────────────────────────────

describe('mutationGovernanceRegistry.findMigrationPath', () => {
  it('returns empty array when from and to are identical', () => {
    const path = mutationGovernanceRegistry.findMigrationPath(
      'event-envelope', '1.0.0',
      'event-envelope', '1.0.0',
    )
    expect(path).toEqual([])
    expect(path).toHaveLength(0)
  })

  it('returns null when no migration is registered for the requested path', () => {
    const path = mutationGovernanceRegistry.findMigrationPath(
      'nonexistent-schema', '1.0.0',
      'nonexistent-schema', '2.0.0',
    )
    expect(path).toBeNull()
  })

  it('returns null when target schema differs from all registered migrations', () => {
    const path = mutationGovernanceRegistry.findMigrationPath(
      'schema-a', '1.0.0',
      'schema-z', '99.0.0',
    )
    expect(path).toBeNull()
  })
})

// ── applyMigrationPath ────────────────────────────────────

describe('mutationGovernanceRegistry.applyMigrationPath', () => {
  it('returns payload unchanged for empty migration path', () => {
    const payload = { value: 42, data: 'test' }
    const result = mutationGovernanceRegistry.applyMigrationPath(payload, [])
    expect(result).toBe(payload)
  })

  it('applies a single transform', () => {
    const migration = makeMigration(
      'inline-1', 's', '1.0', 's', '2.0',
      (p) => ({ ...(p as object), version: 2 }),
    )
    const result = mutationGovernanceRegistry.applyMigrationPath({ version: 1 }, [migration])
    expect(result).toEqual({ version: 2 })
  })

  it('applies transforms in order (chain of two)', () => {
    const step1 = makeMigration('s1', 's', '1.0', 's', '2.0', (p) => ({ ...(p as object), step1: true }))
    const step2 = makeMigration('s2', 's', '2.0', 's', '3.0', (p) => ({ ...(p as object), step2: true }))
    const result = mutationGovernanceRegistry.applyMigrationPath({}, [step1, step2])
    expect(result).toEqual({ step1: true, step2: true })
  })
})

// ── checkPinCompatibility ─────────────────────────────────

describe('mutationGovernanceRegistry.checkPinCompatibility', () => {
  const pin = (version: string) => ({
    schema_version: version,
    verifier_versions: {},
    calibration_model_version: '1.0.0',
    projection_compiler_version: '1.0.0',
    k_measurement_version: '1.0.0',
  })

  it('returns compatible=true, requires_migration=false for identical versions', async () => {
    const result = await mutationGovernanceRegistry.checkPinCompatibility(pin('1.0.0'), pin('1.0.0'))
    expect(result.compatible).toBe(true)
    expect(result.requires_migration).toBe(false)
    expect(result.migration_path).toEqual([])
  })

  it('returns compatible=false when versions differ and no migration path exists', async () => {
    const result = await mutationGovernanceRegistry.checkPinCompatibility(pin('9.9.9'), pin('10.0.0'))
    expect(result.compatible).toBe(false)
    expect(result.requires_migration).toBe(true)
    expect(result.migration_path).toBeNull()
    expect(result.error).toBeTruthy()
  })
})

// ── getMigration / getRollback ────────────────────────────

describe('mutationGovernanceRegistry.getMigration / getRollback', () => {
  it('returns undefined for an unregistered migration ID', () => {
    expect(mutationGovernanceRegistry.getMigration('no-such-migration-xyz')).toBeUndefined()
  })

  it('returns undefined for an unregistered rollback ID', () => {
    expect(mutationGovernanceRegistry.getRollback('no-such-rollback-xyz')).toBeUndefined()
  })
})

// ── seal (runs last — permanent state change) ─────────────

describe('mutationGovernanceRegistry.seal (post-seal register throws)', () => {
  it('throws MutationGovernanceError after seal() is called', async () => {
    mutationGovernanceRegistry.seal()
    await expect(mutationGovernanceRegistry.register(
      makeMigration('post-seal', 'x', '1.0', 'x', '2.0'),
      { migration_id: 'post-seal', rollback_supported: false, rollback_constraints: [] },
    )).rejects.toThrow(MutationGovernanceError)
  })
})
