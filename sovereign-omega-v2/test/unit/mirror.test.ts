// ============================================================
// Gate 36 — Governance Mirror Stream Tests
// ~26 tests: MirrorStream.empty, observe(), sequence monotonicity,
//   immutability, observation fields, hash determinism.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { buildTopology, type GovernanceTopology } from '../../src/frame/topology.js'
import {
  MirrorStream,
  MirrorError,
  MIRROR_SCHEMA_VERSION,
} from '../../src/frame/mirror.js'

// ─── Helpers ───────────────────────────────────────────────

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }
function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }

async function makeTopology(s: number): Promise<GovernanceTopology> {
  return buildTopology({
    sitr_state: 'STABLE',
    aoie_global_state: 'SECURE',
    constitutional_verdict: 'PERMIT',
    ledger_root: h(s.toString(16).padStart(1, '0')),
    consensus_qc_hash: null,
    dfa_certificate_hash: h('c'),
    sequence: seq(s),
  })
}

// ─── Constants ─────────────────────────────────────────────

describe('constants', () => {
  it('MIRROR_SCHEMA_VERSION is 1.0.0', () => {
    expect(MIRROR_SCHEMA_VERSION).toBe('1.0.0')
  })
})

// ─── MirrorError ───────────────────────────────────────────

describe('MirrorError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new MirrorError('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('MirrorError')
    expect(e.message).toBe('test')
  })
})

// ─── MirrorStream.empty() ──────────────────────────────────

describe('MirrorStream.empty()', () => {
  it('length is 0', () => {
    expect(MirrorStream.empty().length).toBe(0)
  })

  it('latestSequence is null', () => {
    expect(MirrorStream.empty().latestSequence).toBeNull()
  })

  it('getAll() returns empty array', () => {
    expect(MirrorStream.empty().getAll()).toHaveLength(0)
  })
})

// ─── observe() — success ───────────────────────────────────

describe('MirrorStream.observe() — success', () => {
  it('returns frozen observation', async () => {
    const t = await makeTopology(1)
    const { observation } = await MirrorStream.empty().observe(t)
    expect(Object.isFrozen(observation)).toBe(true)
  })

  it('observation_hash is 64-char hex', async () => {
    const t = await makeTopology(1)
    const { observation } = await MirrorStream.empty().observe(t)
    expect(observation.observation_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(observation.observation_hash)).toBe(true)
  })

  it('is_replay_reconstructable is true', async () => {
    const t = await makeTopology(1)
    const { observation } = await MirrorStream.empty().observe(t)
    expect(observation.is_replay_reconstructable).toBe(true)
  })

  it('schema_version is 1.0.0', async () => {
    const t = await makeTopology(1)
    const { observation } = await MirrorStream.empty().observe(t)
    expect(observation.schema_version).toBe('1.0.0')
  })

  it('topology fields are preserved in observation', async () => {
    const t = await makeTopology(1)
    const { observation } = await MirrorStream.empty().observe(t)
    expect(observation.observed_topology_hash).toBe(t.topology_hash)
    expect(observation.sitr_state).toBe(t.sitr_state)
    expect(observation.aoie_global_state).toBe(t.aoie_global_state)
    expect(observation.constitutional_verdict).toBe(t.constitutional_verdict)
    expect(observation.sequence).toBe(t.sequence)
  })

  it('stream length increments after observe', async () => {
    let stream = MirrorStream.empty()
    const t1 = await makeTopology(1)
    const { stream: s2 } = await stream.observe(t1)
    expect(s2.length).toBe(1)
    const t2 = await makeTopology(2)
    const { stream: s3 } = await s2.observe(t2)
    expect(s3.length).toBe(2)
  })

  it('latestSequence updates after observe', async () => {
    const t = await makeTopology(5)
    const { stream } = await MirrorStream.empty().observe(t)
    expect(stream.latestSequence).toBe(seq(5))
  })

  it('getAll() returns all observations in order', async () => {
    let stream = MirrorStream.empty()
    for (let i = 1; i <= 3; i++) {
      const { stream: next } = await stream.observe(await makeTopology(i))
      stream = next
    }
    const all = stream.getAll()
    expect(all).toHaveLength(3)
    expect(all[0]!.sequence).toBe(seq(1))
    expect(all[1]!.sequence).toBe(seq(2))
    expect(all[2]!.sequence).toBe(seq(3))
  })
})

// ─── observe() — monotonicity ──────────────────────────────

describe('MirrorStream.observe() — sequence monotonicity', () => {
  it('non-monotonic sequence throws MirrorError', async () => {
    const t1 = await makeTopology(5)
    const { stream } = await MirrorStream.empty().observe(t1)
    const t2 = await makeTopology(3)
    await expect(stream.observe(t2)).rejects.toThrow(MirrorError)
  })

  it('equal sequence throws MirrorError', async () => {
    const t = await makeTopology(1)
    const { stream } = await MirrorStream.empty().observe(t)
    await expect(stream.observe(t)).rejects.toThrow(MirrorError)
  })
})

// ─── Immutability ──────────────────────────────────────────

describe('MirrorStream immutability', () => {
  it('original stream unchanged after observe', async () => {
    const original = MirrorStream.empty()
    await original.observe(await makeTopology(1))
    expect(original.length).toBe(0)
    expect(original.latestSequence).toBeNull()
  })
})

// ─── observation_hash determinism ─────────────────────────

describe('observation_hash', () => {
  it('is deterministic × 3', async () => {
    const t = await makeTopology(1)
    const h1 = (await MirrorStream.empty().observe(t)).observation.observation_hash
    const h2 = (await MirrorStream.empty().observe(t)).observation.observation_hash
    const h3 = (await MirrorStream.empty().observe(t)).observation.observation_hash
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('different topology → different observation_hash', async () => {
    const t1 = await makeTopology(1)
    const t2 = await makeTopology(2)
    const { observation: o1 } = await MirrorStream.empty().observe(t1)
    const { observation: o2 } = await MirrorStream.empty().observe(t2)
    expect(o1.observation_hash).not.toBe(o2.observation_hash)
  })
})
