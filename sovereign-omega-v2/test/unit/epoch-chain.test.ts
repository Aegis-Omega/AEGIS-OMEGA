// ============================================================
// Gate 40 — Epoch Chain Tests
// ~26 tests: EpochChain.empty, append, hash chaining,
//   sequence monotonicity, certifyEpochChain, tamper detection.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { initialMachine, transition, certifyExecution } from '../../src/frame/dfa.js'
import { buildTopology } from '../../src/frame/topology.js'
import { synthesizeEpoch } from '../../src/frame/epoch.js'
import type { EpochRecord } from '../../src/frame/epoch.js'
import {
  EpochChain,
  EpochChainError,
  certifyEpochChain,
  EPOCH_GENESIS_HASH,
  EPOCH_CHAIN_SCHEMA_VERSION,
} from '../../src/frame/epoch-chain.js'

// ─── Helpers ───────────────────────────────────────────────

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }
function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }

async function makeEpoch(s: number): Promise<EpochRecord> {
  let m = initialMachine(seq(s))
  const hashes: SHA256Hex[] = [h('0'), h('1'), h('2'), h('3'), h('4')]
  const phases = ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const
  const records = []
  for (let i = 0; i < phases.length; i++) {
    const { machine, record } = await transition(m, phases[i]!, hashes[i]!)
    records.push(record)
    m = machine
  }
  const cert = await certifyExecution(records, seq(s))
  const topology = await buildTopology({
    sitr_state: 'STABLE', aoie_global_state: 'SECURE',
    constitutional_verdict: 'PERMIT', ledger_root: h('a'),
    consensus_qc_hash: null, dfa_certificate_hash: h('c'),
    sequence: seq(s),
  })
  return synthesizeEpoch({ dfa_certificate: cert, topology, lineage_terminal_hash: null, capsule_attestation_hash: null })
}

async function buildChain(length: number): Promise<EpochChain> {
  let chain = EpochChain.empty()
  for (let i = 1; i <= length; i++) {
    const { chain: next } = await chain.append(await makeEpoch(i))
    chain = next
  }
  return chain
}

// ─── Constants ─────────────────────────────────────────────

describe('constants', () => {
  it('EPOCH_CHAIN_SCHEMA_VERSION is 1.0.0', () => {
    expect(EPOCH_CHAIN_SCHEMA_VERSION).toBe('1.0.0')
  })

  it('EPOCH_GENESIS_HASH is 64 zero chars', () => {
    expect(EPOCH_GENESIS_HASH).toBe('0'.repeat(64))
  })
})

// ─── EpochChainError ───────────────────────────────────────

describe('EpochChainError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new EpochChainError('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('EpochChainError')
  })
})

// ─── EpochChain.empty() ────────────────────────────────────

describe('EpochChain.empty()', () => {
  it('length is 0', () => { expect(EpochChain.empty().length).toBe(0) })
  it('lastHash is EPOCH_GENESIS_HASH', () => { expect(EpochChain.empty().lastHash).toBe(EPOCH_GENESIS_HASH) })
  it('lastSequence is null', () => { expect(EpochChain.empty().lastSequence).toBeNull() })
  it('getAll() returns empty array', () => { expect(EpochChain.empty().getAll()).toHaveLength(0) })
})

// ─── EpochChain.append() ───────────────────────────────────

describe('EpochChain.append()', () => {
  it('link is frozen', async () => {
    const { link } = await EpochChain.empty().append(await makeEpoch(1))
    expect(Object.isFrozen(link)).toBe(true)
  })

  it('link_hash is 64-char hex', async () => {
    const { link } = await EpochChain.empty().append(await makeEpoch(1))
    expect(link.link_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(link.link_hash)).toBe(true)
  })

  it('first link previous_epoch_hash is EPOCH_GENESIS_HASH', async () => {
    const { link } = await EpochChain.empty().append(await makeEpoch(1))
    expect(link.previous_epoch_hash).toBe(EPOCH_GENESIS_HASH)
  })

  it('second link previous_epoch_hash equals first link_hash', async () => {
    const { chain: c1, link: l1 } = await EpochChain.empty().append(await makeEpoch(1))
    const { link: l2 } = await c1.append(await makeEpoch(2))
    expect(l2.previous_epoch_hash).toBe(l1.link_hash)
  })

  it('lastHash updates after append', async () => {
    const { chain, link } = await EpochChain.empty().append(await makeEpoch(1))
    expect(chain.lastHash).toBe(link.link_hash)
  })

  it('lastSequence updates after append', async () => {
    const { chain } = await EpochChain.empty().append(await makeEpoch(3))
    expect(chain.lastSequence).toBe(seq(3))
  })

  it('link_hash is deterministic × 3', async () => {
    const epoch = await makeEpoch(1)
    const h1 = (await EpochChain.empty().append(epoch)).link.link_hash
    const h2 = (await EpochChain.empty().append(epoch)).link.link_hash
    const h3 = (await EpochChain.empty().append(epoch)).link.link_hash
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('original chain unchanged after append (immutable)', async () => {
    const original = EpochChain.empty()
    await original.append(await makeEpoch(1))
    expect(original.length).toBe(0)
    expect(original.lastSequence).toBeNull()
  })

  it('non-monotonic sequence throws EpochChainError', async () => {
    const { chain } = await EpochChain.empty().append(await makeEpoch(5))
    await expect(chain.append(await makeEpoch(3))).rejects.toThrow(EpochChainError)
  })

  it('schema_version and is_replay_reconstructable set correctly', async () => {
    const { link } = await EpochChain.empty().append(await makeEpoch(1))
    expect(link.schema_version).toBe('1.0.0')
    expect(link.is_replay_reconstructable).toBe(true)
  })
})

// ─── certifyEpochChain ─────────────────────────────────────

describe('certifyEpochChain', () => {
  it('empty chain → is_valid: true, link_count: 0, terminal_hash: null', async () => {
    const cert = await certifyEpochChain([])
    expect(cert.is_valid).toBe(true)
    expect(cert.link_count).toBe(0)
    expect(cert.terminal_hash).toBeNull()
  })

  it('valid 4-link chain → is_valid: true', async () => {
    const chain = await buildChain(4)
    const cert = await certifyEpochChain(chain.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.link_count).toBe(4)
    expect(cert.terminal_hash).toHaveLength(64)
    expect(cert.is_replay_reconstructable).toBe(true)
  })

  it('certificate is frozen', async () => {
    const cert = await certifyEpochChain([])
    expect(Object.isFrozen(cert)).toBe(true)
  })

  it('certificate_hash is deterministic × 3', async () => {
    const chain = await buildChain(3)
    const links = chain.getAll()
    const c1 = await certifyEpochChain(links)
    const c2 = await certifyEpochChain(links)
    const c3 = await certifyEpochChain(links)
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })

  it('tampered previous_epoch_hash → is_valid: false', async () => {
    const chain = await buildChain(3)
    const links = [...chain.getAll()]
    const tampered = [
      links[0]!,
      Object.freeze({ ...links[1]!, previous_epoch_hash: h('f') }),
      links[2]!,
    ]
    const cert = await certifyEpochChain(tampered)
    expect(cert.is_valid).toBe(false)
  })

  it('tampered link_hash → is_valid: false', async () => {
    const chain = await buildChain(3)
    const links = [...chain.getAll()]
    const tampered = [
      links[0]!,
      Object.freeze({ ...links[1]!, link_hash: h('e') }),
      links[2]!,
    ]
    const cert = await certifyEpochChain(tampered)
    expect(cert.is_valid).toBe(false)
  })
})
