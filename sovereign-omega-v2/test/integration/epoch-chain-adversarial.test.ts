// ============================================================
// Gate 67 — EpochChain Adversarial (Integration)
// ~22 tests: 50-epoch chain certification; tamper at epoch 25
//   → is_valid=false; chain hash length-sensitivity; non-monotone
//   sequence throws; terminal_hash tracking; determinism ×3.
// ============================================================

import { describe, it, expect } from 'vitest'
import { EpochChain, certifyEpochChain, EPOCH_GENESIS_HASH, EpochChainError } from '../../src/frame/epoch-chain.js'
import { synthesizeEpoch } from '../../src/frame/epoch.js'
import { buildTopology } from '../../src/frame/topology.js'
import { initialMachine, transition, certifyExecution } from '../../src/frame/dfa.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const BASE_TOPOLOGY_INPUT = {
  sitr_state: 'STABLE' as const,
  aoie_global_state: 'SECURE' as const,
  constitutional_verdict: 'PERMIT' as const,
  ledger_root: h('a'),
  consensus_qc_hash: h('b'),
  dfa_certificate_hash: h('c'),
  sequence: seq(1),
}

async function buildEpoch(n: number) {
  const seqN = seq(n)
  // Build DFA trace
  let machine = initialMachine(seqN)
  const records = []
  for (const phase of ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const) {
    const { machine: next, record } = await transition(machine, phase, h(phase[0]!.toLowerCase()))
    machine = next
    records.push(record)
  }
  const cert = await certifyExecution(records, seqN)
  const topology = await buildTopology({ ...BASE_TOPOLOGY_INPUT, dfa_certificate_hash: cert.certificate_hash, sequence: seqN })
  return synthesizeEpoch({ dfa_certificate: cert, topology, lineage_terminal_hash: null, capsule_attestation_hash: null })
}

async function buildChain(n: number): Promise<EpochChain> {
  let chain = EpochChain.empty()
  for (let i = 1; i <= n; i++) {
    const epoch = await buildEpoch(i)
    const { chain: next } = await chain.append(epoch)
    chain = next
  }
  return chain
}

// ─── 50-epoch chain ───────────────────────────────────────

describe('EpochChain: 50-epoch certification', () => {
  it('50 epochs → chain.length=50, certifyEpochChain is_valid=true', async () => {
    const chain = await buildChain(50)
    expect(chain.length).toBe(50)
    const cert = await certifyEpochChain(chain.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.link_count).toBe(50)
  })

  it('certifyEpochChain deterministic ×3 on 50-epoch chain', async () => {
    const chain = await buildChain(50)
    const links = chain.getAll()
    const [c1, c2, c3] = await Promise.all([
      certifyEpochChain(links),
      certifyEpochChain(links),
      certifyEpochChain(links),
    ])
    expect(c1!.certificate_hash).toBe(c2!.certificate_hash)
    expect(c2!.certificate_hash).toBe(c3!.certificate_hash)
  })

  it('terminal_hash of 50-epoch chain matches last link_hash', async () => {
    const chain = await buildChain(50)
    const links = chain.getAll()
    const cert = await certifyEpochChain(links)
    expect(cert.terminal_hash).toBe(links[49]!.link_hash)
  })
})

// ─── Tamper detection at position 25 ──────────────────────

describe('EpochChain: tamper detection', () => {
  it('tamper link_hash at position 25 → is_valid=false', async () => {
    const chain = await buildChain(50)
    const links = [...chain.getAll()]
    links[24] = { ...links[24]!, link_hash: h('z') }
    const cert = await certifyEpochChain(links)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper epoch_hash at position 1 → is_valid=false', async () => {
    const chain = await buildChain(10)
    const links = [...chain.getAll()]
    links[0] = { ...links[0]!, epoch_hash: h('z') }
    const cert = await certifyEpochChain(links)
    expect(cert.is_valid).toBe(false)
  })

  it('tamper previous_epoch_hash at position 5 → is_valid=false', async () => {
    const chain = await buildChain(10)
    const links = [...chain.getAll()]
    links[4] = { ...links[4]!, previous_epoch_hash: h('z') }
    const cert = await certifyEpochChain(links)
    expect(cert.is_valid).toBe(false)
  })
})

// ─── Chain hash length-sensitivity ───────────────────────

describe('EpochChain: certificate_hash length-sensitivity', () => {
  it('5-epoch chain ≠ 6-epoch chain certificate_hash', async () => {
    const c5 = await certifyEpochChain((await buildChain(5)).getAll())
    const c6 = await certifyEpochChain((await buildChain(6)).getAll())
    expect(c5.certificate_hash).not.toBe(c6.certificate_hash)
  })

  it('empty chain → terminal_hash=null, is_valid=true', async () => {
    const cert = await certifyEpochChain([])
    expect(cert.is_valid).toBe(true)
    expect(cert.terminal_hash).toBeNull()
    expect(cert.link_count).toBe(0)
  })
})

// ─── Non-monotone sequence ────────────────────────────────

describe('EpochChain: monotonicity enforcement', () => {
  it('non-monotone sequence throws EpochChainError', async () => {
    let chain = EpochChain.empty()
    const e1 = await buildEpoch(1)
    const e2 = await buildEpoch(2)
    const { chain: next } = await chain.append(e2)
    chain = next
    await expect(chain.append(e1)).rejects.toThrow(EpochChainError)
  })

  it('empty chain has lastHash=EPOCH_GENESIS_HASH', () => {
    expect(EpochChain.empty().lastHash).toBe(EPOCH_GENESIS_HASH)
  })

  it('first link.previous_epoch_hash === EPOCH_GENESIS_HASH', async () => {
    const epoch = await buildEpoch(1)
    const { chain } = await EpochChain.empty().append(epoch)
    expect(chain.getAll()[0]!.previous_epoch_hash).toBe(EPOCH_GENESIS_HASH)
  })

  it('immutable: original chain unchanged after append', async () => {
    const chain = EpochChain.empty()
    const epoch = await buildEpoch(1)
    await chain.append(epoch)
    expect(chain.length).toBe(0)
  })
})
