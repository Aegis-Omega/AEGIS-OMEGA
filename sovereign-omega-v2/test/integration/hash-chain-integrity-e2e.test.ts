// ============================================================
// Gate 105 — Hash Chain Integrity E2E (Integration)
// ~22 tests: All chain types (Ledger, Topology, Adaptive,
//   Epoch, Mirror, Attestation) chained via terminal_hash
//   cross-references; tamper in one cascades to its cert.
// ============================================================

import { describe, it, expect } from 'vitest'
import { LedgerChain } from '../../src/ledger/chain.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
import { AdaptiveLineage, certifyAdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { certifyMartingale } from '../../src/constitutional/martingale.js'
import { MirrorStream } from '../../src/frame/mirror.js'
import { buildSelfAttestation, verifySelfAttestation } from '../../src/frame/attestation.js'
import { buildTopology } from '../../src/frame/topology.js'
import { EpochChain, certifyEpochChain } from '../../src/frame/epoch-chain.js'
import { synthesizeEpoch } from '../../src/frame/epoch.js'
import { initialMachine, transition, certifyExecution } from '../../src/frame/dfa.js'
import { hashValue } from '../../src/core/hashing.js'
import type { LedgerEntry } from '../../src/ledger/types.js'
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
const TS = 1_600_000_000_000

// ─── Each chain type certifies independently ─────────────

describe('Hash Chain E2E: each chain type valid', () => {
  it('LedgerChain: 5 entries, length=5', async () => {
    let chain = LedgerChain.empty()
    let prevHash = GENESIS_HASH
    for (let i = 1; i <= 5; i++) {
      const e: LedgerEntry = Object.freeze({
        sequence: seq(i), previous_hash: prevHash,
        frame_hash: h(String.fromCharCode(97 + i)), governance_hash: h('g'), timestamp_ms: TS + i,
      })
      chain = chain.append(e)
      prevHash = await hashValue(e) as SHA256Hex
    }
    expect(chain.length).toBe(5)
  })

  it('AdaptiveLineage: 5 entries, is_valid=true', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 5; i++) {
      const topo = await buildTopology({ ...BASE, sequence: seq(i) })
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: topo.topology_hash }, seq(i),
      )
      lineage = next
    }
    const cert = await certifyAdaptiveLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
  })

  it('MirrorStream: 5 observations, all hashes populated', async () => {
    let mirror = MirrorStream.empty()
    for (let i = 1; i <= 5; i++) {
      const topo = await buildTopology({ ...BASE, sequence: seq(i) })
      const { stream } = await mirror.observe(topo)
      mirror = stream
    }
    expect(mirror.length).toBe(5)
    for (const obs of mirror.getAll()) {
      expect(obs.observation_hash).toHaveLength(64)
    }
  })

  it('EpochChain: 3 epochs, is_valid=true', async () => {
    let chain = EpochChain.empty()
    for (let i = 1; i <= 3; i++) {
      const topo = await buildTopology({ ...BASE, sequence: seq(i) })
      let machine = initialMachine(seq(i))
      const records = []
      for (const phase of ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const) {
        const { machine: next, record } = await transition(machine, phase, h(phase[0]!.toLowerCase()))
        machine = next; records.push(record)
      }
      const dfaCert = await certifyExecution(records, seq(i))
      const epoch = await synthesizeEpoch({ dfa_certificate: dfaCert, topology: topo, lineage_terminal_hash: null, capsule_attestation_hash: null })
      const { chain: next } = await chain.append(epoch)
      chain = next
    }
    const cert = await certifyEpochChain(chain.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.link_count).toBe(3)
  })

  it('SelfAttestation chain: 5 attestations, all verify=true', async () => {
    for (let i = 1; i <= 5; i++) {
      const topo = await buildTopology({ ...BASE, sequence: seq(i) })
      const att = await buildSelfAttestation({
        dfa_certificate_hash: h('d'), topology_hash: topo.topology_hash,
        lineage_terminal_hash: null, capsule_attestation_hash: null, sequence: seq(i),
      })
      expect(await verifySelfAttestation(att)).toBe(true)
    }
  })
})

// ─── Tamper cascade within each chain type ────────────────

describe('Hash Chain E2E: tamper cascades', () => {
  it('tamper adaptive entry → certifyAdaptiveLineage is_valid=false', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 5; i++) {
      const topo = await buildTopology({ ...BASE, sequence: seq(i) })
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: topo.topology_hash }, seq(i),
      )
      lineage = next
    }
    const entries = [...lineage.getAll()]
    entries[2] = { ...entries[2]!, entry_hash: h('z') }
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper epoch link_hash → certifyEpochChain is_valid=false', async () => {
    let chain = EpochChain.empty()
    for (let i = 1; i <= 3; i++) {
      const topo = await buildTopology({ ...BASE, sequence: seq(i) })
      let machine = initialMachine(seq(i))
      const records = []
      for (const phase of ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const) {
        const { machine: next, record } = await transition(machine, phase, h(phase[0]!.toLowerCase()))
        machine = next; records.push(record)
      }
      const dfaCert = await certifyExecution(records, seq(i))
      const epoch = await synthesizeEpoch({ dfa_certificate: dfaCert, topology: topo, lineage_terminal_hash: null, capsule_attestation_hash: null })
      const { chain: next } = await chain.append(epoch)
      chain = next
    }
    const links = [...chain.getAll()]
    links[1] = { ...links[1]!, link_hash: h('z') }
    const cert = await certifyEpochChain(links)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper attestation_hash → verifySelfAttestation=false', async () => {
    const topo = await buildTopology({ ...BASE, sequence: seq(1) })
    const att = await buildSelfAttestation({
      dfa_certificate_hash: h('d'), topology_hash: topo.topology_hash,
      lineage_terminal_hash: null, capsule_attestation_hash: null, sequence: seq(1),
    })
    const tampered = { ...att, attestation_hash: h('z') }
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })

  it('martingale detects tampered adaptive chain', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 5; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + i)) }, seq(i),
      )
      lineage = next
    }
    const entries = [...lineage.getAll()]
    entries[3] = { ...entries[3]!, entry_hash: h('z') }
    const cert = await certifyMartingale(entries)
    expect(cert.is_anchored).toBe(false)
  })
})

// ─── Cross-chain hash binding ─────────────────────────────

describe('Hash Chain E2E: cross-chain terminal_hash binding', () => {
  it('AdaptiveLineage terminal_hash binds into attestation', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 3; i++) {
      const topo = await buildTopology({ ...BASE, sequence: seq(i) })
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: topo.topology_hash }, seq(i),
      )
      lineage = next
    }
    const entries = lineage.getAll()
    const terminalHash = entries[2]!.entry_hash
    const topo = await buildTopology({ ...BASE, sequence: seq(4) })
    const att = await buildSelfAttestation({
      dfa_certificate_hash: h('d'),
      topology_hash: topo.topology_hash,
      lineage_terminal_hash: terminalHash,
      capsule_attestation_hash: null,
      sequence: seq(4),
    })
    expect(att.lineage_terminal_hash).toBe(terminalHash)
    expect(await verifySelfAttestation(att)).toBe(true)
  })

  it('MirrorStream observation_hash is deterministic ×3', async () => {
    const topo = await buildTopology({ ...BASE, sequence: seq(1) })
    let m1 = MirrorStream.empty(), m2 = MirrorStream.empty(), m3 = MirrorStream.empty()
    const [{ observation: o1 }, { observation: o2 }, { observation: o3 }] = await Promise.all([
      m1.observe(topo), m2.observe(topo), m3.observe(topo),
    ])
    expect(o1.observation_hash).toBe(o2.observation_hash)
    expect(o2.observation_hash).toBe(o3.observation_hash)
  })
})
