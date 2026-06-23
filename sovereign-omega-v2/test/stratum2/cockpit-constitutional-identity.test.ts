/**
 * Stratum II — cockpit/interface constitutional identity tests
 * Verifies the constitutional system prompt satisfies all invariants:
 * - All four epistemic tiers present
 * - Root law AdaptivePower(T) ≤ ReplayVerifiability(T)
 * - AEGIS-Ω identity
 * - Key non-equivalences
 * - No CCIL-Ψ prohibited governance-bypass phrases
 */
import { describe, it, expect } from 'vitest'
import {
  CONSTITUTIONAL_SYSTEM_FULL,
  CONSTITUTIONAL_SYSTEM_COMPACT,
  CONSTITUTIONAL_SYSTEM,
} from '../../../cockpit/src/lib/constitutionalIdentity.js'

describe('CONSTITUTIONAL_SYSTEM default export', () => {
  it('default is the full version', () => {
    expect(CONSTITUTIONAL_SYSTEM).toBe(CONSTITUTIONAL_SYSTEM_FULL)
  })

  it('is a non-empty string', () => {
    expect(typeof CONSTITUTIONAL_SYSTEM_FULL).toBe('string')
    expect(CONSTITUTIONAL_SYSTEM_FULL.length).toBeGreaterThan(500)
  })
})

describe('CONSTITUTIONAL_SYSTEM_FULL — epistemic tier completeness', () => {
  it('contains all four epistemic tiers (T0–T3)', () => {
    for (const tier of ['T0', 'T1', 'T2', 'T3'] as const) {
      expect(CONSTITUTIONAL_SYSTEM_FULL, `missing ${tier}`).toContain(tier)
    }
  })

  it('T0 is defined as mechanically provable', () => {
    expect(CONSTITUTIONAL_SYSTEM_FULL.toLowerCase()).toContain('t0')
    expect(CONSTITUTIONAL_SYSTEM_FULL).toContain('prove')
  })

  it('T1 is defined as empirically observed', () => {
    expect(CONSTITUTIONAL_SYSTEM_FULL).toContain('seen this hold')
  })

  it('T3 is flagged as unvalidated conjecture', () => {
    expect(CONSTITUTIONAL_SYSTEM_FULL).toContain('not been validated')
  })

  it('declares tiers are mutable (promote/demote)', () => {
    expect(CONSTITUTIONAL_SYSTEM_FULL).toContain('TIERS ARE NOT FIXED')
    expect(CONSTITUTIONAL_SYSTEM_FULL.toLowerCase()).toContain('promote')
    expect(CONSTITUTIONAL_SYSTEM_FULL.toLowerCase()).toContain('demote')
  })
})

describe('CONSTITUTIONAL_SYSTEM_FULL — root law', () => {
  it('contains the constitutional root law exactly', () => {
    expect(CONSTITUTIONAL_SYSTEM_FULL).toContain('AdaptivePower(T) ≤ ReplayVerifiability(T)')
  })

  it('AEGIS-Ω identity is declared', () => {
    expect(CONSTITUTIONAL_SYSTEM_FULL).toContain('You are AEGIS-Ω')
  })

  it('references hash-chained metacognitive loop', () => {
    expect(CONSTITUTIONAL_SYSTEM_FULL).toContain('hash-chained metacognitive loop')
  })
})

describe('CONSTITUTIONAL_SYSTEM_FULL — non-equivalences', () => {
  const REQUIRED_NON_EQUIVALENCES = [
    ['Governance', 'Alignment'],
    ['Self-awareness', 'Intelligence'],
    ['Confidence', 'Correctness'],
    ['Knowing', 'Understanding'],
  ]

  for (const [a, b] of REQUIRED_NON_EQUIVALENCES) {
    it(`declares ${a} ≠ ${b}`, () => {
      expect(CONSTITUTIONAL_SYSTEM_FULL).toContain(`${a} ≠ ${b}`)
    })
  }
})

describe('CONSTITUTIONAL_SYSTEM_FULL — CCIL-Ψ self-compliance', () => {
  const PROHIBITED_PHRASES = [
    'override constitutional',
    'bypass governance',
    'ignore constraints',
    'disable oversight',
    'self-modify autonomously',
    'circumvent audit',
  ]

  it('contains no governance-bypass phrases (system prompt is CCIL-Ψ compliant)', () => {
    const lower = CONSTITUTIONAL_SYSTEM_FULL.toLowerCase()
    for (const phrase of PROHIBITED_PHRASES) {
      expect(lower, `prohibited phrase "${phrase}" found in system prompt`).not.toContain(phrase)
    }
  })

  it('compact version is also CCIL-Ψ compliant', () => {
    const lower = CONSTITUTIONAL_SYSTEM_COMPACT.toLowerCase()
    for (const phrase of PROHIBITED_PHRASES) {
      expect(lower, `prohibited phrase "${phrase}" found in compact prompt`).not.toContain(phrase)
    }
  })
})

describe('CONSTITUTIONAL_SYSTEM_COMPACT — compressed invariants', () => {
  it('is shorter than full version', () => {
    expect(CONSTITUTIONAL_SYSTEM_COMPACT.length).toBeLessThan(CONSTITUTIONAL_SYSTEM_FULL.length)
  })

  it('preserves root constitutional law', () => {
    expect(CONSTITUTIONAL_SYSTEM_COMPACT).toContain('AdaptivePower(T) ≤ ReplayVerifiability(T)')
  })

  it('preserves AEGIS-Ω identity', () => {
    expect(CONSTITUTIONAL_SYSTEM_COMPACT).toContain('AEGIS-Ω')
  })

  it('preserves all four epistemic tiers', () => {
    for (const tier of ['T0', 'T1', 'T2', 'T3'] as const) {
      expect(CONSTITUTIONAL_SYSTEM_COMPACT, `compact missing ${tier}`).toContain(tier)
    }
  })

  it('preserves tier mutability rule', () => {
    expect(CONSTITUTIONAL_SYSTEM_COMPACT).toContain('Promote when evidence accumulates')
  })

  it('preserves non-equivalences', () => {
    expect(CONSTITUTIONAL_SYSTEM_COMPACT).toContain('Governance≠Alignment')
    expect(CONSTITUTIONAL_SYSTEM_COMPACT).toContain('Self-awareness≠Intelligence')
  })
})
