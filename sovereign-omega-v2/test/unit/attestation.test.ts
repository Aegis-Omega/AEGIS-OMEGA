// ============================================================
// Gate 35 — Self-Attestation Protocol Tests
// ~26 tests: buildSelfAttestation, verifySelfAttestation,
//   null fields, hash determinism, tamper detection.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import {
  buildSelfAttestation,
  verifySelfAttestation,
  AttestationError,
  ATTESTATION_SCHEMA_VERSION,
  type AttestationInput,
} from '../../src/frame/attestation.js'

// ─── Helpers ───────────────────────────────────────────────

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }
function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }

const BASE: AttestationInput = {
  dfa_certificate_hash: h('a'),
  topology_hash: h('b'),
  lineage_terminal_hash: h('c'),
  capsule_attestation_hash: h('d'),
  sequence: seq(1),
}

// ─── Constants ─────────────────────────────────────────────

describe('constants', () => {
  it('ATTESTATION_SCHEMA_VERSION is 1.0.0', () => {
    expect(ATTESTATION_SCHEMA_VERSION).toBe('1.0.0')
  })
})

// ─── AttestationError ──────────────────────────────────────

describe('AttestationError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new AttestationError('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('AttestationError')
    expect(e.message).toBe('test')
  })
})

// ─── buildSelfAttestation ──────────────────────────────────

describe('buildSelfAttestation', () => {
  it('produces a frozen record', async () => {
    const r = await buildSelfAttestation(BASE)
    expect(Object.isFrozen(r)).toBe(true)
  })

  it('attestation_hash is 64-char hex', async () => {
    const r = await buildSelfAttestation(BASE)
    expect(r.attestation_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(r.attestation_hash)).toBe(true)
  })

  it('is_replay_reconstructable is true', async () => {
    const r = await buildSelfAttestation(BASE)
    expect(r.is_replay_reconstructable).toBe(true)
  })

  it('schema_version is 1.0.0', async () => {
    const r = await buildSelfAttestation(BASE)
    expect(r.schema_version).toBe('1.0.0')
  })

  it('all input fields are preserved verbatim', async () => {
    const r = await buildSelfAttestation(BASE)
    expect(r.dfa_certificate_hash).toBe(BASE.dfa_certificate_hash)
    expect(r.topology_hash).toBe(BASE.topology_hash)
    expect(r.lineage_terminal_hash).toBe(BASE.lineage_terminal_hash)
    expect(r.capsule_attestation_hash).toBe(BASE.capsule_attestation_hash)
    expect(r.sequence).toBe(BASE.sequence)
  })

  it('null lineage_terminal_hash is valid', async () => {
    const r = await buildSelfAttestation({ ...BASE, lineage_terminal_hash: null })
    expect(r.lineage_terminal_hash).toBeNull()
    expect(r.attestation_hash).toHaveLength(64)
  })

  it('null capsule_attestation_hash is valid', async () => {
    const r = await buildSelfAttestation({ ...BASE, capsule_attestation_hash: null })
    expect(r.capsule_attestation_hash).toBeNull()
    expect(r.attestation_hash).toHaveLength(64)
  })

  it('both null fields are valid', async () => {
    const r = await buildSelfAttestation({
      ...BASE,
      lineage_terminal_hash: null,
      capsule_attestation_hash: null,
    })
    expect(r.lineage_terminal_hash).toBeNull()
    expect(r.capsule_attestation_hash).toBeNull()
    expect(r.attestation_hash).toHaveLength(64)
  })

  it('attestation_hash is deterministic × 3', async () => {
    const h1 = (await buildSelfAttestation(BASE)).attestation_hash
    const h2 = (await buildSelfAttestation(BASE)).attestation_hash
    const h3 = (await buildSelfAttestation(BASE)).attestation_hash
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('different dfa_certificate_hash → different attestation_hash', async () => {
    const r1 = await buildSelfAttestation(BASE)
    const r2 = await buildSelfAttestation({ ...BASE, dfa_certificate_hash: h('e') })
    expect(r1.attestation_hash).not.toBe(r2.attestation_hash)
  })

  it('different topology_hash → different attestation_hash', async () => {
    const r1 = await buildSelfAttestation(BASE)
    const r2 = await buildSelfAttestation({ ...BASE, topology_hash: h('f') })
    expect(r1.attestation_hash).not.toBe(r2.attestation_hash)
  })

  it('null vs non-null lineage_terminal_hash → different attestation_hash', async () => {
    const r1 = await buildSelfAttestation(BASE)
    const r2 = await buildSelfAttestation({ ...BASE, lineage_terminal_hash: null })
    expect(r1.attestation_hash).not.toBe(r2.attestation_hash)
  })

  it('different sequence → different attestation_hash', async () => {
    const r1 = await buildSelfAttestation(BASE)
    const r2 = await buildSelfAttestation({ ...BASE, sequence: seq(99) })
    expect(r1.attestation_hash).not.toBe(r2.attestation_hash)
  })
})

// ─── verifySelfAttestation ─────────────────────────────────

describe('verifySelfAttestation', () => {
  it('valid record → true', async () => {
    const r = await buildSelfAttestation(BASE)
    expect(await verifySelfAttestation(r)).toBe(true)
  })

  it('tampered attestation_hash → false', async () => {
    const r = await buildSelfAttestation(BASE)
    const tampered = Object.freeze({ ...r, attestation_hash: h('0') })
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })

  it('tampered topology_hash → false', async () => {
    const r = await buildSelfAttestation(BASE)
    const tampered = Object.freeze({ ...r, topology_hash: h('z') })
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })

  it('tampered dfa_certificate_hash → false', async () => {
    const r = await buildSelfAttestation(BASE)
    const tampered = Object.freeze({ ...r, dfa_certificate_hash: h('z') })
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })

  it('is deterministic × 3', async () => {
    const r = await buildSelfAttestation(BASE)
    const v1 = await verifySelfAttestation(r)
    const v2 = await verifySelfAttestation(r)
    const v3 = await verifySelfAttestation(r)
    expect(v1).toBe(true)
    expect(v2).toBe(true)
    expect(v3).toBe(true)
  })

  it('null fields verify correctly', async () => {
    const r = await buildSelfAttestation({ ...BASE, lineage_terminal_hash: null, capsule_attestation_hash: null })
    expect(await verifySelfAttestation(r)).toBe(true)
  })
})
