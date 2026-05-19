// ============================================================
// Gate 15 — Subatomic Holon Particle (SHP) Tests
// ~20 tests: phase ordering, execution identity, invariant guard,
//   phase factories, temporal separation, determinism
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  SHP_PHASE_ORDER,
  phaseOrdinal,
  type SHPExecutionIdentity,
} from '../../src/shp/types.js'
import {
  SHP_EXECUTION_INVARIANTS,
} from '../../src/shp/execution.js'
import {
  checkSHPInvariants,
  validatePhaseTransition,
  validatePhaseSequence,
} from '../../src/shp/guard.js'
import {
  createReadIdentity,
  createAssessIdentity,
  createLockIdentity,
  createPropagateIdentity,
  createHarmonizeIdentity,
} from '../../src/shp/factory.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types'

// ─── Test helpers ──────────────────────────────────────────

const SEQ1 = BigInt(1) as SequenceNumber
const SEQ2 = BigInt(2) as SequenceNumber
const PARENT = 'a'.repeat(64) as SHA256Hex
const HOLON = 'holon-agent-001'

// ─── Phase Ordering ────────────────────────────────────────

describe('SHP phase ordering', () => {
  it('SHP_PHASE_ORDER has exactly 5 phases in R→A→L→P→H sequence', () => {
    expect(SHP_PHASE_ORDER).toHaveLength(5)
    expect(SHP_PHASE_ORDER).toEqual(['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'])
  })

  it('phaseOrdinal is strictly increasing across the order', () => {
    for (let i = 1; i < SHP_PHASE_ORDER.length; i++) {
      expect(phaseOrdinal(SHP_PHASE_ORDER[i]!)).toBeGreaterThan(phaseOrdinal(SHP_PHASE_ORDER[i - 1]!))
    }
  })

  it('phaseOrdinal: READ=0, LOCK=2, HARMONIZE=4', () => {
    expect(phaseOrdinal('READ')).toBe(0)
    expect(phaseOrdinal('LOCK')).toBe(2)
    expect(phaseOrdinal('HARMONIZE')).toBe(4)
  })

  it('ASSESS precedes LOCK — INV-SHP-01 satisfied by ordinal', () => {
    expect(phaseOrdinal('ASSESS')).toBeLessThan(phaseOrdinal('LOCK'))
  })

  it('AOIE (PROPAGATE) is strictly post-LOCK — INV-SHP-06/07 temporal basis', () => {
    expect(phaseOrdinal('LOCK')).toBeLessThan(phaseOrdinal('PROPAGATE'))
  })
})

// ─── Invariant Registry ────────────────────────────────────

describe('SHP_EXECUTION_INVARIANTS', () => {
  it('has exactly 8 invariants', () => {
    expect(SHP_EXECUTION_INVARIANTS).toHaveLength(8)
  })

  it('all invariants have unique IDs INV-SHP-01..08', () => {
    const ids = SHP_EXECUTION_INVARIANTS.map(i => i.id)
    expect(new Set(ids).size).toBe(8)
    expect(ids.every(id => id.startsWith('INV-SHP-'))).toBe(true)
  })
})

// ─── Phase Transition Validation ──────────────────────────

describe('validatePhaseTransition', () => {
  it('READ → ASSESS is valid', () => {
    expect(validatePhaseTransition('READ', 'ASSESS')).toBe(true)
  })

  it('ASSESS → LOCK is valid', () => {
    expect(validatePhaseTransition('ASSESS', 'LOCK')).toBe(true)
  })

  it('READ → LOCK skips ASSESS — invalid', () => {
    expect(validatePhaseTransition('READ', 'LOCK')).toBe(false)
  })

  it('HARMONIZE → READ reverse — invalid', () => {
    expect(validatePhaseTransition('HARMONIZE', 'READ')).toBe(false)
  })
})

describe('validatePhaseSequence', () => {
  it('empty sequence is valid', () => {
    expect(validatePhaseSequence([])).toBe(true)
  })

  it('valid prefix [READ, ASSESS, LOCK] passes', () => {
    expect(validatePhaseSequence(['READ', 'ASSESS', 'LOCK'])).toBe(true)
  })

  it('full sequence passes', () => {
    expect(validatePhaseSequence([...SHP_PHASE_ORDER])).toBe(true)
  })

  it('out-of-order [ASSESS, READ] fails', () => {
    expect(validatePhaseSequence(['ASSESS', 'READ'])).toBe(false)
  })
})

// ─── Invariant Guard ───────────────────────────────────────

describe('checkSHPInvariants', () => {
  it('valid ASSESS identity passes all invariants', () => {
    const id = createAssessIdentity({
      holonId: HOLON,
      state: {},
      eventSlice: [],
      constraintResult: { violated: false, severity: 'NONE' },
      sequence: SEQ1,
      parentCommitHash: null,
    })
    const r = checkSHPInvariants(id)
    expect(r.valid).toBe(true)
    expect(r.violations).toHaveLength(0)
  })

  it('ASSESS phase with classification → INV-SHP-06 violation', () => {
    const base = createAssessIdentity({
      holonId: HOLON, state: {}, eventSlice: [],
      constraintResult: { violated: false, severity: 'NONE' },
      sequence: SEQ1, parentCommitHash: null,
    })
    // Manually inject the forbidden field (cast to override readonly)
    const bad = { ...base, classification: { arbitration: 'RESOLVED', identity: 'CONTINUOUS', drift: 'STABLE' } } as SHPExecutionIdentity
    const r = checkSHPInvariants(bad)
    expect(r.valid).toBe(false)
    expect(r.violations.some(v => v.rule === 'INV-SHP-06')).toBe(true)
  })

  it('PROPAGATE phase with constraintResult → INV-SHP-07 violation', () => {
    const base = createPropagateIdentity({
      holonId: HOLON, state: {},
      commitHash: PARENT,
      sequence: SEQ1, parentCommitHash: null,
    })
    const bad = { ...base, constraintResult: { violated: true, severity: 'DEGRADED' } } as SHPExecutionIdentity
    const r = checkSHPInvariants(bad)
    expect(r.valid).toBe(false)
    expect(r.violations.some(v => v.rule === 'INV-SHP-07')).toBe(true)
  })
})

// ─── Phase Factories ───────────────────────────────────────

describe('SHP phase factories', () => {
  it('createReadIdentity: frozen, phase=READ, no classification/constraint', () => {
    const id = createReadIdentity({ holonId: HOLON, state: {}, eventSlice: ['e1'], sequence: SEQ1, parentCommitHash: null })
    expect(Object.isFrozen(id)).toBe(true)
    expect(id.phase).toBe('READ')
    expect(id.isReplaySafe).toBe(true)
    expect(id.classification).toBeUndefined()
    expect(id.constraintResult).toBeUndefined()
  })

  it('createAssessIdentity: constraintResult present, no classification', () => {
    const id = createAssessIdentity({ holonId: HOLON, state: {}, eventSlice: [], constraintResult: { violated: true, severity: 'UNSTABLE' }, sequence: SEQ1, parentCommitHash: null })
    expect(id.phase).toBe('ASSESS')
    expect(id.constraintResult?.violated).toBe(true)
    expect(id.classification).toBeUndefined()
  })

  it('createLockIdentity: phase=LOCK, no constraintResult, no classification', () => {
    const id = createLockIdentity({ holonId: HOLON, frozenState: {}, sequence: SEQ1, parentCommitHash: PARENT })
    expect(id.phase).toBe('LOCK')
    expect(id.constraintResult).toBeUndefined()
    expect(id.classification).toBeUndefined()
  })

  it('createHarmonizeIdentity: classification present, no constraintResult', () => {
    const id = createHarmonizeIdentity({ holonId: HOLON, state: {}, classification: { arbitration: 'RESOLVED', identity: 'CONTINUOUS', drift: 'STABLE' }, commitHash: PARENT, sequence: SEQ1, parentCommitHash: null })
    expect(id.phase).toBe('HARMONIZE')
    expect(id.classification?.arbitration).toBe('RESOLVED')
    expect(id.constraintResult).toBeUndefined()
  })

  it('commitHash is deterministic (3 identical READ factory calls)', () => {
    const p = { holonId: HOLON, state: {}, eventSlice: [], sequence: SEQ1, parentCommitHash: null }
    const h1 = createReadIdentity(p).commitHash
    const h2 = createReadIdentity(p).commitHash
    const h3 = createReadIdentity(p).commitHash
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('different sequence produces different commitHash', () => {
    const p1 = createReadIdentity({ holonId: HOLON, state: {}, eventSlice: [], sequence: SEQ1, parentCommitHash: null })
    const p2 = createReadIdentity({ holonId: HOLON, state: {}, eventSlice: [], sequence: SEQ2, parentCommitHash: null })
    expect(p1.commitHash).not.toBe(p2.commitHash)
  })
})
