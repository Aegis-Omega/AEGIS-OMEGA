// ============================================================
// Gate 43 — Divergence Adversarial Simulation
// ~24 tests: 5-node network partition, cascading drift,
//   severity ordering totality, tamper-induced D1 vs D4,
//   freeze law idempotency, empty-to-D4 authority progression.
//
// Uses only existing compareTopologies, mutationAuthorityActive,
// and isMoreSevere — no src changes.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { buildTopology, type TopologyInput } from '../../src/frame/topology.js'
import {
  compareTopologies,
  mutationAuthorityActive,
  isMoreSevere,
  type DivergenceClass,
  type DivergenceReport,
} from '../../src/frame/divergence.js'

// ─── Helpers ───────────────────────────────────────────────

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const BASE: TopologyInput = {
  sitr_state: 'STABLE',
  aoie_global_state: 'SECURE',
  constitutional_verdict: 'PERMIT',
  ledger_root: h('a'),
  consensus_qc_hash: h('q'),
  dfa_certificate_hash: h('d'),
  sequence: seq(10),
}

// ─── Scenario 1 — 5-node network partition ─────────────────
// Nodes A/B/C share ledger_root X; nodes D/E share ledger_root Y.
// Different ledger_root → D2. mutationAuthorityActive must be false.

describe('Scenario 1: 5-node network partition (D2)', () => {
  it('A vs D: different ledger_root → D2', async () => {
    const nodeA = await buildTopology({ ...BASE, ledger_root: h('a') })
    const nodeD = await buildTopology({ ...BASE, ledger_root: h('b') })
    const result = await compareTopologies(nodeA, nodeD)
    expect(result.kind).toBe('DIVERGED')
    if (result.kind === 'DIVERGED') {
      expect(result.report.divergence_class).toBe('D2')
      expect(result.report.mutation_authority_active).toBe(false)
    }
  })

  it('A vs B: same ledger_root → CONVERGED', async () => {
    const nodeA = await buildTopology({ ...BASE, ledger_root: h('a') })
    const nodeB = await buildTopology({ ...BASE, ledger_root: h('a') })
    const result = await compareTopologies(nodeA, nodeB)
    expect(result.kind).toBe('CONVERGED')
  })

  it('D2 report: mutationAuthorityActive([d2]) === false', async () => {
    const nodeA = await buildTopology({ ...BASE, ledger_root: h('a') })
    const nodeD = await buildTopology({ ...BASE, ledger_root: h('b') })
    const result = await compareTopologies(nodeA, nodeD)
    expect(result.kind).toBe('DIVERGED')
    if (result.kind === 'DIVERGED') {
      expect(mutationAuthorityActive([result.report])).toBe(false)
    }
  })

  it('mixed reports (D0 + D2): authority still frozen', async () => {
    const nodeA = await buildTopology({ ...BASE, sequence: seq(10) })
    const nodeB = await buildTopology({ ...BASE, sequence: seq(11) })  // D0
    const nodeC = await buildTopology({ ...BASE, ledger_root: h('b') })  // D2

    const r1 = await compareTopologies(nodeA, nodeB)
    const r2 = await compareTopologies(nodeA, nodeC)
    expect(r1.kind).toBe('DIVERGED')
    expect(r2.kind).toBe('DIVERGED')
    if (r1.kind === 'DIVERGED' && r2.kind === 'DIVERGED') {
      expect(r1.report.divergence_class).toBe('D0')
      expect(r2.report.divergence_class).toBe('D2')
      expect(mutationAuthorityActive([r1.report, r2.report])).toBe(false)
    }
  })
})

// ─── Scenario 2 — Cascading drift (D0 → D1 → D2) ─────────
// Authority freezes when D2 appears; stays frozen even with D0 present.

describe('Scenario 2: cascading drift then freeze', () => {
  it('D0 alone: authority active', async () => {
    const a = await buildTopology({ ...BASE, sequence: seq(1) })
    const b = await buildTopology({ ...BASE, sequence: seq(2) })
    const r = await compareTopologies(a, b)
    expect(r.kind).toBe('DIVERGED')
    if (r.kind === 'DIVERGED') {
      expect(r.report.divergence_class).toBe('D0')
      expect(mutationAuthorityActive([r.report])).toBe(true)
    }
  })

  it('D1 alone: authority still active', async () => {
    const a = await buildTopology({ ...BASE, constitutional_verdict: 'PERMIT' })
    const b = await buildTopology({ ...BASE, constitutional_verdict: 'DEFER' })
    const r = await compareTopologies(a, b)
    expect(r.kind).toBe('DIVERGED')
    if (r.kind === 'DIVERGED') {
      expect(r.report.divergence_class).toBe('D1')
      expect(mutationAuthorityActive([r.report])).toBe(true)
    }
  })

  it('D2 appears: authority freezes', async () => {
    const a = await buildTopology({ ...BASE })
    const b = await buildTopology({ ...BASE, ledger_root: h('x') })
    const r = await compareTopologies(a, b)
    expect(r.kind).toBe('DIVERGED')
    if (r.kind === 'DIVERGED') {
      expect(r.report.divergence_class).toBe('D2')
      expect(mutationAuthorityActive([r.report])).toBe(false)
    }
  })

  it('D0 added after D2: authority stays frozen', async () => {
    const base = await buildTopology({ ...BASE })
    const drift = await buildTopology({ ...BASE, sequence: seq(11) })  // D0
    const mismatch = await buildTopology({ ...BASE, ledger_root: h('z') })  // D2

    const r0 = await compareTopologies(base, drift)
    const r2 = await compareTopologies(base, mismatch)
    expect(r0.kind).toBe('DIVERGED')
    expect(r2.kind).toBe('DIVERGED')
    if (r0.kind === 'DIVERGED' && r2.kind === 'DIVERGED') {
      expect(mutationAuthorityActive([r2.report, r0.report])).toBe(false)
    }
  })
})

// ─── Scenario 3 — Severity ordering totality ──────────────
// D4 > D3 > D2 > D1 > D0 for all 10 consecutive pairs.
// Antisymmetry: isMoreSevere(a, b) && isMoreSevere(b, a) is never true.

describe('Scenario 3: severity ordering totality', () => {
  const classes: DivergenceClass[] = ['D0', 'D1', 'D2', 'D3', 'D4']

  it('strict ordering: D1>D0, D2>D1, D3>D2, D4>D3', () => {
    expect(isMoreSevere('D1', 'D0')).toBe(true)
    expect(isMoreSevere('D2', 'D1')).toBe(true)
    expect(isMoreSevere('D3', 'D2')).toBe(true)
    expect(isMoreSevere('D4', 'D3')).toBe(true)
  })

  it('transitivity: D4>D0, D4>D1, D4>D2, D3>D0, D3>D1, D2>D0', () => {
    expect(isMoreSevere('D4', 'D0')).toBe(true)
    expect(isMoreSevere('D4', 'D1')).toBe(true)
    expect(isMoreSevere('D4', 'D2')).toBe(true)
    expect(isMoreSevere('D3', 'D0')).toBe(true)
    expect(isMoreSevere('D3', 'D1')).toBe(true)
    expect(isMoreSevere('D2', 'D0')).toBe(true)
  })

  it('antisymmetry: isMoreSevere(a, b) && isMoreSevere(b, a) is always false', () => {
    for (const a of classes) {
      for (const b of classes) {
        expect(isMoreSevere(a, b) && isMoreSevere(b, a)).toBe(false)
      }
    }
  })

  it('irreflexivity: isMoreSevere(x, x) is always false', () => {
    for (const c of classes) {
      expect(isMoreSevere(c, c)).toBe(false)
    }
  })
})

// ─── Scenario 4 — Tamper-induced D1 vs D4 ─────────────────
// Tamper constitutional_verdict via buildTopology (self-consistent hash).
// → D1 (same seq, same ledger/DFA, different verdict).
// Tamper topology_hash directly (self-inconsistent) → D4.

describe('Scenario 4: tamper-induced D1 and D4', () => {
  it('different verdict via buildTopology → D1', async () => {
    const a = await buildTopology({ ...BASE, constitutional_verdict: 'PERMIT' })
    const b = await buildTopology({ ...BASE, constitutional_verdict: 'DEFER' })
    const r = await compareTopologies(a, b)
    expect(r.kind).toBe('DIVERGED')
    if (r.kind === 'DIVERGED') {
      expect(r.report.divergence_class).toBe('D1')
    }
  })

  it('D1 report: mutation authority still active', async () => {
    const a = await buildTopology({ ...BASE, constitutional_verdict: 'PERMIT' })
    const b = await buildTopology({ ...BASE, constitutional_verdict: 'DEFER' })
    const r = await compareTopologies(a, b)
    if (r.kind === 'DIVERGED') {
      expect(r.report.mutation_authority_active).toBe(true)
    }
  })

  it('manually tampered topology_hash → D4', async () => {
    const a = await buildTopology({ ...BASE })
    // Tamper b: corrupt topology_hash so verifyTopology fails
    const b_raw = await buildTopology({ ...BASE })
    const b_tampered = Object.freeze({ ...b_raw, topology_hash: h('f') })
    const r = await compareTopologies(a, b_tampered)
    expect(r.kind).toBe('DIVERGED')
    if (r.kind === 'DIVERGED') {
      expect(r.report.divergence_class).toBe('D4')
    }
  })

  it('D4 report: mutation authority inactive', async () => {
    const a = await buildTopology({ ...BASE })
    const b_raw = await buildTopology({ ...BASE })
    const b_tampered = Object.freeze({ ...b_raw, topology_hash: h('f') })
    const r = await compareTopologies(a, b_tampered)
    if (r.kind === 'DIVERGED') {
      expect(r.report.mutation_authority_active).toBe(false)
      expect(mutationAuthorityActive([r.report])).toBe(false)
    }
  })
})

// ─── Scenario 5 — Freeze law idempotency ──────────────────
// mutationAuthorityActive called ≥3× on same report set → identical result.

describe('Scenario 5: freeze law idempotency', () => {
  it('mutationAuthorityActive([]) is true × 3', () => {
    const r1 = mutationAuthorityActive([])
    const r2 = mutationAuthorityActive([])
    const r3 = mutationAuthorityActive([])
    expect(r1).toBe(true)
    expect(r2).toBe(true)
    expect(r3).toBe(true)
  })

  it('mutationAuthorityActive([d2_report]) is false × 3', async () => {
    const a = await buildTopology({ ...BASE })
    const b = await buildTopology({ ...BASE, ledger_root: h('b') })
    const r = await compareTopologies(a, b)
    expect(r.kind).toBe('DIVERGED')
    if (r.kind === 'DIVERGED') {
      const reports: readonly DivergenceReport[] = [r.report]
      const v1 = mutationAuthorityActive(reports)
      const v2 = mutationAuthorityActive(reports)
      const v3 = mutationAuthorityActive(reports)
      expect(v1).toBe(false)
      expect(v2).toBe(false)
      expect(v3).toBe(false)
    }
  })

  it('mutationAuthorityActive([d0_report]) is true × 3', async () => {
    const a = await buildTopology({ ...BASE, sequence: seq(1) })
    const b = await buildTopology({ ...BASE, sequence: seq(2) })
    const r = await compareTopologies(a, b)
    expect(r.kind).toBe('DIVERGED')
    if (r.kind === 'DIVERGED') {
      const reports: readonly DivergenceReport[] = [r.report]
      expect(mutationAuthorityActive(reports)).toBe(true)
      expect(mutationAuthorityActive(reports)).toBe(true)
      expect(mutationAuthorityActive(reports)).toBe(true)
    }
  })
})

// ─── Scenario 6 — Empty-to-D4 authority progression ───────
// Inserting reports of each class in order confirms authority flips at D2.

describe('Scenario 6: empty-to-D4 authority progression', () => {
  it('no reports: authority active', () => {
    expect(mutationAuthorityActive([])).toBe(true)
  })

  it('D0 report: authority active', async () => {
    const a = await buildTopology({ ...BASE, sequence: seq(1) })
    const b = await buildTopology({ ...BASE, sequence: seq(2) })
    const r = await compareTopologies(a, b)
    if (r.kind === 'DIVERGED') {
      expect(r.report.divergence_class).toBe('D0')
      expect(mutationAuthorityActive([r.report])).toBe(true)
    }
  })

  it('D1 report: authority still active', async () => {
    const a = await buildTopology({ ...BASE, constitutional_verdict: 'PERMIT' })
    const b = await buildTopology({ ...BASE, constitutional_verdict: 'REJECT' })
    const r = await compareTopologies(a, b)
    if (r.kind === 'DIVERGED') {
      expect(r.report.divergence_class).toBe('D1')
      expect(mutationAuthorityActive([r.report])).toBe(true)
    }
  })

  it('D2 report: authority frozen', async () => {
    const a = await buildTopology({ ...BASE })
    const b = await buildTopology({ ...BASE, ledger_root: h('c') })
    const r = await compareTopologies(a, b)
    if (r.kind === 'DIVERGED') {
      expect(r.report.divergence_class).toBe('D2')
      expect(mutationAuthorityActive([r.report])).toBe(false)
    }
  })

  it('D3 report: authority frozen', async () => {
    const a = await buildTopology({ ...BASE, consensus_qc_hash: h('q') })
    const b = await buildTopology({ ...BASE, consensus_qc_hash: h('r') })
    const r = await compareTopologies(a, b)
    if (r.kind === 'DIVERGED') {
      expect(r.report.divergence_class).toBe('D3')
      expect(mutationAuthorityActive([r.report])).toBe(false)
    }
  })

  it('D4 report: authority frozen', async () => {
    const a = await buildTopology({ ...BASE })
    const b_raw = await buildTopology({ ...BASE })
    const b_tampered = Object.freeze({ ...b_raw, topology_hash: h('e') })
    const r = await compareTopologies(a, b_tampered)
    if (r.kind === 'DIVERGED') {
      expect(r.report.divergence_class).toBe('D4')
      expect(mutationAuthorityActive([r.report])).toBe(false)
    }
  })
})
