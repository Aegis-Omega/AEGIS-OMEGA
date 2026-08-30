// ============================================================
// SOVEREIGN OMEGA — Metacognitive Observation Loop tests
// EPISTEMIC TIER: T2
//
// Tests for metacognition/loop.ts:
//   MetacognitiveLoop  — empty, observe, length, lastHash, sequence guard
//   certifyMetacognitiveLoop — empty, valid chain, tampered entry
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  MetacognitiveLoop,
  MetacognitiveError,
  certifyMetacognitiveLoop,
  METACOGNITION_GENESIS_HASH,
  METACOGNITION_SCHEMA_VERSION,
} from '../../src/metacognition/loop.js'
import type { MetacognitiveObservation, MetacognitiveEntry } from '../../src/metacognition/loop.js'
import type { SequenceNumber, SHA256Hex } from '../../src/core/types.js'

const SEQ = (n: number) => BigInt(n) as unknown as SequenceNumber

function obs(layer: MetacognitiveObservation['layer'] = 'SENSATION'): MetacognitiveObservation {
  return { layer, signal: `signal-${layer}`, tier: 'T2' }
}

// ── MetacognitiveError ─────────────────────────────────────

describe('MetacognitiveError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new MetacognitiveError('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('MetacognitiveError')
    expect(e.message).toBe('test')
  })
})

// ── MetacognitiveLoop — empty ──────────────────────────────

describe('MetacognitiveLoop — empty()', () => {
  it('starts with length 0', () => {
    expect(MetacognitiveLoop.empty().length).toBe(0)
  })

  it('lastHash is the genesis hash (64 zeros)', () => {
    expect(MetacognitiveLoop.empty().lastHash).toBe(METACOGNITION_GENESIS_HASH)
  })

  it('lastSequence is null', () => {
    expect(MetacognitiveLoop.empty().lastSequence).toBeNull()
  })

  it('getAll() returns empty array', () => {
    expect(MetacognitiveLoop.empty().getAll()).toHaveLength(0)
  })
})

// ── MetacognitiveLoop — observe ────────────────────────────

describe('MetacognitiveLoop — observe()', () => {
  it('observe returns entry with correct fields and frozen result', async () => {
    const { loop, entry } = await MetacognitiveLoop.empty().observe(obs('SENSATION'), SEQ(1))
    expect(loop.length).toBe(1)
    expect(entry.observation.layer).toBe('SENSATION')
    expect(entry.sequence).toBe(SEQ(1))
    expect(entry.previous_entry_hash).toBe(METACOGNITION_GENESIS_HASH)
    expect(entry.schema_version).toBe(METACOGNITION_SCHEMA_VERSION)
    expect(entry.is_replay_reconstructable).toBe(true)
    expect(Object.isFrozen(entry)).toBe(true)
  })

  it('entry_hash is a 64-char hex string', async () => {
    const { entry } = await MetacognitiveLoop.empty().observe(obs(), SEQ(1))
    expect(entry.entry_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('chained observe: previous_entry_hash links to prior entry', async () => {
    const { loop: l1, entry: e1 } = await MetacognitiveLoop.empty().observe(obs('SENSATION'), SEQ(1))
    const { entry: e2 } = await l1.observe(obs('PERCEPTION'), SEQ(2))
    expect(e2.previous_entry_hash).toBe(e1.entry_hash)
  })

  it('three sequential observations produce increasing length', async () => {
    const { loop: l1 } = await MetacognitiveLoop.empty().observe(obs('SENSATION'), SEQ(1))
    const { loop: l2 } = await l1.observe(obs('WORKING_MEMORY'), SEQ(2))
    const { loop: l3 } = await l2.observe(obs('EXECUTIVE'), SEQ(3))
    expect(l3.length).toBe(3)
    expect(l3.lastSequence).toBe(SEQ(3))
  })

  it('lastHash after observe equals the entry_hash of the last entry', async () => {
    const { loop, entry } = await MetacognitiveLoop.empty().observe(obs(), SEQ(1))
    expect(loop.lastHash).toBe(entry.entry_hash)
  })

  it('throws MetacognitiveError when sequence is non-monotonic', async () => {
    const { loop } = await MetacognitiveLoop.empty().observe(obs(), SEQ(5))
    await expect(loop.observe(obs(), SEQ(3))).rejects.toThrow(MetacognitiveError)
  })

  it('throws MetacognitiveError when sequence equals current lastSequence', async () => {
    const { loop } = await MetacognitiveLoop.empty().observe(obs(), SEQ(5))
    await expect(loop.observe(obs(), SEQ(5))).rejects.toThrow(MetacognitiveError)
  })
})

// ── certifyMetacognitiveLoop ────────────────────────────────

describe('certifyMetacognitiveLoop', () => {
  it('empty entries → is_valid=true, entry_count=0, terminal_hash=null', async () => {
    const cert = await certifyMetacognitiveLoop([])
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(0)
    expect(cert.terminal_hash).toBeNull()
    expect(cert.is_replay_reconstructable).toBe(true)
    expect(Object.isFrozen(cert)).toBe(true)
  })

  it('certificate_hash is a 64-char hex string', async () => {
    const cert = await certifyMetacognitiveLoop([])
    expect(cert.certificate_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('valid 3-entry chain → is_valid=true, entry_count=3', async () => {
    const { loop: l1 } = await MetacognitiveLoop.empty().observe(obs('SENSATION'), SEQ(1))
    const { loop: l2 } = await l1.observe(obs('PERCEPTION'), SEQ(2))
    const { loop: l3 } = await l2.observe(obs('EXECUTIVE'), SEQ(3))
    const cert = await certifyMetacognitiveLoop(l3.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(3)
    expect(cert.terminal_hash).toBe(l3.lastHash)
  })

  it('tampered previous_entry_hash → is_valid=false', async () => {
    const { loop: l1 } = await MetacognitiveLoop.empty().observe(obs('SENSATION'), SEQ(1))
    const { loop: l2 } = await l1.observe(obs('PERCEPTION'), SEQ(2))
    const entries = l2.getAll()
    const tampered: readonly MetacognitiveEntry[] = [
      { ...entries[0]!, previous_entry_hash: 'f'.repeat(64) as SHA256Hex },
      entries[1]!,
    ]
    const cert = await certifyMetacognitiveLoop(tampered)
    expect(cert.is_valid).toBe(false)
  })

  it('tampered entry_hash → is_valid=false', async () => {
    const { loop } = await MetacognitiveLoop.empty().observe(obs(), SEQ(1))
    const entries = loop.getAll()
    const tampered: readonly MetacognitiveEntry[] = [
      { ...entries[0]!, entry_hash: 'e'.repeat(64) as SHA256Hex },
    ]
    const cert = await certifyMetacognitiveLoop(tampered)
    expect(cert.is_valid).toBe(false)
  })

  it('is deterministic — three certifications of the same chain produce equal certificate_hash', async () => {
    const { loop: l1 } = await MetacognitiveLoop.empty().observe(obs('SENSATION'), SEQ(1))
    const { loop: l2 } = await l1.observe(obs('SELF_MODEL'), SEQ(2))
    const entries = l2.getAll()
    const [c1, c2, c3] = await Promise.all([
      certifyMetacognitiveLoop(entries),
      certifyMetacognitiveLoop(entries),
      certifyMetacognitiveLoop(entries),
    ])
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })
})
