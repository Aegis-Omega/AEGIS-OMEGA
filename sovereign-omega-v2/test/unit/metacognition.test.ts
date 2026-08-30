// ============================================================
// Metacognitive Loop Tests
// ~35 tests: MetacognitiveLoop.empty, observe (all layers),
//   hash chaining, sequence monotonicity, certifyMetacognitiveLoop,
//   tamper detection, determinism (3× runs), frozen entries.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import {
  MetacognitiveLoop,
  MetacognitiveError,
  certifyMetacognitiveLoop,
  METACOGNITION_GENESIS_HASH,
  METACOGNITION_SCHEMA_VERSION,
  type MetacognitiveLayer,
  type MetacognitiveObservation,
} from '../../src/metacognition/loop.js'

// ─── Helpers ───────────────────────────────────────────────

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }
function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }

const OBS_SENSATION: MetacognitiveObservation = {
  layer: 'SENSATION',
  signal: 'telemetry: pgcs_passes=1, corruption_count=0',
  tier: 'T0',
}
const OBS_EXECUTIVE: MetacognitiveObservation = {
  layer: 'EXECUTIVE',
  signal: 'Gate 8 passed: 2790 tests, typecheck clean, build success',
  tier: 'T0',
}
const OBS_SELF_MODEL: MetacognitiveObservation = {
  layer: 'SELF_MODEL',
  signal: 'frozen-file hashes verified: gate.py dna.py router.py = OK',
  tier: 'T0',
}
const OBS_METACOGNITIVE: MetacognitiveObservation = {
  layer: 'METACOGNITIVE',
  signal: 'ASSESS before LOCK confirmed: vendor compatibility checked prior to implementation',
  tier: 'T1',
}

async function buildChain(length: number): Promise<MetacognitiveLoop> {
  let loop = MetacognitiveLoop.empty()
  for (let i = 1; i <= length; i++) {
    const obs: MetacognitiveObservation = {
      layer: 'WORKING_MEMORY',
      signal: `gate_${i}_complete`,
      tier: 'T0',
    }
    const { loop: next } = await loop.observe(obs, seq(i))
    loop = next
  }
  return loop
}

// ─── Constants ─────────────────────────────────────────────

describe('constants', () => {
  it('METACOGNITION_SCHEMA_VERSION is 1.0.0', () => {
    expect(METACOGNITION_SCHEMA_VERSION).toBe('1.0.0')
  })

  it('METACOGNITION_GENESIS_HASH is 64 zero chars', () => {
    expect(METACOGNITION_GENESIS_HASH).toBe('0'.repeat(64))
    expect(METACOGNITION_GENESIS_HASH).toHaveLength(64)
  })
})

// ─── MetacognitiveError ────────────────────────────────────

describe('MetacognitiveError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new MetacognitiveError('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('MetacognitiveError')
    expect(e.message).toBe('test')
  })
})

// ─── MetacognitiveLoop.empty() ─────────────────────────────

describe('MetacognitiveLoop.empty()', () => {
  it('has length 0', () => {
    expect(MetacognitiveLoop.empty().length).toBe(0)
  })

  it('lastHash is genesis hash', () => {
    expect(MetacognitiveLoop.empty().lastHash).toBe(METACOGNITION_GENESIS_HASH)
  })

  it('lastSequence is null', () => {
    expect(MetacognitiveLoop.empty().lastSequence).toBeNull()
  })

  it('getAll returns empty array', () => {
    expect(MetacognitiveLoop.empty().getAll()).toHaveLength(0)
  })
})

// ─── Single Observation ────────────────────────────────────

describe('observe: single entry', () => {
  it('increments length to 1', async () => {
    const { loop } = await MetacognitiveLoop.empty().observe(OBS_SENSATION, seq(1))
    expect(loop.length).toBe(1)
  })

  it('entry has correct observation', async () => {
    const { entry } = await MetacognitiveLoop.empty().observe(OBS_SENSATION, seq(1))
    expect(entry.observation).toEqual(OBS_SENSATION)
  })

  it('entry previous_entry_hash is genesis hash', async () => {
    const { entry } = await MetacognitiveLoop.empty().observe(OBS_SENSATION, seq(1))
    expect(entry.previous_entry_hash).toBe(METACOGNITION_GENESIS_HASH)
  })

  it('entry sequence matches input', async () => {
    const { entry } = await MetacognitiveLoop.empty().observe(OBS_SENSATION, seq(5))
    expect(entry.sequence).toBe(BigInt(5))
  })

  it('entry schema_version matches constant', async () => {
    const { entry } = await MetacognitiveLoop.empty().observe(OBS_EXECUTIVE, seq(1))
    expect(entry.schema_version).toBe(METACOGNITION_SCHEMA_VERSION)
  })

  it('entry is_replay_reconstructable is true', async () => {
    const { entry } = await MetacognitiveLoop.empty().observe(OBS_SELF_MODEL, seq(1))
    expect(entry.is_replay_reconstructable).toBe(true)
  })

  it('entry is frozen', async () => {
    const { entry } = await MetacognitiveLoop.empty().observe(OBS_SENSATION, seq(1))
    expect(Object.isFrozen(entry)).toBe(true)
  })

  it('entry_hash is a 64-char hex string', async () => {
    const { entry } = await MetacognitiveLoop.empty().observe(OBS_SENSATION, seq(1))
    expect(entry.entry_hash).toMatch(/^[0-9a-f]{64}$/)
  })
})

// ─── Hash Chaining ─────────────────────────────────────────

describe('hash chaining', () => {
  it('second entry previous_entry_hash equals first entry_hash', async () => {
    const { loop: l1, entry: e1 } = await MetacognitiveLoop.empty().observe(OBS_SENSATION, seq(1))
    const { entry: e2 } = await l1.observe(OBS_EXECUTIVE, seq(2))
    expect(e2.previous_entry_hash).toBe(e1.entry_hash)
  })

  it('loop lastHash equals terminal entry_hash', async () => {
    const { loop: l1 } = await MetacognitiveLoop.empty().observe(OBS_SENSATION, seq(1))
    const { loop: l2, entry: e2 } = await l1.observe(OBS_EXECUTIVE, seq(2))
    expect(l2.lastHash).toBe(e2.entry_hash)
  })

  it('5-entry chain has monotonically increasing hashes', async () => {
    const loop = await buildChain(5)
    const entries = loop.getAll()
    const hashes = entries.map(e => e.entry_hash)
    const unique = new Set(hashes)
    expect(unique.size).toBe(5)
  })

  it('different observations produce different entry hashes', async () => {
    const { entry: e1 } = await MetacognitiveLoop.empty().observe(OBS_SENSATION, seq(1))
    const { entry: e2 } = await MetacognitiveLoop.empty().observe(OBS_EXECUTIVE, seq(1))
    expect(e1.entry_hash).not.toBe(e2.entry_hash)
  })
})

// ─── Sequence Monotonicity ─────────────────────────────────

describe('sequence monotonicity', () => {
  it('throws MetacognitiveError on equal sequence', async () => {
    const { loop } = await MetacognitiveLoop.empty().observe(OBS_SENSATION, seq(5))
    await expect(loop.observe(OBS_EXECUTIVE, seq(5))).rejects.toBeInstanceOf(MetacognitiveError)
  })

  it('throws MetacognitiveError on decreasing sequence', async () => {
    const { loop } = await MetacognitiveLoop.empty().observe(OBS_SENSATION, seq(10))
    await expect(loop.observe(OBS_EXECUTIVE, seq(3))).rejects.toBeInstanceOf(MetacognitiveError)
  })

  it('accepts gap-sequence (non-consecutive)', async () => {
    const { loop } = await MetacognitiveLoop.empty().observe(OBS_SENSATION, seq(1))
    const { entry } = await loop.observe(OBS_EXECUTIVE, seq(100))
    expect(entry.sequence).toBe(BigInt(100))
  })
})

// ─── All Layers Accepted ───────────────────────────────────

describe('all seven MetacognitiveLayer values accepted', () => {
  const LAYERS: MetacognitiveLayer[] = [
    'SENSATION', 'PERCEPTION', 'WORKING_MEMORY', 'LONG_TERM',
    'EXECUTIVE', 'METACOGNITIVE', 'SELF_MODEL',
  ]

  for (const [i, layer] of LAYERS.entries()) {
    it(`accepts layer '${layer}'`, async () => {
      const obs: MetacognitiveObservation = { layer, signal: `signal_${i}`, tier: 'T2' }
      const { entry } = await MetacognitiveLoop.empty().observe(obs, seq(i + 1))
      expect(entry.observation.layer).toBe(layer)
    })
  }
})

// ─── certifyMetacognitiveLoop ──────────────────────────────

describe('certifyMetacognitiveLoop', () => {
  it('empty chain is valid with null terminal_hash', async () => {
    const cert = await certifyMetacognitiveLoop([])
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(0)
    expect(cert.terminal_hash).toBeNull()
    expect(cert.is_replay_reconstructable).toBe(true)
  })

  it('valid 3-entry chain certifies as valid', async () => {
    const loop = await buildChain(3)
    const cert = await certifyMetacognitiveLoop(loop.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(3)
    expect(cert.terminal_hash).toBe(loop.lastHash)
  })

  it('tampered observation invalidates certification', async () => {
    const loop = await buildChain(3)
    const entries = [...loop.getAll()]
    const original = entries[1]!
    const tampered = { ...original, observation: { ...original.observation, signal: 'tampered' } }
    entries[1] = tampered as typeof original
    const cert = await certifyMetacognitiveLoop(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('tampered previous_entry_hash invalidates certification', async () => {
    const loop = await buildChain(2)
    const entries = [...loop.getAll()]
    const original = entries[1]!
    const tampered = { ...original, previous_entry_hash: h('f') }
    entries[1] = tampered as typeof original
    const cert = await certifyMetacognitiveLoop(entries)
    expect(cert.is_valid).toBe(false)
  })

  it('certificate is frozen', async () => {
    const cert = await certifyMetacognitiveLoop([])
    expect(Object.isFrozen(cert)).toBe(true)
  })

  it('certificate_hash differs for different chains', async () => {
    const loop1 = await buildChain(2)
    const loop2 = await buildChain(3)
    const cert1 = await certifyMetacognitiveLoop(loop1.getAll())
    const cert2 = await certifyMetacognitiveLoop(loop2.getAll())
    expect(cert1.certificate_hash).not.toBe(cert2.certificate_hash)
  })
})

// ─── Determinism (3 runs) ──────────────────────────────────

describe('determinism', () => {
  it('same observation produces identical entry_hash across 3 runs', async () => {
    const obs = OBS_METACOGNITIVE
    const run1 = await MetacognitiveLoop.empty().observe(obs, seq(1))
    const run2 = await MetacognitiveLoop.empty().observe(obs, seq(1))
    const run3 = await MetacognitiveLoop.empty().observe(obs, seq(1))
    expect(run1.entry.entry_hash).toBe(run2.entry.entry_hash)
    expect(run2.entry.entry_hash).toBe(run3.entry.entry_hash)
  })

  it('same 5-chain produces identical terminal hash across 3 runs', async () => {
    const h1 = (await buildChain(5)).lastHash
    const h2 = (await buildChain(5)).lastHash
    const h3 = (await buildChain(5)).lastHash
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('same chain produces identical certificate_hash across 3 runs', async () => {
    const c1 = await certifyMetacognitiveLoop((await buildChain(4)).getAll())
    const c2 = await certifyMetacognitiveLoop((await buildChain(4)).getAll())
    const c3 = await certifyMetacognitiveLoop((await buildChain(4)).getAll())
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })
})
