// ============================================================
// SOVEREIGN OMEGA — Epistemic Tier Tests (T0)
// Verifies: getTierMetadata, classifyPathTier (fail-closed),
// assertTierCompatibility (migration rule enforcement),
// TierViolationError name and message.
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  EpistemicTier,
  getTierMetadata,
  classifyPathTier,
  assertTierCompatibility,
  TierViolationError,
} from '../../src/core/tier'

describe('EpistemicTier — getTierMetadata', () => {

  it('all 6 tiers have non-empty metadata fields', () => {
    for (let t = 0; t <= 5; t++) {
      const meta = getTierMetadata(t as EpistemicTier)
      expect(meta.tier).toBe(t)
      expect(meta.standard.length).toBeGreaterThan(0)
      expect(meta.validation_requirement.length).toBeGreaterThan(0)
      expect(meta.promotion_condition.length).toBeGreaterThan(0)
      expect(meta.domain_ceiling.length).toBeGreaterThan(0)
    }
  })

  it('T0 standard is mechanically proven', () => {
    const meta = getTierMetadata(EpistemicTier.T0)
    expect(meta.standard.toLowerCase()).toContain('mechanically proven')
  })

  it('T4 and T5 have no validation requirement (speculative/creative)', () => {
    expect(getTierMetadata(EpistemicTier.T4).validation_requirement).toBe('None — speculative tier')
    expect(getTierMetadata(EpistemicTier.T5).validation_requirement).toBe('None — creative tier')
  })

  it('getTierMetadata is deterministic — identical result on 3 calls', () => {
    for (let t = 0; t <= 5; t++) {
      const m1 = getTierMetadata(t as EpistemicTier)
      const m2 = getTierMetadata(t as EpistemicTier)
      const m3 = getTierMetadata(t as EpistemicTier)
      expect(JSON.stringify(m1)).toBe(JSON.stringify(m2))
      expect(JSON.stringify(m2)).toBe(JSON.stringify(m3))
    }
  })

})

describe('classifyPathTier — ceiling classification', () => {

  it('src/core/* paths get T0 ceiling', () => {
    expect(classifyPathTier('src/core/canonicalize.ts')).toBe(EpistemicTier.T0)
    expect(classifyPathTier('src/core/fixedpoint.ts')).toBe(EpistemicTier.T0)
  })

  it('src/event/* paths get T0 ceiling', () => {
    expect(classifyPathTier('src/event/store.ts')).toBe(EpistemicTier.T0)
    expect(classifyPathTier('src/event/uuid.ts')).toBe(EpistemicTier.T0)
  })

  it('src/gate/* paths get T0 ceiling', () => {
    expect(classifyPathTier('src/gate/hoeffding.ts')).toBe(EpistemicTier.T0)
  })

  it('src/verifier/* and src/calibration/* paths get T1 ceiling', () => {
    expect(classifyPathTier('src/verifier/registry.ts')).toBe(EpistemicTier.T1)
    expect(classifyPathTier('src/calibration/vcg.ts')).toBe(EpistemicTier.T1)
  })

  it('src/projection/* and src/pipeline/* paths get T2 ceiling', () => {
    expect(classifyPathTier('src/projection/reducer.ts')).toBe(EpistemicTier.T2)
    expect(classifyPathTier('src/pipeline/index.ts')).toBe(EpistemicTier.T2)
  })

  it('docs/vision/* paths get T4 ceiling', () => {
    expect(classifyPathTier('docs/vision/swarm.md')).toBe(EpistemicTier.T4)
  })

  it('FAILS CLOSED: unrecognised paths return T0 (not T5)', () => {
    // An unrecognised path must never grant a permissive ceiling
    expect(classifyPathTier('unknown/some/path.ts')).toBe(EpistemicTier.T0)
    expect(classifyPathTier('')).toBe(EpistemicTier.T0)
    expect(classifyPathTier('src/unknown-module/foo.ts')).toBe(EpistemicTier.T0)
  })

  it('classifyPathTier is deterministic — 3 identical calls per path', () => {
    const paths = [
      'src/core/canonicalize.ts',
      'src/calibration/vcg.ts',
      'docs/vision/swarm.md',
      'unknown/path.ts',
    ]
    for (const p of paths) {
      const r1 = classifyPathTier(p)
      const r2 = classifyPathTier(p)
      const r3 = classifyPathTier(p)
      expect(r1).toBe(r2)
      expect(r2).toBe(r3)
    }
  })

})

describe('assertTierCompatibility — migration rule enforcement', () => {

  it('passes when construct tier ≤ ceiling tier', () => {
    // T0 construct in T0 path — always allowed
    expect(() =>
      assertTierCompatibility(EpistemicTier.T0, 'src/core/canonicalize.ts', 'RFC8785')
    ).not.toThrow()

    // T1 construct in T1 path — allowed
    expect(() =>
      assertTierCompatibility(EpistemicTier.T1, 'src/calibration/vcg.ts', 'VCG')
    ).not.toThrow()

    // T0 construct in T1 path — also allowed (T0 ≤ T1)
    expect(() =>
      assertTierCompatibility(EpistemicTier.T0, 'src/calibration/vcg.ts', 'hash')
    ).not.toThrow()
  })

  it('throws TierViolationError when T4 or T5 construct grounds T0 path', () => {
    // MIGRATION RULE: No T4/T5 may ground T0–T2 claim without evidence review
    expect(() =>
      assertTierCompatibility(EpistemicTier.T4, 'src/core/canonicalize.ts', 'swarm-vision')
    ).toThrow(TierViolationError)

    expect(() =>
      assertTierCompatibility(EpistemicTier.T5, 'src/event/store.ts', 'cycle-narrative')
    ).toThrow(TierViolationError)
  })

  it('throws TierViolationError when T3 construct grounds T0 path', () => {
    expect(() =>
      assertTierCompatibility(EpistemicTier.T3, 'src/gate/hoeffding.ts', 'quasicrystal-conjecture')
    ).toThrow(TierViolationError)
  })

  it('TierViolationError has correct name and contains tier info in message', () => {
    let caught: unknown
    try {
      assertTierCompatibility(EpistemicTier.T4, 'src/core/canonicalize.ts', 'swarm')
    } catch (e) {
      caught = e
    }
    expect(caught).toBeInstanceOf(TierViolationError)
    expect((caught as TierViolationError).name).toBe('TierViolationError')
    expect((caught as TierViolationError).message).toContain('T4')
    expect((caught as TierViolationError).message).toContain('Evidence review required')
  })

  it('T2 construct in T2 path — allowed; T3 in T2 path — throws', () => {
    expect(() =>
      assertTierCompatibility(EpistemicTier.T2, 'src/pipeline/index.ts', 'heuristic')
    ).not.toThrow()

    expect(() =>
      assertTierCompatibility(EpistemicTier.T3, 'src/pipeline/index.ts', 'conjecture')
    ).toThrow(TierViolationError)
  })

})
