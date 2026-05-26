import { describe, it, expect } from 'vitest'
import {
  PHI_SQ_THRESHOLD,
  checkPropagation,
  requirePropagable,
  PropagationError,
} from '../../src/skill-harness/propagation.js'
import { PHI_THRESHOLD } from '../../src/skill-harness/resonance.js'
import { buildSkillRecord } from '../../src/skill-harness/catalog.js'
import { COGNITIVE_TRIAD } from '../../src/skill-harness/seeds.js'
import type { SkillInput } from '../../src/skill-harness/types.js'

// ============================================================
// 3-Layer Network Resonance Propagation Gate Tests
// LAN (local) · IP (routing) · WWW (semantic)
// ============================================================

// Resonant seed for testing
const resonantInput: SkillInput = {
  skill_id: 'test_prop',
  name: 'hash-chain-seal',   // length=15, dr=6, Triadic
  confidence: 0.9,
  validated_runs: 10,
  failure_rate: 0.05,
  recency_score: 0.9,
  domain_affinity: ['integrity', 'hash', 'integrity'],  // palindrome
  dependencies: [],
  evidence_refs: ['evt_001'],
  last_validated: '2026-01-01T00:00:00Z',
  epistemic_tier: 'T1',
  primitive_mapping: 'HASH',
}

const DIRECT_PATH: readonly number[] = []   // zero hops
const LOW_DIV_PATH: readonly number[] = [0.1, 0.1]  // total=0.2 < 1/φ², inv=0.8 > 1/φ

describe('Constants', () => {
  it('PHI_SQ_THRESHOLD = 1 - PHI_THRESHOLD (golden identity: 1/φ + 1/φ² = 1)', () => {
    expect(PHI_SQ_THRESHOLD).toBeCloseTo(1.0 - PHI_THRESHOLD, 12)
    expect(PHI_SQ_THRESHOLD).toBeCloseTo(0.3819660112501051, 12)
  })

  it('1/φ + 1/φ² = 1 (verified)', () => {
    expect(PHI_THRESHOLD + PHI_SQ_THRESHOLD).toBeCloseTo(1.0, 12)
  })
})

describe('checkPropagation — full 3-layer pass', () => {
  it('direct link (no hops): inverse_divergence=1.0, all 3 layers pass', async () => {
    const record = await buildSkillRecord(resonantInput)
    const report = checkPropagation(record, DIRECT_PATH, ['integrity', 'hash'])
    expect(report.lan_resonant).toBe(true)
    expect(report.ip_resonant).toBe(true)
    expect(report.www_resonant).toBe(true)
    expect(report.can_propagate).toBe(true)
    expect(report.network_depth).toBe(3)
    expect(report.inverse_divergence).toBe(1.0)
    expect(report.cumulative_divergence).toBe(0.0)
  })

  it('low-divergence path: inverse_divergence > 1/φ, all layers pass', async () => {
    const record = await buildSkillRecord(resonantInput)
    const report = checkPropagation(record, LOW_DIV_PATH, ['integrity', 'hash'])
    expect(report.ip_resonant).toBe(true)
    expect(report.can_propagate).toBe(true)
    expect(report.inverse_divergence).toBeCloseTo(0.8, 10)
    expect(report.cumulative_divergence).toBeCloseTo(0.2, 10)
  })
})

describe('checkPropagation — IP gate (inverse divergence)', () => {
  it('cumulative divergence at 1/φ² boundary: inverse_divergence = 1/φ → ip barely passes', async () => {
    const record = await buildSkillRecord(resonantInput)
    // inverse_divergence = 1 - (1-1/φ) = 1/φ → exactly at threshold
    // Need inverse_divergence strictly > 1/φ, so we use slightly below 1/φ²
    const path = [PHI_SQ_THRESHOLD - 0.001]
    const report = checkPropagation(record, path, ['integrity', 'hash'])
    expect(report.ip_resonant).toBe(true)
    expect(report.inverse_divergence).toBeGreaterThan(PHI_THRESHOLD)
  })

  it('cumulative divergence > 1/φ²: inverse_divergence < 1/φ → ip blocked', async () => {
    const record = await buildSkillRecord(resonantInput)
    const path = [0.2, 0.2, 0.1]  // total=0.5 > 0.382 → inv=0.5 < 0.618
    const report = checkPropagation(record, path, ['integrity', 'hash'])
    expect(report.ip_resonant).toBe(false)
    expect(report.can_propagate).toBe(false)
    expect(report.inverse_divergence).toBeCloseTo(0.5, 10)
  })

  it('throws PropagationError on invalid hop divergence (> 1)', async () => {
    const record = await buildSkillRecord(resonantInput)
    expect(() => checkPropagation(record, [1.5], ['integrity'])).toThrow(PropagationError)
  })

  it('throws PropagationError on negative hop divergence', async () => {
    const record = await buildSkillRecord(resonantInput)
    expect(() => checkPropagation(record, [-0.1], ['integrity'])).toThrow(PropagationError)
  })
})

describe('checkPropagation — WWW gate (semantic alignment)', () => {
  it('full domain overlap: semantic_alignment=1.0, www passes', async () => {
    const record = await buildSkillRecord(resonantInput)
    // unique source domains: ["integrity","hash"], target contains both
    const report = checkPropagation(record, DIRECT_PATH, ['integrity', 'hash', 'extra'])
    expect(report.semantic_alignment).toBe(1.0)
    expect(report.www_resonant).toBe(true)
  })

  it('partial overlap ≥ 1/φ: www passes', async () => {
    // unique source = ["integrity","hash"] (2 unique), target has 2 → 2/2=1.0
    // Use a skill with 3 unique domains, target covers 2 → 2/3 ≈ 0.667 > 0.618
    const input: SkillInput = {
      ...resonantInput,
      skill_id: 'test_www_partial',
      domain_affinity: ['alpha', 'beta', 'gamma', 'beta', 'alpha'],  // unique: alpha,beta,gamma
    }
    const record = await buildSkillRecord(input)
    const report = checkPropagation(record, DIRECT_PATH, ['alpha', 'beta'])  // 2/3 overlap
    expect(report.semantic_alignment).toBeCloseTo(2 / 3, 10)
    expect(report.www_resonant).toBe(true)  // 0.667 > 0.618
  })

  it('overlap below 1/φ: www blocked', async () => {
    // unique source = ["alpha","beta","gamma","delta"] (4 unique), target covers 1 → 0.25
    const input: SkillInput = {
      ...resonantInput,
      skill_id: 'test_www_low',
      domain_affinity: ['alpha', 'beta', 'gamma', 'delta'],
    }
    const record = await buildSkillRecord(input)
    const report = checkPropagation(record, DIRECT_PATH, ['alpha', 'other'])  // 1/4=0.25 < 0.618
    expect(report.www_resonant).toBe(false)
    expect(report.can_propagate).toBe(false)
  })

  it('no common domains: semantic_alignment=0, www blocked', async () => {
    const record = await buildSkillRecord(resonantInput)
    const report = checkPropagation(record, DIRECT_PATH, ['unrelated', 'domain'])
    expect(report.semantic_alignment).toBe(0)
    expect(report.www_resonant).toBe(false)
    expect(report.can_propagate).toBe(false)
  })
})

describe('checkPropagation — LAN gate blocked', () => {
  it('non-resonant skill: lan_resonant=false, propagation blocked', async () => {
    const input: SkillInput = {
      ...resonantInput,
      skill_id: 'test_lan_fail',
      failure_rate: 0.8,  // phi_convergent=false → not resonant
    }
    const record = await buildSkillRecord(input)
    const report = checkPropagation(record, DIRECT_PATH, ['integrity', 'hash'])
    expect(report.lan_resonant).toBe(false)
    expect(report.can_propagate).toBe(false)
  })
})

describe('checkPropagation — determinism and structure', () => {
  it('same inputs produce identical report ×3', async () => {
    const record = await buildSkillRecord(resonantInput)
    const r1 = checkPropagation(record, LOW_DIV_PATH, ['integrity', 'hash'])
    const r2 = checkPropagation(record, LOW_DIV_PATH, ['integrity', 'hash'])
    const r3 = checkPropagation(record, LOW_DIV_PATH, ['integrity', 'hash'])
    expect(r1.can_propagate).toBe(r2.can_propagate)
    expect(r2.can_propagate).toBe(r3.can_propagate)
    expect(r1.inverse_divergence).toBe(r2.inverse_divergence)
    expect(r2.semantic_alignment).toBe(r3.semantic_alignment)
  })

  it('report is frozen', async () => {
    const record = await buildSkillRecord(resonantInput)
    const report = checkPropagation(record, DIRECT_PATH, ['integrity', 'hash'])
    expect(Object.isFrozen(report)).toBe(true)
  })

  it('lan_coefficient matches source skill resonance_coefficient', async () => {
    const record = await buildSkillRecord(resonantInput)
    const report = checkPropagation(record, DIRECT_PATH, ['integrity', 'hash'])
    expect(report.lan_coefficient).toBeGreaterThan(5.0)  // certified seed
  })
})

describe('requirePropagable', () => {
  it('does not throw when all 3 layers pass', async () => {
    const record = await buildSkillRecord(resonantInput)
    expect(() => requirePropagable(record, DIRECT_PATH, ['integrity', 'hash'])).not.toThrow()
  })

  it('throws PropagationError when blocked, message contains skill_id', async () => {
    const input: SkillInput = {
      ...resonantInput,
      skill_id: 'blocked_skill_abc',
      failure_rate: 0.9,
    }
    const record = await buildSkillRecord(input)
    expect(() => requirePropagable(record, DIRECT_PATH, ['integrity'])).toThrow(PropagationError)
    expect(() => requirePropagable(record, DIRECT_PATH, ['integrity'])).toThrow(/blocked_skill_abc/)
  })

  it('PropagationError is an Error subclass', () => {
    const err = new PropagationError('test')
    expect(err).toBeInstanceOf(Error)
    expect(err.name).toBe('PropagationError')
  })
})

describe('Cognitive Triad propagation to aligned agent', () => {
  it('all 3 seeds propagate through direct link to fully aligned agent', async () => {
    const allDomains = ['governance', 'replay', 'integrity', 'hash', 'harmony', 'structure']
    let propagated = 0
    for (const seed of COGNITIVE_TRIAD) {
      const record = await buildSkillRecord(seed)
      const report = checkPropagation(record, DIRECT_PATH, allDomains)
      if (report.can_propagate) propagated++
    }
    expect(propagated).toBe(3)
  })
})
