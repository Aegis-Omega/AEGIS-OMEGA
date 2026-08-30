// ============================================================
// SOVEREIGN OMEGA — Replay Lineage Certifier tests
// EPISTEMIC TIER: T0
//
// Tests for frame/lineage.ts:
//   LineageError          — error subclass
//   computeLineageHash    — deterministic 64-char hex
//   buildLineageEntry     — fields, frozen, throws on non-monotonic sequence
//   TopologyLineage       — empty state, append, hash linking, sequence guard
//   certifyLineage        — empty, valid chain, hash-chain break, seq non-monotone
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  LineageError,
  computeLineageHash,
  buildLineageEntry,
  TopologyLineage,
  certifyLineage,
  GENESIS_TOPOLOGY_HASH,
  LINEAGE_SCHEMA_VERSION,
} from '../../src/frame/lineage.js'
import type { LineageEntry } from '../../src/frame/lineage.js'
import type { GovernanceTopology } from '../../src/frame/topology.js'
import type { SequenceNumber, SHA256Hex } from '../../src/core/types.js'

const SEQ = (n: number) => BigInt(n) as unknown as SequenceNumber
const H1 = 'a'.repeat(64) as SHA256Hex
const H2 = 'b'.repeat(64) as SHA256Hex
const H3 = 'c'.repeat(64) as SHA256Hex

function makeTopology(seq: number, hash: SHA256Hex): GovernanceTopology {
  return { topology_hash: hash, sequence: SEQ(seq) } as unknown as GovernanceTopology
}

// ── LineageError ───────────────────────────────────────────

describe('LineageError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new LineageError('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('LineageError')
    expect(e.message).toBe('test')
  })
})

// ── computeLineageHash ─────────────────────────────────────

describe('computeLineageHash', () => {
  it('returns a 64-char hex string', async () => {
    const h = await computeLineageHash(H1, GENESIS_TOPOLOGY_HASH, SEQ(1))
    expect(h).toMatch(/^[0-9a-f]{64}$/)
  })

  it('is deterministic — three identical calls produce equal output', async () => {
    const [h1, h2, h3] = await Promise.all([
      computeLineageHash(H1, GENESIS_TOPOLOGY_HASH, SEQ(1)),
      computeLineageHash(H1, GENESIS_TOPOLOGY_HASH, SEQ(1)),
      computeLineageHash(H1, GENESIS_TOPOLOGY_HASH, SEQ(1)),
    ])
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('different inputs produce different hashes', async () => {
    const h1 = await computeLineageHash(H1, GENESIS_TOPOLOGY_HASH, SEQ(1))
    const h2 = await computeLineageHash(H2, GENESIS_TOPOLOGY_HASH, SEQ(1))
    expect(h1).not.toBe(h2)
  })
})

// ── buildLineageEntry ──────────────────────────────────────

describe('buildLineageEntry', () => {
  it('returns a frozen entry with correct fields', async () => {
    const entry = await buildLineageEntry(makeTopology(1, H1), GENESIS_TOPOLOGY_HASH, null)
    expect(Object.isFrozen(entry)).toBe(true)
    expect(entry.topology_hash).toBe(H1)
    expect(entry.previous_topology_hash).toBe(GENESIS_TOPOLOGY_HASH)
    expect(entry.sequence).toBe(SEQ(1))
    expect(entry.lineage_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(entry.schema_version).toBe(LINEAGE_SCHEMA_VERSION)
    expect(entry.is_replay_reconstructable).toBe(true)
  })

  it('throws LineageError when sequence is not strictly greater than prevSequence', async () => {
    await expect(
      buildLineageEntry(makeTopology(5, H1), GENESIS_TOPOLOGY_HASH, SEQ(5))
    ).rejects.toThrow(LineageError)
  })

  it('throws LineageError when sequence is less than prevSequence', async () => {
    await expect(
      buildLineageEntry(makeTopology(3, H1), GENESIS_TOPOLOGY_HASH, SEQ(7))
    ).rejects.toThrow(LineageError)
  })

  it('succeeds when prevSequence is null (first entry)', async () => {
    await expect(
      buildLineageEntry(makeTopology(1, H1), GENESIS_TOPOLOGY_HASH, null)
    ).resolves.not.toThrow()
  })
})

// ── TopologyLineage ────────────────────────────────────────

describe('TopologyLineage — empty()', () => {
  it('length is 0', () => {
    expect(TopologyLineage.empty().length).toBe(0)
  })

  it('lastHash equals GENESIS_TOPOLOGY_HASH', () => {
    expect(TopologyLineage.empty().lastHash).toBe(GENESIS_TOPOLOGY_HASH)
  })

  it('lastSequence is null', () => {
    expect(TopologyLineage.empty().lastSequence).toBeNull()
  })

  it('getAll() returns an empty array', () => {
    expect(TopologyLineage.empty().getAll()).toHaveLength(0)
  })
})

describe('TopologyLineage — append()', () => {
  it('appended entry has previous_topology_hash = GENESIS_TOPOLOGY_HASH', async () => {
    const l1 = await TopologyLineage.empty().append(makeTopology(1, H1))
    expect(l1.length).toBe(1)
    expect(l1.getAll()[0]!.previous_topology_hash).toBe(GENESIS_TOPOLOGY_HASH)
    expect(l1.lastHash).toBe(H1)
    expect(l1.lastSequence).toBe(SEQ(1))
  })

  it('second entry previous_topology_hash links to first entry topology_hash', async () => {
    const l1 = await TopologyLineage.empty().append(makeTopology(1, H1))
    const l2 = await l1.append(makeTopology(2, H2))
    expect(l2.length).toBe(2)
    expect(l2.getAll()[1]!.previous_topology_hash).toBe(H1)
    expect(l2.lastHash).toBe(H2)
  })

  it('three appends produce a 3-entry lineage', async () => {
    const l1 = await TopologyLineage.empty().append(makeTopology(1, H1))
    const l2 = await l1.append(makeTopology(2, H2))
    const l3 = await l2.append(makeTopology(3, H3))
    expect(l3.length).toBe(3)
    expect(l3.lastSequence).toBe(SEQ(3))
  })

  it('throws LineageError on non-monotonic sequence', async () => {
    const l1 = await TopologyLineage.empty().append(makeTopology(5, H1))
    await expect(l1.append(makeTopology(3, H2))).rejects.toThrow(LineageError)
  })
})

// ── certifyLineage ─────────────────────────────────────────

describe('certifyLineage', () => {
  it('empty chain → is_valid=true, entry_count=0, terminal_hash=null', async () => {
    const cert = await certifyLineage([])
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(0)
    expect(cert.terminal_hash).toBeNull()
    expect(cert.is_replay_reconstructable).toBe(true)
    expect(Object.isFrozen(cert)).toBe(true)
  })

  it('valid 3-entry chain → is_valid=true, entry_count=3', async () => {
    const l1 = await TopologyLineage.empty().append(makeTopology(1, H1))
    const l2 = await l1.append(makeTopology(2, H2))
    const l3 = await l2.append(makeTopology(3, H3))
    const cert = await certifyLineage(l3.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(3)
    expect(cert.terminal_hash).toBe(l3.getAll()[2]!.lineage_hash)
  })

  it('tampered previous_topology_hash → is_valid=false', async () => {
    const l1 = await TopologyLineage.empty().append(makeTopology(1, H1))
    const l2 = await l1.append(makeTopology(2, H2))
    const entries = l2.getAll()
    const tampered: readonly LineageEntry[] = [
      entries[0]!,
      { ...entries[1]!, previous_topology_hash: H3 },  // breaks the chain
    ]
    const cert = await certifyLineage(tampered)
    expect(cert.is_valid).toBe(false)
  })

  it('tampered lineage_hash → is_valid=false', async () => {
    const l1 = await TopologyLineage.empty().append(makeTopology(1, H1))
    const entries = l1.getAll()
    const tampered: readonly LineageEntry[] = [
      { ...entries[0]!, lineage_hash: 'f'.repeat(64) as SHA256Hex },
    ]
    const cert = await certifyLineage(tampered)
    expect(cert.is_valid).toBe(false)
  })

  it('is deterministic — three certifications of the same chain produce equal certificate_hash', async () => {
    const l1 = await TopologyLineage.empty().append(makeTopology(1, H1))
    const entries = l1.getAll()
    const [c1, c2, c3] = await Promise.all([
      certifyLineage(entries),
      certifyLineage(entries),
      certifyLineage(entries),
    ])
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })
})
