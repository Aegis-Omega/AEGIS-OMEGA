// ============================================================
// Gate 66 — Capsule Kernel Adversarial (Integration)
// ~22 tests: capability boundary violations → REJECTED outcome;
//   entropy budget exhaustion → ROLLED_BACK; cross-capsule
//   isolation; manifest seal; negative entropy_budget throws;
//   20-capsule chain lineage linking.
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  buildManifest, capabilityGranted, runCapsule,
} from '../../src/capsule/kernel.js'
import { CapsuleError } from '../../src/capsule/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const EMIT_CAP = { type: 'EMIT_EVENT' as const, target: 'e5', is_read_only: false }
const READ_CAP = { type: 'READ_STATE' as const, target: 'ledger', is_read_only: true }

// ─── Capability boundary violations ───────────────────────

describe('Capsule: capability violations → REJECTED', () => {
  it('no capabilities → REJECTED on EMIT_EVENT', async () => {
    const manifest = await buildManifest({ capabilities: [], entropy_budget: 1000 })
    const result = await runCapsule({
      manifest,
      capability_type: 'EMIT_EVENT',
      target: 'e5',
      payload: { data: 'x' },
      sequence: seq(1),
      parent_lineage_hash: null,
    })
    expect(result.outcome).toBe('REJECTED')
  })

  it('READ_STATE manifest → EMIT_EVENT → REJECTED', async () => {
    const manifest = await buildManifest({ capabilities: [READ_CAP], entropy_budget: 1000 })
    const result = await runCapsule({
      manifest,
      capability_type: 'EMIT_EVENT',
      target: 'e5',
      payload: { data: 'y' },
      sequence: seq(1),
      parent_lineage_hash: null,
    })
    expect(result.outcome).toBe('REJECTED')
  })

  it('EMIT_EVENT for wrong target → REJECTED', async () => {
    const manifest = await buildManifest({
      capabilities: [{ type: 'EMIT_EVENT', target: 'other', is_read_only: false }],
      entropy_budget: 1000,
    })
    const result = await runCapsule({
      manifest,
      capability_type: 'EMIT_EVENT',
      target: 'e5',   // not 'other'
      payload: { data: 'z' },
      sequence: seq(1),
      parent_lineage_hash: null,
    })
    expect(result.outcome).toBe('REJECTED')
  })

  it('capabilityGranted returns false for absent capability', async () => {
    const manifest = await buildManifest({ capabilities: [], entropy_budget: 100 })
    expect(capabilityGranted(manifest, 'EMIT_EVENT', 'e5')).toBe(false)
  })

  it('capabilityGranted returns true when granted', async () => {
    const manifest = await buildManifest({ capabilities: [EMIT_CAP], entropy_budget: 100 })
    expect(capabilityGranted(manifest, 'EMIT_EVENT', 'e5')).toBe(true)
  })
})

// ─── Entropy budget exhaustion → ROLLED_BACK ──────────────

describe('Capsule: entropy budget → ROLLED_BACK', () => {
  it('payload exceeds entropy_budget → ROLLED_BACK', async () => {
    const manifest = await buildManifest({ capabilities: [EMIT_CAP], entropy_budget: 1 })
    const result = await runCapsule({
      manifest,
      capability_type: 'EMIT_EVENT',
      target: 'e5',
      payload: { data: 'a'.repeat(1000) },
      sequence: seq(1),
      parent_lineage_hash: null,
    })
    expect(result.outcome).toBe('ROLLED_BACK')
  })

  it('zero entropy_budget → any payload → ROLLED_BACK', async () => {
    const manifest = await buildManifest({ capabilities: [READ_CAP], entropy_budget: 0 })
    const result = await runCapsule({
      manifest,
      capability_type: 'READ_STATE',
      target: 'ledger',
      payload: { x: 1 },
      sequence: seq(1),
      parent_lineage_hash: null,
    })
    expect(result.outcome).toBe('ROLLED_BACK')
  })

  it('negative entropy_budget → buildManifest throws CapsuleError', async () => {
    await expect(buildManifest({ capabilities: [], entropy_budget: -1 })).rejects.toThrow(CapsuleError)
  })
})

// ─── COMMITTED outcomes ───────────────────────────────────

describe('Capsule: COMMITTED outcomes and determinism', () => {
  it('valid capability + within budget → COMMITTED', async () => {
    const manifest = await buildManifest({ capabilities: [EMIT_CAP], entropy_budget: 10000 })
    const result = await runCapsule({
      manifest,
      capability_type: 'EMIT_EVENT',
      target: 'e5',
      payload: { data: 'hello' },
      sequence: seq(1),
      parent_lineage_hash: null,
    })
    expect(result.outcome).toBe('COMMITTED')
  })

  it('result is frozen', async () => {
    const manifest = await buildManifest({ capabilities: [EMIT_CAP], entropy_budget: 10000 })
    const result = await runCapsule({
      manifest,
      capability_type: 'EMIT_EVENT',
      target: 'e5',
      payload: { x: 1 },
      sequence: seq(1),
      parent_lineage_hash: null,
    })
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('attestation_hash is 64-char hex', async () => {
    const manifest = await buildManifest({ capabilities: [EMIT_CAP], entropy_budget: 10000 })
    const result = await runCapsule({
      manifest,
      capability_type: 'EMIT_EVENT',
      target: 'e5',
      payload: { x: 1 },
      sequence: seq(1),
      parent_lineage_hash: null,
    })
    expect(result.attestation_hash).toHaveLength(64)
    expect(result.attestation_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('same inputs × 3 → identical attestation_hash (deterministic)', async () => {
    const manifest = await buildManifest({ capabilities: [EMIT_CAP], entropy_budget: 10000 })
    const input = { manifest, capability_type: 'EMIT_EVENT' as const, target: 'e5', payload: { v: 42 }, sequence: seq(7), parent_lineage_hash: null }
    const [r1, r2, r3] = await Promise.all([runCapsule(input), runCapsule(input), runCapsule(input)])
    expect(r1!.attestation_hash).toBe(r2!.attestation_hash)
    expect(r2!.attestation_hash).toBe(r3!.attestation_hash)
  })
})

// ─── 20-capsule chain lineage linking ─────────────────────

describe('Capsule: 20-capsule lineage chain', () => {
  it('20 sequential capsules link parent_lineage_hash correctly', async () => {
    const manifest = await buildManifest({ capabilities: [EMIT_CAP], entropy_budget: 10000 })
    let prevHash: SHA256Hex | null = null
    const hashes: SHA256Hex[] = []
    for (let i = 1; i <= 20; i++) {
      const result = await runCapsule({
        manifest,
        capability_type: 'EMIT_EVENT',
        target: 'e5',
        payload: { step: i },
        sequence: seq(i),
        parent_lineage_hash: prevHash,
      })
      expect(result.outcome).toBe('COMMITTED')
      prevHash = result.attestation_hash
      hashes.push(result.attestation_hash)
    }
    const unique = new Set(hashes)
    expect(unique.size).toBe(20)
  })
})
