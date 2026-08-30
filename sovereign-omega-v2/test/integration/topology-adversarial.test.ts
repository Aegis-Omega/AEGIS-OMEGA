// ============================================================
// Gate 65 — Governance Topology Adversarial (Integration)
// ~22 tests: topology_hash tamper detection across all 7 input
//   fields; topologiesConverge logic; verifyTopology rejects
//   tampered records; buildTopology determinism at scale.
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  buildTopology, computeTopologyHash, topologiesConverge, verifyTopology,
  type TopologyInput,
} from '../../src/frame/topology.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const BASE: TopologyInput = {
  sitr_state: 'STABLE',
  aoie_global_state: 'SECURE',
  constitutional_verdict: 'PERMIT',
  ledger_root: h('a'),
  consensus_qc_hash: h('b'),
  dfa_certificate_hash: h('c'),
  sequence: seq(1),
}

async function build(input: TopologyInput) {
  return buildTopology(input)
}

// ─── Tamper detection across all input fields ──────────────

describe('Topology: topology_hash tamper detection', () => {
  it('tampered sitr_state → verifyTopology=false', async () => {
    const topo = await build(BASE)
    const tampered = { ...topo, sitr_state: 'DEGRADED' as const }
    expect(await verifyTopology(tampered)).toBe(false)
  })

  it('tampered aoie_global_state → verifyTopology=false', async () => {
    const topo = await build(BASE)
    const tampered = { ...topo, aoie_global_state: 'ALERT' as const }
    expect(await verifyTopology(tampered)).toBe(false)
  })

  it('tampered constitutional_verdict → verifyTopology=false', async () => {
    const topo = await build(BASE)
    const tampered = { ...topo, constitutional_verdict: 'REJECT' as const }
    expect(await verifyTopology(tampered)).toBe(false)
  })

  it('tampered ledger_root → verifyTopology=false', async () => {
    const topo = await build(BASE)
    const tampered = { ...topo, ledger_root: h('z') }
    expect(await verifyTopology(tampered)).toBe(false)
  })

  it('tampered consensus_qc_hash → verifyTopology=false', async () => {
    const topo = await build(BASE)
    const tampered = { ...topo, consensus_qc_hash: h('z') }
    expect(await verifyTopology(tampered)).toBe(false)
  })

  it('tampered dfa_certificate_hash → verifyTopology=false', async () => {
    const topo = await build(BASE)
    const tampered = { ...topo, dfa_certificate_hash: h('z') }
    expect(await verifyTopology(tampered)).toBe(false)
  })

  it('tampered sequence → verifyTopology=false', async () => {
    const topo = await build(BASE)
    const tampered = { ...topo, sequence: seq(999) }
    expect(await verifyTopology(tampered)).toBe(false)
  })

  it('untampered topology → verifyTopology=true', async () => {
    const topo = await build(BASE)
    expect(await verifyTopology(topo)).toBe(true)
  })
})

// ─── Convergence ──────────────────────────────────────────

describe('Topology: topologiesConverge', () => {
  it('same topology_hash → topologiesConverge=true', async () => {
    const t1 = await build(BASE)
    const t2 = await build(BASE)
    expect(topologiesConverge(t1, t2)).toBe(true)
  })

  it('different ledger_root → topologiesConverge=false', async () => {
    const t1 = await build(BASE)
    const t2 = await build({ ...BASE, ledger_root: h('z') })
    expect(topologiesConverge(t1, t2)).toBe(false)
  })

  it('different sequence → topologiesConverge=false', async () => {
    const t1 = await build(BASE)
    const t2 = await build({ ...BASE, sequence: seq(2) })
    expect(topologiesConverge(t1, t2)).toBe(false)
  })
})

// ─── Determinism at scale ─────────────────────────────────

describe('Topology: buildTopology determinism at scale', () => {
  it('same input × 3 → identical topology_hash', async () => {
    const [t1, t2, t3] = await Promise.all([build(BASE), build(BASE), build(BASE)])
    expect(t1!.topology_hash).toBe(t2!.topology_hash)
    expect(t2!.topology_hash).toBe(t3!.topology_hash)
  })

  it('50 sequential topologies → 50 distinct topology_hashes', async () => {
    const hashes = new Set<string>()
    for (let i = 1; i <= 50; i++) {
      const topo = await build({ ...BASE, sequence: seq(i) })
      hashes.add(topo.topology_hash)
    }
    expect(hashes.size).toBe(50)
  })

  it('topology is frozen', async () => {
    const topo = await build(BASE)
    expect(Object.isFrozen(topo)).toBe(true)
  })

  it('is_replay_reconstructable=true', async () => {
    const topo = await build(BASE)
    expect(topo.is_replay_reconstructable).toBe(true)
  })

  it('null consensus_qc_hash is accepted (pre-consensus)', async () => {
    const topo = await build({ ...BASE, consensus_qc_hash: null })
    expect(topo.consensus_qc_hash).toBeNull()
    expect(await verifyTopology(topo)).toBe(true)
  })

  it('computeTopologyHash matches buildTopology.topology_hash', async () => {
    const hash = await computeTopologyHash(BASE)
    const topo = await build(BASE)
    expect(hash).toBe(topo.topology_hash)
  })
})
