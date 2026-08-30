// ============================================================
// Gate 59 — Self-Attestation Tamper Matrix
// ~22 tests: verifySelfAttestation adversarial — independently
//   tamper each of the 5 fields (dfa_certificate_hash,
//   topology_hash, lineage_terminal_hash, capsule_attestation_hash,
//   sequence) → verify returns false; tamper attestation_hash
//   directly → false; valid record × 10 → all true.
//   Null serialization contract: null lineage → 'genesis' in
//   hash, null capsule → 'none' in hash — different attestation_hash
//   than non-null values.
//
// Gaps filled vs test/unit/attestation.test.ts:
//   - Full 5-field tamper matrix (each field independently)
//   - Direct attestation_hash tamper → false
//   - 10× consecutive verify of valid record → always true
//   - Null→'genesis' vs non-null contract (hash difference)
//   - Null→'none' vs non-null capsule contract
//   - Cross-build: same input × 3 invocations → same result
//   - sequence as string in hash (sequence=1 ≠ sequence=2)
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  buildSelfAttestation, verifySelfAttestation,
  ATTESTATION_SCHEMA_VERSION,
  type AttestationInput, type SelfAttestationRecord,
} from '../../src/frame/attestation.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const BASE: AttestationInput = Object.freeze({
  dfa_certificate_hash: h('a'),
  topology_hash: h('b'),
  lineage_terminal_hash: h('c'),
  capsule_attestation_hash: h('d'),
  sequence: seq(1),
})

// ─── Tamper matrix ────────────────────────────────────────

describe('SelfAttestation: per-field tamper matrix', () => {
  it('tamper dfa_certificate_hash → verifySelfAttestation returns false', async () => {
    const record = await buildSelfAttestation(BASE)
    const tampered: SelfAttestationRecord = { ...record, dfa_certificate_hash: h('x') }
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })

  it('tamper topology_hash → returns false', async () => {
    const record = await buildSelfAttestation(BASE)
    const tampered: SelfAttestationRecord = { ...record, topology_hash: h('x') }
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })

  it('tamper lineage_terminal_hash (non-null → different hash) → returns false', async () => {
    const record = await buildSelfAttestation(BASE)
    const tampered: SelfAttestationRecord = { ...record, lineage_terminal_hash: h('x') }
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })

  it('tamper capsule_attestation_hash → returns false', async () => {
    const record = await buildSelfAttestation(BASE)
    const tampered: SelfAttestationRecord = { ...record, capsule_attestation_hash: h('x') }
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })

  it('tamper sequence → returns false', async () => {
    const record = await buildSelfAttestation(BASE)
    const tampered: SelfAttestationRecord = { ...record, sequence: seq(99) }
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })

  it('tamper attestation_hash directly → returns false', async () => {
    const record = await buildSelfAttestation(BASE)
    const tampered: SelfAttestationRecord = { ...record, attestation_hash: h('z') }
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })
})

// ─── Positive cases ───────────────────────────────────────

describe('SelfAttestation: positive verification cases', () => {
  it('valid record: verifySelfAttestation returns true', async () => {
    const record = await buildSelfAttestation(BASE)
    expect(await verifySelfAttestation(record)).toBe(true)
  })

  it('10 consecutive verify calls on valid record → all true', async () => {
    const record = await buildSelfAttestation(BASE)
    const results = await Promise.all(
      Array.from({ length: 10 }, () => verifySelfAttestation(record)),
    )
    for (const r of results) expect(r).toBe(true)
  })

  it('null lineage_terminal_hash: valid record verifies true', async () => {
    const input: AttestationInput = { ...BASE, lineage_terminal_hash: null }
    const record = await buildSelfAttestation(input)
    expect(await verifySelfAttestation(record)).toBe(true)
  })

  it('null capsule_attestation_hash: valid record verifies true', async () => {
    const input: AttestationInput = { ...BASE, capsule_attestation_hash: null }
    const record = await buildSelfAttestation(input)
    expect(await verifySelfAttestation(record)).toBe(true)
  })

  it('both null: valid record verifies true', async () => {
    const input: AttestationInput = { ...BASE, lineage_terminal_hash: null, capsule_attestation_hash: null }
    const record = await buildSelfAttestation(input)
    expect(await verifySelfAttestation(record)).toBe(true)
  })
})

// ─── Null serialization contract ──────────────────────────

describe('SelfAttestation: null serialization contract', () => {
  it('null lineage → different attestation_hash than h("c") lineage', async () => {
    const withNull = await buildSelfAttestation({ ...BASE, lineage_terminal_hash: null })
    const withHash = await buildSelfAttestation({ ...BASE, lineage_terminal_hash: h('c') })
    expect(withNull.attestation_hash).not.toBe(withHash.attestation_hash)
  })

  it('null capsule → different attestation_hash than h("d") capsule', async () => {
    const withNull = await buildSelfAttestation({ ...BASE, capsule_attestation_hash: null })
    const withHash = await buildSelfAttestation({ ...BASE, capsule_attestation_hash: h('d') })
    expect(withNull.attestation_hash).not.toBe(withHash.attestation_hash)
  })

  it('tamper null lineage to non-null in record → verifySelfAttestation returns false', async () => {
    const record = await buildSelfAttestation({ ...BASE, lineage_terminal_hash: null })
    // Manually inject a non-null value into the record (simulating corruption)
    const tampered: SelfAttestationRecord = { ...record, lineage_terminal_hash: h('x') }
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })

  it('tamper non-null lineage to null in record → returns false', async () => {
    const record = await buildSelfAttestation(BASE)
    const tampered: SelfAttestationRecord = { ...record, lineage_terminal_hash: null }
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })
})

// ─── Determinism ──────────────────────────────────────────

describe('SelfAttestation: determinism', () => {
  it('same input × 3 → identical attestation_hash', async () => {
    const [r1, r2, r3] = await Promise.all([
      buildSelfAttestation(BASE),
      buildSelfAttestation(BASE),
      buildSelfAttestation(BASE),
    ])
    expect(r1!.attestation_hash).toBe(r2!.attestation_hash)
    expect(r2!.attestation_hash).toBe(r3!.attestation_hash)
  })

  it('different sequence → different attestation_hash', async () => {
    const r1 = await buildSelfAttestation({ ...BASE, sequence: seq(1) })
    const r2 = await buildSelfAttestation({ ...BASE, sequence: seq(2) })
    expect(r1.attestation_hash).not.toBe(r2.attestation_hash)
  })

  it('schema_version is 1.0.0', async () => {
    const record = await buildSelfAttestation(BASE)
    expect(record.schema_version).toBe(ATTESTATION_SCHEMA_VERSION)
    expect(ATTESTATION_SCHEMA_VERSION).toBe('1.0.0')
  })
})
