// ============================================================
// Gate 29 — Topology Hash Engine Tests
// ~27 tests: buildTopology, computeTopologyHash, topologiesConverge,
//   verifyTopology, determinism, tamper detection, null QC.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import {
  buildTopology,
  computeTopologyHash,
  topologiesConverge,
  verifyTopology,
  TopologyError,
  TOPOLOGY_SCHEMA_VERSION,
  type TopologyInput,
} from '../../src/frame/topology.js'

// ─── Fixtures ──────────────────────────────────────────────

const SEQ = 1n as SequenceNumber
const LEDGER = ('a'.repeat(64)) as SHA256Hex
const QC    = ('b'.repeat(64)) as SHA256Hex
const DFA   = ('c'.repeat(64)) as SHA256Hex

const BASE_INPUT: TopologyInput = {
  sitr_state: 'STABLE',
  aoie_global_state: 'SECURE',
  constitutional_verdict: 'PERMIT',
  ledger_root: LEDGER,
  consensus_qc_hash: QC,
  dfa_certificate_hash: DFA,
  sequence: SEQ,
}

// ─── buildTopology ─────────────────────────────────────────

describe('buildTopology', () => {
  it('returns a frozen topology', async () => {
    const t = await buildTopology(BASE_INPUT)
    expect(Object.isFrozen(t)).toBe(true)
  })

  it('topology_hash is 64-char hex', async () => {
    const t = await buildTopology(BASE_INPUT)
    expect(t.topology_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(t.topology_hash)).toBe(true)
  })

  it('schema_version and is_replay_reconstructable are set', async () => {
    const t = await buildTopology(BASE_INPUT)
    expect(t.schema_version).toBe(TOPOLOGY_SCHEMA_VERSION)
    expect(t.is_replay_reconstructable).toBe(true)
  })

  it('all input fields are preserved verbatim', async () => {
    const t = await buildTopology(BASE_INPUT)
    expect(t.sitr_state).toBe('STABLE')
    expect(t.aoie_global_state).toBe('SECURE')
    expect(t.constitutional_verdict).toBe('PERMIT')
    expect(t.ledger_root).toBe(LEDGER)
    expect(t.consensus_qc_hash).toBe(QC)
    expect(t.dfa_certificate_hash).toBe(DFA)
    expect(t.sequence).toBe(SEQ)
  })

  it('null consensus_qc_hash is valid (pre-quorum / single-node)', async () => {
    const t = await buildTopology({ ...BASE_INPUT, consensus_qc_hash: null })
    expect(t.consensus_qc_hash).toBeNull()
    expect(t.topology_hash).toHaveLength(64)
  })
})

// ─── computeTopologyHash determinism ──────────────────────

describe('computeTopologyHash determinism', () => {
  it('same input → same hash × 3', async () => {
    const h1 = await computeTopologyHash(BASE_INPUT)
    const h2 = await computeTopologyHash(BASE_INPUT)
    const h3 = await computeTopologyHash(BASE_INPUT)
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('topology_hash matches computeTopologyHash independently', async () => {
    const t = await buildTopology(BASE_INPUT)
    const independent = await computeTopologyHash(BASE_INPUT)
    expect(t.topology_hash).toBe(independent)
  })
})

// ─── Hash sensitivity ──────────────────────────────────────

describe('topology_hash changes with each field', () => {
  it('different sitr_state', async () => {
    const h1 = await computeTopologyHash(BASE_INPUT)
    const h2 = await computeTopologyHash({ ...BASE_INPUT, sitr_state: 'COMPROMISED' })
    expect(h1).not.toBe(h2)
  })

  it('different aoie_global_state', async () => {
    const h1 = await computeTopologyHash(BASE_INPUT)
    const h2 = await computeTopologyHash({ ...BASE_INPUT, aoie_global_state: 'ALERT' })
    expect(h1).not.toBe(h2)
  })

  it('different constitutional_verdict', async () => {
    const h1 = await computeTopologyHash(BASE_INPUT)
    const h2 = await computeTopologyHash({ ...BASE_INPUT, constitutional_verdict: 'ESCALATE' })
    expect(h1).not.toBe(h2)
  })

  it('different ledger_root', async () => {
    const h1 = await computeTopologyHash(BASE_INPUT)
    const h2 = await computeTopologyHash({ ...BASE_INPUT, ledger_root: ('d'.repeat(64)) as SHA256Hex })
    expect(h1).not.toBe(h2)
  })

  it('different consensus_qc_hash', async () => {
    const h1 = await computeTopologyHash(BASE_INPUT)
    const h2 = await computeTopologyHash({ ...BASE_INPUT, consensus_qc_hash: ('e'.repeat(64)) as SHA256Hex })
    expect(h1).not.toBe(h2)
  })

  it('null vs non-null consensus_qc_hash', async () => {
    const h1 = await computeTopologyHash(BASE_INPUT)
    const h2 = await computeTopologyHash({ ...BASE_INPUT, consensus_qc_hash: null })
    expect(h1).not.toBe(h2)
  })

  it('different dfa_certificate_hash', async () => {
    const h1 = await computeTopologyHash(BASE_INPUT)
    const h2 = await computeTopologyHash({ ...BASE_INPUT, dfa_certificate_hash: ('f'.repeat(64)) as SHA256Hex })
    expect(h1).not.toBe(h2)
  })

  it('different sequence', async () => {
    const h1 = await computeTopologyHash(BASE_INPUT)
    const h2 = await computeTopologyHash({ ...BASE_INPUT, sequence: 99n as SequenceNumber })
    expect(h1).not.toBe(h2)
  })
})

// ─── topologiesConverge ────────────────────────────────────

describe('topologiesConverge', () => {
  it('identical inputs → converge = true', async () => {
    const t1 = await buildTopology(BASE_INPUT)
    const t2 = await buildTopology(BASE_INPUT)
    expect(topologiesConverge(t1, t2)).toBe(true)
  })

  it('different sitr_state → converge = false', async () => {
    const t1 = await buildTopology(BASE_INPUT)
    const t2 = await buildTopology({ ...BASE_INPUT, sitr_state: 'UNSTABLE' })
    expect(topologiesConverge(t1, t2)).toBe(false)
  })

  it('different sequence → converge = false', async () => {
    const t1 = await buildTopology(BASE_INPUT)
    const t2 = await buildTopology({ ...BASE_INPUT, sequence: 2n as SequenceNumber })
    expect(topologiesConverge(t1, t2)).toBe(false)
  })

  it('converge is symmetric: converge(a,b) === converge(b,a)', async () => {
    const t1 = await buildTopology(BASE_INPUT)
    const t2 = await buildTopology({ ...BASE_INPUT, sitr_state: 'DEGRADED' })
    expect(topologiesConverge(t1, t2)).toBe(topologiesConverge(t2, t1))
  })
})

// ─── verifyTopology ────────────────────────────────────────

describe('verifyTopology', () => {
  it('valid topology verifies as true', async () => {
    const t = await buildTopology(BASE_INPUT)
    expect(await verifyTopology(t)).toBe(true)
  })

  it('tampered topology_hash verifies as false', async () => {
    const t = await buildTopology(BASE_INPUT)
    const tampered = Object.freeze({ ...t, topology_hash: ('0'.repeat(64)) as SHA256Hex })
    expect(await verifyTopology(tampered)).toBe(false)
  })

  it('tampered field (sitr_state) verifies as false', async () => {
    const t = await buildTopology(BASE_INPUT)
    const tampered = Object.freeze({ ...t, sitr_state: 'COMPROMISED' as const })
    expect(await verifyTopology(tampered)).toBe(false)
  })

  it('verifyTopology is deterministic × 3', async () => {
    const t = await buildTopology(BASE_INPUT)
    const r1 = await verifyTopology(t)
    const r2 = await verifyTopology(t)
    const r3 = await verifyTopology(t)
    expect(r1).toBe(r2)
    expect(r2).toBe(r3)
    expect(r1).toBe(true)
  })
})

// Unused import guard — TopologyError is exported for callers
it('TopologyError is a proper Error subclass', () => {
  const e = new TopologyError('test')
  expect(e).toBeInstanceOf(Error)
  expect(e.name).toBe('TopologyError')
  expect(e.message).toBe('test')
})
