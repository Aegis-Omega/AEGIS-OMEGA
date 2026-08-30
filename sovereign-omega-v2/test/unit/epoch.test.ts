// ============================================================
// Gate 39 — Epoch Synthesis Tests
// ~28 tests: synthesizeEpoch, verifyEpoch, EpochError,
//   sequence guard, topology guard, DFA cert guard,
//   epoch_hash determinism, tamper detection.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { initialMachine, transition, certifyExecution } from '../../src/frame/dfa.js'
import { buildTopology, type GovernanceTopology } from '../../src/frame/topology.js'
import type { ExecutionCertificate } from '../../src/frame/dfa.js'
import {
  synthesizeEpoch,
  verifyEpoch,
  EpochError,
  EPOCH_SCHEMA_VERSION,
  type EpochInput,
} from '../../src/frame/epoch.js'

// ─── Helpers ───────────────────────────────────────────────

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }
function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }

async function makeCert(s: number): Promise<ExecutionCertificate> {
  let m = initialMachine(seq(s))
  const hashes: SHA256Hex[] = [h('0'), h('1'), h('2'), h('3'), h('4')]
  const phases = ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const
  const records = []
  for (let i = 0; i < phases.length; i++) {
    const { machine, record } = await transition(m, phases[i]!, hashes[i]!)
    records.push(record)
    m = machine
  }
  return certifyExecution(records, seq(s))
}

async function makeTopology(s: number): Promise<GovernanceTopology> {
  return buildTopology({
    sitr_state: 'STABLE',
    aoie_global_state: 'SECURE',
    constitutional_verdict: 'PERMIT',
    ledger_root: h('a'),
    consensus_qc_hash: null,
    dfa_certificate_hash: h('c'),
    sequence: seq(s),
  })
}

async function makeInput(s: number = 1): Promise<EpochInput> {
  return {
    dfa_certificate: await makeCert(s),
    topology: await makeTopology(s),
    lineage_terminal_hash: h('e'),
    capsule_attestation_hash: null,
  }
}

// ─── Constants ─────────────────────────────────────────────

describe('constants', () => {
  it('EPOCH_SCHEMA_VERSION is 1.0.0', () => {
    expect(EPOCH_SCHEMA_VERSION).toBe('1.0.0')
  })
})

// ─── EpochError ────────────────────────────────────────────

describe('EpochError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new EpochError('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('EpochError')
    expect(e.message).toBe('test')
  })
})

// ─── synthesizeEpoch — success ─────────────────────────────

describe('synthesizeEpoch — success', () => {
  it('produces a frozen EpochRecord', async () => {
    const record = await synthesizeEpoch(await makeInput())
    expect(Object.isFrozen(record)).toBe(true)
  })

  it('epoch_hash is 64-char hex', async () => {
    const record = await synthesizeEpoch(await makeInput())
    expect(record.epoch_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(record.epoch_hash)).toBe(true)
  })

  it('is_replay_reconstructable is true', async () => {
    const record = await synthesizeEpoch(await makeInput())
    expect(record.is_replay_reconstructable).toBe(true)
  })

  it('schema_version is 1.0.0', async () => {
    const record = await synthesizeEpoch(await makeInput())
    expect(record.schema_version).toBe('1.0.0')
  })

  it('fields are preserved from inputs', async () => {
    const input = await makeInput()
    const record = await synthesizeEpoch(input)
    expect(record.dfa_certificate_hash).toBe(input.dfa_certificate.certificate_hash)
    expect(record.topology_hash).toBe(input.topology.topology_hash)
    expect(record.lineage_terminal_hash).toBe(input.lineage_terminal_hash)
    expect(record.capsule_attestation_hash).toBe(input.capsule_attestation_hash)
    expect(record.sequence).toBe(input.topology.sequence)
  })

  it('null lineage_terminal_hash is valid', async () => {
    const input = { ...(await makeInput()), lineage_terminal_hash: null }
    const record = await synthesizeEpoch(input)
    expect(record.lineage_terminal_hash).toBeNull()
    expect(record.epoch_hash).toHaveLength(64)
  })

  it('epoch_hash is deterministic × 3', async () => {
    const input = await makeInput()
    const h1 = (await synthesizeEpoch(input)).epoch_hash
    const h2 = (await synthesizeEpoch(input)).epoch_hash
    const h3 = (await synthesizeEpoch(input)).epoch_hash
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('different topology → different epoch_hash', async () => {
    const input1 = await makeInput(1)
    const input2 = await makeInput(2)
    const r1 = await synthesizeEpoch(input1)
    const r2 = await synthesizeEpoch(input2)
    expect(r1.epoch_hash).not.toBe(r2.epoch_hash)
  })
})

// ─── synthesizeEpoch — error cases ────────────────────────

describe('synthesizeEpoch — error cases', () => {
  it('invalid DFA certificate throws EpochError', async () => {
    const input = await makeInput()
    const badCert = Object.freeze({ ...input.dfa_certificate, is_valid: false })
    await expect(synthesizeEpoch({ ...input, dfa_certificate: badCert }))
      .rejects.toThrow(EpochError)
  })

  it('error message mentions DFA on invalid cert', async () => {
    const input = await makeInput()
    const badCert = Object.freeze({ ...input.dfa_certificate, is_valid: false })
    const err = await synthesizeEpoch({ ...input, dfa_certificate: badCert }).catch(e => e)
    expect((err as Error).message).toContain('DFA')
  })

  it('tampered topology_hash throws EpochError', async () => {
    const input = await makeInput()
    const badTopology = Object.freeze({ ...input.topology, topology_hash: h('z') })
    await expect(synthesizeEpoch({ ...input, topology: badTopology }))
      .rejects.toThrow(EpochError)
  })

  it('sequence mismatch between DFA cert and topology throws EpochError', async () => {
    const cert = await makeCert(1)
    const topology = await makeTopology(2)  // different sequence
    await expect(synthesizeEpoch({ dfa_certificate: cert, topology, lineage_terminal_hash: null, capsule_attestation_hash: null }))
      .rejects.toThrow(EpochError)
  })

  it('error message mentions sequence on mismatch', async () => {
    const cert = await makeCert(1)
    const topology = await makeTopology(2)
    const err = await synthesizeEpoch({
      dfa_certificate: cert, topology,
      lineage_terminal_hash: null, capsule_attestation_hash: null,
    }).catch(e => e)
    expect((err as Error).message).toContain('Sequence')
  })
})

// ─── verifyEpoch ───────────────────────────────────────────

describe('verifyEpoch', () => {
  it('valid epoch record → true', async () => {
    const record = await synthesizeEpoch(await makeInput())
    expect(await verifyEpoch(record)).toBe(true)
  })

  it('tampered epoch_hash → false', async () => {
    const record = await synthesizeEpoch(await makeInput())
    const tampered = Object.freeze({ ...record, epoch_hash: h('0') })
    expect(await verifyEpoch(tampered)).toBe(false)
  })

  it('tampered topology_hash → false', async () => {
    const record = await synthesizeEpoch(await makeInput())
    const tampered = Object.freeze({ ...record, topology_hash: h('z') })
    expect(await verifyEpoch(tampered)).toBe(false)
  })

  it('tampered dfa_certificate_hash → false', async () => {
    const record = await synthesizeEpoch(await makeInput())
    const tampered = Object.freeze({ ...record, dfa_certificate_hash: h('z') })
    expect(await verifyEpoch(tampered)).toBe(false)
  })

  it('is deterministic × 3', async () => {
    const record = await synthesizeEpoch(await makeInput())
    const v1 = await verifyEpoch(record)
    const v2 = await verifyEpoch(record)
    const v3 = await verifyEpoch(record)
    expect(v1).toBe(true)
    expect(v2).toBe(true)
    expect(v3).toBe(true)
  })
})
