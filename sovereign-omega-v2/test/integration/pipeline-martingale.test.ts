// ============================================================
// Gate 98 — Pipeline + Martingale (Integration)
// ~18 tests: AdaptiveLineage + MartingaleCertificate after
//   a full pipeline run; audit_trace binding via certificate_hash;
//   entropy_bounded=true for normal operation; violation cascade.
// ============================================================

import { describe, it, expect } from 'vitest'
import { AdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { certifyMartingale, assertMartingaleAnchored, MartingaleViolation, MUTATION_RATE_LIMIT } from '../../src/constitutional/martingale.js'
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

async function runDFA(seqN: number) {
  let machine = initialMachine(seq(seqN))
  const records = []
  for (const phase of ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const) {
    const { machine: next, record } = await transition(machine, phase, h(phase[0]!.toLowerCase()))
    machine = next
    records.push(record)
  }
  return certifyExecution(records, seq(seqN))
}

// ─── Normal operation ─────────────────────────────────────

describe('Pipeline + Martingale: normal operation', () => {
  it('10 DFA+topology events → lineage certifies → entropy_bounded=true', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 10; i++) {
      const topo = await buildTopology({ ...BASE, sequence: seq(i) })
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: topo.topology_hash },
        seq(i),
      )
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.entropy_bounded).toBe(true)
    expect(cert.adaptive_power).toBe(0)
    expect(cert.replay_verifiability).toBe(10)
    expect(cert.is_anchored).toBe(true)
  })

  it('DFA cert valid → PASS harmonize → no martingale violation', async () => {
    const dfaCert = await runDFA(1)
    expect(dfaCert.is_valid).toBe(true)

    let lineage = AdaptiveLineage.empty()
    const topo = await buildTopology({ ...BASE, sequence: seq(1) })
    const { lineage: next } = await lineage.append(
      { kind: 'TOPOLOGY_TRANSITION', topology_hash: topo.topology_hash },
      seq(1),
    )
    lineage = next
    const mart = await certifyMartingale(lineage.getAll())
    expect(() => assertMartingaleAnchored(mart)).not.toThrow()
  })

  it('certificate_hash is 64-char hex', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 5; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + i)) },
        seq(i),
      )
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.certificate_hash).toHaveLength(64)
    expect(cert.certificate_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('certifyMartingale is deterministic ×3 on same entries', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 5; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + i)) },
        seq(i),
      )
      lineage = next
    }
    const entries = lineage.getAll()
    const [c1, c2, c3] = await Promise.all([
      certifyMartingale(entries),
      certifyMartingale(entries),
      certifyMartingale(entries),
    ])
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })
})

// ─── Audit trace binding ──────────────────────────────────

describe('Pipeline + Martingale: audit trace binding', () => {
  it('different lineage → different certificate_hash', async () => {
    const makeLineage = async (offset: number) => {
      let l = AdaptiveLineage.empty()
      for (let i = 1; i <= 5; i++) {
        const { lineage: next } = await l.append(
          { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + i + offset)) },
          seq(i),
        )
        l = next
      }
      return certifyMartingale(l.getAll())
    }
    const [c1, c2] = await Promise.all([makeLineage(0), makeLineage(1)])
    expect(c1.certificate_hash).not.toBe(c2.certificate_hash)
  })

  it('terminal_hash matches last entry_hash in pipeline', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 5; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + i)) },
        seq(i),
      )
      lineage = next
    }
    const entries = lineage.getAll()
    const cert = await certifyMartingale(entries)
    expect(cert.terminal_hash).toBe(entries[4]!.entry_hash)
  })

  it('MUTATION_RATE_LIMIT present in certificate', async () => {
    let lineage = AdaptiveLineage.empty()
    const { lineage: next } = await lineage.append(
      { kind: 'TOPOLOGY_TRANSITION', topology_hash: h('x') },
      seq(1),
    )
    lineage = next
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.mutation_rate_limit).toBe(MUTATION_RATE_LIMIT)
  })
})

// ─── Violation cascade ────────────────────────────────────

describe('Pipeline + Martingale: violation cascade', () => {
  it('tampered entry → is_anchored=false → assert throws MartingaleViolation', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 5; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + i)) },
        seq(i),
      )
      lineage = next
    }
    const entries = [...lineage.getAll()]
    entries[2] = { ...entries[2]!, entry_hash: h('z') }
    const cert = await certifyMartingale(entries)
    expect(cert.is_anchored).toBe(false)
    expect(() => assertMartingaleAnchored(cert)).toThrow(MartingaleViolation)
  })

  it('100 CAPABILITY_EVOLUTION APPROVED → entropy_bounded=false → assert throws', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 100; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'CAPABILITY_EVOLUTION', proposal_id: h(String.fromCharCode(97 + (i % 26))), verdict: 'APPROVED' },
        seq(i),
      )
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.entropy_bounded).toBe(false)
    expect(() => assertMartingaleAnchored(cert)).toThrow(MartingaleViolation)
  })

  it('MartingaleViolation is instanceof Error', () => {
    expect(new MartingaleViolation('test')).toBeInstanceOf(Error)
  })

  it('schema_version is 1.0.0', async () => {
    const cert = await certifyMartingale([])
    expect(cert.schema_version).toBe('1.0.0')
  })
})
