// ============================================================
// Gate 47 — Lineage Compaction Economics
// ~22 tests: topology_hash as continuation anchor, segment
//   boundary continuity, certifier terminal_hash semantics,
//   EpochChain half-chain invariants, LedgerChain Merkle
//   checkpoint compaction, re-certification idempotency.
//
// Compaction anchor law (verified per chain type):
//
//   TopologyLineage:
//     chain.lastHash  === entries[k].topology_hash
//                     === entries[k+1].previous_topology_hash
//     (topology_hash is the continuation anchor; lineage_hash
//      is separate — it is the certifier's terminal_hash)
//
//   EpochChain:
//     certifyEpochChain(links[0..k]).terminal_hash
//       === links[k].link_hash
//       === links[k+1].previous_epoch_hash
//     (link_hash IS both the certifier terminal and the anchor)
//
//   LedgerChain:
//     captureCheckpoint(chain).merkle_root compresses n entries
//     into a single 64-byte digest — the minimal replay checkpoint.
//
// No src/ changes — uses existing certify* and captureCheckpoint APIs.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { buildTopology } from '../../src/frame/topology.js'
import {
  TopologyLineage, certifyLineage,
  GENESIS_TOPOLOGY_HASH,
} from '../../src/frame/lineage.js'
import {
  AdaptiveLineage, certifyAdaptiveLineage,
  GENESIS_TOPOLOGY_HASH as ADAPTIVE_GENESIS,
} from '../../src/frame/adaptive-lineage.js'
import {
  EpochChain, certifyEpochChain,
  EPOCH_GENESIS_HASH,
} from '../../src/frame/epoch-chain.js'
import { LedgerChain } from '../../src/ledger/chain.js'
import { captureCheckpoint } from '../../src/ledger/checkpoint.js'
import { hashValue } from '../../src/core/hashing.js'
import { GENESIS_HASH, type LedgerEntry } from '../../src/ledger/types.js'
import { initialMachine, transition, certifyExecution } from '../../src/frame/dfa.js'
import { synthesizeEpoch } from '../../src/frame/epoch.js'
import type { EpochRecord } from '../../src/frame/epoch.js'

// ─── Helpers ───────────────────────────────────────────────

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const TS = 1_600_000_000_000

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

async function buildLedgerChain(n: number): Promise<LedgerChain> {
  let chain = LedgerChain.empty()
  let prevHash = GENESIS_HASH
  for (let i = 1; i <= n; i++) {
    const entry = Object.freeze<LedgerEntry>({
      sequence: seq(i),
      previous_hash: prevHash,
      frame_hash: h('f'),
      governance_hash: h('e'),
      timestamp_ms: TS + i,
    })
    chain = chain.append(entry)
    prevHash = await hashValue(entry)
  }
  return chain
}

// ─── TopologyLineage: continuation anchor law ─────────────
// topology_hash (chain.lastHash) is the anchor for the next append.
// lineage_hash (certifyLineage.terminal_hash) is the certifier's record.
// These are distinct fields — important for correct compaction reasoning.

describe('TopologyLineage: continuation anchor law', () => {
  it('chain.lastHash equals last entry topology_hash', async () => {
    const lineage = await buildTopoChain(20)
    const entries = lineage.getAll()
    expect(lineage.lastHash).toBe(entries[entries.length - 1]!.topology_hash)
  })

  it('entries[k].topology_hash equals entries[k+1].previous_topology_hash', async () => {
    const lineage = await buildTopoChain(20)
    const entries = lineage.getAll()
    for (const k of [0, 5, 10, 14, 18]) {
      expect(entries[k]!.topology_hash).toBe(entries[k + 1]!.previous_topology_hash)
    }
  })

  it('first entry previous_topology_hash equals GENESIS_TOPOLOGY_HASH', async () => {
    const lineage = await buildTopoChain(5)
    expect(lineage.getAll()[0]!.previous_topology_hash).toBe(GENESIS_TOPOLOGY_HASH)
  })

  it('certifyLineage terminal_hash equals last entry lineage_hash (not topology_hash)', async () => {
    const lineage = await buildTopoChain(20)
    const entries = lineage.getAll()
    const cert = await certifyLineage(entries)
    const lastEntry = entries[entries.length - 1]!
    expect(cert.terminal_hash).toBe(lastEntry.lineage_hash)
    // topology_hash and lineage_hash are distinct fields
    expect(lastEntry.lineage_hash).not.toBe(lastEntry.topology_hash)
  })

  it('chain.lastHash differs from certifyLineage terminal_hash (distinct concepts)', async () => {
    const lineage = await buildTopoChain(20)
    const cert = await certifyLineage(lineage.getAll())
    // lastHash = topology_hash; terminal_hash = lineage_hash — not the same
    expect(lineage.lastHash).not.toBe(cert.terminal_hash)
  })

  it('two chains built with different topologies have distinct lastHash and terminal_hash', async () => {
    const chain1 = await buildTopoChain(15)
    let chain2 = TopologyLineage.empty()
    for (let i = 1; i <= 15; i++) {
      chain2 = await chain2.append(await buildTopology({ ...BASE, ledger_root: h('b'), sequence: seq(i) }))
    }
    const c1 = await certifyLineage(chain1.getAll())
    const c2 = await certifyLineage(chain2.getAll())
    expect(chain1.lastHash).not.toBe(chain2.lastHash)
    expect(c1.terminal_hash).not.toBe(c2.terminal_hash)
  })
})

// ─── EpochChain: link_hash serves dual role ────────────────
// For EpochChain, link_hash is BOTH the certifier terminal_hash AND
// the continuation anchor (previous_epoch_hash for the next link).
// This makes epoch chains more compact — one hash suffices.

describe('EpochChain: link_hash as dual-role anchor', () => {
  it('certifyEpochChain terminal_hash equals last link.link_hash', async () => {
    const chain = await buildEpochChain(20)
    const links = chain.getAll()
    const cert = await certifyEpochChain(links)
    expect(cert.terminal_hash).toBe(links[links.length - 1]!.link_hash)
  })

  it('chain.lastHash equals certifyEpochChain terminal_hash', async () => {
    const chain = await buildEpochChain(20)
    const cert = await certifyEpochChain(chain.getAll())
    expect(chain.lastHash).toBe(cert.terminal_hash)
  })

  it('terminal_hash of first half equals links[k+1].previous_epoch_hash', async () => {
    const chain = await buildEpochChain(30)
    const links = chain.getAll()
    const firstHalf = links.slice(0, 15)
    const cert = await certifyEpochChain(firstHalf)
    expect(cert.terminal_hash).toBe(links[15]!.previous_epoch_hash)
  })

  it('first link previous_epoch_hash equals EPOCH_GENESIS_HASH', async () => {
    const chain = await buildEpochChain(5)
    expect(chain.getAll()[0]!.previous_epoch_hash).toBe(EPOCH_GENESIS_HASH)
  })

  it('second half without first-half context fails certification (expected behavior)', async () => {
    const chain = await buildEpochChain(20)
    const secondHalf = chain.getAll().slice(10)
    const cert = await certifyEpochChain(secondHalf)
    // links[10].previous_epoch_hash != EPOCH_GENESIS_HASH → fails
    expect(cert.is_valid).toBe(false)
  })
})

// ─── AdaptiveLineage: entry_hash as anchor ────────────────

describe('AdaptiveLineage: continuation anchor law', () => {
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

  it('entries[k].entry_hash equals entries[k+1].previous_entry_hash', async () => {
    const lineage = await buildAdaptiveChain(20)
    const entries = lineage.getAll()
    for (const k of [0, 5, 10, 14, 18]) {
      expect(entries[k]!.entry_hash).toBe(entries[k + 1]!.previous_entry_hash)
    }
  })

  it('first entry previous_entry_hash equals GENESIS_TOPOLOGY_HASH', async () => {
    const lineage = await buildAdaptiveChain(5)
    expect(lineage.getAll()[0]!.previous_entry_hash).toBe(ADAPTIVE_GENESIS)
  })

  it('certifyAdaptiveLineage terminal_hash equals last entry entry_hash', async () => {
    const lineage = await buildAdaptiveChain(20)
    const entries = lineage.getAll()
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.terminal_hash).toBe(entries[entries.length - 1]!.entry_hash)
  })

  it('terminal_hash of prefix equals next entry previous_entry_hash', async () => {
    const lineage = await buildAdaptiveChain(20)
    const entries = lineage.getAll()
    const prefix = entries.slice(0, 10)
    const cert = await certifyAdaptiveLineage(prefix)
    expect(cert.terminal_hash).toBe(entries[10]!.previous_entry_hash)
  })
})

// ─── LedgerChain: Merkle checkpoint compaction ────────────
// captureCheckpoint produces a single 64-byte Merkle root that
// summarizes n entries — the practical compaction mechanism.

describe('LedgerChain Merkle checkpoint compaction', () => {
  it('captureCheckpoint on 50-entry chain: 64-char merkle_root', async () => {
    const chain = await buildLedgerChain(50)
    const snapshot = await captureCheckpoint(chain)
    expect(snapshot.merkle_root).toHaveLength(64)
    expect(snapshot.entry_count).toBe(50)
    expect(snapshot.snapshot_sequence).toBe(seq(50))
    expect(Object.isFrozen(snapshot)).toBe(true)
  })

  it('same chain state → same merkle_root × 3', async () => {
    const chain = await buildLedgerChain(20)
    const s1 = await captureCheckpoint(chain)
    const s2 = await captureCheckpoint(chain)
    const s3 = await captureCheckpoint(chain)
    expect(s1.merkle_root).toBe(s2.merkle_root)
    expect(s2.merkle_root).toBe(s3.merkle_root)
  })

  it('chain-10 vs chain-20: different merkle_roots', async () => {
    const chain10 = await buildLedgerChain(10)
    const chain20 = await buildLedgerChain(20)
    const s10 = await captureCheckpoint(chain10)
    const s20 = await captureCheckpoint(chain20)
    expect(s10.merkle_root).not.toBe(s20.merkle_root)
  })
})
