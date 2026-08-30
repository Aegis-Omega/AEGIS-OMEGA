// ============================================================
// Gate 60 — Adaptive Lineage Scale
// ~22 tests: AdaptiveLineage and certifyAdaptiveLineage at
//   100-entry scale; 100-entry mixed chain (alternating
//   TOPOLOGY_TRANSITION + CAPABILITY_EVOLUTION); tamper
//   entry_hash at position 50 → is_valid=false; tamper
//   previous_entry_hash at position 50 → is_valid=false;
//   certificate_hash length-sensitive (100 ≠ 99 entries);
//   certify × 3 → identical certificate_hash.
//
// Gaps filled vs test/unit/adaptive-lineage.test.ts:
//   - 100-entry TOPOLOGY chain → certify → is_valid=true
//   - 100-entry mixed chain → certify → is_valid=true
//   - Tamper entry_hash mid-chain (pos 50) → is_valid=false
//   - Tamper previous_entry_hash mid-chain → is_valid=false
//   - Tamper first entry → is_valid=false
//   - Tamper last entry → is_valid=false
//   - Certificate hash differs for chains of length 99 vs 100
//   - certifyAdaptiveLineage × 3 → identical certificate_hash
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  AdaptiveLineage,
  AdaptiveLineageError,
  certifyAdaptiveLineage,
  GENESIS_TOPOLOGY_HASH,
  ADAPTIVE_LINEAGE_SCHEMA_VERSION,
  type AdaptiveEvent, type AdaptiveLineageEntry,
} from '../../src/frame/adaptive-lineage.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

function topoEvent(n: number): AdaptiveEvent {
  return { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + (n % 26))) }
}

function capEvent(n: number): AdaptiveEvent {
  return {
    kind: 'CAPABILITY_EVOLUTION',
    proposal_id: h(String.fromCharCode(97 + (n % 26))),
    verdict: n % 3 === 0 ? 'REJECTED' : 'APPROVED',
  }
}

async function buildTopoChain(length: number): Promise<readonly AdaptiveLineageEntry[]> {
  let lineage = AdaptiveLineage.empty()
  for (let i = 1; i <= length; i++) {
    const { lineage: next } = await lineage.append(topoEvent(i), seq(i))
    lineage = next
  }
  return lineage.getAll()
}

async function buildMixedChain(length: number): Promise<readonly AdaptiveLineageEntry[]> {
  let lineage = AdaptiveLineage.empty()
  for (let i = 1; i <= length; i++) {
    const event = i % 2 === 0 ? capEvent(i) : topoEvent(i)
    const { lineage: next } = await lineage.append(event, seq(i))
    lineage = next
  }
  return lineage.getAll()
}

// ─── 100-entry topo chain ─────────────────────────────────

describe('AdaptiveLineage: 100-entry TOPOLOGY chain', () => {
  it('100-entry chain builds without error', async () => {
    const entries = await buildTopoChain(100)
    expect(entries.length).toBe(100)
  })

  it('certifyAdaptiveLineage(100 entries) → is_valid=true', async () => {
    const entries = await buildTopoChain(100)
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(100)
  })

  it('terminal_hash of 100-entry chain is 64-char hex', async () => {
    const entries = await buildTopoChain(100)
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.terminal_hash).toHaveLength(64)
    expect(cert.terminal_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('certify × 3 on same 100-entry chain → identical certificate_hash', async () => {
    const entries = await buildTopoChain(100)
    const [c1, c2, c3] = await Promise.all([
      certifyAdaptiveLineage(entries),
      certifyAdaptiveLineage(entries),
      certifyAdaptiveLineage(entries),
    ])
    expect(c1!.certificate_hash).toBe(c2!.certificate_hash)
    expect(c2!.certificate_hash).toBe(c3!.certificate_hash)
  })

  it('certificate_hash for 100 entries ≠ certificate_hash for 99 entries', async () => {
    const full = await buildTopoChain(100)
    const short = full.slice(0, 99)
    const certFull = await certifyAdaptiveLineage(full)
    const certShort = await certifyAdaptiveLineage(short)
    expect(certFull.certificate_hash).not.toBe(certShort.certificate_hash)
  })
})

// ─── 100-entry mixed chain ────────────────────────────────

describe('AdaptiveLineage: 100-entry mixed chain', () => {
  it('100-entry mixed chain (TOPOLOGY+CAPABILITY) → certify is_valid=true', async () => {
    const entries = await buildMixedChain(100)
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(100)
  })

  it('mixed chain has both event kinds present', async () => {
    const entries = await buildMixedChain(20)
    const topoCount = entries.filter(e => e.event.kind === 'TOPOLOGY_TRANSITION').length
    const capCount = entries.filter(e => e.event.kind === 'CAPABILITY_EVOLUTION').length
    expect(topoCount).toBe(10)
    expect(capCount).toBe(10)
  })
})

// ─── Tamper detection at scale ────────────────────────────

describe('AdaptiveLineage: tamper detection at scale', () => {
  it('tamper entry_hash at position 0 (first) → is_valid=false', async () => {
    const entries = [...await buildTopoChain(20)]
    entries[0] = { ...entries[0]!, entry_hash: h('z') }
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper entry_hash at position 10 of 20 → is_valid=false', async () => {
    const entries = [...await buildTopoChain(20)]
    entries[10] = { ...entries[10]!, entry_hash: h('z') }
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper entry_hash at last position → is_valid=false', async () => {
    const entries = [...await buildTopoChain(20)]
    const last = entries.length - 1
    entries[last] = { ...entries[last]!, entry_hash: h('z') }
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper previous_entry_hash at position 10 → is_valid=false', async () => {
    const entries = [...await buildTopoChain(20)]
    entries[10] = { ...entries[10]!, previous_entry_hash: h('z') }
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper first entry previous_entry_hash (must be GENESIS) → is_valid=false', async () => {
    const entries = [...await buildTopoChain(10)]
    // First entry's previous_entry_hash must be GENESIS_TOPOLOGY_HASH
    entries[0] = { ...entries[0]!, previous_entry_hash: h('x') }
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper at position 50 of 100-entry chain → is_valid=false', async () => {
    const entries = [...await buildTopoChain(100)]
    entries[50] = { ...entries[50]!, entry_hash: h('z') }
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.is_valid).toBe(false)
  })
})

// ─── Empty and structural ─────────────────────────────────

describe('AdaptiveLineage: empty and structural guarantees', () => {
  it('empty chain → is_valid=true, entry_count=0, terminal_hash=null', async () => {
    const cert = await certifyAdaptiveLineage([])
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(0)
    expect(cert.terminal_hash).toBeNull()
  })

  it('empty().lastHash equals GENESIS_TOPOLOGY_HASH', () => {
    expect(AdaptiveLineage.empty().lastHash).toBe(GENESIS_TOPOLOGY_HASH)
    expect(GENESIS_TOPOLOGY_HASH).toBe('0'.repeat(64))
  })

  it('non-monotonic sequence → AdaptiveLineageError', async () => {
    let lineage = AdaptiveLineage.empty()
    const { lineage: l2 } = await lineage.append(topoEvent(1), seq(5))
    await expect(l2.append(topoEvent(2), seq(3))).rejects.toThrow(AdaptiveLineageError)
  })

  it('source lineage unchanged after append (immutable)', async () => {
    const initial = AdaptiveLineage.empty()
    await initial.append(topoEvent(1), seq(1))
    expect(initial.length).toBe(0)
    expect(initial.lastSequence).toBeNull()
  })

  it('schema_version is 1.0.0', () => {
    expect(ADAPTIVE_LINEAGE_SCHEMA_VERSION).toBe('1.0.0')
  })
})
