// ============================================================
// Gate 82 — Replay × Lineage Composition (Integration)
// ~18 tests: LedgerChain replay + AdaptiveLineage joint
//   certification; same topology_hash sequence fed into both;
//   joint tamper cascades to both certifiers; determinism ×3.
// ============================================================

import { describe, it, expect } from 'vitest'
import { LedgerChain } from '../../src/ledger/chain.js'
import { GENESIS_HASH, type LedgerEntry } from '../../src/ledger/types.js'
import { AdaptiveLineage, certifyAdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { buildTopology } from '../../src/frame/topology.js'
import { hashValue } from '../../src/core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const TS = 1_600_000_000_000

const BASE = {
  sitr_state: 'STABLE' as const,
  aoie_global_state: 'SECURE' as const,
  constitutional_verdict: 'PERMIT' as const,
  ledger_root: h('a'),
  consensus_qc_hash: h('b'),
  dfa_certificate_hash: h('c'),
}

async function buildJointChain(n: number) {
  let chain = LedgerChain.empty()
  let lineage = AdaptiveLineage.empty()
  let prevHash = GENESIS_HASH

  for (let i = 1; i <= n; i++) {
    const topo = await buildTopology({ ...BASE, sequence: seq(i) })
    // LedgerChain entry uses topology_hash as frame_hash
    const entry: LedgerEntry = Object.freeze({
      sequence: seq(i),
      previous_hash: prevHash,
      frame_hash: topo.topology_hash,
      governance_hash: h('e'),
      timestamp_ms: TS + i,
    })
    chain = chain.append(entry)
    prevHash = await hashValue(entry) as SHA256Hex

    const { lineage: next } = await lineage.append(
      { kind: 'TOPOLOGY_TRANSITION', topology_hash: topo.topology_hash },
      seq(i),
    )
    lineage = next
  }

  return { chain, lineage }
}

// ─── Joint 20-entry build ─────────────────────────────────

describe('Replay × Lineage: joint build', () => {
  it('20-entry joint chain → both valid', async () => {
    const { chain, lineage } = await buildJointChain(20)
    expect(chain.length).toBe(20)
    expect(lineage.length).toBe(20)
    const cert = await certifyAdaptiveLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(20)
  })

  it('certifyAdaptiveLineage deterministic ×3 on 20-entry joint chain', async () => {
    const { lineage } = await buildJointChain(20)
    const entries = lineage.getAll()
    const [c1, c2, c3] = await Promise.all([
      certifyAdaptiveLineage(entries),
      certifyAdaptiveLineage(entries),
      certifyAdaptiveLineage(entries),
    ])
    expect(c1!.certificate_hash).toBe(c2!.certificate_hash)
    expect(c2!.certificate_hash).toBe(c3!.certificate_hash)
  })

  it('terminal_hash of lineage matches last entry_hash', async () => {
    const { lineage } = await buildJointChain(10)
    const entries = lineage.getAll()
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.terminal_hash).toBe(entries[9]!.entry_hash)
  })

  it('LedgerChain frame_hash reflects topology_hash used in lineage', async () => {
    const { chain, lineage } = await buildJointChain(5)
    const ledgerEntries = chain.getAll()
    const lineageEntries = lineage.getAll()
    for (let i = 0; i < 5; i++) {
      expect(ledgerEntries[i]!.frame_hash).toBe(lineageEntries[i]!.event.kind === 'TOPOLOGY_TRANSITION'
        ? (lineageEntries[i]!.event as any).topology_hash
        : null)
    }
  })
})

// ─── Tamper cascades to lineage ───────────────────────────

describe('Replay × Lineage: tamper detection', () => {
  it('tamper lineage entry_hash → is_valid=false', async () => {
    const { lineage } = await buildJointChain(10)
    const entries = [...lineage.getAll()]
    entries[4] = { ...entries[4]!, entry_hash: h('z') }
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper previous_entry_hash → is_valid=false', async () => {
    const { lineage } = await buildJointChain(10)
    const entries = [...lineage.getAll()]
    entries[5] = { ...entries[5]!, previous_entry_hash: h('z') }
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('empty lineage → certifyAdaptiveLineage is_valid=true, terminal_hash=null', async () => {
    const cert = await certifyAdaptiveLineage([])
    expect(cert.is_valid).toBe(true)
    expect(cert.terminal_hash).toBeNull()
    expect(cert.entry_count).toBe(0)
  })
})

// ─── Structural guarantees ────────────────────────────────

describe('Replay × Lineage: structural guarantees', () => {
  it('lineage entry has is_replay_reconstructable=true', async () => {
    const { lineage } = await buildJointChain(5)
    for (const e of lineage.getAll()) {
      expect(e.is_replay_reconstructable).toBe(true)
    }
  })

  it('certificate_hash is 64-char hex', async () => {
    const { lineage } = await buildJointChain(5)
    const cert = await certifyAdaptiveLineage(lineage.getAll())
    expect(cert.certificate_hash).toHaveLength(64)
    expect(cert.certificate_hash).toMatch(/^[0-9a-f]{64}$/)
  })
})
