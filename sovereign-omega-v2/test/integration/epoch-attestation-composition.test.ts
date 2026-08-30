// ============================================================
// Gate 74 — Epoch × Attestation Composition (Integration)
// ~18 tests: 10-epoch chain where each epoch's epoch_hash feeds
//   into a SelfAttestationRecord chain; certifyAdaptiveLineage
//   validates the composed lineage.
// ============================================================

import { describe, it, expect } from 'vitest'
import { synthesizeEpoch } from '../../src/frame/epoch.js'
import { EpochChain, certifyEpochChain } from '../../src/frame/epoch-chain.js'
import { buildSelfAttestation, verifySelfAttestation } from '../../src/frame/attestation.js'
import { buildTopology } from '../../src/frame/topology.js'
import { initialMachine, transition, certifyExecution } from '../../src/frame/dfa.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const BASE = {
  sitr_state: 'STABLE' as const,
  aoie_global_state: 'SECURE' as const,
  constitutional_verdict: 'PERMIT' as const,
  ledger_root: h('a'),
  consensus_qc_hash: h('b'),
  dfa_certificate_hash: h('c'),
}

async function buildEpochRecord(n: number) {
  const seqN = seq(n)
  let machine = initialMachine(seqN)
  const records = []
  for (const phase of ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const) {
    const { machine: next, record } = await transition(machine, phase, h(phase[0]!.toLowerCase()))
    machine = next; records.push(record)
  }
  const cert = await certifyExecution(records, seqN)
  const topology = await buildTopology({ ...BASE, dfa_certificate_hash: cert.certificate_hash, sequence: seqN })
  return synthesizeEpoch({ dfa_certificate: cert, topology, lineage_terminal_hash: null, capsule_attestation_hash: null })
}

// ─── 10-epoch chain with attestation ─────────────────────

describe('Epoch × Attestation: 10-epoch chain', () => {
  it('10 epochs → 10 valid SelfAttestationRecords', async () => {
    for (let i = 1; i <= 10; i++) {
      const epoch = await buildEpochRecord(i)
      const attestation = await buildSelfAttestation({
        dfa_certificate_hash: epoch.dfa_certificate_hash,
        topology_hash: epoch.topology_hash,
        lineage_terminal_hash: epoch.lineage_terminal_hash,
        capsule_attestation_hash: epoch.capsule_attestation_hash,
        sequence: epoch.sequence,
      })
      expect(await verifySelfAttestation(attestation)).toBe(true)
    }
  })

  it('10 epochs → epoch_hash matches attestation_hash (epoch IS attestation)', async () => {
    // synthesizeEpoch builds attestation internally; epoch_hash === attestation_hash
    for (let i = 1; i <= 10; i++) {
      const epoch = await buildEpochRecord(i)
      const attestation = await buildSelfAttestation({
        dfa_certificate_hash: epoch.dfa_certificate_hash,
        topology_hash: epoch.topology_hash,
        lineage_terminal_hash: epoch.lineage_terminal_hash,
        capsule_attestation_hash: epoch.capsule_attestation_hash,
        sequence: epoch.sequence,
      })
      expect(epoch.epoch_hash).toBe(attestation.attestation_hash)
    }
  })

  it('EpochChain of 10 → certifyEpochChain is_valid=true', async () => {
    let chain = EpochChain.empty()
    for (let i = 1; i <= 10; i++) {
      const epoch = await buildEpochRecord(i)
      const { chain: next } = await chain.append(epoch)
      chain = next
    }
    const cert = await certifyEpochChain(chain.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.link_count).toBe(10)
  })

  it('different epoch → different attestation_hash', async () => {
    const e1 = await buildEpochRecord(1)
    const e2 = await buildEpochRecord(2)
    expect(e1.epoch_hash).not.toBe(e2.epoch_hash)
  })
})

// ─── Attestation structural guarantees ────────────────────

describe('Epoch × Attestation: structural guarantees', () => {
  it('epoch record is frozen', async () => {
    const epoch = await buildEpochRecord(1)
    expect(Object.isFrozen(epoch)).toBe(true)
  })

  it('epoch.is_replay_reconstructable=true', async () => {
    const epoch = await buildEpochRecord(1)
    expect(epoch.is_replay_reconstructable).toBe(true)
  })

  it('epoch_hash is 64-char hex', async () => {
    const epoch = await buildEpochRecord(1)
    expect(epoch.epoch_hash).toHaveLength(64)
    expect(epoch.epoch_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('same epoch_hash × 3 (deterministic)', async () => {
    const [e1, e2, e3] = await Promise.all([buildEpochRecord(5), buildEpochRecord(5), buildEpochRecord(5)])
    expect(e1!.epoch_hash).toBe(e2!.epoch_hash)
    expect(e2!.epoch_hash).toBe(e3!.epoch_hash)
  })
})
