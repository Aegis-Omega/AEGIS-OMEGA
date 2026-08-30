// ============================================================
// Gate 30 — Replay Lineage Certifier Tests
// ~28 tests: buildLineageEntry, TopologyLineage, certifyLineage,
//   hash chaining, sequence monotonicity, tamper detection.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { buildTopology, type GovernanceTopology } from '../../src/frame/topology.js'
import {
  buildLineageEntry,
  certifyLineage,
  computeLineageHash,
  TopologyLineage,
  LineageError,
  GENESIS_TOPOLOGY_HASH,
  LINEAGE_SCHEMA_VERSION,
} from '../../src/frame/lineage.js'

// ─── Helpers ───────────────────────────────────────────────

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

async function makeTopology(s: number): Promise<GovernanceTopology> {
  return buildTopology({
    sitr_state: 'STABLE',
    aoie_global_state: 'SECURE',
    constitutional_verdict: 'PERMIT',
    ledger_root: (s.toString(16).padStart(64, '0')) as SHA256Hex,
    consensus_qc_hash: null,
    dfa_certificate_hash: ((s + 100).toString(16).padStart(64, '0')) as SHA256Hex,
    sequence: seq(s),
  })
}

async function buildChain(length: number): Promise<TopologyLineage> {
  let lineage = TopologyLineage.empty()
  for (let i = 1; i <= length; i++) {
    lineage = await lineage.append(await makeTopology(i))
  }
  return lineage
}

// ─── GENESIS_TOPOLOGY_HASH ─────────────────────────────────

describe('constants', () => {
  it('GENESIS_TOPOLOGY_HASH is 64 zero chars', () => {
    expect(GENESIS_TOPOLOGY_HASH).toBe('0'.repeat(64))
    expect(GENESIS_TOPOLOGY_HASH).toHaveLength(64)
  })
})

// ─── buildLineageEntry ─────────────────────────────────────

describe('buildLineageEntry', () => {
  it('first entry uses GENESIS_TOPOLOGY_HASH as previous', async () => {
    const t = await makeTopology(1)
    const entry = await buildLineageEntry(t, GENESIS_TOPOLOGY_HASH, null)
    expect(entry.previous_topology_hash).toBe(GENESIS_TOPOLOGY_HASH)
    expect(entry.topology_hash).toBe(t.topology_hash)
    expect(entry.sequence).toBe(seq(1))
  })

  it('lineage_hash is 64-char hex', async () => {
    const t = await makeTopology(1)
    const entry = await buildLineageEntry(t, GENESIS_TOPOLOGY_HASH, null)
    expect(entry.lineage_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(entry.lineage_hash)).toBe(true)
  })

  it('is frozen and is_replay_reconstructable', async () => {
    const t = await makeTopology(1)
    const entry = await buildLineageEntry(t, GENESIS_TOPOLOGY_HASH, null)
    expect(Object.isFrozen(entry)).toBe(true)
    expect(entry.is_replay_reconstructable).toBe(true)
    expect(entry.schema_version).toBe(LINEAGE_SCHEMA_VERSION)
  })

  it('throws LineageError when sequence is not strictly greater', async () => {
    const t = await makeTopology(1)
    await expect(buildLineageEntry(t, GENESIS_TOPOLOGY_HASH, seq(1)))
      .rejects.toThrow(LineageError)
    await expect(buildLineageEntry(t, GENESIS_TOPOLOGY_HASH, seq(2)))
      .rejects.toThrow(LineageError)
  })

  it('lineage_hash is deterministic × 3', async () => {
    const t = await makeTopology(1)
    const h1 = (await buildLineageEntry(t, GENESIS_TOPOLOGY_HASH, null)).lineage_hash
    const h2 = (await buildLineageEntry(t, GENESIS_TOPOLOGY_HASH, null)).lineage_hash
    const h3 = (await buildLineageEntry(t, GENESIS_TOPOLOGY_HASH, null)).lineage_hash
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })
})

// ─── TopologyLineage ───────────────────────────────────────

describe('TopologyLineage', () => {
  it('empty lineage has length 0 and genesis lastHash', () => {
    const lineage = TopologyLineage.empty()
    expect(lineage.length).toBe(0)
    expect(lineage.lastHash).toBe(GENESIS_TOPOLOGY_HASH)
    expect(lineage.lastSequence).toBeNull()
  })

  it('append builds chain with correct previous_topology_hash links', async () => {
    const lineage = await buildChain(3)
    const entries = lineage.getAll()
    expect(entries).toHaveLength(3)
    expect(entries[0]!.previous_topology_hash).toBe(GENESIS_TOPOLOGY_HASH)
    expect(entries[1]!.previous_topology_hash).toBe(entries[0]!.topology_hash)
    expect(entries[2]!.previous_topology_hash).toBe(entries[1]!.topology_hash)
  })

  it('lastHash after n appends equals nth topology_hash', async () => {
    const lineage = await buildChain(3)
    const entries = lineage.getAll()
    expect(lineage.lastHash).toBe(entries[2]!.topology_hash)
  })

  it('lastSequence tracks latest sequence', async () => {
    const lineage = await buildChain(3)
    expect(lineage.lastSequence).toBe(seq(3))
  })

  it('throws LineageError on non-monotonic sequence', async () => {
    let lineage = TopologyLineage.empty()
    lineage = await lineage.append(await makeTopology(5))
    const earlier = await makeTopology(3)
    await expect(lineage.append(earlier)).rejects.toThrow(LineageError)
  })

  it('append is immutable — original lineage unchanged', async () => {
    const original = TopologyLineage.empty()
    await original.append(await makeTopology(1))
    expect(original.length).toBe(0)
  })
})

// ─── certifyLineage ────────────────────────────────────────

describe('certifyLineage', () => {
  it('empty lineage → is_valid: true, entry_count: 0', async () => {
    const cert = await certifyLineage([])
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(0)
    expect(cert.terminal_hash).toBeNull()
  })

  it('valid 5-entry chain → is_valid: true', async () => {
    const lineage = await buildChain(5)
    const cert = await certifyLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(5)
    expect(cert.terminal_hash).toHaveLength(64)
    expect(cert.is_replay_reconstructable).toBe(true)
  })

  it('certificate is frozen', async () => {
    const lineage = await buildChain(3)
    const cert = await certifyLineage(lineage.getAll())
    expect(Object.isFrozen(cert)).toBe(true)
  })

  it('certificate_hash is deterministic × 3', async () => {
    const lineage = await buildChain(3)
    const entries = lineage.getAll()
    const c1 = await certifyLineage(entries)
    const c2 = await certifyLineage(entries)
    const c3 = await certifyLineage(entries)
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })

  it('tampered previous_topology_hash → is_valid: false', async () => {
    const lineage = await buildChain(3)
    const entries = [...lineage.getAll()]
    const tampered = [
      entries[0]!,
      Object.freeze({ ...entries[1]!, previous_topology_hash: ('f'.repeat(64)) as SHA256Hex }),
      entries[2]!,
    ]
    const cert = await certifyLineage(tampered)
    expect(cert.is_valid).toBe(false)
  })

  it('tampered lineage_hash → is_valid: false', async () => {
    const lineage = await buildChain(3)
    const entries = [...lineage.getAll()]
    const tampered = [
      entries[0]!,
      Object.freeze({ ...entries[1]!, lineage_hash: ('e'.repeat(64)) as SHA256Hex }),
      entries[2]!,
    ]
    const cert = await certifyLineage(tampered)
    expect(cert.is_valid).toBe(false)
  })

  it('different chain lengths produce different certificate_hash', async () => {
    const c3 = await certifyLineage((await buildChain(3)).getAll())
    const c4 = await certifyLineage((await buildChain(4)).getAll())
    expect(c3.certificate_hash).not.toBe(c4.certificate_hash)
  })
})

// ─── computeLineageHash ────────────────────────────────────

describe('computeLineageHash', () => {
  it('is deterministic × 3', async () => {
    const h1 = await computeLineageHash(('a'.repeat(64)) as SHA256Hex, GENESIS_TOPOLOGY_HASH, seq(1))
    const h2 = await computeLineageHash(('a'.repeat(64)) as SHA256Hex, GENESIS_TOPOLOGY_HASH, seq(1))
    const h3 = await computeLineageHash(('a'.repeat(64)) as SHA256Hex, GENESIS_TOPOLOGY_HASH, seq(1))
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('different inputs produce different hashes', async () => {
    const h1 = await computeLineageHash(('a'.repeat(64)) as SHA256Hex, GENESIS_TOPOLOGY_HASH, seq(1))
    const h2 = await computeLineageHash(('b'.repeat(64)) as SHA256Hex, GENESIS_TOPOLOGY_HASH, seq(1))
    expect(h1).not.toBe(h2)
  })
})
