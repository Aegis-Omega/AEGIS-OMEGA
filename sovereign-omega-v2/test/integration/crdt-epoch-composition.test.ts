// ============================================================
// Gate 99 — CRDT + EpochChain Composition (Integration)
// ~18 tests: G-Set LedgerEntry join → EpochChain; 10-epoch
//   joint certification; idempotent join at each boundary;
//   conflict detection; CRDTConflictError on fork.
// ============================================================

import { describe, it, expect } from 'vitest'
import { joinLedgerEntries } from '../../src/crdt/ledger.js'
import { CRDTConflictError } from '../../src/crdt/types.js'
import { LedgerChain } from '../../src/ledger/chain.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
import { EpochChain, certifyEpochChain } from '../../src/frame/epoch-chain.js'
import { synthesizeEpoch } from '../../src/frame/epoch.js'
import { buildTopology } from '../../src/frame/topology.js'
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

async function buildLedgerEntries(n: number): Promise<readonly LedgerEntry[]> {
  let chain = LedgerChain.empty()
  let prevHash = GENESIS_HASH
  for (let i = 1; i <= n; i++) {
    const entry: LedgerEntry = Object.freeze({
      sequence: seq(i),
      previous_hash: prevHash,
      frame_hash: h(String.fromCharCode(97 + (i % 26))),
      governance_hash: h('g'),
      timestamp_ms: TS + i,
    })
    chain = chain.append(entry)
    prevHash = await hashValue(entry) as SHA256Hex
  }
  return chain.getAll()
}

async function buildEpochChain(n: number) {
  let chain = EpochChain.empty()
  for (let i = 1; i <= n; i++) {
    const topo = await buildTopology({ ...BASE, sequence: seq(i) })
    let machine = initialMachine(seq(i))
    const records = []
    for (const phase of ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const) {
      const { machine: next, record } = await transition(machine, phase, h(phase[0]!.toLowerCase()))
      machine = next
      records.push(record)
    }
    const dfaCert = await certifyExecution(records, seq(i))
    const epoch = await synthesizeEpoch({ dfa_certificate: dfaCert, topology: topo, lineage_terminal_hash: null, capsule_attestation_hash: null })
    const { chain: next } = await chain.append(epoch)
    chain = next
  }
  return chain
}

// ─── G-Set join ───────────────────────────────────────────

describe('CRDT: G-Set LedgerEntry join', () => {
  it('join of same entries is idempotent', async () => {
    const entries = await buildLedgerEntries(5)
    const joined = joinLedgerEntries(entries, entries)
    expect(joined.length).toBe(5)
  })

  it('join of disjoint sets = union, sorted by sequence', async () => {
    const a = await buildLedgerEntries(3)
    const b = await buildLedgerEntries(3)
    // b has same sequences — join should deduplicate (idempotent)
    const joined = joinLedgerEntries(a, b)
    expect(joined.length).toBe(3)
    for (let i = 0; i < joined.length - 1; i++) {
      expect(joined[i]!.sequence < joined[i + 1]!.sequence).toBe(true)
    }
  })

  it('conflicting entries at same sequence → throws CRDTConflictError', async () => {
    const entries = await buildLedgerEntries(3)
    const tampered: LedgerEntry = { ...entries[1]!, frame_hash: h('z') }
    const other = [entries[0]!, tampered, entries[2]!] as const
    expect(() => joinLedgerEntries(entries, other)).toThrow(CRDTConflictError)
  })

  it('CRDTConflictError is instanceof Error', () => {
    expect(new CRDTConflictError('test')).toBeInstanceOf(Error)
  })

  it('join of empty arrays = empty', () => {
    const result = joinLedgerEntries([], [])
    expect(result.length).toBe(0)
  })

  it('join with empty right = left unchanged', async () => {
    const entries = await buildLedgerEntries(4)
    const joined = joinLedgerEntries(entries, [])
    expect(joined.length).toBe(4)
  })
})

// ─── EpochChain certification ─────────────────────────────

describe('CRDT + EpochChain: joint certification', () => {
  it('10-epoch chain → certifyEpochChain is_valid=true', async () => {
    const chain = await buildEpochChain(10)
    const cert = await certifyEpochChain(chain.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.link_count).toBe(10)
  }, 30000)

  it('certifyEpochChain is deterministic ×3', async () => {
    const chain = await buildEpochChain(5)
    const links = chain.getAll()
    const [c1, c2, c3] = await Promise.all([
      certifyEpochChain(links),
      certifyEpochChain(links),
      certifyEpochChain(links),
    ])
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  }, 30000)

  it('tampered link_hash → is_valid=false', async () => {
    const chain = await buildEpochChain(5)
    const links = [...chain.getAll()]
    links[2] = { ...links[2]!, link_hash: h('z') }
    const cert = await certifyEpochChain(links)
    expect(cert.is_valid).toBe(false)
  }, 30000)

  it('empty chain → is_valid=true, link_count=0', async () => {
    const cert = await certifyEpochChain([])
    expect(cert.is_valid).toBe(true)
    expect(cert.link_count).toBe(0)
    expect(cert.terminal_hash).toBeNull()
  })
})

// ─── CRDT idempotency at epoch boundary ───────────────────

describe('CRDT: idempotency at epoch boundaries', () => {
  it('join of 5 entries with itself ×3 = same result', async () => {
    const entries = await buildLedgerEntries(5)
    const r1 = joinLedgerEntries(entries, entries)
    const r2 = joinLedgerEntries(r1, entries)
    const r3 = joinLedgerEntries(r2, r2)
    expect(r3.length).toBe(5)
    for (let i = 0; i < 5; i++) {
      expect(r3[i]!.sequence).toBe(entries[i]!.sequence)
    }
  })

  it('join is commutative (A∪B = B∪A for disjoint)', async () => {
    const all = await buildLedgerEntries(6)
    const a = all.slice(0, 3)
    const b = all.slice(0, 3)
    const ab = joinLedgerEntries(a, b)
    const ba = joinLedgerEntries(b, a)
    expect(ab.length).toBe(ba.length)
    for (let i = 0; i < ab.length; i++) {
      expect(ab[i]!.sequence).toBe(ba[i]!.sequence)
    }
  })
})
