// ============================================================
// Gate 38 — Adaptive Lineage Tests
// ~28 tests: AdaptiveLineage.empty, append (TOPOLOGY/CAPABILITY),
//   hash chaining, sequence monotonicity, certifyAdaptiveLineage,
//   tamper detection, determinism.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import {
  AdaptiveLineage,
  AdaptiveLineageError,
  certifyAdaptiveLineage,
  GENESIS_TOPOLOGY_HASH,
  ADAPTIVE_LINEAGE_SCHEMA_VERSION,
  type AdaptiveEvent,
} from '../../src/frame/adaptive-lineage.js'

// ─── Helpers ───────────────────────────────────────────────

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }
function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }

const TOPO_EVENT: AdaptiveEvent = { kind: 'TOPOLOGY_TRANSITION', topology_hash: h('a') }
const CAP_APPROVED: AdaptiveEvent = { kind: 'CAPABILITY_EVOLUTION', proposal_id: h('b'), verdict: 'APPROVED' }
const CAP_REJECTED: AdaptiveEvent = { kind: 'CAPABILITY_EVOLUTION', proposal_id: h('c'), verdict: 'REJECTED' }

async function buildChain(length: number): Promise<AdaptiveLineage> {
  let lineage = AdaptiveLineage.empty()
  for (let i = 1; i <= length; i++) {
    const event: AdaptiveEvent = { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(i.toString(16)) }
    const { lineage: next } = await lineage.append(event, seq(i))
    lineage = next
  }
  return lineage
}

// ─── Constants ─────────────────────────────────────────────

describe('constants', () => {
  it('ADAPTIVE_LINEAGE_SCHEMA_VERSION is 1.0.0', () => {
    expect(ADAPTIVE_LINEAGE_SCHEMA_VERSION).toBe('1.0.0')
  })

  it('GENESIS_TOPOLOGY_HASH is 64 zero chars', () => {
    expect(GENESIS_TOPOLOGY_HASH).toBe('0'.repeat(64))
  })
})

// ─── AdaptiveLineageError ──────────────────────────────────

describe('AdaptiveLineageError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new AdaptiveLineageError('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('AdaptiveLineageError')
  })
})

// ─── AdaptiveLineage.empty() ───────────────────────────────

describe('AdaptiveLineage.empty()', () => {
  it('length is 0', () => {
    expect(AdaptiveLineage.empty().length).toBe(0)
  })

  it('lastHash is GENESIS_TOPOLOGY_HASH', () => {
    expect(AdaptiveLineage.empty().lastHash).toBe(GENESIS_TOPOLOGY_HASH)
  })

  it('lastSequence is null', () => {
    expect(AdaptiveLineage.empty().lastSequence).toBeNull()
  })

  it('getAll() returns empty array', () => {
    expect(AdaptiveLineage.empty().getAll()).toHaveLength(0)
  })
})

// ─── append — TOPOLOGY_TRANSITION ─────────────────────────

describe('AdaptiveLineage.append() — TOPOLOGY_TRANSITION', () => {
  it('entry is frozen', async () => {
    const { entry } = await AdaptiveLineage.empty().append(TOPO_EVENT, seq(1))
    expect(Object.isFrozen(entry)).toBe(true)
  })

  it('entry_hash is 64-char hex', async () => {
    const { entry } = await AdaptiveLineage.empty().append(TOPO_EVENT, seq(1))
    expect(entry.entry_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(entry.entry_hash)).toBe(true)
  })

  it('first entry previous_entry_hash is GENESIS_TOPOLOGY_HASH', async () => {
    const { entry } = await AdaptiveLineage.empty().append(TOPO_EVENT, seq(1))
    expect(entry.previous_entry_hash).toBe(GENESIS_TOPOLOGY_HASH)
  })

  it('second entry previous_entry_hash equals first entry_hash', async () => {
    const { lineage: l1, entry: e1 } = await AdaptiveLineage.empty().append(TOPO_EVENT, seq(1))
    const { entry: e2 } = await l1.append(TOPO_EVENT, seq(2))
    expect(e2.previous_entry_hash).toBe(e1.entry_hash)
  })

  it('lastHash updates after append', async () => {
    const { lineage, entry } = await AdaptiveLineage.empty().append(TOPO_EVENT, seq(1))
    expect(lineage.lastHash).toBe(entry.entry_hash)
  })

  it('lastSequence updates after append', async () => {
    const { lineage } = await AdaptiveLineage.empty().append(TOPO_EVENT, seq(7))
    expect(lineage.lastSequence).toBe(seq(7))
  })

  it('entry_hash is deterministic × 3', async () => {
    const h1 = (await AdaptiveLineage.empty().append(TOPO_EVENT, seq(1))).entry.entry_hash
    const h2 = (await AdaptiveLineage.empty().append(TOPO_EVENT, seq(1))).entry.entry_hash
    const h3 = (await AdaptiveLineage.empty().append(TOPO_EVENT, seq(1))).entry.entry_hash
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('original lineage unchanged after append (immutable)', async () => {
    const original = AdaptiveLineage.empty()
    await original.append(TOPO_EVENT, seq(1))
    expect(original.length).toBe(0)
    expect(original.lastSequence).toBeNull()
  })

  it('non-monotonic sequence throws AdaptiveLineageError', async () => {
    const { lineage } = await AdaptiveLineage.empty().append(TOPO_EVENT, seq(5))
    await expect(lineage.append(TOPO_EVENT, seq(3))).rejects.toThrow(AdaptiveLineageError)
  })

  it('schema_version is 1.0.0', async () => {
    const { entry } = await AdaptiveLineage.empty().append(TOPO_EVENT, seq(1))
    expect(entry.schema_version).toBe('1.0.0')
  })

  it('is_replay_reconstructable is true', async () => {
    const { entry } = await AdaptiveLineage.empty().append(TOPO_EVENT, seq(1))
    expect(entry.is_replay_reconstructable).toBe(true)
  })
})

// ─── append — CAPABILITY_EVOLUTION ────────────────────────

describe('AdaptiveLineage.append() — CAPABILITY_EVOLUTION', () => {
  it('APPROVED verdict entry is accepted', async () => {
    const { entry } = await AdaptiveLineage.empty().append(CAP_APPROVED, seq(1))
    expect(entry.event.kind).toBe('CAPABILITY_EVOLUTION')
    if (entry.event.kind === 'CAPABILITY_EVOLUTION') {
      expect(entry.event.verdict).toBe('APPROVED')
    }
  })

  it('REJECTED verdict entry is accepted', async () => {
    const { entry } = await AdaptiveLineage.empty().append(CAP_REJECTED, seq(1))
    if (entry.event.kind === 'CAPABILITY_EVOLUTION') {
      expect(entry.event.verdict).toBe('REJECTED')
    }
  })
})

// ─── Mixed chain ───────────────────────────────────────────

describe('mixed AdaptiveEvent chain', () => {
  it('3-entry mixed chain builds correctly', async () => {
    let lineage = AdaptiveLineage.empty()
    const { lineage: l1, entry: e1 } = await lineage.append(TOPO_EVENT, seq(1))
    const { lineage: l2, entry: e2 } = await l1.append(CAP_APPROVED, seq(2))
    const { lineage: l3, entry: e3 } = await l2.append(TOPO_EVENT, seq(3))
    expect(l3.length).toBe(3)
    expect(e1.previous_entry_hash).toBe(GENESIS_TOPOLOGY_HASH)
    expect(e2.previous_entry_hash).toBe(e1.entry_hash)
    expect(e3.previous_entry_hash).toBe(e2.entry_hash)
  })
})

// ─── certifyAdaptiveLineage ────────────────────────────────

describe('certifyAdaptiveLineage', () => {
  it('empty lineage → is_valid: true, entry_count: 0, terminal_hash: null', async () => {
    const cert = await certifyAdaptiveLineage([])
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(0)
    expect(cert.terminal_hash).toBeNull()
  })

  it('valid 5-entry chain → is_valid: true', async () => {
    const lineage = await buildChain(5)
    const cert = await certifyAdaptiveLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(5)
    expect(cert.terminal_hash).toHaveLength(64)
  })

  it('certificate is frozen', async () => {
    const cert = await certifyAdaptiveLineage([])
    expect(Object.isFrozen(cert)).toBe(true)
  })

  it('is_replay_reconstructable is true', async () => {
    const cert = await certifyAdaptiveLineage([])
    expect(cert.is_replay_reconstructable).toBe(true)
  })

  it('certificate_hash is deterministic × 3', async () => {
    const lineage = await buildChain(3)
    const entries = lineage.getAll()
    const c1 = await certifyAdaptiveLineage(entries)
    const c2 = await certifyAdaptiveLineage(entries)
    const c3 = await certifyAdaptiveLineage(entries)
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })

  it('tampered previous_entry_hash → is_valid: false', async () => {
    const lineage = await buildChain(3)
    const entries = [...lineage.getAll()]
    const tampered = [
      entries[0]!,
      Object.freeze({ ...entries[1]!, previous_entry_hash: h('f') }),
      entries[2]!,
    ]
    const cert = await certifyAdaptiveLineage(tampered)
    expect(cert.is_valid).toBe(false)
  })

  it('tampered entry_hash → is_valid: false', async () => {
    const lineage = await buildChain(3)
    const entries = [...lineage.getAll()]
    const tampered = [
      entries[0]!,
      Object.freeze({ ...entries[1]!, entry_hash: h('e') }),
      entries[2]!,
    ]
    const cert = await certifyAdaptiveLineage(tampered)
    expect(cert.is_valid).toBe(false)
  })
})
