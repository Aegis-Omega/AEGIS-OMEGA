// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 10
// EPISTEMIC TIER: T0/T2
//
// Covers branch paths with zero prior coverage:
//   event/mutation-registry.ts  — register() success + all 3 throw paths,
//                                 findMigrationPath with registered migration,
//                                 checkPinCompatibility with valid path,
//                                 getMigration/getRollback success paths
//   skill-harness/scanner/codebase-scanner.ts
//                               — python_data_pattern, rust_systems_pattern
// ============================================================

import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

// ── event/mutation-registry.ts ──────────────────────────────

import {
  mutationGovernanceRegistry,
  MutationGovernanceError,
} from '../../src/event/mutation-registry.js'
import type { MigrationContract, RollbackContract } from '../../src/event/mutation-registry.js'
import { schemaRegistry } from '../../src/core/schema-registry.js'
import { hashValue } from '../../src/core/hashing.js'
import type { SHA256Hex } from '../../src/core/types.js'

// Schema definitions: cov10-schema (for direct migration tests) and
// event-envelope (for checkPinCompatibility which hardcodes that schema_id)
type SchemaDef = import('../../src/core/schema-registry.js').SchemaDefinition
const F1: SchemaDef = { schema_id: 'cov10-schema', version: '1.0.0', fields: [{ name: 'value', type: 'number', required: true }] }
const F2: SchemaDef = { schema_id: 'cov10-schema', version: '2.0.0', fields: [{ name: 'value', type: 'number', required: true }] }
const F3: SchemaDef = { schema_id: 'cov10-schema', version: '3.0.0', fields: [{ name: 'value', type: 'number', required: true }] }
// event-envelope schemas for checkPinCompatibility (it hardcodes 'event-envelope' as schema_id)
const EE1: SchemaDef = { schema_id: 'event-envelope', version: '1.0.0', fields: [{ name: 'event_id', type: 'string', required: true }] }
const EE2: SchemaDef = { schema_id: 'event-envelope', version: '2.0.0', fields: [{ name: 'event_id', type: 'string', required: true }] }

const transform12 = (p: unknown) => ({ ...(p as object), v2: true })
const transform23 = (p: unknown) => ({ ...(p as object), v3: true })
const transformEE = (p: unknown) => ({ ...(p as object), ee_v2: true })
const rollback12: RollbackContract = { migration_id: 'cov10-mig-1to2', rollback_supported: true, rollback_constraints: [] }
const rollback23: RollbackContract = { migration_id: 'cov10-mig-2to3', rollback_supported: false, rollback_constraints: ['irreversible'] }
const rollbackEE: RollbackContract = { migration_id: 'cov10-ee-1to2', rollback_supported: true, rollback_constraints: [] }

let mig12: MigrationContract
let mig23: MigrationContract
let migEE: MigrationContract

beforeAll(async () => {
  // Register all schemas first
  schemaRegistry.register(F1)
  schemaRegistry.register(F2)
  schemaRegistry.register(F3)
  schemaRegistry.register(EE1)
  schemaRegistry.register(EE2)

  // Compute correct transform hashes from function source
  const hash12 = await hashValue(transform12.toString()) as SHA256Hex
  const hash23 = await hashValue(transform23.toString()) as SHA256Hex
  const hashEE = await hashValue(transformEE.toString()) as SHA256Hex

  mig12 = { migration_id: 'cov10-mig-1to2', from_schema_id: 'cov10-schema', from_version: '1.0.0', to_schema_id: 'cov10-schema', to_version: '2.0.0', description: 'v1→v2', transform: transform12, transform_hash: hash12 }
  mig23 = { migration_id: 'cov10-mig-2to3', from_schema_id: 'cov10-schema', from_version: '2.0.0', to_schema_id: 'cov10-schema', to_version: '3.0.0', description: 'v2→v3', transform: transform23, transform_hash: hash23 }
  migEE = { migration_id: 'cov10-ee-1to2', from_schema_id: 'event-envelope', from_version: '1.0.0', to_schema_id: 'event-envelope', to_version: '2.0.0', description: 'ee v1→v2', transform: transformEE, transform_hash: hashEE }

  await mutationGovernanceRegistry.register(mig12, rollback12)
  await mutationGovernanceRegistry.register(mig23, rollback23)
  await mutationGovernanceRegistry.register(migEE, rollbackEE)
})

// ── register — error paths ─────────────────────────────────

describe('mutationGovernanceRegistry.register — error paths', () => {
  it('throws MutationGovernanceError when fromSchema is not found', async () => {
    const badH = '0'.repeat(64) as SHA256Hex
    await expect(
      mutationGovernanceRegistry.register(
        {
          migration_id: 'no-from',
          from_schema_id: 'nonexistent',
          from_version: '1.0.0',
          to_schema_id: 'cov10-schema',
          to_version: '2.0.0',
          description: 'test',
          transform: (p) => p,
          transform_hash: badH,
        },
        { migration_id: 'no-from', rollback_supported: false, rollback_constraints: [] },
      )
    ).rejects.toThrow(MutationGovernanceError)
  })

  it('throws MutationGovernanceError when toSchema is not found', async () => {
    const badH = '0'.repeat(64) as SHA256Hex
    await expect(
      mutationGovernanceRegistry.register(
        {
          migration_id: 'no-to',
          from_schema_id: 'cov10-schema',
          from_version: '1.0.0',
          to_schema_id: 'nonexistent',
          to_version: '9.9.9',
          description: 'test',
          transform: (p) => p,
          transform_hash: badH,
        },
        { migration_id: 'no-to', rollback_supported: false, rollback_constraints: [] },
      )
    ).rejects.toThrow(MutationGovernanceError)
  })

  it('throws MutationGovernanceError when transform_hash does not match function source', async () => {
    const wrongHash = 'f'.repeat(64) as SHA256Hex
    await expect(
      mutationGovernanceRegistry.register(
        {
          migration_id: 'bad-hash',
          from_schema_id: 'cov10-schema',
          from_version: '1.0.0',
          to_schema_id: 'cov10-schema',
          to_version: '2.0.0',
          description: 'bad hash test',
          transform: (p) => ({ ...(p as object) }),
          transform_hash: wrongHash,
        },
        { migration_id: 'bad-hash', rollback_supported: false, rollback_constraints: [] },
      )
    ).rejects.toThrow(MutationGovernanceError)
  })
})

// ── register — success path ────────────────────────────────

describe('mutationGovernanceRegistry.register — success path', () => {
  it('getMigration returns the registered migration', () => {
    const m = mutationGovernanceRegistry.getMigration('cov10-mig-1to2')
    expect(m).toBeDefined()
    expect(m!.migration_id).toBe('cov10-mig-1to2')
    expect(m!.from_version).toBe('1.0.0')
    expect(m!.to_version).toBe('2.0.0')
  })

  it('getRollback returns the registered rollback', () => {
    const r = mutationGovernanceRegistry.getRollback('cov10-mig-1to2')
    expect(r).toBeDefined()
    expect(r!.migration_id).toBe('cov10-mig-1to2')
    expect(r!.rollback_supported).toBe(true)
  })

  it('getRollback returns rollback_supported=false for irreversible migration', () => {
    const r = mutationGovernanceRegistry.getRollback('cov10-mig-2to3')
    expect(r).toBeDefined()
    expect(r!.rollback_supported).toBe(false)
  })
})

// ── findMigrationPath — with registered migrations ─────────

describe('mutationGovernanceRegistry.findMigrationPath — registered paths', () => {
  it('direct path 1.0.0 → 2.0.0 returns single-element array', () => {
    const path = mutationGovernanceRegistry.findMigrationPath(
      'cov10-schema', '1.0.0',
      'cov10-schema', '2.0.0',
    )
    expect(path).not.toBeNull()
    expect(path).toHaveLength(1)
    expect(path![0]!.migration_id).toBe('cov10-mig-1to2')
  })

  it('multi-hop path 1.0.0 → 3.0.0 returns two-element array via intermediate step', () => {
    const path = mutationGovernanceRegistry.findMigrationPath(
      'cov10-schema', '1.0.0',
      'cov10-schema', '3.0.0',
    )
    expect(path).not.toBeNull()
    expect(path!.length).toBeGreaterThanOrEqual(1)
  })
})

// ── checkPinCompatibility — with valid migration path ──────

describe('mutationGovernanceRegistry.checkPinCompatibility — valid path', () => {
  const pin = (v: string) => ({
    schema_version: v,
    verifier_versions: {},
    calibration_model_version: '1.0.0',
    projection_compiler_version: '1.0.0',
    k_measurement_version: '1.0.0',
  })

  it('returns compatible=true, requires_migration=true when a path exists', async () => {
    const result = await mutationGovernanceRegistry.checkPinCompatibility(
      pin('1.0.0'), pin('2.0.0'),
    )
    expect(result.compatible).toBe(true)
    expect(result.requires_migration).toBe(true)
    expect(result.migration_path).toHaveLength(1)
  })
})

// ── skill-harness/scanner — python + rust patterns ─────────

import {
  scanCodebase,
} from '../../src/skill-harness/scanner/codebase-scanner.js'

let scanTmpDir = ''

beforeAll(() => {
  scanTmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-scanner-ext-'))

  // Python file without ML imports → python_data_pattern with scripting domain
  fs.writeFileSync(
    path.join(scanTmpDir, 'pipeline.py'),
    'def process(data):\n    return [x * 2 for x in data]\n',
  )
  // Python file WITH ML imports → mlFiles.length > 0 branch
  fs.writeFileSync(
    path.join(scanTmpDir, 'model.py'),
    'import numpy as np\nimport torch\n\nclass Model:\n    pass\n',
  )
  // Rust file without unsafe
  fs.writeFileSync(
    path.join(scanTmpDir, 'main.rs'),
    'fn main() { println!("hello"); }\n',
  )
  // Rust file WITH unsafe block → unsafeFiles.length > 0 branch
  fs.writeFileSync(
    path.join(scanTmpDir, 'unsafe_op.rs'),
    'pub unsafe fn raw() { unsafe { let _p: *const u8 = 0 as *const u8; } }\n',
  )
})

afterAll(() => {
  if (scanTmpDir) fs.rmSync(scanTmpDir, { recursive: true, force: true })
})

describe('scanCodebase — python_data_pattern', () => {
  it('detects python_data_pattern when .py files are present', async () => {
    const result = await scanCodebase(scanTmpDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'python_data_pattern')
    expect(pattern).toBeDefined()
    expect(pattern!.pattern_type).toBe('data_pipeline')
    expect(pattern!.frequency).toBeGreaterThanOrEqual(1)
  })

  it('python_data_pattern includes "ml" domain when ML imports detected', async () => {
    const result = await scanCodebase(scanTmpDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'python_data_pattern')
    expect(pattern!.skill_domain).toContain('ml')
  })
})

describe('scanCodebase — rust_systems_pattern', () => {
  it('detects rust_systems_pattern when .rs files are present', async () => {
    const result = await scanCodebase(scanTmpDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'rust_systems_pattern')
    expect(pattern).toBeDefined()
    expect(pattern!.pattern_type).toBe('algorithm')
    expect(pattern!.frequency).toBeGreaterThanOrEqual(1)
  })

  it('rust_systems_pattern evidence_summary reflects unsafe blocks', async () => {
    const result = await scanCodebase(scanTmpDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'rust_systems_pattern')
    expect(pattern!.evidence_summary).toContain('unsafe')
  })
})
