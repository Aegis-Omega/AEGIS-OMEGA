// ============================================================
// Gate 32 — Constitutional Capsule VM Tests
// ~30 tests: manifest, capability grammar, entropy enforcement,
//   outcomes (COMMITTED/REJECTED/ROLLED_BACK), attestation
//   hash chaining, determinism.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import {
  buildManifest,
  capabilityGranted,
  runCapsule,
  type ManifestInput,
} from '../../src/capsule/kernel.js'
import { CapsuleError } from '../../src/capsule/types.js'

// ─── Helpers ───────────────────────────────────────────────

const SEQ = 1n as SequenceNumber
const PARENT = ('a'.repeat(64)) as SHA256Hex

const READ_CAP: ManifestInput = {
  capabilities: [{ type: 'READ_STATE', target: 'ledger', is_read_only: true }],
  entropy_budget: 512,
}

const EMIT_CAP: ManifestInput = {
  capabilities: [{ type: 'EMIT_EVENT', target: 'e5', is_read_only: false }],
  entropy_budget: 1024,
}

// ─── buildManifest ─────────────────────────────────────────

describe('buildManifest', () => {
  it('produces frozen manifest with is_rollback_safe: true', async () => {
    const m = await buildManifest(READ_CAP)
    expect(Object.isFrozen(m)).toBe(true)
    expect(m.is_rollback_safe).toBe(true)
    expect(m.is_replay_reconstructable).toBe(true)
  })

  it('capsule_id is 64-char hex', async () => {
    const m = await buildManifest(READ_CAP)
    expect(m.capsule_id).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(m.capsule_id)).toBe(true)
  })

  it('capsule_id is content-addressed — deterministic × 3', async () => {
    const id1 = (await buildManifest(READ_CAP)).capsule_id
    const id2 = (await buildManifest(READ_CAP)).capsule_id
    const id3 = (await buildManifest(READ_CAP)).capsule_id
    expect(id1).toBe(id2)
    expect(id2).toBe(id3)
  })

  it('different capabilities → different capsule_id', async () => {
    const m1 = await buildManifest(READ_CAP)
    const m2 = await buildManifest(EMIT_CAP)
    expect(m1.capsule_id).not.toBe(m2.capsule_id)
  })

  it('different entropy_budget → different capsule_id', async () => {
    const m1 = await buildManifest({ ...READ_CAP, entropy_budget: 100 })
    const m2 = await buildManifest({ ...READ_CAP, entropy_budget: 200 })
    expect(m1.capsule_id).not.toBe(m2.capsule_id)
  })

  it('throws CapsuleError on negative entropy_budget', async () => {
    await expect(buildManifest({ ...READ_CAP, entropy_budget: -1 }))
      .rejects.toThrow(CapsuleError)
  })

  it('entropy_budget of 0 is valid (read-only capsule)', async () => {
    const m = await buildManifest({ capabilities: [], entropy_budget: 0 })
    expect(m.entropy_budget).toBe(0)
  })
})

// ─── capabilityGranted ─────────────────────────────────────

describe('capabilityGranted', () => {
  it('returns true for declared capability + target', async () => {
    const m = await buildManifest(READ_CAP)
    expect(capabilityGranted(m, 'READ_STATE', 'ledger')).toBe(true)
  })

  it('returns false for undeclared capability type', async () => {
    const m = await buildManifest(READ_CAP)
    expect(capabilityGranted(m, 'EMIT_EVENT', 'ledger')).toBe(false)
  })

  it('returns false for wrong target', async () => {
    const m = await buildManifest(READ_CAP)
    expect(capabilityGranted(m, 'READ_STATE', 'topology')).toBe(false)
  })

  it('empty capabilities grants nothing', async () => {
    const m = await buildManifest({ capabilities: [], entropy_budget: 100 })
    expect(capabilityGranted(m, 'READ_STATE', 'ledger')).toBe(false)
  })
})

// ─── runCapsule — COMMITTED ────────────────────────────────

describe('runCapsule — COMMITTED', () => {
  it('granted capability + within budget → COMMITTED', async () => {
    const m = await buildManifest(READ_CAP)
    const result = await runCapsule({
      manifest: m, capability_type: 'READ_STATE', target: 'ledger',
      payload: { query: 'latest' }, sequence: SEQ, parent_lineage_hash: PARENT,
    })
    expect(result.outcome).toBe('COMMITTED')
    expect(result.capsule_id).toBe(m.capsule_id)
    expect(result.is_replay_reconstructable).toBe(true)
  })

  it('result is frozen', async () => {
    const m = await buildManifest(READ_CAP)
    const result = await runCapsule({
      manifest: m, capability_type: 'READ_STATE', target: 'ledger',
      payload: {}, sequence: SEQ, parent_lineage_hash: null,
    })
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('event_hash and attestation_hash are 64-char hex', async () => {
    const m = await buildManifest(READ_CAP)
    const result = await runCapsule({
      manifest: m, capability_type: 'READ_STATE', target: 'ledger',
      payload: { x: 1 }, sequence: SEQ, parent_lineage_hash: PARENT,
    })
    expect(result.event_hash).toHaveLength(64)
    expect(result.attestation_hash).toHaveLength(64)
  })

  it('deterministic — same inputs → same hashes × 3', async () => {
    const m = await buildManifest(READ_CAP)
    const args = {
      manifest: m, capability_type: 'READ_STATE' as const, target: 'ledger',
      payload: { v: 42 }, sequence: SEQ, parent_lineage_hash: PARENT,
    }
    const r1 = await runCapsule(args)
    const r2 = await runCapsule(args)
    const r3 = await runCapsule(args)
    expect(r1.event_hash).toBe(r2.event_hash)
    expect(r2.event_hash).toBe(r3.event_hash)
    expect(r1.attestation_hash).toBe(r2.attestation_hash)
  })

  it('different sequence → different hashes', async () => {
    const m = await buildManifest(READ_CAP)
    const base = { manifest: m, capability_type: 'READ_STATE' as const, target: 'ledger', payload: {}, parent_lineage_hash: null }
    const r1 = await runCapsule({ ...base, sequence: 1n as SequenceNumber })
    const r2 = await runCapsule({ ...base, sequence: 2n as SequenceNumber })
    expect(r1.event_hash).not.toBe(r2.event_hash)
  })

  it('different parent_lineage_hash → different attestation_hash', async () => {
    const m = await buildManifest(READ_CAP)
    const base = { manifest: m, capability_type: 'READ_STATE' as const, target: 'ledger', payload: {}, sequence: SEQ }
    const r1 = await runCapsule({ ...base, parent_lineage_hash: PARENT })
    const r2 = await runCapsule({ ...base, parent_lineage_hash: null })
    expect(r1.attestation_hash).not.toBe(r2.attestation_hash)
  })
})

// ─── runCapsule — REJECTED ─────────────────────────────────

describe('runCapsule — REJECTED', () => {
  it('undeclared capability → REJECTED', async () => {
    const m = await buildManifest(READ_CAP)
    const result = await runCapsule({
      manifest: m, capability_type: 'EMIT_EVENT', target: 'e5',
      payload: {}, sequence: SEQ, parent_lineage_hash: null,
    })
    expect(result.outcome).toBe('REJECTED')
    expect(result.entropy_consumed).toBe(0)
    expect(result.reason).toBeDefined()
  })

  it('wrong target → REJECTED', async () => {
    const m = await buildManifest(READ_CAP)
    const result = await runCapsule({
      manifest: m, capability_type: 'READ_STATE', target: 'consensus',
      payload: {}, sequence: SEQ, parent_lineage_hash: null,
    })
    expect(result.outcome).toBe('REJECTED')
  })
})

// ─── runCapsule — ROLLED_BACK ─────────────────────────────

describe('runCapsule — ROLLED_BACK', () => {
  it('payload exceeding entropy_budget → ROLLED_BACK', async () => {
    const m = await buildManifest({ ...READ_CAP, entropy_budget: 5 })
    const result = await runCapsule({
      manifest: m, capability_type: 'READ_STATE', target: 'ledger',
      payload: { this_payload_is_far_too_large: true, extra: 'data' },
      sequence: SEQ, parent_lineage_hash: null,
    })
    expect(result.outcome).toBe('ROLLED_BACK')
    expect(result.entropy_consumed).toBeGreaterThan(5)
    expect(result.reason).toContain('exceeds budget')
  })

  it('zero entropy_budget + any payload → ROLLED_BACK', async () => {
    const m = await buildManifest({
      capabilities: [{ type: 'READ_STATE', target: 'ledger', is_read_only: true }],
      entropy_budget: 0,
    })
    const result = await runCapsule({
      manifest: m, capability_type: 'READ_STATE', target: 'ledger',
      payload: { x: 1 }, sequence: SEQ, parent_lineage_hash: null,
    })
    expect(result.outcome).toBe('ROLLED_BACK')
  })

  it('empty payload {} fits budget 2 → COMMITTED', async () => {
    const m = await buildManifest({ ...READ_CAP, entropy_budget: 2 })
    const result = await runCapsule({
      manifest: m, capability_type: 'READ_STATE', target: 'ledger',
      payload: {}, sequence: SEQ, parent_lineage_hash: null,
    })
    expect(result.outcome).toBe('COMMITTED')
  })
})
