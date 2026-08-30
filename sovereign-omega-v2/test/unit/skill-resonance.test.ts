import { describe, it, expect } from 'vitest'
import {
  PHI_THRESHOLD,
  RESONANCE_CERT_THRESHOLD,
  checkSkillResonance,
  requireResonant,
  SkillResonanceError,
} from '../../src/skill-harness/resonance.js'
import { buildSkillRecord, SkillCatalog } from '../../src/skill-harness/catalog.js'
import { COGNITIVE_TRIAD, COGNITIVE_TRIAD_IDS } from '../../src/skill-harness/seeds.js'
import type { SkillInput } from '../../src/skill-harness/types.js'

// ============================================================
// Gate 222 — Skill Resonance Gate + Cognitive Triad Tests
// Every position of a character (x) in the swarm must be
// in resonance before its skill propagates.
// ============================================================

// Base resonant skill: name.length=15 (dr=6, Triadic), palindrome domain, low failure_rate
const resonantInput: SkillInput = {
  skill_id: 'test_resonant',
  name: 'hash-chain-seal',  // length=15, dr=6, Triadic
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

describe('Constants', () => {
  it('PHI_THRESHOLD is 1/φ', () => {
    expect(PHI_THRESHOLD).toBeCloseTo(0.6180339887498948, 15)
  })

  it('RESONANCE_CERT_THRESHOLD is 5.0', () => {
    expect(RESONANCE_CERT_THRESHOLD).toBe(5.0)
  })

  it('COGNITIVE_TRIAD has exactly 3 seeds', () => {
    expect(COGNITIVE_TRIAD.length).toBe(3)
    expect(COGNITIVE_TRIAD_IDS.length).toBe(3)
  })

  it('COGNITIVE_TRIAD_IDS are the correct skill_ids', () => {
    expect(COGNITIVE_TRIAD_IDS).toContain('replay_sovereignty')
    expect(COGNITIVE_TRIAD_IDS).toContain('hash_chain_seal')
    expect(COGNITIVE_TRIAD_IDS).toContain('ring_harmony_verifier')
  })
})

describe('checkSkillResonance — Cognitive Triad seeds are all CERTIFIED', () => {
  it('replay_sovereignty: all 4 conditions true, coefficient > 5.0', async () => {
    const seed = COGNITIVE_TRIAD.find(s => s.skill_id === 'replay_sovereignty')!
    const record = await buildSkillRecord(seed)
    const report = checkSkillResonance(record)
    expect(report.phi_convergent).toBe(true)
    expect(report.ring_valid).toBe(true)
    expect(report.sequence_monotone).toBe(true)
    expect(report.vortex_triadic).toBe(true)
    expect(report.is_resonant).toBe(true)
    expect(report.is_certified).toBe(true)
    expect(report.resonance_depth).toBe(4)
    expect(report.resonance_coefficient).toBeGreaterThan(5.0)
  })

  it('hash_chain_seal: all 4 conditions true, coefficient > 5.0', async () => {
    const seed = COGNITIVE_TRIAD.find(s => s.skill_id === 'hash_chain_seal')!
    const record = await buildSkillRecord(seed)
    const report = checkSkillResonance(record)
    expect(report.phi_convergent).toBe(true)
    expect(report.ring_valid).toBe(true)
    expect(report.sequence_monotone).toBe(true)
    expect(report.vortex_triadic).toBe(true)
    expect(report.is_resonant).toBe(true)
    expect(report.is_certified).toBe(true)
    expect(report.resonance_coefficient).toBeGreaterThan(5.0)
  })

  it('ring_harmony_verifier: all 4 conditions true, coefficient > 5.0', async () => {
    const seed = COGNITIVE_TRIAD.find(s => s.skill_id === 'ring_harmony_verifier')!
    const record = await buildSkillRecord(seed)
    const report = checkSkillResonance(record)
    expect(report.phi_convergent).toBe(true)
    expect(report.ring_valid).toBe(true)
    expect(report.sequence_monotone).toBe(true)
    expect(report.vortex_triadic).toBe(true)
    expect(report.is_resonant).toBe(true)
    expect(report.is_certified).toBe(true)
    expect(report.resonance_coefficient).toBeGreaterThan(5.0)
  })
})

describe('checkSkillResonance — individual condition failures', () => {
  it('failure_rate >= PHI_THRESHOLD → phi_convergent=false, not resonant', async () => {
    const input: SkillInput = { ...resonantInput, skill_id: 'test_phi', failure_rate: 0.619 }
    const record = await buildSkillRecord(input)
    const report = checkSkillResonance(record)
    expect(report.phi_convergent).toBe(false)
    expect(report.is_resonant).toBe(false)
    expect(report.phi_headroom).toBeLessThan(0)
  })

  it('non-palindrome domain_affinity → ring_valid=false, not resonant', async () => {
    const input: SkillInput = {
      ...resonantInput,
      skill_id: 'test_ring',
      domain_affinity: ['alpha', 'beta', 'gamma'],  // not palindrome
    }
    const record = await buildSkillRecord(input)
    const report = checkSkillResonance(record)
    expect(report.ring_valid).toBe(false)
    expect(report.is_resonant).toBe(false)
  })

  it('empty evidence and zero runs → sequence_monotone=false, not resonant', async () => {
    const input: SkillInput = {
      ...resonantInput,
      skill_id: 'test_seq',
      validated_runs: 0,
      evidence_refs: [],
    }
    const record = await buildSkillRecord(input)
    const report = checkSkillResonance(record)
    expect(report.sequence_monotone).toBe(false)
    expect(report.is_resonant).toBe(false)
  })

  it('Hexadic name length → vortex_triadic=false (not resonant requires only 3 conditions)', async () => {
    // name length=16 → dr(16%9=7)=7 → Hexadic
    const input: SkillInput = {
      ...resonantInput,
      skill_id: 'test_vortex',
      name: 'hexadic-name-len!',  // length=17 → dr(17%9=8)=8 Hexadic
    }
    const record = await buildSkillRecord(input)
    const report = checkSkillResonance(record)
    expect(report.vortex_triadic).toBe(false)
    // is_resonant only requires phi_convergent + ring_valid + sequence_monotone
    expect(report.is_resonant).toBe(true)
    // but with hexadic vortex_factor=1 and depth=3 (no vortex): 3 × 1.0 × headroom < 5.0
    expect(report.is_certified).toBe(false)
  })

  it('all 4 conditions fail → depth=0, coefficient=0, not resonant', async () => {
    const input: SkillInput = {
      ...resonantInput,
      skill_id: 'test_all_fail',
      name: 'hexadic-name-len!',  // Hexadic
      failure_rate: 0.7,           // phi_convergent=false
      domain_affinity: ['a', 'b', 'c'],  // not palindrome
      validated_runs: 0,
      evidence_refs: [],
    }
    const record = await buildSkillRecord(input)
    const report = checkSkillResonance(record)
    expect(report.phi_convergent).toBe(false)
    expect(report.ring_valid).toBe(false)
    expect(report.sequence_monotone).toBe(false)
    expect(report.vortex_triadic).toBe(false)
    expect(report.resonance_depth).toBe(0)
    expect(report.resonance_coefficient).toBe(0)
    expect(report.is_resonant).toBe(false)
    expect(report.is_certified).toBe(false)
  })
})

describe('checkSkillResonance — formula correctness', () => {
  it('phi_headroom = PHI_THRESHOLD - failure_rate', async () => {
    const record = await buildSkillRecord(resonantInput)
    const report = checkSkillResonance(record)
    expect(report.phi_headroom).toBeCloseTo(PHI_THRESHOLD - resonantInput.failure_rate, 12)
  })

  it('resonance_coefficient = depth × vortex_factor × phi_headroom (Triadic)', async () => {
    const record = await buildSkillRecord(resonantInput)
    const report = checkSkillResonance(record)
    // Triadic seed: depth=4, vortex_factor=3.0
    const expected = report.resonance_depth * 3.0 * Math.max(report.phi_headroom, 0)
    expect(report.resonance_coefficient).toBeCloseTo(expected, 12)
  })

  it('is_resonant requires phi_convergent AND ring_valid AND sequence_monotone', async () => {
    // Only phi_convergent + sequence_monotone, not ring_valid
    const input: SkillInput = {
      ...resonantInput,
      skill_id: 'test_partial',
      domain_affinity: ['x', 'y', 'z'],  // not palindrome
    }
    const record = await buildSkillRecord(input)
    const report = checkSkillResonance(record)
    expect(report.phi_convergent).toBe(true)
    expect(report.sequence_monotone).toBe(true)
    expect(report.ring_valid).toBe(false)
    expect(report.is_resonant).toBe(false)
  })

  it('sequence_monotone=true when evidence_refs non-empty even with validated_runs=0', async () => {
    const input: SkillInput = {
      ...resonantInput,
      skill_id: 'test_evref',
      validated_runs: 0,
      evidence_refs: ['evt_abc'],
    }
    const record = await buildSkillRecord(input)
    const report = checkSkillResonance(record)
    expect(report.sequence_monotone).toBe(true)
  })

  it('report is frozen (deepFreeze)', async () => {
    const record = await buildSkillRecord(resonantInput)
    const report = checkSkillResonance(record)
    expect(Object.isFrozen(report)).toBe(true)
  })

  it('determinism: same skill → identical report ×3', async () => {
    const record = await buildSkillRecord(resonantInput)
    const r1 = checkSkillResonance(record)
    const r2 = checkSkillResonance(record)
    const r3 = checkSkillResonance(record)
    expect(r1.resonance_coefficient).toBe(r2.resonance_coefficient)
    expect(r2.resonance_coefficient).toBe(r3.resonance_coefficient)
    expect(r1.resonance_depth).toBe(r2.resonance_depth)
    expect(r1.is_certified).toBe(r2.is_certified)
    expect(r1.is_certified).toBe(r3.is_certified)
  })
})

describe('requireResonant', () => {
  it('does not throw for a resonant skill', async () => {
    const record = await buildSkillRecord(resonantInput)
    expect(() => requireResonant(record)).not.toThrow()
  })

  it('throws SkillResonanceError for a non-resonant skill', async () => {
    const input: SkillInput = {
      ...resonantInput,
      skill_id: 'test_breach',
      failure_rate: 0.8,  // phi_convergent=false
    }
    const record = await buildSkillRecord(input)
    expect(() => requireResonant(record)).toThrow(SkillResonanceError)
  })

  it('error message contains skill_id', async () => {
    const input: SkillInput = {
      ...resonantInput,
      skill_id: 'sentinel_breach_id',
      failure_rate: 0.8,
    }
    const record = await buildSkillRecord(input)
    expect(() => requireResonant(record)).toThrow(/sentinel_breach_id/)
  })

  it('SkillResonanceError is an Error subclass', () => {
    const err = new SkillResonanceError('test')
    expect(err).toBeInstanceOf(Error)
    expect(err.name).toBe('SkillResonanceError')
  })
})

describe('SkillCatalog.registerResonant', () => {
  it('admits a resonant skill and grows the catalog', async () => {
    const record = await buildSkillRecord(resonantInput)
    const cat = SkillCatalog.empty()
    const { catalog } = cat.registerResonant(record)
    expect(catalog.size).toBe(1)
    expect(catalog.lookup('test_resonant')).toBe(record)
  })

  it('rejects a non-resonant skill with SkillResonanceError', async () => {
    const input: SkillInput = {
      ...resonantInput,
      skill_id: 'test_reject',
      failure_rate: 0.9,  // phi_convergent=false → not resonant
    }
    const record = await buildSkillRecord(input)
    const cat = SkillCatalog.empty()
    expect(() => cat.registerResonant(record)).toThrow(SkillResonanceError)
    expect(cat.size).toBe(0)  // catalog unchanged
  })

  it('all 3 Cognitive Triad seeds register as resonant', async () => {
    let cat = SkillCatalog.empty()
    for (const seed of COGNITIVE_TRIAD) {
      const record = await buildSkillRecord(seed)
      const { catalog } = cat.registerResonant(record)
      cat = catalog
    }
    expect(cat.size).toBe(3)
    for (const id of COGNITIVE_TRIAD_IDS) {
      expect(cat.lookup(id)).not.toBeNull()
    }
  })
})
