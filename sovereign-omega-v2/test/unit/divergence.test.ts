// ============================================================
// Gate 31 — Divergence Classification Engine Tests
// ~29 tests: D0..D4 classification, freeze law, convergence,
//   report determinism, severity ordering, tamper detection.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { buildTopology, type GovernanceTopology, type TopologyInput } from '../../src/frame/topology.js'
import {
  compareTopologies,
  mutationAuthorityActive,
  isMoreSevere,
} from '../../src/frame/divergence.js'

// ─── Fixtures ──────────────────────────────────────────────

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }
function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }

const BASE: TopologyInput = {
  sitr_state: 'STABLE',
  aoie_global_state: 'SECURE',
  constitutional_verdict: 'PERMIT',
  ledger_root: h('a'),
  consensus_qc_hash: h('b'),
  dfa_certificate_hash: h('c'),
  sequence: seq(1),
}

async function t(overrides: Partial<TopologyInput> = {}): Promise<GovernanceTopology> {
  return buildTopology({ ...BASE, ...overrides })
}

// ─── Convergence ───────────────────────────────────────────

describe('compareTopologies — CONVERGED', () => {
  it('identical topologies → CONVERGED', async () => {
    const t1 = await t()
    const t2 = await t()
    const result = await compareTopologies(t1, t2)
    expect(result.kind).toBe('CONVERGED')
  })

  it('converged record has correct topology_hash and sequence', async () => {
    const t1 = await t()
    const t2 = await t()
    const result = await compareTopologies(t1, t2)
    if (result.kind !== 'CONVERGED') throw new Error('expected CONVERGED')
    expect(result.record.topology_hash).toBe(t1.topology_hash)
    expect(result.record.sequence).toBe(seq(1))
    expect(result.record.is_converged).toBe(true)
    expect(Object.isFrozen(result.record)).toBe(true)
  })
})

// ─── D0 — sequence drift ───────────────────────────────────

describe('D0 — observational drift (sequence only)', () => {
  it('different sequence with matching state → D0', async () => {
    const t1 = await t({ sequence: seq(1) })
    const t2 = await t({ sequence: seq(2) })
    const result = await compareTopologies(t1, t2)
    expect(result.kind).toBe('DIVERGED')
    if (result.kind !== 'DIVERGED') return
    expect(result.report.divergence_class).toBe('D0')
    expect(result.report.mutation_authority_active).toBe(true)
  })
})

// ─── D1 — serializer mismatch ──────────────────────────────

describe('D1 — serializer mismatch (same seq, different classification)', () => {
  it('same seq, different sitr_state → D1', async () => {
    const t1 = await t()
    const t2 = await t({ sitr_state: 'DEGRADED' })
    const result = await compareTopologies(t1, t2)
    expect(result.kind).toBe('DIVERGED')
    if (result.kind !== 'DIVERGED') return
    expect(result.report.divergence_class).toBe('D1')
    expect(result.report.mutation_authority_active).toBe(true)
  })

  it('same seq, different constitutional_verdict → D1', async () => {
    const t1 = await t()
    const t2 = await t({ constitutional_verdict: 'ESCALATE' })
    const result = await compareTopologies(t1, t2)
    if (result.kind !== 'DIVERGED') throw new Error('expected DIVERGED')
    expect(result.report.divergence_class).toBe('D1')
  })
})

// ─── D2 — topology mismatch ────────────────────────────────

describe('D2 — topology mismatch (ledger or DFA)', () => {
  it('different ledger_root → D2, mutation frozen', async () => {
    const t1 = await t()
    const t2 = await t({ ledger_root: h('d') })
    const result = await compareTopologies(t1, t2)
    expect(result.kind).toBe('DIVERGED')
    if (result.kind !== 'DIVERGED') return
    expect(result.report.divergence_class).toBe('D2')
    expect(result.report.mutation_authority_active).toBe(false)
  })

  it('different dfa_certificate_hash → D2', async () => {
    const t1 = await t()
    const t2 = await t({ dfa_certificate_hash: h('e') })
    const result = await compareTopologies(t1, t2)
    if (result.kind !== 'DIVERGED') throw new Error('expected DIVERGED')
    expect(result.report.divergence_class).toBe('D2')
    expect(result.report.mutation_authority_active).toBe(false)
  })
})

// ─── D3 — ownership inconsistency ──────────────────────────

describe('D3 — ownership inconsistency (consensus_qc_hash)', () => {
  it('same ledger+DFA, different consensus_qc_hash → D3', async () => {
    const t1 = await t()
    const t2 = await t({ consensus_qc_hash: h('f') })
    const result = await compareTopologies(t1, t2)
    if (result.kind !== 'DIVERGED') throw new Error('expected DIVERGED')
    expect(result.report.divergence_class).toBe('D3')
    expect(result.report.mutation_authority_active).toBe(false)
  })

  it('null vs non-null consensus_qc_hash → D3', async () => {
    const t1 = await t()
    const t2 = await t({ consensus_qc_hash: null })
    const result = await compareTopologies(t1, t2)
    if (result.kind !== 'DIVERGED') throw new Error('expected DIVERGED')
    expect(result.report.divergence_class).toBe('D3')
  })
})

// ─── D4 — constitutional invalidity ────────────────────────

describe('D4 — constitutional invalidity (tampered topology)', () => {
  it('tampered topology_hash → D4', async () => {
    const t1 = await t()
    const tampered = Object.freeze({ ...t1, topology_hash: h('0') })
    const result = await compareTopologies(t1, tampered)
    if (result.kind !== 'DIVERGED') throw new Error('expected DIVERGED')
    expect(result.report.divergence_class).toBe('D4')
    expect(result.report.mutation_authority_active).toBe(false)
  })
})

// ─── DivergenceReport properties ──────────────────────────

describe('DivergenceReport structure', () => {
  it('report is frozen', async () => {
    const t1 = await t()
    const t2 = await t({ sequence: seq(2) })
    const result = await compareTopologies(t1, t2)
    if (result.kind !== 'DIVERGED') throw new Error('expected DIVERGED')
    expect(Object.isFrozen(result.report)).toBe(true)
  })

  it('report_hash is 64-char hex', async () => {
    const t1 = await t()
    const t2 = await t({ sequence: seq(2) })
    const result = await compareTopologies(t1, t2)
    if (result.kind !== 'DIVERGED') throw new Error('expected DIVERGED')
    expect(result.report.report_hash).toHaveLength(64)
  })

  it('report_hash is deterministic × 3', async () => {
    const t1 = await t()
    const t2 = await t({ sequence: seq(2) })
    const r1 = await compareTopologies(t1, t2)
    const r2 = await compareTopologies(t1, t2)
    const r3 = await compareTopologies(t1, t2)
    if (r1.kind !== 'DIVERGED' || r2.kind !== 'DIVERGED' || r3.kind !== 'DIVERGED') return
    expect(r1.report.report_hash).toBe(r2.report.report_hash)
    expect(r2.report.report_hash).toBe(r3.report.report_hash)
  })

  it('is_replay_reconstructable is true', async () => {
    const t1 = await t()
    const t2 = await t({ sequence: seq(2) })
    const result = await compareTopologies(t1, t2)
    if (result.kind !== 'DIVERGED') throw new Error('expected DIVERGED')
    expect(result.report.is_replay_reconstructable).toBe(true)
  })
})

// ─── mutationAuthorityActive (freeze law) ─────────────────

describe('mutationAuthorityActive — Divergence Freeze Law', () => {
  it('empty reports → authority active', () => {
    expect(mutationAuthorityActive([])).toBe(true)
  })

  it('all D0 reports → authority active', async () => {
    const t1 = await t({ sequence: seq(1) })
    const t2 = await t({ sequence: seq(2) })
    const r = await compareTopologies(t1, t2)
    if (r.kind !== 'DIVERGED') throw new Error()
    expect(mutationAuthorityActive([r.report])).toBe(true)
  })

  it('any D2 report → authority frozen', async () => {
    const t1 = await t()
    const t2 = await t({ ledger_root: h('z') })
    const r = await compareTopologies(t1, t2)
    if (r.kind !== 'DIVERGED') throw new Error()
    expect(mutationAuthorityActive([r.report])).toBe(false)
  })

  it('mix of D0 and D2 → authority frozen', async () => {
    const t1 = await t({ sequence: seq(1) })
    const t2 = await t({ sequence: seq(2) })
    const t3 = await t({ ledger_root: h('z') })
    const r1 = await compareTopologies(t1, t2)
    const r2 = await compareTopologies(t1, t3)
    if (r1.kind !== 'DIVERGED' || r2.kind !== 'DIVERGED') throw new Error()
    expect(mutationAuthorityActive([r1.report, r2.report])).toBe(false)
  })
})

// ─── isMoreSevere ──────────────────────────────────────────

describe('isMoreSevere', () => {
  it('D4 > D3 > D2 > D1 > D0', () => {
    expect(isMoreSevere('D4', 'D3')).toBe(true)
    expect(isMoreSevere('D3', 'D2')).toBe(true)
    expect(isMoreSevere('D2', 'D1')).toBe(true)
    expect(isMoreSevere('D1', 'D0')).toBe(true)
  })

  it('D0 is not more severe than D0', () => {
    expect(isMoreSevere('D0', 'D0')).toBe(false)
  })

  it('D0 is not more severe than D4', () => {
    expect(isMoreSevere('D0', 'D4')).toBe(false)
  })
})
