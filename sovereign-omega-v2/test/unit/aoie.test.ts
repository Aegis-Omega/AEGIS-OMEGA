// ============================================================
// Gate 12 — AOIE Structural Classification Oracle Tests
// ~20 tests: classifyRuntime determinism, arbitration, identity,
//   drift, lattice, hash, freeze, phase guard
// ============================================================

import { describe, it, expect } from 'vitest'
import type { RuntimeSnapshot, PolicyMutation, EpistemicAssertion } from '../../src/aoie/types'
import { AOIE_SCHEMA_VERSION } from '../../src/aoie/types.js'
import { hashSnapshot, snapshotsAreIdentical, computeIdentityDrift } from '../../src/aoie/hash.js'
import { classifyArbitration } from '../../src/aoie/arbitration.js'
import { classifyIdentityContinuity } from '../../src/aoie/identity.js'
import { classifyConstitutionalDrift } from '../../src/aoie/drift.js'
import { classifyGlobalState, compareGlobalStates, AOIE_SEVERITY_ORDER } from '../../src/aoie/lattice.js'
import { freezeClassification, freezeSnapshot } from '../../src/aoie/freeze.js'
import { classifyRuntime } from '../../src/aoie/runtime.js'
import { SITRConstraintError } from '../../src/sitr/types.js'
import { EpistemicTier } from '../../src/core/types'
import type { SHA256Hex } from '../../src/core/types'

// ─── Test helpers ──────────────────────────────────────────

const mockHash = (s: string) => s.padEnd(64, '0') as SHA256Hex
const ZERO_HASH = '0'.repeat(64) as SHA256Hex

function makeSnapshot(overrides: Partial<RuntimeSnapshot> = {}): RuntimeSnapshot {
  return Object.freeze({
    snapshot_id: 'snap-001',
    sequence: 1,
    schema_version: AOIE_SCHEMA_VERSION,
    phase: 'post_enforcement' as const,
    state_hash: mockHash('h1'),
    panel_sequence_numbers: Object.freeze([1, 1, 1, 1, 1, 1, 1, 1, 1, 1]),
    ...overrides,
  })
}

function makeMutation(overrides: Partial<PolicyMutation> = {}): PolicyMutation {
  return Object.freeze({
    mutation_id: 'm-001',
    sequence: 1,
    policy_type: 'capability',
    prior_hash: mockHash('p1'),
    next_hash: mockHash('n1'),
    ...overrides,
  })
}

function makeAssertion(overrides: Partial<EpistemicAssertion> = {}): EpistemicAssertion {
  return Object.freeze({
    assertion_id: 'a-001',
    sequence: 1,
    subject_id: 'module-x',
    claimed_tier: EpistemicTier.T2,
    evidence_hash: mockHash('ev1'),
    ...overrides,
  })
}

const BASE_PARAMS = {
  snapshots: [makeSnapshot()],
  mutations: [] as PolicyMutation[],
  assertions: [] as EpistemicAssertion[],
  sequence: 1,
}

// ─── Hash ──────────────────────────────────────────────────

describe('AOIE hash', () => {
  it('identical snapshots return the same hash', () => {
    const s = makeSnapshot()
    expect(hashSnapshot(s)).toBe(hashSnapshot(s))
  })

  it('snapshots with different state_hash are not identical', () => {
    const a = makeSnapshot({ state_hash: mockHash('A') })
    const b = makeSnapshot({ state_hash: mockHash('B') })
    expect(snapshotsAreIdentical(a, b)).toBe(false)
  })

  it('computeIdentityDrift is 0 for single snapshot', () => {
    expect(computeIdentityDrift([makeSnapshot()])).toBe(0)
  })

  it('computeIdentityDrift is 1 when all adjacent snapshots differ', () => {
    const a = makeSnapshot({ snapshot_id: 's1', state_hash: mockHash('A') })
    const b = makeSnapshot({ snapshot_id: 's2', state_hash: mockHash('B') })
    const c = makeSnapshot({ snapshot_id: 's3', state_hash: mockHash('C') })
    expect(computeIdentityDrift([a, b, c])).toBe(1)
  })
})

// ─── Arbitration ───────────────────────────────────────────

describe('classifyArbitration', () => {
  it('RESOLVED for empty inputs', () => {
    expect(classifyArbitration([], [])).toBe('RESOLVED')
  })

  it('RESOLVED for valid non-conflicting mutations and verified assertions', () => {
    expect(classifyArbitration([makeMutation()], [makeAssertion()])).toBe('RESOLVED')
  })

  it('CONTESTED when assertion has zero evidence_hash', () => {
    const unverified = makeAssertion({ evidence_hash: ZERO_HASH })
    expect(classifyArbitration([], [unverified])).toBe('CONTESTED')
  })

  it('DEADLOCKED when two mutations target same policy_type at different sequences', () => {
    const m1 = makeMutation({ mutation_id: 'm1', sequence: 1, policy_type: 'capability' })
    const m2 = makeMutation({ mutation_id: 'm2', sequence: 2, policy_type: 'capability' })
    expect(classifyArbitration([m1, m2], [])).toBe('DEADLOCKED')
  })
})

// ─── Identity Continuity ───────────────────────────────────

describe('classifyIdentityContinuity', () => {
  it('CONTINUOUS for empty or single snapshot', () => {
    expect(classifyIdentityContinuity([])).toBe('CONTINUOUS')
    expect(classifyIdentityContinuity([makeSnapshot()])).toBe('CONTINUOUS')
  })

  it('CONTINUOUS when all snapshots have the same hash', () => {
    const s = makeSnapshot({ state_hash: mockHash('same') })
    expect(classifyIdentityContinuity([s, s, s])).toBe('CONTINUOUS')
  })

  it('BROKEN when drift > 0.3 (all snapshots different)', () => {
    const snapshots = [
      makeSnapshot({ snapshot_id: 's1', state_hash: mockHash('A') }),
      makeSnapshot({ snapshot_id: 's2', state_hash: mockHash('B') }),
      makeSnapshot({ snapshot_id: 's3', state_hash: mockHash('C') }),
      makeSnapshot({ snapshot_id: 's4', state_hash: mockHash('D') }),
      makeSnapshot({ snapshot_id: 's5', state_hash: mockHash('E') }),
    ]
    expect(classifyIdentityContinuity(snapshots)).toBe('BROKEN')
  })
})

// ─── Constitutional Drift ──────────────────────────────────

describe('classifyConstitutionalDrift', () => {
  it('STABLE with no mutations', () => {
    expect(classifyConstitutionalDrift([makeSnapshot()], [])).toBe('STABLE')
  })

  it('STABLE with mutation rate <= 0.1 per snapshot', () => {
    // 1 mutation / 100 snapshots = 0.01 < 0.1
    const snapshots = Array.from({ length: 100 }, (_, i) =>
      makeSnapshot({ snapshot_id: `s${i}`, sequence: i })
    )
    expect(classifyConstitutionalDrift(snapshots, [makeMutation()])).toBe('STABLE')
  })

  it('DIVERGED when mutation rate > 0.5', () => {
    // 10 mutations / 1 snapshot = 10 > 0.5
    const mutations = Array.from({ length: 10 }, (_, i) =>
      makeMutation({ mutation_id: `m${i}`, sequence: i, policy_type: `policy-${i}` })
    )
    expect(classifyConstitutionalDrift([makeSnapshot()], mutations)).toBe('DIVERGED')
  })
})

// ─── Global State Lattice ──────────────────────────────────

describe('AOIE lattice', () => {
  it('AOIE_SEVERITY_ORDER has 3 states in correct order', () => {
    expect(AOIE_SEVERITY_ORDER).toEqual(['SECURE', 'ALERT', 'COMPROMISED'])
  })

  it('SECURE when all signals clean', () => {
    expect(classifyGlobalState('RESOLVED', 'CONTINUOUS', 'STABLE')).toBe('SECURE')
  })

  it('ALERT when any signal is intermediate', () => {
    expect(classifyGlobalState('CONTESTED', 'CONTINUOUS', 'STABLE')).toBe('ALERT')
    expect(classifyGlobalState('RESOLVED', 'DRIFTED', 'STABLE')).toBe('ALERT')
    expect(classifyGlobalState('RESOLVED', 'CONTINUOUS', 'DRIFTING')).toBe('ALERT')
  })

  it('COMPROMISED when any signal is broken', () => {
    expect(classifyGlobalState('DEADLOCKED', 'CONTINUOUS', 'STABLE')).toBe('COMPROMISED')
    expect(classifyGlobalState('RESOLVED', 'BROKEN', 'STABLE')).toBe('COMPROMISED')
    expect(classifyGlobalState('RESOLVED', 'CONTINUOUS', 'DIVERGED')).toBe('COMPROMISED')
  })

  it('compareGlobalStates returns correct ordering', () => {
    expect(compareGlobalStates('SECURE', 'COMPROMISED')).toBe(-1)
    expect(compareGlobalStates('COMPROMISED', 'SECURE')).toBe(1)
    expect(compareGlobalStates('ALERT', 'ALERT')).toBe(0)
  })
})

// ─── Freeze ────────────────────────────────────────────────

describe('AOIE freeze', () => {
  it('freezeClassification returns frozen object', () => {
    const c = freezeClassification({
      global_state: 'SECURE',
      arbitration: 'RESOLVED',
      identity_continuity: 'CONTINUOUS',
      constitutional_drift: 'STABLE',
      classified_at_sequence: 1,
      is_replay_reconstructable: true,
      schema_version: AOIE_SCHEMA_VERSION,
    })
    expect(Object.isFrozen(c)).toBe(true)
  })

  it('freezeSnapshot returns frozen object', () => {
    const s = freezeSnapshot(makeSnapshot())
    expect(Object.isFrozen(s)).toBe(true)
  })
})

// ─── classifyRuntime ───────────────────────────────────────

describe('classifyRuntime', () => {
  it('returns SECURE for clean inputs', () => {
    const result = classifyRuntime(BASE_PARAMS)
    expect(result.global_state).toBe('SECURE')
    expect(result.is_replay_reconstructable).toBe(true)
    expect(result.schema_version).toBe(AOIE_SCHEMA_VERSION)
  })

  it('output is frozen', () => {
    expect(Object.isFrozen(classifyRuntime(BASE_PARAMS))).toBe(true)
  })

  it('phase guard rejects non-post_enforcement snapshot', () => {
    const badSnapshot = makeSnapshot({ phase: 'pre_commit' as const })
    expect(() => classifyRuntime({ ...BASE_PARAMS, snapshots: [badSnapshot] }))
      .toThrowError(SITRConstraintError)
  })

  it('deterministic: 3 runs same args → byte-identical output', () => {
    const r1 = JSON.stringify(classifyRuntime(BASE_PARAMS))
    const r2 = JSON.stringify(classifyRuntime(BASE_PARAMS))
    const r3 = JSON.stringify(classifyRuntime(BASE_PARAMS))
    expect(r1).toBe(r2)
    expect(r2).toBe(r3)
  })

  it('ALERT when unverified assertion present', () => {
    const result = classifyRuntime({
      ...BASE_PARAMS,
      assertions: [makeAssertion({ evidence_hash: ZERO_HASH })],
    })
    expect(result.global_state).toBe('ALERT')
    expect(result.arbitration).toBe('CONTESTED')
  })

  it('COMPROMISED when identity broken', () => {
    const divergentSnapshots = [
      makeSnapshot({ snapshot_id: 's1', state_hash: mockHash('A') }),
      makeSnapshot({ snapshot_id: 's2', state_hash: mockHash('B') }),
      makeSnapshot({ snapshot_id: 's3', state_hash: mockHash('C') }),
      makeSnapshot({ snapshot_id: 's4', state_hash: mockHash('D') }),
      makeSnapshot({ snapshot_id: 's5', state_hash: mockHash('E') }),
    ]
    const result = classifyRuntime({ ...BASE_PARAMS, snapshots: divergentSnapshots })
    expect(result.global_state).toBe('COMPROMISED')
    expect(result.identity_continuity).toBe('BROKEN')
  })
})
