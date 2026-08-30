// ============================================================
// Gate 21 — Guardian Policy Runtime Tests
// ~22 tests: amendment lifecycle, deterministic IDs, verdict
//   recording, invariant regression guard, immutability.
// ============================================================

import { describe, it, expect } from 'vitest'
import { PolicyAmendmentEngine } from '../../src/constitutional/policy.js'
import { PolicyAmendmentError } from '../../src/constitutional/amendment.js'

// ─── Helpers ───────────────────────────────────────────────

const BASE_PARAMS = {
  target: 'src/gate/risk.ts',
  description: 'Relax risk budget ceiling from 0.15 to 0.20',
  constraint_delta: 'risk_ceiling: 0.20',
  at_sequence: 42,
} as const

function engineWithProposal() {
  return PolicyAmendmentEngine.empty().propose(BASE_PARAMS)
}

// ─── PolicyAmendmentEngine ─────────────────────────────────

describe('PolicyAmendmentEngine — propose', () => {
  it('empty() has zero amendments', () => {
    expect(PolicyAmendmentEngine.empty().count).toBe(0)
    expect(PolicyAmendmentEngine.empty().getAll()).toHaveLength(0)
  })

  it('propose() increments count', () => {
    const { engine } = engineWithProposal()
    expect(engine.count).toBe(1)
  })

  it('proposed amendment has PROPOSED status', () => {
    const { amendment } = engineWithProposal()
    expect(amendment.status).toBe('PROPOSED')
  })

  it('proposed amendment is frozen', () => {
    const { amendment } = engineWithProposal()
    expect(Object.isFrozen(amendment)).toBe(true)
  })

  it('amendment_id is deterministic — same inputs → same id 3×', () => {
    const { amendment: a1 } = engineWithProposal()
    const { amendment: a2 } = engineWithProposal()
    const { amendment: a3 } = engineWithProposal()
    expect(a1.amendment_id).toBe(a2.amendment_id)
    expect(a2.amendment_id).toBe(a3.amendment_id)
  })

  it('different sequence → different amendment_id', () => {
    const { amendment: a1 } = PolicyAmendmentEngine.empty().propose({ ...BASE_PARAMS, at_sequence: 1 })
    const { amendment: a2 } = PolicyAmendmentEngine.empty().propose({ ...BASE_PARAMS, at_sequence: 2 })
    expect(a1.amendment_id).not.toBe(a2.amendment_id)
  })

  it('amendment has is_replay_reconstructable: true', () => {
    const { amendment } = engineWithProposal()
    expect(amendment.is_replay_reconstructable).toBe(true)
  })

  it('amendment has schema_version', () => {
    const { amendment } = engineWithProposal()
    expect(amendment.schema_version).toBe('1.0.0')
  })

  it('propose() is immutable — original engine unaffected', () => {
    const e0 = PolicyAmendmentEngine.empty()
    const { engine: e1 } = e0.propose(BASE_PARAMS)
    expect(e0.count).toBe(0)
    expect(e1.count).toBe(1)
  })

  it('getById() returns correct amendment', () => {
    const { engine, amendment } = engineWithProposal()
    const found = engine.getById(amendment.amendment_id)
    expect(found?.amendment_id).toBe(amendment.amendment_id)
  })

  it('getById() returns null for unknown id', () => {
    const { engine } = engineWithProposal()
    expect(engine.getById('nonexistent')).toBeNull()
  })

  it('multiple proposals coexist', () => {
    const { engine: e1 } = PolicyAmendmentEngine.empty().propose({ ...BASE_PARAMS, at_sequence: 1 })
    const { engine: e2 } = e1.propose({ ...BASE_PARAMS, at_sequence: 2 })
    const { engine: e3 } = e2.propose({ ...BASE_PARAMS, at_sequence: 3 })
    expect(e3.count).toBe(3)
  })
})

describe('PolicyAmendmentEngine — recordVerdict', () => {
  it('APPROVED verdict → status APPROVED', () => {
    const { engine, amendment } = engineWithProposal()
    const e2 = engine.recordVerdict(amendment.amendment_id, 'APPROVED')
    expect(e2.getById(amendment.amendment_id)?.status).toBe('APPROVED')
    expect(e2.getById(amendment.amendment_id)?.guardian_verdict).toBe('APPROVED')
  })

  it('VETOED verdict → status REJECTED', () => {
    const { engine, amendment } = engineWithProposal()
    const e2 = engine.recordVerdict(amendment.amendment_id, 'VETOED')
    expect(e2.getById(amendment.amendment_id)?.status).toBe('REJECTED')
  })

  it('recordVerdict on unknown id → throws PolicyAmendmentError', () => {
    const { engine } = engineWithProposal()
    expect(() => engine.recordVerdict('bad_id', 'APPROVED')).toThrow(PolicyAmendmentError)
  })

  it('recordVerdict on APPLIED amendment → throws PolicyAmendmentError', () => {
    const { engine, amendment } = engineWithProposal()
    const e2 = engine.recordVerdict(amendment.amendment_id, 'APPROVED')
    const e3 = e2.apply(amendment.amendment_id, { at_sequence: 100, invariants_passed: true })
    expect(() => e3.recordVerdict(amendment.amendment_id, 'APPROVED')).toThrow(PolicyAmendmentError)
  })

  it('recordVerdict is immutable — previous engine unchanged', () => {
    const { engine, amendment } = engineWithProposal()
    const e2 = engine.recordVerdict(amendment.amendment_id, 'APPROVED')
    expect(engine.getById(amendment.amendment_id)?.status).toBe('PROPOSED')
    expect(e2.getById(amendment.amendment_id)?.status).toBe('APPROVED')
  })
})

describe('PolicyAmendmentEngine — apply', () => {
  it('apply APPROVED amendment → status APPLIED', () => {
    const { engine, amendment } = engineWithProposal()
    const e2 = engine.recordVerdict(amendment.amendment_id, 'APPROVED')
    const e3 = e2.apply(amendment.amendment_id, { at_sequence: 99, invariants_passed: true })
    const applied = e3.getById(amendment.amendment_id)
    expect(applied?.status).toBe('APPLIED')
    expect(applied?.applied_at_sequence).toBe(99)
  })

  it('apply PROPOSED amendment → throws PolicyAmendmentError', () => {
    const { engine, amendment } = engineWithProposal()
    expect(() => engine.apply(amendment.amendment_id, { at_sequence: 99, invariants_passed: true }))
      .toThrow(PolicyAmendmentError)
  })

  it('apply REJECTED amendment → throws PolicyAmendmentError', () => {
    const { engine, amendment } = engineWithProposal()
    const e2 = engine.recordVerdict(amendment.amendment_id, 'VETOED')
    expect(() => e2.apply(amendment.amendment_id, { at_sequence: 99, invariants_passed: true }))
      .toThrow(PolicyAmendmentError)
  })

  it('apply with invariants_passed: false → throws PolicyAmendmentError', () => {
    const { engine, amendment } = engineWithProposal()
    const e2 = engine.recordVerdict(amendment.amendment_id, 'APPROVED')
    expect(() => e2.apply(amendment.amendment_id, { at_sequence: 99, invariants_passed: false }))
      .toThrow(PolicyAmendmentError)
  })

  it('apply on unknown id → throws PolicyAmendmentError', () => {
    const { engine } = engineWithProposal()
    expect(() => engine.apply('bad_id', { at_sequence: 1, invariants_passed: true }))
      .toThrow(PolicyAmendmentError)
  })

  it('getAll() is frozen', () => {
    const { engine } = engineWithProposal()
    expect(Object.isFrozen(engine.getAll())).toBe(true)
  })
})
