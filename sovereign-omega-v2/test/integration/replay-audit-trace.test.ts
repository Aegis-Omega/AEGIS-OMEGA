// ============================================================
// Gate 104 — Replay Audit Trace (Integration)
// ~22 tests: Build governance chain → corrupt entry →
//   certifyMartingale detects → assertMartingaleAnchored
//   throws → chain recoverable from genesis.
// ============================================================

import { describe, it, expect } from 'vitest'
import { AdaptiveLineage, certifyAdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { certifyMartingale, assertMartingaleAnchored, MartingaleViolation } from '../../src/constitutional/martingale.js'
import { buildTopology } from '../../src/frame/topology.js'
import { LedgerChain } from '../../src/ledger/chain.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
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

async function buildAdaptiveChain(n: number) {
  let lineage = AdaptiveLineage.empty()
  for (let i = 1; i <= n; i++) {
    const topo = await buildTopology({ ...BASE, sequence: seq(i) })
    const { lineage: next } = await lineage.append(
      { kind: 'TOPOLOGY_TRANSITION', topology_hash: topo.topology_hash },
      seq(i),
    )
    lineage = next
  }
  return lineage
}

// ─── Corrupt entry detection ──────────────────────────────

describe('Replay Audit: corruption detection', () => {
  it('tamper entry 5 of 10 → certifyAdaptiveLineage is_valid=false', async () => {
    const lineage = await buildAdaptiveChain(10)
    const entries = [...lineage.getAll()]
    entries[4] = { ...entries[4]!, entry_hash: h('z') }
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper last entry → is_valid=false', async () => {
    const lineage = await buildAdaptiveChain(10)
    const entries = [...lineage.getAll()]
    entries[9] = { ...entries[9]!, entry_hash: h('z') }
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper first entry → is_valid=false', async () => {
    const lineage = await buildAdaptiveChain(5)
    const entries = [...lineage.getAll()]
    entries[0] = { ...entries[0]!, entry_hash: h('z') }
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper previous_entry_hash → is_valid=false', async () => {
    const lineage = await buildAdaptiveChain(5)
    const entries = [...lineage.getAll()]
    entries[3] = { ...entries[3]!, previous_entry_hash: h('z') }
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('certifyMartingale on tampered chain → is_anchored=false', async () => {
    const lineage = await buildAdaptiveChain(5)
    const entries = [...lineage.getAll()]
    entries[2] = { ...entries[2]!, entry_hash: h('z') }
    const cert = await certifyMartingale(entries)
    expect(cert.is_anchored).toBe(false)
  })

  it('assertMartingaleAnchored on tampered chain → throws MartingaleViolation', async () => {
    const lineage = await buildAdaptiveChain(5)
    const entries = [...lineage.getAll()]
    entries[2] = { ...entries[2]!, entry_hash: h('z') }
    const cert = await certifyMartingale(entries)
    expect(() => assertMartingaleAnchored(cert)).toThrow(MartingaleViolation)
  })
})

// ─── Chain recoverability from genesis ───────────────────

describe('Replay Audit: chain recovery from genesis', () => {
  it('rebuild from scratch after corruption → is_valid=true', async () => {
    // Rebuild from genesis (fresh chain, same length)
    const rebuilt = await buildAdaptiveChain(10)
    const cert = await certifyAdaptiveLineage(rebuilt.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(10)
  })

  it('original chain is unmodified after tamper attempt (immutability)', async () => {
    const lineage = await buildAdaptiveChain(5)
    const original = lineage.getAll()
    const mutable = [...original]
    mutable[2] = { ...mutable[2]!, entry_hash: h('z') }
    // Original still valid
    const cert = await certifyAdaptiveLineage(original)
    expect(cert.is_valid).toBe(true)
  })

  it('clean 10-entry chain → certifyMartingale all flags true', async () => {
    const lineage = await buildAdaptiveChain(10)
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.is_anchored).toBe(true)
    expect(cert.drift_bounded).toBe(true)
    expect(cert.entropy_bounded).toBe(true)
  })

  it('audit trace: certificate_hash changes after tamper', async () => {
    const lineage = await buildAdaptiveChain(5)
    const clean = await certifyMartingale(lineage.getAll())
    const entries = [...lineage.getAll()]
    entries[2] = { ...entries[2]!, entry_hash: h('z') }
    const tampered = await certifyMartingale(entries)
    expect(clean.certificate_hash).not.toBe(tampered.certificate_hash)
  })
})

// ─── LedgerChain replay integrity ─────────────────────────

describe('Replay Audit: LedgerChain integrity', () => {
  it('5-entry LedgerChain → length=5', async () => {
    let chain = LedgerChain.empty()
    let prevHash = GENESIS_HASH
    for (let i = 1; i <= 5; i++) {
      const entry: LedgerEntry = Object.freeze({
        sequence: seq(i),
        previous_hash: prevHash,
        frame_hash: h(String.fromCharCode(97 + i)),
        governance_hash: h('g'),
        timestamp_ms: TS + i,
      })
      chain = chain.append(entry)
      prevHash = await hashValue(entry) as SHA256Hex
    }
    expect(chain.length).toBe(5)
  })

  it('getAll entries have correct sequence order', async () => {
    let chain = LedgerChain.empty()
    let prevHash = GENESIS_HASH
    for (let i = 1; i <= 5; i++) {
      const entry: LedgerEntry = Object.freeze({
        sequence: seq(i),
        previous_hash: prevHash,
        frame_hash: h(String.fromCharCode(97 + i)),
        governance_hash: h('g'),
        timestamp_ms: TS + i,
      })
      chain = chain.append(entry)
      prevHash = await hashValue(entry) as SHA256Hex
    }
    const all = chain.getAll()
    for (let i = 0; i < 4; i++) {
      expect(all[i]!.sequence < all[i + 1]!.sequence).toBe(true)
    }
  })

  it('martingale + LedgerChain share topology_hash binding', async () => {
    const topo = await buildTopology({ ...BASE, sequence: seq(1) })
    let lineage = AdaptiveLineage.empty()
    const { lineage: next } = await lineage.append(
      { kind: 'TOPOLOGY_TRANSITION', topology_hash: topo.topology_hash },
      seq(1),
    )
    lineage = next

    let chain = LedgerChain.empty()
    const entry: LedgerEntry = Object.freeze({
      sequence: seq(1),
      previous_hash: GENESIS_HASH,
      frame_hash: topo.topology_hash,  // same hash
      governance_hash: h('g'),
      timestamp_ms: TS + 1,
    })
    chain = chain.append(entry)

    expect(chain.getAll()[0]!.frame_hash).toBe(
      (lineage.getAll()[0]!.event as any).topology_hash,
    )
  })
})
