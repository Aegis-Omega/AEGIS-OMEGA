import { describe, it, expect } from 'vitest'
import { buildSkillRecord, SkillCatalog } from '../../src/skill-harness/catalog.js'
import { SKILL_HARNESS_SCHEMA_VERSION, SkillCatalogError } from '../../src/skill-harness/types.js'
import type { SkillInput } from '../../src/skill-harness/types.js'

// ============================================================
// Gate 125 — Skill Harness: SkillRecord + SkillCatalog Tests
// ============================================================

const base: SkillInput = {
  skill_id: 'workflow_orchestration',
  name: 'Workflow Orchestration',
  confidence: 0.87,
  validated_runs: 183,
  failure_rate: 0.06,
  recency_score: 0.91,
  domain_affinity: ['operations', 'automation'],
  dependencies: ['task_decomposition'],
  evidence_refs: ['evt_001'],
  last_validated: '2026-05-20T12:00:00Z',
  epistemic_tier: 'T2',
  primitive_mapping: 'SEQUENCE',
}

describe('SKILL_HARNESS_SCHEMA_VERSION', () => {
  it('is 1.0.0', () => {
    expect(SKILL_HARNESS_SCHEMA_VERSION).toBe('1.0.0')
  })
})

describe('buildSkillRecord', () => {
  it('produces a frozen record with skill_hash', async () => {
    const record = await buildSkillRecord(base)
    expect(record.skill_id).toBe('workflow_orchestration')
    expect(record.skill_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(record.schema_version).toBe('1.0.0')
    expect(record.is_replay_reconstructable).toBe(true)
    expect(Object.isFrozen(record)).toBe(true)
  })

  it('preserves all input fields', async () => {
    const record = await buildSkillRecord(base)
    expect(record.confidence).toBe(0.87)
    expect(record.validated_runs).toBe(183)
    expect(record.failure_rate).toBe(0.06)
    expect(record.recency_score).toBe(0.91)
    expect(record.epistemic_tier).toBe('T2')
    expect(record.primitive_mapping).toBe('SEQUENCE')
  })

  it('is deterministic ×3', async () => {
    const [r1, r2, r3] = await Promise.all([
      buildSkillRecord(base),
      buildSkillRecord(base),
      buildSkillRecord(base),
    ])
    expect(r1.skill_hash).toBe(r2.skill_hash)
    expect(r2.skill_hash).toBe(r3.skill_hash)
  })

  it('different skill_id → different skill_hash', async () => {
    const r1 = await buildSkillRecord(base)
    const r2 = await buildSkillRecord({ ...base, skill_id: 'different_skill' })
    expect(r1.skill_hash).not.toBe(r2.skill_hash)
  })

  it('different confidence → different skill_hash', async () => {
    const r1 = await buildSkillRecord(base)
    const r2 = await buildSkillRecord({ ...base, confidence: 0.50 })
    expect(r1.skill_hash).not.toBe(r2.skill_hash)
  })

  it('throws SkillCatalogError if confidence > 1', async () => {
    await expect(buildSkillRecord({ ...base, confidence: 1.1 }))
      .rejects.toBeInstanceOf(SkillCatalogError)
  })

  it('throws SkillCatalogError if confidence < 0', async () => {
    await expect(buildSkillRecord({ ...base, confidence: -0.1 }))
      .rejects.toBeInstanceOf(SkillCatalogError)
  })

  it('throws SkillCatalogError if failure_rate > 1', async () => {
    await expect(buildSkillRecord({ ...base, failure_rate: 2.0 }))
      .rejects.toBeInstanceOf(SkillCatalogError)
  })

  it('throws SkillCatalogError if recency_score < 0', async () => {
    await expect(buildSkillRecord({ ...base, recency_score: -0.5 }))
      .rejects.toBeInstanceOf(SkillCatalogError)
  })

  it('accepts T0, T1, T2 epistemic tiers', async () => {
    const t0 = await buildSkillRecord({ ...base, epistemic_tier: 'T0' })
    const t1 = await buildSkillRecord({ ...base, epistemic_tier: 'T1' })
    expect(t0.epistemic_tier).toBe('T0')
    expect(t1.epistemic_tier).toBe('T1')
  })
})

describe('SkillCatalog', () => {
  it('empty() starts with size=0', () => {
    expect(SkillCatalog.empty().size).toBe(0)
  })

  it('register returns new catalog with size+1', async () => {
    const record = await buildSkillRecord(base)
    const { catalog } = SkillCatalog.empty().register(record)
    expect(catalog.size).toBe(1)
  })

  it('original catalog is unchanged after register', async () => {
    const record = await buildSkillRecord(base)
    const empty = SkillCatalog.empty()
    empty.register(record)
    expect(empty.size).toBe(0)
  })

  it('lookup returns record by skill_id', async () => {
    const record = await buildSkillRecord(base)
    const { catalog } = SkillCatalog.empty().register(record)
    const found = catalog.lookup('workflow_orchestration')
    expect(found?.skill_id).toBe('workflow_orchestration')
  })

  it('lookup returns null for unknown skill_id', async () => {
    expect(SkillCatalog.empty().lookup('nonexistent')).toBeNull()
  })

  it('throws SkillCatalogError on duplicate skill_id', async () => {
    const record = await buildSkillRecord(base)
    const { catalog } = SkillCatalog.empty().register(record)
    expect(() => catalog.register(record)).toThrow(SkillCatalogError)
  })

  it('byDomain filters by domain_affinity', async () => {
    const r1 = await buildSkillRecord({ ...base, skill_id: 'skill_ops', domain_affinity: ['operations'] })
    const r2 = await buildSkillRecord({ ...base, skill_id: 'skill_ml', domain_affinity: ['ml'] })
    const { catalog: c1 } = SkillCatalog.empty().register(r1)
    const { catalog: c2 } = c1.register(r2)
    expect(c2.byDomain('operations').length).toBe(1)
    expect(c2.byDomain('ml').length).toBe(1)
    expect(c2.byDomain('unknown').length).toBe(0)
  })

  it('getAll returns all records', async () => {
    const r1 = await buildSkillRecord({ ...base, skill_id: 's1' })
    const r2 = await buildSkillRecord({ ...base, skill_id: 's2' })
    const { catalog: c1 } = SkillCatalog.empty().register(r1)
    const { catalog: c2 } = c1.register(r2)
    expect(c2.getAll().length).toBe(2)
  })

  it('catalogHash is a 64-char hex string', async () => {
    const record = await buildSkillRecord(base)
    const { catalog } = SkillCatalog.empty().register(record)
    const hash = await catalog.catalogHash()
    expect(hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('catalogHash is deterministic ×3', async () => {
    const record = await buildSkillRecord(base)
    const { catalog } = SkillCatalog.empty().register(record)
    const [h1, h2, h3] = await Promise.all([
      catalog.catalogHash(),
      catalog.catalogHash(),
      catalog.catalogHash(),
    ])
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('different catalog contents → different catalogHash', async () => {
    const r1 = await buildSkillRecord({ ...base, skill_id: 'alpha' })
    const r2 = await buildSkillRecord({ ...base, skill_id: 'beta' })
    const { catalog: c1 } = SkillCatalog.empty().register(r1)
    const { catalog: c2 } = SkillCatalog.empty().register(r2)
    expect(await c1.catalogHash()).not.toBe(await c2.catalogHash())
  })

  it('SkillCatalogError is an Error subclass', () => {
    const err = new SkillCatalogError('test')
    expect(err).toBeInstanceOf(Error)
    expect(err.name).toBe('SkillCatalogError')
  })
})
