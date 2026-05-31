// ============================================================
// SOVEREIGN OMEGA — AOIE Canonicalization tests
// EPISTEMIC TIER: T1
//
// Tests for aoie/canonicalize.ts:
//   canonicalizeSnapshot       — deterministic Uint8Array from RuntimeSnapshot
//   canonicalizePolicyMutation — deterministic Uint8Array from PolicyMutation
//   canonicalizeAssertion      — deterministic Uint8Array from EpistemicAssertion
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  canonicalizeSnapshot,
  canonicalizePolicyMutation,
  canonicalizeAssertion,
} from '../../src/aoie/canonicalize.js'
import { EpistemicTier } from '../../src/core/types.js'
import type { SHA256Hex } from '../../src/core/types.js'
import type {
  RuntimeSnapshot,
  PolicyMutation,
  EpistemicAssertion,
} from '../../src/aoie/types.js'
import { AOIE_SCHEMA_VERSION } from '../../src/aoie/types.js'

const H = '0'.repeat(64) as SHA256Hex
const H2 = 'a'.repeat(64) as SHA256Hex

const SNAPSHOT: RuntimeSnapshot = {
  snapshot_id: 'snap-01',
  sequence: 42,
  schema_version: AOIE_SCHEMA_VERSION,
  phase: 'post_enforcement',
  state_hash: H,
  panel_sequence_numbers: [1, 2, 3],
}

const MUTATION: PolicyMutation = {
  mutation_id: 'mut-01',
  sequence: 10,
  policy_type: 'GATE_THRESHOLD',
  prior_hash: H,
  next_hash: H2,
}

const ASSERTION: EpistemicAssertion = {
  assertion_id: 'assert-01',
  sequence: 5,
  subject_id: 'canonicalize.ts',
  claimed_tier: EpistemicTier.T0,
  evidence_hash: H,
}

// ── canonicalizeSnapshot ──────────────────────────────────

describe('canonicalizeSnapshot', () => {
  it('returns a non-empty byte buffer', () => {
    const result = canonicalizeSnapshot(SNAPSHOT)
    expect(result.length).toBeGreaterThan(0)
    expect(result.BYTES_PER_ELEMENT).toBe(1)
  })

  it('is deterministic — three identical calls produce equal output', () => {
    const r1 = canonicalizeSnapshot(SNAPSHOT)
    const r2 = canonicalizeSnapshot(SNAPSHOT)
    const r3 = canonicalizeSnapshot(SNAPSHOT)
    expect(Buffer.from(r1).toString('hex')).toBe(Buffer.from(r2).toString('hex'))
    expect(Buffer.from(r2).toString('hex')).toBe(Buffer.from(r3).toString('hex'))
  })

  it('produces different output for different sequence numbers', () => {
    const r1 = canonicalizeSnapshot(SNAPSHOT)
    const r2 = canonicalizeSnapshot({ ...SNAPSHOT, sequence: 99 })
    expect(Buffer.from(r1).toString('hex')).not.toBe(Buffer.from(r2).toString('hex'))
  })
})

// ── canonicalizePolicyMutation ────────────────────────────

describe('canonicalizePolicyMutation', () => {
  it('returns a non-empty byte buffer', () => {
    const result = canonicalizePolicyMutation(MUTATION)
    expect(result.length).toBeGreaterThan(0)
    expect(result.BYTES_PER_ELEMENT).toBe(1)
  })

  it('is deterministic — three identical calls produce equal output', () => {
    const r1 = canonicalizePolicyMutation(MUTATION)
    const r2 = canonicalizePolicyMutation(MUTATION)
    const r3 = canonicalizePolicyMutation(MUTATION)
    expect(Buffer.from(r1).toString('hex')).toBe(Buffer.from(r2).toString('hex'))
    expect(Buffer.from(r2).toString('hex')).toBe(Buffer.from(r3).toString('hex'))
  })

  it('produces different output when prior_hash changes', () => {
    const r1 = canonicalizePolicyMutation(MUTATION)
    const r2 = canonicalizePolicyMutation({ ...MUTATION, prior_hash: H2 })
    expect(Buffer.from(r1).toString('hex')).not.toBe(Buffer.from(r2).toString('hex'))
  })
})

// ── canonicalizeAssertion ─────────────────────────────────

describe('canonicalizeAssertion', () => {
  it('returns a non-empty byte buffer', () => {
    const result = canonicalizeAssertion(ASSERTION)
    expect(result.length).toBeGreaterThan(0)
    expect(result.BYTES_PER_ELEMENT).toBe(1)
  })

  it('is deterministic — three identical calls produce equal output', () => {
    const r1 = canonicalizeAssertion(ASSERTION)
    const r2 = canonicalizeAssertion(ASSERTION)
    const r3 = canonicalizeAssertion(ASSERTION)
    expect(Buffer.from(r1).toString('hex')).toBe(Buffer.from(r2).toString('hex'))
    expect(Buffer.from(r2).toString('hex')).toBe(Buffer.from(r3).toString('hex'))
  })

  it('produces different output when claimed_tier changes', () => {
    const r1 = canonicalizeAssertion(ASSERTION)
    const r2 = canonicalizeAssertion({ ...ASSERTION, claimed_tier: EpistemicTier.T2 })
    expect(Buffer.from(r1).toString('hex')).not.toBe(Buffer.from(r2).toString('hex'))
  })
})
