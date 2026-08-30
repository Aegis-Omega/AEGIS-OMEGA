// ============================================================
// Gate 102 — Full Constitutional Stack (Integration)
// ~22 tests: Every constitutional module in one chain:
//   DFA → Topology → Lineage → Attestation → Epoch →
//   Martingale; end-to-end hash binding across all layers.
// ============================================================

import { describe, it, expect } from 'vitest'
import { initialMachine, transition, certifyExecution } from '../../src/frame/dfa.js'
import { buildTopology } from '../../src/frame/topology.js'
import { buildLineageEntry, certifyLineage, GENESIS_TOPOLOGY_HASH } from '../../src/frame/lineage.js'
import { buildSelfAttestation, verifySelfAttestation } from '../../src/frame/attestation.js'
import { synthesizeEpoch } from '../../src/frame/epoch.js'
import { EpochChain, certifyEpochChain } from '../../src/frame/epoch-chain.js'
import { AdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { certifyMartingale, assertMartingaleAnchored } from '../../src/constitutional/martingale.js'
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

async function fullStackFrame(i: number) {
  let machine = initialMachine(seq(i))
  const records = []
  for (const phase of ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const) {
    const { machine: next, record } = await transition(machine, phase, h(phase[0]!.toLowerCase()))
    machine = next
    records.push(record)
  }
  const dfaCert = await certifyExecution(records, seq(i))
  const topo = await buildTopology({ ...BASE, sequence: seq(i) })
  return { dfaCert, topo }
}

// ─── Full stack in sequence ───────────────────────────────

describe('Full Constitutional Stack: DFA→Topo→Lineage→Attestation→Epoch→Martingale', () => {
  it('DFA cert is_valid=true for all 5 phases', async () => {
    const { dfaCert } = await fullStackFrame(1)
    expect(dfaCert.is_valid).toBe(true)
    expect(dfaCert.certificate_hash).toHaveLength(64)
  })

  it('topology hash is 64-char hex', async () => {
    const { topo } = await fullStackFrame(1)
    expect(topo.topology_hash).toHaveLength(64)
    expect(topo.topology_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('lineage entry chains from genesis', async () => {
    const { topo } = await fullStackFrame(1)
    const entry = await buildLineageEntry(topo, GENESIS_TOPOLOGY_HASH, null)
    expect(entry.previous_topology_hash).toBe(GENESIS_TOPOLOGY_HASH)
    expect(entry.lineage_hash).toHaveLength(64)
  })

  it('attestation encodes DFA cert + topology', async () => {
    const { dfaCert, topo } = await fullStackFrame(1)
    const attestation = await buildSelfAttestation({
      dfa_certificate_hash: dfaCert.certificate_hash,
      topology_hash: topo.topology_hash,
      lineage_terminal_hash: null,
      capsule_attestation_hash: null,
      sequence: seq(1),
    })
    expect(await verifySelfAttestation(attestation)).toBe(true)
    expect(attestation.dfa_certificate_hash).toBe(dfaCert.certificate_hash)
    expect(attestation.topology_hash).toBe(topo.topology_hash)
  })

  it('epoch synthesis from DFA cert + topology', async () => {
    const { dfaCert, topo } = await fullStackFrame(1)
    const epoch = await synthesizeEpoch({ dfa_certificate: dfaCert, topology: topo, lineage_terminal_hash: null, capsule_attestation_hash: null })
    expect(epoch.epoch_hash).toHaveLength(64)
    expect(epoch.is_replay_reconstructable).toBe(true)
  })

  it('5-frame full stack → EpochChain is_valid=true', async () => {
    let chain = EpochChain.empty()
    for (let i = 1; i <= 5; i++) {
      const { dfaCert, topo } = await fullStackFrame(i)
      const epoch = await synthesizeEpoch({ dfa_certificate: dfaCert, topology: topo, lineage_terminal_hash: null, capsule_attestation_hash: null })
      const { chain: next } = await chain.append(epoch)
      chain = next
    }
    const cert = await certifyEpochChain(chain.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.link_count).toBe(5)
  })

  it('5-frame AdaptiveLineage + Martingale: anchored and bounded', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 5; i++) {
      const { topo } = await fullStackFrame(i)
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: topo.topology_hash },
        seq(i),
      )
      lineage = next
    }
    const mart = await certifyMartingale(lineage.getAll())
    expect(mart.is_anchored).toBe(true)
    expect(mart.entropy_bounded).toBe(true)
    expect(() => assertMartingaleAnchored(mart)).not.toThrow()
  })
})

// ─── Hash binding across layers ───────────────────────────

describe('Full Constitutional Stack: cross-layer hash binding', () => {
  it('different sequence → different topology_hash', async () => {
    const { topo: t1 } = await fullStackFrame(1)
    const { topo: t2 } = await fullStackFrame(2)
    expect(t1.topology_hash).not.toBe(t2.topology_hash)
  })

  it('different sequence → different DFA certificate_hash', async () => {
    const { dfaCert: d1 } = await fullStackFrame(1)
    const { dfaCert: d2 } = await fullStackFrame(2)
    expect(d1.certificate_hash).not.toBe(d2.certificate_hash)
  })

  it('attestation_hash changes with different topology_hash', async () => {
    const { dfaCert: d1, topo: t1 } = await fullStackFrame(1)
    const { dfaCert: d2, topo: t2 } = await fullStackFrame(2)
    const att1 = await buildSelfAttestation({
      dfa_certificate_hash: d1.certificate_hash, topology_hash: t1.topology_hash,
      lineage_terminal_hash: null, capsule_attestation_hash: null, sequence: seq(1),
    })
    const att2 = await buildSelfAttestation({
      dfa_certificate_hash: d2.certificate_hash, topology_hash: t2.topology_hash,
      lineage_terminal_hash: null, capsule_attestation_hash: null, sequence: seq(2),
    })
    expect(att1.attestation_hash).not.toBe(att2.attestation_hash)
  })

  it('full stack deterministic ×3 (same seq → same hashes)', async () => {
    const [f1, f2, f3] = await Promise.all([fullStackFrame(1), fullStackFrame(1), fullStackFrame(1)])
    expect(f1.dfaCert.certificate_hash).toBe(f2.dfaCert.certificate_hash)
    expect(f2.dfaCert.certificate_hash).toBe(f3.dfaCert.certificate_hash)
    expect(f1.topo.topology_hash).toBe(f2.topo.topology_hash)
    expect(f2.topo.topology_hash).toBe(f3.topo.topology_hash)
  })
})

// ─── Lineage certification at scale ───────────────────────

describe('Full Constitutional Stack: lineage at 10-frame scale', () => {
  it('10-frame lineage certifyLineage is_valid=true', async () => {
    const topos = await Promise.all(Array.from({ length: 10 }, (_, i) => fullStackFrame(i + 1).then(f => f.topo)))
    let prevTopoHash = GENESIS_TOPOLOGY_HASH
    let prevSeq: SequenceNumber | null = null
    const entries = []
    for (let i = 0; i < 10; i++) {
      const entry = await buildLineageEntry(topos[i]!, prevTopoHash, prevSeq)
      entries.push(entry)
      prevTopoHash = entry.topology_hash
      prevSeq = entry.sequence
    }
    const cert = await certifyLineage(entries)
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(10)
  })

  it('martingale terminal_hash = last lineage entry_hash', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 3; i++) {
      const { topo } = await fullStackFrame(i)
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: topo.topology_hash },
        seq(i),
      )
      lineage = next
    }
    const entries = lineage.getAll()
    const mart = await certifyMartingale(entries)
    expect(mart.terminal_hash).toBe(entries[2]!.entry_hash)
  })

  it('all frame records have is_replay_reconstructable=true', async () => {
    const { dfaCert, topo } = await fullStackFrame(1)
    const epoch = await synthesizeEpoch({ dfa_certificate: dfaCert, topology: topo, lineage_terminal_hash: null, capsule_attestation_hash: null })
    const attestation = await buildSelfAttestation({
      dfa_certificate_hash: dfaCert.certificate_hash, topology_hash: topo.topology_hash,
      lineage_terminal_hash: null, capsule_attestation_hash: null, sequence: seq(1),
    })
    expect(dfaCert.is_replay_reconstructable).toBe(true)
    expect(topo.is_replay_reconstructable).toBe(true)
    expect(epoch.is_replay_reconstructable).toBe(true)
    expect(attestation.is_replay_reconstructable).toBe(true)
  })
})
