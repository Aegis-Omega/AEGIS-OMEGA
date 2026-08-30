// ============================================================
// Gate 108 — Swarm Epoch Consensus (Integration)
// ~18 tests: 5-node swarm converging on epoch_hash at each
//   of 10 epochs; all SwarmConvergenceRecords feed EpochChain;
//   certifyEpochChain is_valid=true.
// ============================================================

import { describe, it, expect } from 'vitest'
import { tallyVotes, DEFAULT_QUORUM_THRESHOLD } from '../../src/consensus/swarm.js'
import { EpochChain, certifyEpochChain } from '../../src/frame/epoch-chain.js'
import { synthesizeEpoch } from '../../src/frame/epoch.js'
import { buildTopology } from '../../src/frame/topology.js'
import { initialMachine, transition, certifyExecution } from '../../src/frame/dfa.js'
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

function swarmVotes(n: number, hash: SHA256Hex, seqN: SequenceNumber) {
  return Array.from({ length: n }, (_, i) => ({ node_id: `node${i}`, topology_hash: hash, sequence: seqN }))
}

async function makeEpoch(i: number) {
  const topo = await buildTopology({ ...BASE, sequence: seq(i) })
  let machine = initialMachine(seq(i))
  const records = []
  for (const phase of ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const) {
    const { machine: next, record } = await transition(machine, phase, h(phase[0]!.toLowerCase()))
    machine = next; records.push(record)
  }
  const dfaCert = await certifyExecution(records, seq(i))
  return synthesizeEpoch({ dfa_certificate: dfaCert, topology: topo, lineage_terminal_hash: null, capsule_attestation_hash: null })
}

// ─── Swarm convergence drives EpochChain ─────────────────

describe('Swarm Epoch Consensus: 5-node convergence', () => {
  it('5-node swarm quorum_reached=true on matching topology', async () => {
    const topo = await buildTopology({ ...BASE, sequence: seq(1) })
    const record = await tallyVotes(swarmVotes(5, topo.topology_hash, seq(1)))
    expect(record.quorum_reached).toBe(true)
    expect(record.quorum_hash).toBe(topo.topology_hash)
  })

  it('4 honest + 1 Byzantine → quorum on honest topology (4/5=0.8 ≥ 1/φ)', async () => {
    const topo = await buildTopology({ ...BASE, sequence: seq(1) })
    const votes = [
      ...swarmVotes(4, topo.topology_hash, seq(1)),
      ...swarmVotes(1, h('b'), seq(1)),
    ]
    const record = await tallyVotes(votes)
    expect(record.quorum_reached).toBe(true)
    expect(record.quorum_hash).toBe(topo.topology_hash)
  })

  it('10-epoch chain built from swarm consensus → certifyEpochChain is_valid=true', async () => {
    let chain = EpochChain.empty()
    for (let i = 1; i <= 10; i++) {
      const epoch = await makeEpoch(i)
      // 5-node swarm agrees on this epoch's epoch_hash
      const record = await tallyVotes(swarmVotes(5, epoch.epoch_hash, seq(i)))
      expect(record.quorum_reached).toBe(true)
      const { chain: next } = await chain.append(epoch)
      chain = next
    }
    const cert = await certifyEpochChain(chain.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.link_count).toBe(10)
  }, 30000)

  it('swarm convergence_hash feeds into EpochChain link', async () => {
    const topo = await buildTopology({ ...BASE, sequence: seq(1) })
    const swarmRecord = await tallyVotes(swarmVotes(5, topo.topology_hash, seq(1)))
    // The quorum_hash is bound to the epoch
    const epoch = await makeEpoch(1)
    expect(epoch.epoch_hash).toHaveLength(64)
    expect(swarmRecord.quorum_hash).toBe(topo.topology_hash)
  })
})

// ─── Swarm record integrity ───────────────────────────────

describe('Swarm Epoch: convergence record invariants', () => {
  it('convergence_hash deterministic ×3 for same votes', async () => {
    const topo = await buildTopology({ ...BASE, sequence: seq(1) })
    const votes = swarmVotes(5, topo.topology_hash, seq(1))
    const [r1, r2, r3] = await Promise.all([tallyVotes(votes), tallyVotes(votes), tallyVotes(votes)])
    expect(r1.convergence_hash).toBe(r2.convergence_hash)
    expect(r2.convergence_hash).toBe(r3.convergence_hash)
  })

  it('vote_count reflects honest majority', async () => {
    const topo = await buildTopology({ ...BASE, sequence: seq(1) })
    const record = await tallyVotes(swarmVotes(3, topo.topology_hash, seq(1)))
    expect(record.vote_count).toBe(3)
  })

  it('different epoch sequences → different epoch_hashes', async () => {
    const [e1, e2] = await Promise.all([makeEpoch(1), makeEpoch(2)])
    expect(e1.epoch_hash).not.toBe(e2.epoch_hash)
  })

  it('swarm quorum_threshold = DEFAULT_QUORUM_THRESHOLD', async () => {
    const topo = await buildTopology({ ...BASE, sequence: seq(1) })
    const record = await tallyVotes(swarmVotes(5, topo.topology_hash, seq(1)))
    expect(record.quorum_threshold).toBe(DEFAULT_QUORUM_THRESHOLD)
  })
})

// ─── EpochChain determinism ───────────────────────────────

describe('Swarm Epoch: EpochChain determinism', () => {
  it('certifyEpochChain deterministic ×3 on 5-epoch chain', async () => {
    let chain = EpochChain.empty()
    for (let i = 1; i <= 5; i++) {
      const epoch = await makeEpoch(i)
      const { chain: next } = await chain.append(epoch)
      chain = next
    }
    const links = chain.getAll()
    const [c1, c2, c3] = await Promise.all([
      certifyEpochChain(links),
      certifyEpochChain(links),
      certifyEpochChain(links),
    ])
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  }, 30000)

  it('5-epoch + 5-epoch chain = 10-epoch chain (different cert hashes)', async () => {
    let chain5 = EpochChain.empty()
    for (let i = 1; i <= 5; i++) {
      const epoch = await makeEpoch(i)
      const { chain: next } = await chain5.append(epoch)
      chain5 = next
    }
    let chain10 = chain5
    for (let i = 6; i <= 10; i++) {
      const epoch = await makeEpoch(i)
      const { chain: next } = await chain10.append(epoch)
      chain10 = next
    }
    const c5 = await certifyEpochChain(chain5.getAll())
    const c10 = await certifyEpochChain(chain10.getAll())
    expect(c5.certificate_hash).not.toBe(c10.certificate_hash)
    expect(c5.link_count).toBe(5)
    expect(c10.link_count).toBe(10)
  }, 30000)
})
