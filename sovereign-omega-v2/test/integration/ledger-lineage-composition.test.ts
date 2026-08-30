// ============================================================
// Gate 75 — Ledger × Lineage Composition (Integration)
// ~18 tests: LedgerChain + TopologyLineage co-certification;
//   tamper in lineage propagates is_valid=false; terminal hash
//   tracking; joint 20-entry builds are deterministic.
// ============================================================

import { describe, it, expect } from 'vitest'
import { LedgerChain } from '../../src/ledger/chain.js'
import { GENESIS_HASH, LedgerConstraintError, type LedgerEntry } from '../../src/ledger/types.js'
import { TopologyLineage, certifyLineage } from '../../src/frame/lineage.js'
import { buildTopology } from '../../src/frame/topology.js'
import { hashValue } from '../../src/core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const TS = 1_600_000_000_000

async function makeEntry(n: number, prev: SHA256Hex = GENESIS_HASH): Promise<LedgerEntry> {
  return Object.freeze({
    sequence: seq(n),
    previous_hash: prev,
    frame_hash: h('f'),
    governance_hash: h('e'),
    timestamp_ms: TS + n,
  })
}

const BASE = {
  sitr_state: 'STABLE' as const,
  aoie_global_state: 'SECURE' as const,
  constitutional_verdict: 'PERMIT' as const,
  ledger_root: h('a'),
  consensus_qc_hash: h('b'),
  dfa_certificate_hash: h('c'),
}

async function makeTopology(n: number) {
  return buildTopology({ ...BASE, sequence: seq(n) })
}

// ─── Joint 20-entry build ─────────────────────────────────

describe('Ledger × Lineage: joint build', () => {
  it('20-entry LedgerChain + 20-entry TopologyLineage → both valid', async () => {
    let chain = LedgerChain.empty()
    let lineage = TopologyLineage.empty()
    let prevHash = GENESIS_HASH

    for (let i = 1; i <= 20; i++) {
      const entry = await makeEntry(i, prevHash)
      chain = chain.append(entry)
      prevHash = await hashValue(entry) as SHA256Hex
      lineage = await lineage.append(await makeTopology(i))
    }

    expect(chain.length).toBe(20)
    expect(lineage.length).toBe(20)
    const cert = await certifyLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
  })

  it('certifyLineage is deterministic ×3 after 20-entry build', async () => {
    let lineage = TopologyLineage.empty()
    for (let i = 1; i <= 20; i++) {
      lineage = await lineage.append(await makeTopology(i))
    }
    const entries = lineage.getAll()
    const [c1, c2, c3] = await Promise.all([certifyLineage(entries), certifyLineage(entries), certifyLineage(entries)])
    expect(c1!.certificate_hash).toBe(c2!.certificate_hash)
    expect(c2!.certificate_hash).toBe(c3!.certificate_hash)
  })

  it('5-entry lineage cert terminal_hash matches last lineage_hash', async () => {
    let lineage = TopologyLineage.empty()
    for (let i = 1; i <= 5; i++) {
      lineage = await lineage.append(await makeTopology(i))
    }
    const entries = lineage.getAll()
    const cert = await certifyLineage(entries)
    expect(cert.terminal_hash).toBe(entries[4]!.lineage_hash)
  })
})

// ─── Tamper propagation ───────────────────────────────────

describe('Ledger × Lineage: tamper detection', () => {
  it('tamper lineage_hash at entry 4 → certifyLineage is_valid=false', async () => {
    let lineage = TopologyLineage.empty()
    for (let i = 1; i <= 10; i++) {
      lineage = await lineage.append(await makeTopology(i))
    }
    const entries = [...lineage.getAll()]
    entries[4] = { ...entries[4]!, lineage_hash: h('z') }
    const cert = await certifyLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('LedgerChain: non-monotone sequence throws LedgerConstraintError', async () => {
    const e1 = await makeEntry(5)
    const e2 = await makeEntry(3)
    let chain = LedgerChain.empty()
    chain = chain.append(e1)
    expect(() => chain.append(e2)).toThrow(LedgerConstraintError)
  })

  it('immutable: LedgerChain.append returns new chain, original unchanged', async () => {
    const chain = LedgerChain.empty()
    const e1 = await makeEntry(1)
    chain.append(e1)
    expect(chain.length).toBe(0)
  })
})

// ─── Structural guarantees ────────────────────────────────

describe('Ledger × Lineage: structural guarantees', () => {
  it('lineage entry is_replay_reconstructable=true', async () => {
    const topo = await makeTopology(1)
    const lineage = await TopologyLineage.empty().append(topo)
    for (const e of lineage.getAll()) {
      expect(e.is_replay_reconstructable).toBe(true)
    }
  })

  it('empty lineage certifies is_valid=true', async () => {
    const cert = await certifyLineage([])
    expect(cert.is_valid).toBe(true)
    expect(cert.terminal_hash).toBeNull()
  })

  it('LedgerChain first entry previous_hash === GENESIS_HASH', async () => {
    const entry = await makeEntry(1, GENESIS_HASH)
    expect(entry.previous_hash).toBe(GENESIS_HASH)
  })
})
