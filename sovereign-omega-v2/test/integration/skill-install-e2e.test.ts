import { describe, it, expect } from 'vitest'
import { buildSkillRecord, SkillCatalog } from '../../src/skill-harness/catalog.js'
import { importSkillsFromManifests } from '../../src/skill-harness/import.js'
import { SkillCatalogError } from '../../src/skill-harness/types.js'
import { CORE_AGENT_SKILL_INPUTS } from '../../src/skill-harness/manifests/core-agents.js'
import { ANTIGRAVITY_SKILL_INPUTS } from '../../src/skill-harness/manifests/antigravity.js'
import type { RawSkillManifest } from '../../src/skill-harness/types.js'

// ============================================================
// Gate 132 — Skill Install E2E Tests
// Verifies: SkillCatalog.register → core-agents + antigravity
// manifests; T4/T5 rejection; catalog_hash determinism ×3.
// ============================================================

describe('Core agent manifests — buildSkillRecord + register', () => {
  it('all 15 core agent inputs produce valid SkillRecords', async () => {
    expect(CORE_AGENT_SKILL_INPUTS).toHaveLength(15)
    for (const input of CORE_AGENT_SKILL_INPUTS) {
      const record = await buildSkillRecord(input)
      expect(record.skill_hash).toMatch(/^[0-9a-f]{64}$/)
      expect(record.is_replay_reconstructable).toBe(true)
      expect(Object.isFrozen(record)).toBe(true)
    }
  })

  it('all 15 can register into a single SkillCatalog without collision', async () => {
    let catalog = SkillCatalog.empty()
    for (const input of CORE_AGENT_SKILL_INPUTS) {
      const record = await buildSkillRecord(input)
      const { catalog: next } = catalog.register(record)
      catalog = next
    }
    expect(catalog.size).toBe(15)
  })

  it('replay_audit skill is T0 epistemic_tier', () => {
    const input = CORE_AGENT_SKILL_INPUTS.find(s => s.skill_id === 'replay_audit')
    expect(input?.epistemic_tier).toBe('T0')
  })

  it('duplicate skill_id throws SkillCatalogError', async () => {
    const record = await buildSkillRecord(CORE_AGENT_SKILL_INPUTS[0]!)
    let catalog = SkillCatalog.empty()
    const { catalog: c1 } = catalog.register(record)
    expect(() => c1.register(record)).toThrow(SkillCatalogError)
  })
})

describe('Antigravity manifests', () => {
  it('all 24 antigravity inputs have skill_ids starting with ag_', () => {
    expect(ANTIGRAVITY_SKILL_INPUTS.length).toBeGreaterThanOrEqual(20)
    for (const input of ANTIGRAVITY_SKILL_INPUTS) {
      expect(input.skill_id.startsWith('ag_')).toBe(true)
    }
  })

  it('antigravity + core catalog: combined size = 15 + antigravity count', async () => {
    let catalog = SkillCatalog.empty()
    for (const input of [...CORE_AGENT_SKILL_INPUTS, ...ANTIGRAVITY_SKILL_INPUTS]) {
      const record = await buildSkillRecord(input)
      const { catalog: next } = catalog.register(record)
      catalog = next
    }
    expect(catalog.size).toBe(CORE_AGENT_SKILL_INPUTS.length + ANTIGRAVITY_SKILL_INPUTS.length)
  })
})

describe('importSkillsFromManifests — T4/T5 rejection', () => {
  const T4_MANIFEST: RawSkillManifest = {
    source: 'test',
    path: 'SKILL.md',
    content: `---
name: planetary-consciousness-mesh
description: Planetary coordination of sovereign consciousness entities across civilizational epochs
---
This skill enables T5 speculative planetary coordination.
`,
  }

  const VALID_MANIFEST: RawSkillManifest = {
    source: 'obra/superpowers',
    path: 'skills/git/SKILL.md',
    content: `---
name: git-commit-discipline
description: Write clear atomic commits with conventional format
---
Helps structure git commit messages.
`,
  }

  it('valid manifest → admitted into catalog', async () => {
    const result = await importSkillsFromManifests([VALID_MANIFEST])
    expect(result.admitted).toHaveLength(1)
    expect(result.rejected).toHaveLength(0)
    expect(result.is_replay_reconstructable).toBe(true)
  })

  it('T4/T5 manifest → rejected with ARBITRATION reason', async () => {
    const result = await importSkillsFromManifests([T4_MANIFEST])
    expect(result.admitted).toHaveLength(0)
    expect(result.rejected).toHaveLength(1)
    expect(result.rejected[0]?.reason).toMatch(/ARBITRATION/i)
  })

  it('mixed batch: valid admitted + T4 rejected', async () => {
    const result = await importSkillsFromManifests([VALID_MANIFEST, T4_MANIFEST])
    expect(result.admitted).toHaveLength(1)
    expect(result.rejected).toHaveLength(1)
  })

  it('catalog_hash is deterministic ×3', async () => {
    const run = () => importSkillsFromManifests([VALID_MANIFEST])
    const [r1, r2, r3] = await Promise.all([run(), run(), run()])
    expect(r1.catalog_hash).toBe(r2.catalog_hash)
    expect(r2.catalog_hash).toBe(r3.catalog_hash)
  })

  it('missing frontmatter → rejected', async () => {
    const noFrontmatter: RawSkillManifest = {
      source: 'test',
      path: 'SKILL.md',
      content: 'Just markdown content without frontmatter.',
    }
    const result = await importSkillsFromManifests([noFrontmatter])
    expect(result.rejected).toHaveLength(1)
    expect(result.admitted).toHaveLength(0)
  })
})
