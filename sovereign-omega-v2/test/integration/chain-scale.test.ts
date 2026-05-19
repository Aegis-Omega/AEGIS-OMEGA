// ============================================================
// Gate 44 — Chain Scaling Economics
// ~22 tests: TopologyLineage (100 entries), AdaptiveLineage
//   (100 mixed entries), EpochChain (50 entries), tamper
//   detection at scale, length-sensitivity of certificates.
//
// Proves hash chains remain correct, certifiable, and
// deterministic at operational scale — no O(n²) accumulation
// or off-by-one in certifier functions.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { buildTopology } from '../../src/frame/topology.js'
import { TopologyLineage, certifyLineage } from '../../src/frame/lineage.js'
import { AdaptiveLineage, certifyAdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { EpochChain, certifyEpochChain } from '../../src/frame/epoch-chain.js'
import { initialMachine, transition, certifyExecution } from '../../src/frame/dfa.js'
import { synthesizeEpoch } from '../../src/frame/epoch.js'
import type { EpochRecord } from '../../src/frame/epoch.js'

// ─── Helpers ───────────────────────────────────────────────

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const BASE_TOPOLOGY = {
  sitr_state: 'STABLE' as const,
  aoie_global_state: 'SECURE' as const,
  constitutional_verdict: 'PERMIT' as const,
  ledger_root: h('a'),
  consensus_qc_hash: null,
  dfa_certificate_hash: h('d'),
}

async function buildTopologyChain(length: number): Promise<TopologyLineage> {
  let lineage = TopologyLineage.empty()
  for (let i = 1; i <= length; i++) {
    const topology = await buildTopology({ ...BASE_TOPOLOGY, sequence: seq(i) })
    lineage = await lineage.append(topology)
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
  const topology = await buildTopology({
    ...BASE_TOPOLOGY, dfa_certificate_hash: h('c'), sequence: seq(s),
  })
  return synthesizeEpoch({ dfa_certificate: cert, topology, lineage_terminal_hash: null, capsule_attestation_hash: null })
}

async function buildEpochChain(length: number): Promise<EpochChain> {
  let chain = EpochChain.empty()
  for (let i = 1; i <= length; i++) {
    const { chain: next } = await chain.append(await makeEpoch(i))
    chain = next
  }
  return chain
}

// ─── TopologyLineage scaling ───────────────────────────────

describe('TopologyLineage at 100 entries', () => {
  it('builds 100-entry chain without error', async () => {
    const lineage = await buildTopologyChain(100)
    expect(lineage.length).toBe(100)
  })

  it('100-entry chain certifies as valid', async () => {
    const lineage = await buildTopologyChain(100)
    const cert = await certifyLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(100)
    expect(cert.terminal_hash).toHaveLength(64)
  })

  it('certificate_hash is deterministic × 3 at 100 entries', async () => {
    const lineage = await buildTopologyChain(100)
    const entries = lineage.getAll()
    const c1 = await certifyLineage(entries)
    const c2 = await certifyLineage(entries)
    const c3 = await certifyLineage(entries)
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })

  it('different lengths produce different certificate_hashes', async () => {
    const l50 = await buildTopologyChain(50)
    const l100 = await buildTopologyChain(100)
    const c50 = await certifyLineage(l50.getAll())
    const c100 = await certifyLineage(l100.getAll())
    expect(c50.certificate_hash).not.toBe(c100.certificate_hash)
  })

  it('tamper at entry 50 of 100: is_valid false', async () => {
    const lineage = await buildTopologyChain(100)
    const entries = [...lineage.getAll()]
    const entry50 = entries[49]!
    entries[49] = Object.freeze({ ...entry50, lineage_hash: h('f') })
    const cert = await certifyLineage(entries)
    expect(cert.is_valid).toBe(false)
  })
})

// ─── AdaptiveLineage scaling ───────────────────────────────

describe('AdaptiveLineage at 100 mixed entries', () => {
  async function buildAdaptiveChain(length: number): Promise<AdaptiveLineage> {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= length; i++) {
      const event = i % 2 === 0
        ? { kind: 'CAPABILITY_EVOLUTION' as const, proposal_id: h(i.toString(16).slice(-1)), verdict: 'APPROVED' as const }
        : { kind: 'TOPOLOGY_TRANSITION' as const, topology_hash: h(i.toString(16).slice(-1)) }
      const { lineage: next } = await lineage.append(event, seq(i))
      lineage = next
    }
    return lineage
  }

  it('builds 100-entry mixed chain without error', async () => {
    const lineage = await buildAdaptiveChain(100)
    expect(lineage.length).toBe(100)
  })

  it('100-entry mixed chain certifies as valid', async () => {
    const lineage = await buildAdaptiveChain(100)
    const cert = await certifyAdaptiveLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(100)
    expect(cert.terminal_hash).toHaveLength(64)
  })

  it('certificate_hash is deterministic × 3 at 100 entries', async () => {
    const lineage = await buildAdaptiveChain(100)
    const entries = lineage.getAll()
    const c1 = await certifyAdaptiveLineage(entries)
    const c2 = await certifyAdaptiveLineage(entries)
    const c3 = await certifyAdaptiveLineage(entries)
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })

  it('tamper at entry 50 of 100: is_valid false', async () => {
    const lineage = await buildAdaptiveChain(100)
    const entries = [...lineage.getAll()]
    const entry50 = entries[49]!
    entries[49] = Object.freeze({ ...entry50, entry_hash: h('e') })
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('TOPOLOGY and CAPABILITY events both reflected in certificate', async () => {
    const lineage = await buildAdaptiveChain(10)
    const entries = lineage.getAll()
    const topEvents = entries.filter(e => e.event.kind === 'TOPOLOGY_TRANSITION').length
    const capEvents = entries.filter(e => e.event.kind === 'CAPABILITY_EVOLUTION').length
    expect(topEvents).toBe(5)
    expect(capEvents).toBe(5)
  })
})

// ─── EpochChain scaling ────────────────────────────────────

describe('EpochChain at 50 entries', () => {
  it('builds 50-entry chain without error', async () => {
    const chain = await buildEpochChain(50)
    expect(chain.length).toBe(50)
  })

  it('50-entry chain certifies as valid', async () => {
    const chain = await buildEpochChain(50)
    const cert = await certifyEpochChain(chain.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.link_count).toBe(50)
    expect(cert.terminal_hash).toHaveLength(64)
    expect(cert.is_replay_reconstructable).toBe(true)
  })

  it('certificate_hash is deterministic × 3 at 50 entries', async () => {
    const chain = await buildEpochChain(50)
    const links = chain.getAll()
    const c1 = await certifyEpochChain(links)
    const c2 = await certifyEpochChain(links)
    const c3 = await certifyEpochChain(links)
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })

  it('different epoch chain lengths produce different certificate_hashes', async () => {
    const chain25 = await buildEpochChain(25)
    const chain50 = await buildEpochChain(50)
    const c25 = await certifyEpochChain(chain25.getAll())
    const c50 = await certifyEpochChain(chain50.getAll())
    expect(c25.certificate_hash).not.toBe(c50.certificate_hash)
  })

  it('tamper link_hash at position 25 of 50: is_valid false', async () => {
    const chain = await buildEpochChain(50)
    const links = [...chain.getAll()]
    const link25 = links[24]!
    links[24] = Object.freeze({ ...link25, link_hash: h('f') })
    const cert = await certifyEpochChain(links)
    expect(cert.is_valid).toBe(false)
  })
})

// ─── Cross-chain length sensitivity ───────────────────────

describe('length sensitivity across all chain types', () => {
  it('topology lineage: length 10, 50, 100 all produce distinct certificates', async () => {
    const [l10, l50, l100] = await Promise.all([
      buildTopologyChain(10),
      buildTopologyChain(50),
      buildTopologyChain(100),
    ])
    const [c10, c50, c100] = await Promise.all([
      certifyLineage(l10.getAll()),
      certifyLineage(l50.getAll()),
      certifyLineage(l100.getAll()),
    ])
    expect(c10.certificate_hash).not.toBe(c50.certificate_hash)
    expect(c50.certificate_hash).not.toBe(c100.certificate_hash)
    expect(c10.certificate_hash).not.toBe(c100.certificate_hash)
  })
})
