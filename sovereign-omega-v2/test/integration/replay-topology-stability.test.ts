// ============================================================
// Gate 81 — Replay Topology Stability (Integration)
// ~15 tests: proves replay(genesis, events) → identical terminal
//   hash across 3 independent runs. This is the runtime proof
//   of REPLAY SOVEREIGNTY for the TypeScript governance layer.
//
// Constitutional law: AdaptivePower(T) ≤ ReplayVerifiability(T)
// Replay divergence = T0_ABORT (no exception path).
//
// Covers AdaptiveLineage and MetacognitiveLoop independently —
// both must be independently replay-stable for the constitutional
// invariant to hold end-to-end.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import {
  AdaptiveLineage,
  certifyAdaptiveLineage,
  GENESIS_TOPOLOGY_HASH,
} from '../../src/frame/adaptive-lineage.js'
import {
  MetacognitiveLoop,
  certifyMetacognitiveLoop,
  METACOGNITION_GENESIS_HASH,
} from '../../src/metacognition/loop.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }
function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }

// Fixed event sequences — deterministic inputs for replay
const TOPOLOGY_EVENTS = [
  { kind: 'TOPOLOGY_TRANSITION' as const, topology_hash: h('a') },
  { kind: 'CAPABILITY_EVOLUTION' as const, proposal_id: h('b'), verdict: 'APPROVED' as const },
  { kind: 'TOPOLOGY_TRANSITION' as const, topology_hash: h('c') },
  { kind: 'CAPABILITY_EVOLUTION' as const, proposal_id: h('d'), verdict: 'APPROVED' as const },
  { kind: 'TOPOLOGY_TRANSITION' as const, topology_hash: h('e') },
]

const META_OBSERVATIONS = [
  { layer: 'SENSATION' as const,    signal: 'telemetry: corruption_count=0', tier: 'T0' as const },
  { layer: 'EXECUTIVE' as const,    signal: 'Gate 1 passed: jcs.test.ts',     tier: 'T0' as const },
  { layer: 'SELF_MODEL' as const,   signal: 'verify-hashes.mjs: PASS',        tier: 'T0' as const },
  { layer: 'WORKING_MEMORY' as const, signal: 'RALPH phase: LOCK',           tier: 'T1' as const },
  { layer: 'METACOGNITIVE' as const, signal: 'ASSESS complete — tier T2',    tier: 'T1' as const },
]

async function replayAdaptiveLineage(): Promise<string> {
  let lineage = AdaptiveLineage.empty()
  for (let i = 0; i < TOPOLOGY_EVENTS.length; i++) {
    const { lineage: next } = await lineage.append(TOPOLOGY_EVENTS[i]!, seq(i + 1))
    lineage = next
  }
  const cert = await certifyAdaptiveLineage(lineage.getAll())
  return String(cert.terminal_hash ?? '')
}

async function replayMetacognitiveLoop(): Promise<string> {
  let loop = MetacognitiveLoop.empty()
  for (let i = 0; i < META_OBSERVATIONS.length; i++) {
    const { loop: next } = await loop.observe(META_OBSERVATIONS[i]!, seq(i + 1))
    loop = next
  }
  const cert = await certifyMetacognitiveLoop(loop.getAll())
  return String(cert.terminal_hash)
}

// ─── Genesis hash stability ────────────────────────────────

describe('Gate 81: Genesis hash stability', () => {
  it('GENESIS_TOPOLOGY_HASH is the 64-zero string — stable across imports', () => {
    expect(GENESIS_TOPOLOGY_HASH).toBe('0'.repeat(64))
  })

  it('METACOGNITION_GENESIS_HASH is the 64-zero string — stable across imports', () => {
    expect(METACOGNITION_GENESIS_HASH).toBe('0'.repeat(64))
  })

  it('AdaptiveLineage.empty() has lastHash === GENESIS_TOPOLOGY_HASH', () => {
    expect(AdaptiveLineage.empty().lastHash).toBe(GENESIS_TOPOLOGY_HASH)
  })
})

// ─── AdaptiveLineage replay determinism (3 runs) ──────────

describe('Gate 81: AdaptiveLineage — replay topology stability (3 runs)', () => {
  it('run 1 → terminal_hash is a 64-char hex string', async () => {
    const h1 = await replayAdaptiveLineage()
    expect(h1).toHaveLength(64)
    expect(h1).toMatch(/^[0-9a-f]{64}$/)
  })

  it('run 1 and run 2 produce identical terminal_hash', async () => {
    const h1 = await replayAdaptiveLineage()
    const h2 = await replayAdaptiveLineage()
    expect(h2).toBe(h1)
  })

  it('run 2 and run 3 produce identical terminal_hash', async () => {
    const h2 = await replayAdaptiveLineage()
    const h3 = await replayAdaptiveLineage()
    expect(h3).toBe(h2)
  })

  it('certifyAdaptiveLineage returns is_valid: true on replayed chain', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 0; i < TOPOLOGY_EVENTS.length; i++) {
      const { lineage: next } = await lineage.append(TOPOLOGY_EVENTS[i]!, seq(i + 1))
      lineage = next
    }
    const cert = await certifyAdaptiveLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.is_replay_reconstructable).toBe(true)
  })

  it('entry_count equals number of appended events', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 0; i < TOPOLOGY_EVENTS.length; i++) {
      const { lineage: next } = await lineage.append(TOPOLOGY_EVENTS[i]!, seq(i + 1))
      lineage = next
    }
    const cert = await certifyAdaptiveLineage(lineage.getAll())
    expect(cert.entry_count).toBe(TOPOLOGY_EVENTS.length)
  })
})

// ─── MetacognitiveLoop replay determinism (3 runs) ────────

describe('Gate 81: MetacognitiveLoop — replay topology stability (3 runs)', () => {
  it('run 1 → terminal_hash is a 64-char hex string', async () => {
    const h1 = await replayMetacognitiveLoop()
    expect(h1).toHaveLength(64)
    expect(h1).toMatch(/^[0-9a-f]{64}$/)
  })

  it('run 1 and run 2 produce identical terminal_hash', async () => {
    const h1 = await replayMetacognitiveLoop()
    const h2 = await replayMetacognitiveLoop()
    expect(h2).toBe(h1)
  })

  it('run 2 and run 3 produce identical terminal_hash', async () => {
    const h2 = await replayMetacognitiveLoop()
    const h3 = await replayMetacognitiveLoop()
    expect(h3).toBe(h2)
  })

  it('certifyMetacognitiveLoop returns is_valid: true on replayed chain', async () => {
    let loop = MetacognitiveLoop.empty()
    for (let i = 0; i < META_OBSERVATIONS.length; i++) {
      const { loop: next } = await loop.observe(META_OBSERVATIONS[i]!, seq(i + 1))
      loop = next
    }
    const cert = await certifyMetacognitiveLoop(loop.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(META_OBSERVATIONS.length)
  })
})

// ─── Cross-chain independence ──────────────────────────────

describe('Gate 81: Cross-chain replay independence', () => {
  it('AdaptiveLineage and MetacognitiveLoop produce distinct terminal hashes', async () => {
    const adaptiveHash = await replayAdaptiveLineage()
    const metaHash = await replayMetacognitiveLoop()
    expect(adaptiveHash).not.toBe(metaHash)
  })

  it('different event sequences produce different terminal hashes', async () => {
    let lineageA = AdaptiveLineage.empty()
    let lineageB = AdaptiveLineage.empty()
    const { lineage: nextA } = await lineageA.append(
      { kind: 'TOPOLOGY_TRANSITION', topology_hash: h('a') }, seq(1)
    )
    const { lineage: nextB } = await lineageB.append(
      { kind: 'TOPOLOGY_TRANSITION', topology_hash: h('b') }, seq(1)
    )
    const certA = await certifyAdaptiveLineage(nextA.getAll())
    const certB = await certifyAdaptiveLineage(nextB.getAll())
    expect(certA.terminal_hash).not.toBe(certB.terminal_hash)
  })
})
