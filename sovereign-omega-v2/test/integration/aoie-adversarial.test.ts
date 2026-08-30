// ============================================================
// Gate 52 — AOIE Classification Adversarial
// ~22 tests: identity-continuity DRIFTED boundary (not covered
//   by unit tests), constitutional-drift DRIFTING boundary,
//   full GlobalState composition grid, concurrent determinism,
//   lattice function correctness for all 3 ordered pairs.
//
// Gaps filled vs test/unit/aoie.test.ts:
//   - classifyIdentityContinuity DRIFTED state (drift ∈ (0, 0.3])
//     requires ≥5 snapshots with exactly 1 different adjacent pair
//   - classifyConstitutionalDrift DRIFTING boundary (rate ∈ (0.1, 0.5])
//   - classifyConstitutionalDrift exact-boundary (rate=0.1 → STABLE)
//   - All 7 ALERT/COMPROMISED branches of classifyGlobalState
//   - 10 concurrent classifyRuntime calls → byte-identical results
//   - globalStateOrdinal and compareGlobalStates for all 3 pairs
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  classifyGlobalState, globalStateOrdinal, compareGlobalStates,
  AOIE_SEVERITY_ORDER,
} from '../../src/aoie/lattice.js'
import { classifyIdentityContinuity } from '../../src/aoie/identity.js'
import { classifyConstitutionalDrift } from '../../src/aoie/drift.js'
import { classifyRuntime } from '../../src/aoie/runtime.js'
import { EpistemicTier } from '../../src/core/types.js'
import type { RuntimeSnapshot, PolicyMutation, EpistemicAssertion, GlobalState } from '../../src/aoie/types.js'
import { AOIE_SCHEMA_VERSION } from '../../src/aoie/types.js'
import type { SHA256Hex } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }

const PANEL = Object.freeze([1, 1, 1, 1, 1, 1, 1, 1, 1, 1])

function snap(n: number, stateHash: SHA256Hex = h('a')): RuntimeSnapshot {
  return Object.freeze({
    snapshot_id: `snap-${n}`,
    sequence: n,
    schema_version: AOIE_SCHEMA_VERSION,
    phase: 'post_enforcement' as const,
    state_hash: stateHash,
    panel_sequence_numbers: PANEL,
  })
}

function mutation(n: number, policyType = 'POLICY_A'): PolicyMutation {
  return Object.freeze({
    mutation_id: `mut-${n}`,
    sequence: n,
    policy_type: policyType,
    prior_hash: h('p'),
    next_hash: h('q'),
  })
}

function assertion(n: number, verified = true): EpistemicAssertion {
  return Object.freeze({
    assertion_id: `asr-${n}`,
    sequence: n,
    subject_id: `subject-${n}`,
    claimed_tier: EpistemicTier.T0,
    evidence_hash: verified ? h('e') : '00000000'.padEnd(64, '0') as SHA256Hex,
  })
}

// ─── Identity continuity boundaries ───────────────────────

describe('AOIE: identityContinuity boundary states', () => {
  it('CONTINUOUS: 0 snapshots', () => {
    expect(classifyIdentityContinuity([])).toBe('CONTINUOUS')
  })

  it('CONTINUOUS: 1 snapshot', () => {
    expect(classifyIdentityContinuity([snap(1)])).toBe('CONTINUOUS')
  })

  // snapshotsAreIdentical uses canonicalizeSnapshot which hashes ALL fields
  // (snapshot_id, sequence, state_hash, etc.) — "identical" means same object / same canonical form.
  // To get CONTINUOUS: repeat the same snapshot object.
  it('CONTINUOUS: 5 references to the same snapshot object (drift=0)', () => {
    const s = snap(1, h('a'))
    expect(classifyIdentityContinuity([s, s, s, s, s])).toBe('CONTINUOUS')
  })

  // DRIFTED: drift ∈ (0, 0.3]. Use repeated refs so most pairs are identical,
  // one transition uses a different snapshot → drift = 1/4 = 0.25 → DRIFTED.
  it('DRIFTED: 5 snapshots, 1 of 4 adjacent pairs different (drift=0.25)', () => {
    const sA = snap(1, h('a'))
    const sB = snap(2, h('b'))
    // pairs: (A,A)=same, (A,A)=same, (A,B)=diff, (B,B)=same → drifted=1, drift=0.25
    expect(classifyIdentityContinuity([sA, sA, sA, sB, sB])).toBe('DRIFTED')
  })

  // drift = 2/9 ≈ 0.22 ∈ (0, 0.3] → DRIFTED
  it('DRIFTED: 10 snapshots, 2 of 9 adjacent pairs different (drift≈0.22)', () => {
    const sA = snap(1, h('a'))
    const sB = snap(2, h('b'))
    const sC = snap(3, h('c'))
    // [A,A,A,A,B,B,B,C,C,C]: transitions at index 3→4 and 6→7 → drifted=2, drift=2/9≈0.22
    expect(classifyIdentityContinuity([sA, sA, sA, sA, sB, sB, sB, sC, sC, sC])).toBe('DRIFTED')
  })

  // 2 snapshots, different state_hash → drift = 1.0 > 0.3 → BROKEN
  it('BROKEN: 2 snapshots with different state_hash (drift=1.0)', () => {
    expect(classifyIdentityContinuity([snap(1, h('a')), snap(2, h('b'))])).toBe('BROKEN')
  })
})

// ─── Constitutional drift boundaries ──────────────────────

describe('AOIE: constitutionalDrift boundary states', () => {
  it('STABLE: 0 mutations', () => {
    expect(classifyConstitutionalDrift([snap(1)], [])).toBe('STABLE')
  })

  // rate = 1/10 = 0.1, threshold is > 0.1, so 0.1 is NOT drifting
  it('STABLE: 1 mutation / 10 snapshots (rate=0.1, not > threshold)', () => {
    const snaps = Array.from({ length: 10 }, (_, i) => snap(i + 1))
    expect(classifyConstitutionalDrift(snaps, [mutation(1)])).toBe('STABLE')
  })

  // rate = 2/10 = 0.2 > 0.1 → DRIFTING
  it('DRIFTING: 2 mutations / 10 snapshots (rate=0.2)', () => {
    const snaps = Array.from({ length: 10 }, (_, i) => snap(i + 1))
    expect(classifyConstitutionalDrift(snaps, [mutation(1), mutation(2, 'POLICY_B')])).toBe('DRIFTING')
  })

  // rate = 5/10 = 0.5, threshold is > 0.5, so 0.5 is NOT diverged
  it('DRIFTING: 5 mutations / 10 snapshots (rate=0.5, not > diverged threshold)', () => {
    const snaps = Array.from({ length: 10 }, (_, i) => snap(i + 1))
    const muts = Array.from({ length: 5 }, (_, i) => mutation(i + 1, `POLICY_${i}`))
    expect(classifyConstitutionalDrift(snaps, muts)).toBe('DRIFTING')
  })

  // rate = 6/10 = 0.6 > 0.5 → DIVERGED
  it('DIVERGED: 6 mutations / 10 snapshots (rate=0.6)', () => {
    const snaps = Array.from({ length: 10 }, (_, i) => snap(i + 1))
    const muts = Array.from({ length: 6 }, (_, i) => mutation(i + 1, `POLICY_${i}`))
    expect(classifyConstitutionalDrift(snaps, muts)).toBe('DIVERGED')
  })

  // 1 snapshot, 1 mutation → rate = 1.0 → DIVERGED
  it('DIVERGED: 1 mutation / 1 snapshot (rate=1.0)', () => {
    expect(classifyConstitutionalDrift([snap(1)], [mutation(1)])).toBe('DIVERGED')
  })
})

// ─── GlobalState composition grid ─────────────────────────

describe('AOIE: classifyGlobalState full composition coverage', () => {
  it('SECURE: all three signals resolved/continuous/stable', () => {
    expect(classifyGlobalState('RESOLVED', 'CONTINUOUS', 'STABLE')).toBe('SECURE')
  })

  it('ALERT: CONTESTED arbitration (others clean)', () => {
    expect(classifyGlobalState('CONTESTED', 'CONTINUOUS', 'STABLE')).toBe('ALERT')
  })

  it('ALERT: DRIFTED identity (others clean)', () => {
    expect(classifyGlobalState('RESOLVED', 'DRIFTED', 'STABLE')).toBe('ALERT')
  })

  it('ALERT: DRIFTING drift (others clean)', () => {
    expect(classifyGlobalState('RESOLVED', 'CONTINUOUS', 'DRIFTING')).toBe('ALERT')
  })

  it('COMPROMISED: DEADLOCKED arbitration (takes priority over ALERT signals)', () => {
    expect(classifyGlobalState('DEADLOCKED', 'CONTINUOUS', 'STABLE')).toBe('COMPROMISED')
  })

  it('COMPROMISED: BROKEN identity', () => {
    expect(classifyGlobalState('RESOLVED', 'BROKEN', 'STABLE')).toBe('COMPROMISED')
  })

  it('COMPROMISED: DIVERGED drift', () => {
    expect(classifyGlobalState('RESOLVED', 'CONTINUOUS', 'DIVERGED')).toBe('COMPROMISED')
  })

  it('COMPROMISED beats ALERT: DEADLOCKED + DRIFTED → COMPROMISED', () => {
    expect(classifyGlobalState('DEADLOCKED', 'DRIFTED', 'STABLE')).toBe('COMPROMISED')
  })
})

// ─── Lattice and concurrent determinism ───────────────────

describe('AOIE: lattice correctness and concurrent determinism', () => {
  it('AOIE_SEVERITY_ORDER: [SECURE, ALERT, COMPROMISED]', () => {
    expect([...AOIE_SEVERITY_ORDER]).toEqual(['SECURE', 'ALERT', 'COMPROMISED'])
  })

  it('globalStateOrdinal: SECURE=0, ALERT=1, COMPROMISED=2', () => {
    const all: GlobalState[] = ['SECURE', 'ALERT', 'COMPROMISED']
    expect(all.map(globalStateOrdinal)).toEqual([0, 1, 2])
  })

  it('compareGlobalStates: strict antisymmetry for all 3 ordered pairs', () => {
    const all: GlobalState[] = ['SECURE', 'ALERT', 'COMPROMISED']
    for (let i = 0; i < all.length; i++) {
      for (let j = i + 1; j < all.length; j++) {
        expect(compareGlobalStates(all[i]!, all[j]!)).toBe(-1)
        expect(compareGlobalStates(all[j]!, all[i]!)).toBe(1)
      }
    }
  })

  it('10 concurrent classifyRuntime calls on identical input → identical global_state', async () => {
    const snaps = [snap(1)]
    const input = { snapshots: snaps, mutations: [], assertions: [], sequence: 1 }
    const results = await Promise.all(Array.from({ length: 10 }, () => classifyRuntime(input)))
    for (const r of results) expect(r.global_state).toBe(results[0]!.global_state)
  })

  it('classifyRuntime: ALERT from CONTESTED assertion feeds into global_state', () => {
    const result = classifyRuntime({
      snapshots: [snap(1)],
      mutations: [],
      assertions: [assertion(1, false)],  // unverified → CONTESTED
      sequence: 1,
    })
    expect(result.global_state).toBe('ALERT')
    expect(result.arbitration).toBe('CONTESTED')
  })
})
