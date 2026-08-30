// ============================================================
// Gate 200 — Sovereign Cognition Constitution Tests
// EPISTEMIC TIER: T2
// ============================================================

import { describe, it, expect, beforeAll } from 'vitest'
import {
  DIRECTIVES_SCHEMA_VERSION,
  buildDirective,
  buildConstitutionHash,
  getCanonicalDirectives,
  type SovereignDirective,
  type DirectiveClass,
} from '../../src/constitutional/directives.js'
import {
  FOUNDER_SCHEMA_VERSION,
  buildFounderRecord,
  buildCanonicalFounderRecord,
  verifyFounderRecord,
} from '../../src/constitutional/founder.js'
import type { SHA256Hex } from '../../src/core/types.js'

// ─── Constants ────────────────────────────────────────────

describe('schema versions', () => {
  it('DIRECTIVES_SCHEMA_VERSION is 1.0.0', () => {
    expect(DIRECTIVES_SCHEMA_VERSION).toBe('1.0.0')
  })

  it('FOUNDER_SCHEMA_VERSION is 1.0.0', () => {
    expect(FOUNDER_SCHEMA_VERSION).toBe('1.0.0')
  })
})

// ─── DirectiveClass taxonomy ──────────────────────────────

describe('DirectiveClass taxonomy', () => {
  it('all 4 directive classes are present in canonical directives', async () => {
    const directives = await getCanonicalDirectives()
    const classes = directives.map(d => d.directive_class)
    expect(classes).toContain('ADVERSARIAL_SELF_CORRECTION')
    expect(classes).toContain('CAUSAL_ARCHITECTURE')
    expect(classes).toContain('EPISTEMIC_SOVEREIGNTY')
    expect(classes).toContain('OPERATIONAL_REALISM')
  })

  it('canonical directives are in alphabetical order by directive_class', async () => {
    const directives = await getCanonicalDirectives()
    const classes = directives.map(d => d.directive_class)
    expect(classes).toEqual([...classes].sort())
  })

  it('exactly 4 canonical directives', async () => {
    const directives = await getCanonicalDirectives()
    expect(directives.length).toBe(4)
  })
})

// ─── SovereignDirective structure ─────────────────────────

describe('SovereignDirective fields', () => {
  let directives: readonly SovereignDirective[]

  beforeAll(async () => {
    directives = await getCanonicalDirectives()
  })

  it('all directives have epistemic_tier T2', () => {
    for (const d of directives) {
      expect(d.epistemic_tier).toBe('T2')
    }
  })

  it('all directives have directive_hash as 64-char hex', () => {
    for (const d of directives) {
      expect(d.directive_hash).toHaveLength(64)
      expect(d.directive_hash).toMatch(/^[0-9a-f]{64}$/)
    }
  })

  it('all directives have is_replay_reconstructable = true', () => {
    for (const d of directives) {
      expect(d.is_replay_reconstructable).toBe(true)
    }
  })

  it('all directives have schema_version 1.0.0', () => {
    for (const d of directives) {
      expect(d.schema_version).toBe('1.0.0')
    }
  })

  it('all directives have non-empty aegis_grounding', () => {
    for (const d of directives) {
      expect(d.aegis_grounding.length).toBeGreaterThan(0)
    }
  })

  it('all directives have non-empty aegis_grounding_file', () => {
    for (const d of directives) {
      expect(d.aegis_grounding_file.length).toBeGreaterThan(0)
    }
  })

  it('all directives are frozen — immutable at runtime', () => {
    for (const d of directives) {
      expect(() => {
        (d as { directive_class: string }).directive_class = 'HACK'
      }).toThrow()
    }
  })

  it('all directives have distinct directive_hashes', () => {
    const hashes = new Set(directives.map(d => d.directive_hash))
    expect(hashes.size).toBe(4)
  })
})

// ─── buildDirective factory ───────────────────────────────

describe('buildDirective', () => {
  it('directive_hash is 64-char hex', async () => {
    const d = await buildDirective({
      directive_class: 'EPISTEMIC_SOVEREIGNTY',
      description: 'Truth over flow.',
      aegis_grounding: 'admitAbstraction() blocks T4/T5.',
      aegis_grounding_file: 'src/constitutional/reduction.ts',
      failure_mode_prevented: 'Sycophancy.',
    })
    expect(d.directive_hash).toHaveLength(64)
  })

  it('deterministic ×3 — same input produces same directive_hash', async () => {
    const make = () => buildDirective({
      directive_class: 'CAUSAL_ARCHITECTURE',
      description: 'Mechanism over metaphor.',
      aegis_grounding: 'Hash-chained lineage.',
      aegis_grounding_file: 'src/frame/lineage.ts',
      failure_mode_prevented: 'Pseudo-depth.',
    })
    const [d1, d2, d3] = await Promise.all([make(), make(), make()])
    expect(d1.directive_hash).toBe(d2.directive_hash)
    expect(d2.directive_hash).toBe(d3.directive_hash)
  })

  it('different description → different directive_hash', async () => {
    const base = {
      directive_class: 'OPERATIONAL_REALISM' as DirectiveClass,
      aegis_grounding: 'certifyMartingale().',
      aegis_grounding_file: 'src/constitutional/martingale.ts',
      failure_mode_prevented: 'Paper architecture.',
    }
    const a = await buildDirective({ ...base, description: 'Feasibility as constraint.' })
    const b = await buildDirective({ ...base, description: 'Different description.' })
    expect(a.directive_hash).not.toBe(b.directive_hash)
  })

  it('result is frozen', async () => {
    const d = await buildDirective({
      directive_class: 'ADVERSARIAL_SELF_CORRECTION',
      description: 'Internal audit loop.',
      aegis_grounding: 'BFT quorum at 1/φ.',
      aegis_grounding_file: 'src/consensus/swarm.ts',
      failure_mode_prevented: 'Sycophantic agreement.',
    })
    expect(() => {
      (d as { directive_hash: string }).directive_hash = 'tampered'
    }).toThrow()
  })
})

// ─── buildConstitutionHash ────────────────────────────────

describe('buildConstitutionHash', () => {
  it('returns 64-char hex', async () => {
    const directives = await getCanonicalDirectives()
    const hash = await buildConstitutionHash(directives)
    expect(hash).toHaveLength(64)
    expect(hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('deterministic ×3 — same directives produce same hash', async () => {
    const directives = await getCanonicalDirectives()
    const [h1, h2, h3] = await Promise.all([
      buildConstitutionHash(directives),
      buildConstitutionHash(directives),
      buildConstitutionHash(directives),
    ])
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('different directive description → different constitution hash', async () => {
    const directives = await getCanonicalDirectives()
    const altDirective = await buildDirective({
      directive_class: 'EPISTEMIC_SOVEREIGNTY',
      description: 'Modified description — different hash.',
      aegis_grounding: directives.find(d => d.directive_class === 'EPISTEMIC_SOVEREIGNTY')!.aegis_grounding,
      aegis_grounding_file: 'src/constitutional/reduction.ts',
      failure_mode_prevented: 'Sycophancy.',
    })
    const altDirectives = directives.map(d =>
      d.directive_class === 'EPISTEMIC_SOVEREIGNTY' ? altDirective : d,
    )
    const hashA = await buildConstitutionHash(directives)
    const hashB = await buildConstitutionHash(altDirectives)
    expect(hashA).not.toBe(hashB)
  })

  it('order-independent — alphabetical sort applied before hashing', async () => {
    const directives = await getCanonicalDirectives()
    const reversed = [...directives].reverse()
    const h1 = await buildConstitutionHash(directives)
    const h2 = await buildConstitutionHash(reversed)
    expect(h1).toBe(h2)
  })
})

// ─── getCanonicalDirectives — lazy init ───────────────────

describe('getCanonicalDirectives lazy initialization', () => {
  it('returns same reference on repeated calls', async () => {
    const a = await getCanonicalDirectives()
    const b = await getCanonicalDirectives()
    expect(a).toBe(b)
  })
})

// ─── FounderRecord ────────────────────────────────────────

describe('FounderRecord', () => {
  it('founder_hash is 64-char hex', async () => {
    const directives = await getCanonicalDirectives()
    const constitutionHash = await buildConstitutionHash(directives)
    const record = await buildFounderRecord({
      founder_name: 'Test Founder',
      founder_email: 'test@example.com',
      stewardship_class: 'founding-architect',
      stewardship_scope: 'Test scope.',
      constitution_hash: constitutionHash,
    })
    expect(record.founder_hash).toHaveLength(64)
    expect(record.founder_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('genesis_sequence is 0n', async () => {
    const directives = await getCanonicalDirectives()
    const constitutionHash = await buildConstitutionHash(directives)
    const record = await buildFounderRecord({
      founder_name: 'Test Founder',
      founder_email: 'test@example.com',
      stewardship_class: 'contributing-author',
      stewardship_scope: 'Test scope.',
      constitution_hash: constitutionHash,
    })
    expect(record.genesis_sequence).toBe(0n)
  })

  it('verifyFounderRecord returns true for valid record', async () => {
    const directives = await getCanonicalDirectives()
    const constitutionHash = await buildConstitutionHash(directives)
    const record = await buildFounderRecord({
      founder_name: 'Tarik Skalić',
      founder_email: 'tarikskalic33@gmail.com',
      stewardship_class: 'founding-architect',
      stewardship_scope: 'AEGIS-Ω Constitutional Runtime.',
      constitution_hash: constitutionHash,
    })
    const valid = await verifyFounderRecord(record)
    expect(valid).toBe(true)
  })

  it('verifyFounderRecord returns false after tampering', async () => {
    const directives = await getCanonicalDirectives()
    const constitutionHash = await buildConstitutionHash(directives)
    const record = await buildFounderRecord({
      founder_name: 'Tarik Skalić',
      founder_email: 'tarikskalic33@gmail.com',
      stewardship_class: 'founding-architect',
      stewardship_scope: 'AEGIS-Ω Constitutional Runtime.',
      constitution_hash: constitutionHash,
    })
    const tampered = { ...record, founder_name: 'Attacker' }
    const valid = await verifyFounderRecord(tampered)
    expect(valid).toBe(false)
  })

  it('record is frozen', async () => {
    const directives = await getCanonicalDirectives()
    const constitutionHash = await buildConstitutionHash(directives)
    const record = await buildFounderRecord({
      founder_name: 'Test',
      founder_email: 'test@test.com',
      stewardship_class: 'constitutional-witness',
      stewardship_scope: 'Test.',
      constitution_hash: constitutionHash,
    })
    expect(() => {
      (record as { founder_name: string }).founder_name = 'hack'
    }).toThrow()
  })

  it('is_replay_reconstructable = true', async () => {
    const directives = await getCanonicalDirectives()
    const constitutionHash = await buildConstitutionHash(directives)
    const record = await buildFounderRecord({
      founder_name: 'Test',
      founder_email: 'test@test.com',
      stewardship_class: 'founding-architect',
      stewardship_scope: 'Test.',
      constitution_hash: constitutionHash,
    })
    expect(record.is_replay_reconstructable).toBe(true)
  })

  it('buildCanonicalFounderRecord anchors Tarik Skalić', async () => {
    const directives = await getCanonicalDirectives()
    const constitutionHash = await buildConstitutionHash(directives)
    const record = await buildCanonicalFounderRecord(constitutionHash)
    expect(record.founder_name).toBe('Tarik Skalić')
    expect(record.founder_email).toBe('tarikskalic33@gmail.com')
    expect(record.stewardship_class).toBe('founding-architect')
    expect(record.genesis_sequence).toBe(0n)
    expect(record.constitution_hash).toBe(constitutionHash)
  })

  it('constitution_hash change invalidates founder_hash', async () => {
    const directives = await getCanonicalDirectives()
    const constitutionHash = await buildConstitutionHash(directives)

    const fakeHash = 'a'.repeat(64) as SHA256Hex
    const r1 = await buildFounderRecord({
      founder_name: 'Tarik Skalić',
      founder_email: 'tarikskalic33@gmail.com',
      stewardship_class: 'founding-architect',
      stewardship_scope: 'Test.',
      constitution_hash: constitutionHash,
    })
    const r2 = await buildFounderRecord({
      founder_name: 'Tarik Skalić',
      founder_email: 'tarikskalic33@gmail.com',
      stewardship_class: 'founding-architect',
      stewardship_scope: 'Test.',
      constitution_hash: fakeHash,
    })
    expect(r1.founder_hash).not.toBe(r2.founder_hash)
  })
})
