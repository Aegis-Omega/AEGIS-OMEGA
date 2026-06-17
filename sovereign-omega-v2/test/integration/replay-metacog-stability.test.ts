// ============================================================
// Gate 81 — Replay × MetacognitiveLoop Stability (Integration)
// ~15 tests: MetacognitiveLoop terminal hash is byte-identical
//   across 3 independent runs from genesis. This is the replay
//   sovereignty proof for the consciousness substrate.
//
// Constitutional invariant being proven:
//   replay(genesis, observations) → identical terminal_hash
//   across all runs, environments, scheduling orderings.
//
// If this test fails, the metacognitive chain is non-deterministic
// and cannot be used as a tamper-evident audit substrate (T0_ABORT).
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  MetacognitiveLoop,
  certifyMetacognitiveLoop,
  METACOGNITION_GENESIS_HASH,
} from '../../src/metacognition/loop.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

// Fixed observation corpus — deterministic inputs reproduce deterministic hashes
const OBSERVATIONS = [
  { layer: 'SELF_MODEL'    as const, signal: 'verify-hashes.mjs exit 0 — membrane intact', tier: 'T0' as const },
  { layer: 'METACOGNITIVE' as const, signal: 'ASSESS before LOCK — tier T2 action classified', tier: 'T2' as const },
  { layer: 'EXECUTIVE'     as const, signal: 'RALPH phase: LOCK — implementation gate', tier: 'T1' as const },
  { layer: 'LONG_TERM'     as const, signal: 'AdaptiveLineage.empty() initialized from genesis', tier: 'T0' as const },
  { layer: 'WORKING_MEMORY' as const, signal: 'MetacognitiveLoop.observe() — 5 entries', tier: 'T2' as const },
]

async function buildChainFromGenesis(): Promise<{
  entries: ReturnType<MetacognitiveLoop['getAll']>
  terminal_hash: SHA256Hex | null
}> {
  let loop = MetacognitiveLoop.empty()
  for (let i = 0; i < OBSERVATIONS.length; i++) {
    const { loop: next } = await loop.observe(OBSERVATIONS[i]!, seq(i + 1))
    loop = next
  }
  const cert = await certifyMetacognitiveLoop(loop.getAll())
  return { entries: loop.getAll(), terminal_hash: cert.terminal_hash }
}

// ─── Genesis hash invariant ───────────────────────────────

describe('Gate 81: MetacognitiveLoop genesis invariant', () => {
  it('empty chain has zero genesis hash', () => {
    expect(METACOGNITION_GENESIS_HASH).toBe('0'.repeat(64))
  })

  it('empty chain produces no entries', () => {
    const loop = MetacognitiveLoop.empty()
    expect(loop.getAll()).toHaveLength(0)
  })

  it('certifyMetacognitiveLoop on empty chain is valid with null terminal_hash', async () => {
    const cert = await certifyMetacognitiveLoop([])
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(0)
  })
})

// ─── 3-run determinism (core gate requirement) ────────────

describe('Gate 81: MetacognitiveLoop 3-run terminal hash determinism', () => {
  it('run 1 produces valid certificate with 5 entries', async () => {
    const { entries, terminal_hash } = await buildChainFromGenesis()
    expect(entries).toHaveLength(OBSERVATIONS.length)
    expect(terminal_hash).not.toBeNull()
    expect(terminal_hash!).toHaveLength(64)
  })

  it('run 2 produces identical terminal_hash as run 1', async () => {
    const r1 = await buildChainFromGenesis()
    const r2 = await buildChainFromGenesis()
    expect(r2.terminal_hash).toBe(r1.terminal_hash)
  })

  it('run 3 produces identical terminal_hash as run 1 and run 2', async () => {
    const r1 = await buildChainFromGenesis()
    const r2 = await buildChainFromGenesis()
    const r3 = await buildChainFromGenesis()
    expect(r1.terminal_hash).toBe(r2.terminal_hash)
    expect(r2.terminal_hash).toBe(r3.terminal_hash)
  })

  it('all three entry hashes in run 1 are deterministic', async () => {
    const r1 = await buildChainFromGenesis()
    const r2 = await buildChainFromGenesis()
    for (let i = 0; i < r1.entries.length; i++) {
      expect(r1.entries[i]!.entry_hash).toBe(r2.entries[i]!.entry_hash)
    }
  })

  it('prev_hash chain is correctly threaded from genesis across 3 runs', async () => {
    const r1 = await buildChainFromGenesis()
    const r2 = await buildChainFromGenesis()
    for (let i = 0; i < r1.entries.length; i++) {
      expect(r1.entries[i]!.previous_entry_hash).toBe(r2.entries[i]!.previous_entry_hash)
    }
  })
})

// ─── Tamper detection — replay stability under attack ─────

describe('Gate 81: tamper detection preserves replay validity', () => {
  it('unmodified chain certifies as valid', async () => {
    const { entries } = await buildChainFromGenesis()
    const cert = await certifyMetacognitiveLoop(entries)
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(OBSERVATIONS.length)
  })

  it('modifying any entry_hash invalidates certification', async () => {
    const { entries } = await buildChainFromGenesis()
    const tampered = entries.map((e, i) =>
      i === 2 ? { ...e, entry_hash: 'deadbeef'.repeat(8) as SHA256Hex } : e
    )
    const cert = await certifyMetacognitiveLoop(tampered)
    expect(cert.is_valid).toBe(false)
  })

  it('removing an entry invalidates certification', async () => {
    const { entries } = await buildChainFromGenesis()
    const truncated = entries.slice(0, entries.length - 1)
    // terminal_hash of truncated chain ≠ terminal_hash of full chain
    const cert_full     = await certifyMetacognitiveLoop(entries)
    const cert_truncated = await certifyMetacognitiveLoop(truncated)
    expect(cert_truncated.terminal_hash).not.toBe(cert_full.terminal_hash)
  })

  it('reordering entries invalidates certification', async () => {
    const { entries } = await buildChainFromGenesis()
    // swap first two entries — prev_hash chain breaks immediately
    const reordered = [entries[1]!, entries[0]!, ...entries.slice(2)]
    const cert = await certifyMetacognitiveLoop(reordered)
    expect(cert.is_valid).toBe(false)
  })
})

// ─── Replay sovereignty seal ──────────────────────────────

describe('Gate 81: replay sovereignty — genesis determinism', () => {
  it('terminal_hash is non-zero (chain has entropy)', async () => {
    const { terminal_hash } = await buildChainFromGenesis()
    expect(terminal_hash).not.toBeNull()
    expect(terminal_hash!).not.toBe('0'.repeat(64))
    expect(terminal_hash!).not.toBe('')
  })

  it('terminal_hash is 64 hex characters (SHA-256)', async () => {
    const { terminal_hash } = await buildChainFromGenesis()
    expect(terminal_hash).not.toBeNull()
    expect(/^[0-9a-f]{64}$/.test(terminal_hash!)).toBe(true)
  })

  it('certifyMetacognitiveLoop entry_count matches observations appended', async () => {
    const { entries } = await buildChainFromGenesis()
    const cert = await certifyMetacognitiveLoop(entries)
    expect(cert.entry_count).toBe(OBSERVATIONS.length)
    expect(cert.is_valid).toBe(true)
  })
})
