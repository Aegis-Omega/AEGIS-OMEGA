// ============================================================
// Gate 70 — Self-Attestation Chain (Integration)
// ~22 tests: 20-entry SelfAttestation chain — build, verify all
//   → true; tamper middle → verify=false; deterministic ×3;
//   all-null lineage/capsule; sequential attestation_hash chain.
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  buildSelfAttestation, verifySelfAttestation,
  type AttestationInput,
} from '../../src/frame/attestation.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

function input(n: number, overrides: Partial<AttestationInput> = {}): AttestationInput {
  return {
    dfa_certificate_hash: h(String.fromCharCode(97 + (n % 26))),
    topology_hash: h(String.fromCharCode(65 + (n % 26))),
    lineage_terminal_hash: h('l'),
    capsule_attestation_hash: h('k'),
    sequence: seq(n),
    ...overrides,
  }
}

// ─── 20-entry attestation chain ───────────────────────────

describe('AttestationChain: 20-entry build and verify', () => {
  it('20 attestations → all verifySelfAttestation=true', async () => {
    const records = []
    for (let i = 1; i <= 20; i++) {
      records.push(await buildSelfAttestation(input(i)))
    }
    for (const rec of records) {
      expect(await verifySelfAttestation(rec)).toBe(true)
    }
  })

  it('20 attestations → 20 distinct attestation_hashes', async () => {
    const hashes = new Set<string>()
    for (let i = 1; i <= 20; i++) {
      const rec = await buildSelfAttestation(input(i))
      hashes.add(rec.attestation_hash)
    }
    expect(hashes.size).toBe(20)
  })

  it('tamper attestation_hash at position 10 → verifySelfAttestation=false', async () => {
    const records = []
    for (let i = 1; i <= 20; i++) {
      records.push(await buildSelfAttestation(input(i)))
    }
    const tampered = { ...records[9]!, attestation_hash: h('z') }
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })

  it('tamper topology_hash → verifySelfAttestation=false', async () => {
    const rec = await buildSelfAttestation(input(5))
    const tampered = { ...rec, topology_hash: h('z') }
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })

  it('tamper dfa_certificate_hash → verifySelfAttestation=false', async () => {
    const rec = await buildSelfAttestation(input(5))
    const tampered = { ...rec, dfa_certificate_hash: h('z') }
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })

  it('tamper sequence → verifySelfAttestation=false', async () => {
    const rec = await buildSelfAttestation(input(5))
    const tampered = { ...rec, sequence: seq(999) }
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })
})

// ─── All-null fields ──────────────────────────────────────

describe('AttestationChain: null lineage/capsule fields', () => {
  it('null lineage_terminal_hash → valid attestation', async () => {
    const rec = await buildSelfAttestation(input(1, { lineage_terminal_hash: null }))
    expect(await verifySelfAttestation(rec)).toBe(true)
  })

  it('null capsule_attestation_hash → valid attestation', async () => {
    const rec = await buildSelfAttestation(input(1, { capsule_attestation_hash: null }))
    expect(await verifySelfAttestation(rec)).toBe(true)
  })

  it('both null → valid attestation', async () => {
    const rec = await buildSelfAttestation(input(1, { lineage_terminal_hash: null, capsule_attestation_hash: null }))
    expect(await verifySelfAttestation(rec)).toBe(true)
  })

  it('null vs non-null lineage → different attestation_hash', async () => {
    const r1 = await buildSelfAttestation(input(1, { lineage_terminal_hash: null }))
    const r2 = await buildSelfAttestation(input(1, { lineage_terminal_hash: h('l') }))
    expect(r1.attestation_hash).not.toBe(r2.attestation_hash)
  })
})

// ─── Determinism ──────────────────────────────────────────

describe('AttestationChain: determinism', () => {
  it('same input × 3 → identical attestation_hash', async () => {
    const inp = input(42)
    const [r1, r2, r3] = await Promise.all([
      buildSelfAttestation(inp),
      buildSelfAttestation(inp),
      buildSelfAttestation(inp),
    ])
    expect(r1!.attestation_hash).toBe(r2!.attestation_hash)
    expect(r2!.attestation_hash).toBe(r3!.attestation_hash)
  })

  it('record is frozen', async () => {
    const rec = await buildSelfAttestation(input(1))
    expect(Object.isFrozen(rec)).toBe(true)
  })

  it('attestation_hash is 64-char hex', async () => {
    const rec = await buildSelfAttestation(input(1))
    expect(rec.attestation_hash).toHaveLength(64)
    expect(rec.attestation_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('is_replay_reconstructable=true', async () => {
    const rec = await buildSelfAttestation(input(1))
    expect(rec.is_replay_reconstructable).toBe(true)
  })
})
