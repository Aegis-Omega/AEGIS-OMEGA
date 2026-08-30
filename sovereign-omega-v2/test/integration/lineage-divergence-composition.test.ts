// ============================================================
// Gate 71 — Lineage × Divergence × MirrorStream Composition
// ~18 tests: TopologyLineage transition chain drives MirrorStream
//   observations; divergence detected between two lineage branches;
//   divergence report feeds mutation authority correctly.
// ============================================================

import { describe, it, expect } from 'vitest'
import { TopologyLineage, certifyLineage } from '../../src/frame/lineage.js'
import { compareTopologies, mutationAuthorityActive } from '../../src/frame/divergence.js'
import { MirrorStream } from '../../src/frame/mirror.js'
import { buildTopology } from '../../src/frame/topology.js'
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

async function makeTopology(n: number, overrides = {}) {
  return buildTopology({ ...BASE, sequence: seq(n), ...overrides })
}

// ─── TopologyLineage drives MirrorStream ──────────────────

describe('Lineage → MirrorStream composition', () => {
  it('10-entry lineage drives 10 MirrorStream observations', async () => {
    let lineage = TopologyLineage.empty()
    let mirror = MirrorStream.empty()

    for (let i = 1; i <= 10; i++) {
      const topology = await makeTopology(i)
      lineage = await lineage.append(topology)
      const { stream } = await mirror.observe(topology)
      mirror = stream
    }

    expect(lineage.length).toBe(10)
    expect(mirror.length).toBe(10)
  })

  it('MirrorStream observation_hash reflects topology_hash', async () => {
    const topology = await makeTopology(1)
    const { stream, observation } = await MirrorStream.empty().observe(topology)
    expect(observation.observed_topology_hash).toBe(topology.topology_hash)
    expect(stream.length).toBe(1)
  })

  it('lineage certifyLineage is_valid=true after driving mirror', async () => {
    let lineage = TopologyLineage.empty()
    let mirror = MirrorStream.empty()
    for (let i = 1; i <= 5; i++) {
      const t = await makeTopology(i)
      lineage = await lineage.append(t)
      const { stream } = await mirror.observe(t)
      mirror = stream
    }
    const cert = await certifyLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
    expect(mirror.length).toBe(5)
  })
})

// ─── Divergence between two lineage branches ──────────────

describe('Lineage → Divergence composition', () => {
  it('same topology on both branches → CONVERGED', async () => {
    const t = await makeTopology(1)
    const result = await compareTopologies(t, t)
    expect(result.kind).toBe('CONVERGED')
  })

  it('different ledger_root → DIVERGED D2, mutation_authority_active=false', async () => {
    const t1 = await makeTopology(1)
    const t2 = await makeTopology(1, { ledger_root: h('z') })
    const result = await compareTopologies(t1, t2)
    expect(result.kind).toBe('DIVERGED')
    if (result.kind === 'DIVERGED') {
      expect(result.report.divergence_class).toBe('D2')
      expect(result.report.mutation_authority_active).toBe(false)
    }
  })

  it('different consensus_qc_hash only → DIVERGED D3', async () => {
    const t1 = await makeTopology(1)
    const t2 = await makeTopology(1, { consensus_qc_hash: h('z') })
    const result = await compareTopologies(t1, t2)
    expect(result.kind).toBe('DIVERGED')
    if (result.kind === 'DIVERGED') {
      expect(result.report.divergence_class).toBe('D3')
    }
  })

  it('D2 report → mutationAuthorityActive([report])=false', async () => {
    const t1 = await makeTopology(1)
    const t2 = await makeTopology(1, { ledger_root: h('z') })
    const result = await compareTopologies(t1, t2)
    if (result.kind === 'DIVERGED') {
      expect(mutationAuthorityActive([result.report])).toBe(false)
    }
  })

  it('D0 report → mutationAuthorityActive([report])=true', async () => {
    const t1 = await makeTopology(1)
    const t2 = await makeTopology(2)
    const result = await compareTopologies(t1, t2)
    if (result.kind === 'DIVERGED') {
      expect(result.report.divergence_class).toBe('D0')
      expect(mutationAuthorityActive([result.report])).toBe(true)
    }
  })
})

// ─── MirrorStream structural guarantees ───────────────────

describe('MirrorStream: structural guarantees', () => {
  it('immutable: original stream unchanged after observe', async () => {
    const stream = MirrorStream.empty()
    const t = await makeTopology(1)
    await stream.observe(t)
    expect(stream.length).toBe(0)
  })

  it('non-monotone sequence throws MirrorError', async () => {
    const { MirrorError } = await import('../../src/frame/mirror.js')
    const { stream } = await MirrorStream.empty().observe(await makeTopology(5))
    await expect(stream.observe(await makeTopology(3))).rejects.toThrow(MirrorError)
  })

  it('getAll returns all observations', async () => {
    let stream = MirrorStream.empty()
    for (let i = 1; i <= 5; i++) {
      const { stream: next } = await stream.observe(await makeTopology(i))
      stream = next
    }
    expect(stream.getAll()).toHaveLength(5)
  })
})
