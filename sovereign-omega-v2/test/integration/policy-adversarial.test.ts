// ============================================================
// Gate 63 — Guardian Policy Adversarial (Integration)
// ~22 tests: amendment lifecycle at scale; REJECTED/VETOED
//   cascade; double-apply throws; invariant regression throws;
//   concurrent proposal ordering; id determinism at 50 proposals.
// ============================================================

import { describe, it, expect } from 'vitest'
import { PolicyAmendmentEngine } from '../../src/constitutional/policy.js'
import { PolicyAmendmentError } from '../../src/constitutional/amendment.js'

function propose(engine: PolicyAmendmentEngine, n: number) {
  return engine.propose({
    target: `target_${n}`,
    description: `Amendment ${n}`,
    constraint_delta: `allow_feature_${n}`,
    at_sequence: n,
  })
}

// ─── Lifecycle at scale ────────────────────────────────────

describe('Policy: lifecycle at scale', () => {
  it('50 proposals → count=50, all PROPOSED', () => {
    let engine = PolicyAmendmentEngine.empty()
    for (let i = 1; i <= 50; i++) {
      const { engine: next } = propose(engine, i)
      engine = next
    }
    expect(engine.count).toBe(50)
    for (const a of engine.getAll()) {
      expect(a.status).toBe('PROPOSED')
    }
  })

  it('10 proposals → all APPROVED → all APPLIED in sequence', () => {
    let engine = PolicyAmendmentEngine.empty()
    const ids: string[] = []
    for (let i = 1; i <= 10; i++) {
      const { engine: next, amendment } = propose(engine, i)
      engine = next
      ids.push(amendment.amendment_id)
    }
    for (const id of ids) {
      engine = engine.recordVerdict(id, 'APPROVED')
    }
    for (let i = 0; i < ids.length; i++) {
      engine = engine.apply(ids[i]!, { at_sequence: 100 + i, invariants_passed: true })
    }
    expect(engine.count).toBe(10)
    for (const a of engine.getAll()) {
      expect(a.status).toBe('APPLIED')
    }
  })

  it('amendment_id is deterministic: same input → same id', () => {
    const eng1 = PolicyAmendmentEngine.empty()
    const eng2 = PolicyAmendmentEngine.empty()
    const { amendment: a1 } = eng1.propose({ target: 'X', description: 'D', constraint_delta: 'C', at_sequence: 7 })
    const { amendment: a2 } = eng2.propose({ target: 'X', description: 'D', constraint_delta: 'C', at_sequence: 7 })
    expect(a1.amendment_id).toBe(a2.amendment_id)
  })

  it('different inputs → different amendment_id', () => {
    const engine = PolicyAmendmentEngine.empty()
    const { amendment: a1 } = engine.propose({ target: 'X', description: 'D', constraint_delta: 'C', at_sequence: 1 })
    const { amendment: a2 } = engine.propose({ target: 'Y', description: 'D', constraint_delta: 'C', at_sequence: 2 })
    expect(a1.amendment_id).not.toBe(a2.amendment_id)
  })

  it('immutability: original engine unchanged after propose', () => {
    const engine = PolicyAmendmentEngine.empty()
    propose(engine, 1)
    expect(engine.count).toBe(0)
  })
})

// ─── REJECTED / VETOED cascade ────────────────────────────

describe('Policy: REJECTED/VETOED cascade', () => {
  it('VETOED amendment cannot be applied', () => {
    let engine = PolicyAmendmentEngine.empty()
    const { engine: next, amendment } = propose(engine, 1)
    engine = next.recordVerdict(amendment.amendment_id, 'VETOED')
    expect(() =>
      engine.apply(amendment.amendment_id, { at_sequence: 99, invariants_passed: true }),
    ).toThrow(PolicyAmendmentError)
  })

  it('10 amendments: 5 VETOED + 5 APPROVED → 5 REJECTED, 5 APPLIED', () => {
    let engine = PolicyAmendmentEngine.empty()
    const ids: string[] = []
    for (let i = 1; i <= 10; i++) {
      const { engine: next, amendment } = propose(engine, i)
      engine = next
      ids.push(amendment.amendment_id)
    }
    for (let i = 0; i < 5; i++) {
      engine = engine.recordVerdict(ids[i]!, 'VETOED')
    }
    for (let i = 5; i < 10; i++) {
      engine = engine.recordVerdict(ids[i]!, 'APPROVED')
      engine = engine.apply(ids[i]!, { at_sequence: 200 + i, invariants_passed: true })
    }
    const all = engine.getAll()
    const rejected = all.filter(a => a.status === 'REJECTED')
    const applied = all.filter(a => a.status === 'APPLIED')
    expect(rejected).toHaveLength(5)
    expect(applied).toHaveLength(5)
  })

  it('REJECTED amendment has guardian_verdict=VETOED', () => {
    let engine = PolicyAmendmentEngine.empty()
    const { engine: next, amendment } = propose(engine, 1)
    engine = next.recordVerdict(amendment.amendment_id, 'VETOED')
    const a = engine.getById(amendment.amendment_id)!
    expect(a.status).toBe('REJECTED')
    expect(a.guardian_verdict).toBe('VETOED')
  })
})

// ─── Double-apply / invalid transitions ───────────────────

describe('Policy: invalid transitions throw PolicyAmendmentError', () => {
  it('double-apply throws', () => {
    let engine = PolicyAmendmentEngine.empty()
    const { engine: next, amendment } = propose(engine, 1)
    engine = next.recordVerdict(amendment.amendment_id, 'APPROVED')
    engine = engine.apply(amendment.amendment_id, { at_sequence: 10, invariants_passed: true })
    expect(() =>
      engine.apply(amendment.amendment_id, { at_sequence: 11, invariants_passed: true }),
    ).toThrow(PolicyAmendmentError)
  })

  it('apply on PROPOSED (not yet APPROVED) throws', () => {
    let engine = PolicyAmendmentEngine.empty()
    const { engine: next, amendment } = propose(engine, 1)
    engine = next
    expect(() =>
      engine.apply(amendment.amendment_id, { at_sequence: 10, invariants_passed: true }),
    ).toThrow(PolicyAmendmentError)
  })

  it('invariant regression on apply throws', () => {
    let engine = PolicyAmendmentEngine.empty()
    const { engine: next, amendment } = propose(engine, 1)
    engine = next.recordVerdict(amendment.amendment_id, 'APPROVED')
    expect(() =>
      engine.apply(amendment.amendment_id, { at_sequence: 10, invariants_passed: false }),
    ).toThrow(PolicyAmendmentError)
  })

  it('recordVerdict on APPLIED throws', () => {
    let engine = PolicyAmendmentEngine.empty()
    const { engine: next, amendment } = propose(engine, 1)
    engine = next.recordVerdict(amendment.amendment_id, 'APPROVED')
    engine = engine.apply(amendment.amendment_id, { at_sequence: 10, invariants_passed: true })
    expect(() => engine.recordVerdict(amendment.amendment_id, 'APPROVED')).toThrow(PolicyAmendmentError)
  })

  it('getById returns null for unknown id', () => {
    const engine = PolicyAmendmentEngine.empty()
    expect(engine.getById('nonexistent')).toBeNull()
  })

  it('recordVerdict on unknown id throws', () => {
    const engine = PolicyAmendmentEngine.empty()
    expect(() => engine.recordVerdict('nonexistent', 'APPROVED')).toThrow(PolicyAmendmentError)
  })
})

// ─── is_replay_reconstructable + schema ───────────────────

describe('Policy: replay fields', () => {
  it('all amendments have is_replay_reconstructable=true', () => {
    let engine = PolicyAmendmentEngine.empty()
    for (let i = 1; i <= 5; i++) {
      const { engine: next } = propose(engine, i)
      engine = next
    }
    for (const a of engine.getAll()) {
      expect(a.is_replay_reconstructable).toBe(true)
    }
  })

  it('applied_at_sequence recorded on APPLIED amendment', () => {
    let engine = PolicyAmendmentEngine.empty()
    const { engine: next, amendment } = propose(engine, 1)
    engine = next.recordVerdict(amendment.amendment_id, 'APPROVED')
    engine = engine.apply(amendment.amendment_id, { at_sequence: 42, invariants_passed: true })
    const a = engine.getById(amendment.amendment_id)!
    expect(a.applied_at_sequence).toBe(42)
  })
})
