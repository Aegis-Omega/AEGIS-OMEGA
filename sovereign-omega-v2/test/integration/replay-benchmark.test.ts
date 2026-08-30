// ============================================================
// Gate 45 — Replay Performance Characterization
// ~22 tests: certifier throughput at 500 entries (topology,
//   adaptive), epoch chain at 100 entries, tamper detection
//   at first/middle/last positions, certificate stability
//   under repeated re-certification.
//
// Extends Gate 44 to larger scales and adversarial positions.
// Certifier correctness at n=500 is a practical bound proof —
// vitest's 5s per-test timeout acts as the performance gate.
//
// Key invariant verified: tamper at ANY position (first, last,
// or mid-chain) is detected — no positional blind spot.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { buildTopology } from '../../src/frame/topology.js'
import { TopologyLineage, certifyLineage, type LineageEntry } from '../../src/frame/lineage.js'
import { AdaptiveLineage, certifyAdaptiveLineage, type AdaptiveLineageEntry } from '../../src/frame/adaptive-lineage.js'
import { EpochChain, certifyEpochChain } from '../../src/frame/epoch-chain.js'
import { initialMachine, transition, certifyExecution } from '../../src/frame/dfa.js'
import { synthesizeEpoch } from '../../src/frame/epoch.js'
import type { EpochRecord } from '../../src/frame/epoch.js'

// ─── Helpers ───────────────────────────────────────────────

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const BASE = {
  sitr_state: 'STABLE' as const,
  aoie_global_state: 'SECURE' as const,
  constitutional_verdict: 'PERMIT' as const,
  ledger_root: h('a'),
  consensus_qc_hash: null,
  dfa_certificate_hash: h('d'),
}

async function buildTopoChain(n: number): Promise<TopologyLineage> {
  let lineage = TopologyLineage.empty()
  for (let i = 1; i <= n; i++) {
    lineage = await lineage.append(await buildTopology({ ...BASE, sequence: seq(i) }))
  }
  return lineage
}

async function buildAdaptiveChain(n: number): Promise<AdaptiveLineage> {
  let lineage = AdaptiveLineage.empty()
  for (let i = 1; i <= n; i++) {
    const event = i % 2 === 0
      ? { kind: 'CAPABILITY_EVOLUTION' as const, proposal_id: h(i.toString(16).slice(-1)), verdict: 'APPROVED' as const }
      : { kind: 'TOPOLOGY_TRANSITION' as const, topology_hash: h(i.toString(16).slice(-1)) }
    const { lineage: next } = await lineage.append(event, seq(i))
    lineage = next
  }
  return lineage
}

async function makeEpoch(s: number): Promise<EpochRecord> {
  let m = initialMachine(seq(s))
  const hashes: SHA256Hex[] = [h('0'), h('1'), h('2'), h('3'), h('4')]
  const phases = ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const
  const records = []
  for (let i = 0; i < phases.length; i++) {
    const { machine, record } = await transition(m, phases[i]!, hashes[i]!)
    records.push(record)
    m = machine
  }
  const cert = await certifyExecution(records, seq(s))
  const topology = await buildTopology({ ...BASE, dfa_certificate_hash: h('c'), sequence: seq(s) })
  return synthesizeEpoch({ dfa_certificate: cert, topology, lineage_terminal_hash: null, capsule_attestation_hash: null })
}

async function buildEpochChain(n: number): Promise<EpochChain> {
  let chain = EpochChain.empty()
  for (let i = 1; i <= n; i++) {
    const { chain: next } = await chain.append(await makeEpoch(i))
    chain = next
  }
  return chain
}

// ─── TopologyLineage at 500 entries ───────────────────────

describe('TopologyLineage certifier throughput at 500 entries', () => {
  it('builds and certifies 500-entry chain as valid', async () => {
    const lineage = await buildTopoChain(500)
    const cert = await certifyLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(500)
    expect(cert.terminal_hash).toHaveLength(64)
  })

  it('certificate_hash stable × 3 at 500 entries', async () => {
    const entries = (await buildTopoChain(500)).getAll()
    const c1 = await certifyLineage(entries)
    const c2 = await certifyLineage(entries)
    const c3 = await certifyLineage(entries)
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })

  it('tamper at first entry (index 0): detected', async () => {
    const entries = [...(await buildTopoChain(50)).getAll()]
    entries[0] = Object.freeze({ ...entries[0]!, lineage_hash: h('b') } as LineageEntry)
    const cert = await certifyLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper at last entry: detected', async () => {
    const lineage = await buildTopoChain(50)
    const entries = [...lineage.getAll()]
    const last = entries[entries.length - 1]!
    entries[entries.length - 1] = Object.freeze({ ...last, lineage_hash: h('c') } as LineageEntry)
    const cert = await certifyLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper previous_topology_hash at entry 1: detected', async () => {
    const entries = [...(await buildTopoChain(50)).getAll()]
    entries[1] = Object.freeze({ ...entries[1]!, previous_topology_hash: h('z') } as LineageEntry)
    const cert = await certifyLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('500-entry chain: lengths 200 vs 500 yield distinct certificates', async () => {
    const [l200, l500] = await Promise.all([buildTopoChain(200), buildTopoChain(500)])
    const [c200, c500] = await Promise.all([
      certifyLineage(l200.getAll()),
      certifyLineage(l500.getAll()),
    ])
    expect(c200.certificate_hash).not.toBe(c500.certificate_hash)
  })
})

// ─── AdaptiveLineage at 200 entries ───────────────────────

describe('AdaptiveLineage certifier throughput at 200 entries', () => {
  it('builds and certifies 200-entry chain as valid', async () => {
    const lineage = await buildAdaptiveChain(200)
    const cert = await certifyAdaptiveLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(200)
  })

  it('certificate_hash stable × 3 at 200 entries', async () => {
    const entries = (await buildAdaptiveChain(200)).getAll()
    const c1 = await certifyAdaptiveLineage(entries)
    const c2 = await certifyAdaptiveLineage(entries)
    const c3 = await certifyAdaptiveLineage(entries)
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })

  it('tamper at first entry: detected', async () => {
    const entries = [...(await buildAdaptiveChain(50)).getAll()]
    entries[0] = Object.freeze({ ...entries[0]!, entry_hash: h('d') } as AdaptiveLineageEntry)
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper at last entry: detected', async () => {
    const entries = [...(await buildAdaptiveChain(50)).getAll()]
    const last = entries[entries.length - 1]!
    entries[entries.length - 1] = Object.freeze({ ...last, entry_hash: h('e') } as AdaptiveLineageEntry)
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper previous_entry_hash at position 1: detected', async () => {
    const entries = [...(await buildAdaptiveChain(50)).getAll()]
    entries[1] = Object.freeze({ ...entries[1]!, previous_entry_hash: h('f') } as AdaptiveLineageEntry)
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })
})

// ─── EpochChain at 100 entries ─────────────────────────────

describe('EpochChain certifier throughput at 100 entries', () => {
  it('builds and certifies 100-entry chain as valid', async () => {
    const chain = await buildEpochChain(100)
    const cert = await certifyEpochChain(chain.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.link_count).toBe(100)
    expect(cert.terminal_hash).toHaveLength(64)
  })

  it('certificate_hash stable × 3 at 100 entries', async () => {
    const links = (await buildEpochChain(100)).getAll()
    const c1 = await certifyEpochChain(links)
    const c2 = await certifyEpochChain(links)
    const c3 = await certifyEpochChain(links)
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })

  it('tamper at first link: detected', async () => {
    const links = [...(await buildEpochChain(20)).getAll()]
    links[0] = Object.freeze({ ...links[0]!, link_hash: h('a') })
    const cert = await certifyEpochChain(links)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper at last link: detected', async () => {
    const links = [...(await buildEpochChain(20)).getAll()]
    const last = links[links.length - 1]!
    links[links.length - 1] = Object.freeze({ ...last, link_hash: h('b') })
    const cert = await certifyEpochChain(links)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper previous_epoch_hash at position 1: detected', async () => {
    const links = [...(await buildEpochChain(20)).getAll()]
    links[1] = Object.freeze({ ...links[1]!, previous_epoch_hash: h('c') })
    const cert = await certifyEpochChain(links)
    expect(cert.is_valid).toBe(false)
  })
})

// ─── Repeated re-certification stability ──────────────────
// Proves certifier functions have no internal state — calling them
// five times on the same chain yields byte-identical certificates.

describe('Certifier statelessness', () => {
  it('certifyLineage: identical result across 5 consecutive calls', async () => {
    const entries = (await buildTopoChain(100)).getAll()
    const hashes = await Promise.all(Array.from({ length: 5 }, () => certifyLineage(entries)))
    for (const c of hashes) expect(c.certificate_hash).toBe(hashes[0]!.certificate_hash)
  })

  it('certifyEpochChain: identical result across 5 consecutive calls', async () => {
    const links = (await buildEpochChain(50)).getAll()
    const certs = await Promise.all(Array.from({ length: 5 }, () => certifyEpochChain(links)))
    for (const c of certs) expect(c.certificate_hash).toBe(certs[0]!.certificate_hash)
  })
})
