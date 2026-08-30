// ============================================================
// Gate 83 — Constitutional Assembly (Integration)
// ~22 tests: All constitutional modules imported together:
//   assertMartingaleAnchored + tallyVotes + admitAbstraction +
//   assertMartingaleAnchored compose without conflict; full stack
//   from topology → lineage → swarm → martingale in one suite.
// ============================================================

import { describe, it, expect } from 'vitest'
import { tallyVotes, DEFAULT_QUORUM_THRESHOLD } from '../../src/consensus/swarm.js'
import {
  certifyMartingale, assertMartingaleAnchored,
  MartingaleViolation, MUTATION_RATE_LIMIT,
} from '../../src/constitutional/martingale.js'
import { buildOntologyRecord, admitAbstraction } from '../../src/constitutional/reduction.js'
import { PolicyAmendmentEngine } from '../../src/constitutional/policy.js'
import { AdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { buildTopology } from '../../src/frame/topology.js'
import { MirrorStream } from '../../src/frame/mirror.js'
import { buildSelfAttestation, verifySelfAttestation } from '../../src/frame/attestation.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const BASE_TOPO = {
  sitr_state: 'STABLE' as const,
  aoie_global_state: 'SECURE' as const,
  constitutional_verdict: 'PERMIT' as const,
  ledger_root: h('a'),
  consensus_qc_hash: h('b'),
  dfa_certificate_hash: h('c'),
}

function votes(n: number, hash: SHA256Hex) {
  return Array.from({ length: n }, (_, i) => ({ node_id: `n${i}`, topology_hash: hash, sequence: seq(1) }))
}

// ─── Full constitutional stack ─────────────────────────────

describe('Constitutional Assembly: full stack', () => {
  it('topology → lineage → martingale: all pass', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 10; i++) {
      const topo = await buildTopology({ ...BASE_TOPO, sequence: seq(i) })
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: topo.topology_hash },
        seq(i),
      )
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.is_anchored).toBe(true)
    expect(cert.entropy_bounded).toBe(true)
    expect(() => assertMartingaleAnchored(cert)).not.toThrow()
  })

  it('swarm convergence → attestation → martingale: all pass', async () => {
    const swarmRecord = await tallyVotes([...votes(7, h('a')), ...votes(3, h('b'))])
    expect(swarmRecord.quorum_reached).toBe(true)

    const attestation = await buildSelfAttestation({
      dfa_certificate_hash: h('d'),
      topology_hash: swarmRecord.quorum_hash,
      lineage_terminal_hash: null,
      capsule_attestation_hash: null,
      sequence: swarmRecord.sequence,
    })
    expect(await verifySelfAttestation(attestation)).toBe(true)

    let lineage = AdaptiveLineage.empty()
    const { lineage: next } = await lineage.append(
      { kind: 'TOPOLOGY_TRANSITION', topology_hash: swarmRecord.quorum_hash },
      seq(1),
    )
    lineage = next
    const cert = await certifyMartingale(lineage.getAll())
    expect(() => assertMartingaleAnchored(cert)).not.toThrow()
  })

  it('policy → reduction → admission: full lifecycle', async () => {
    let engine = PolicyAmendmentEngine.empty()
    const { engine: next, amendment } = engine.propose({
      target: 'HolonicTriad', description: 'Holonic triad', constraint_delta: 'allow_holonic', at_sequence: 1,
    })
    engine = next.recordVerdict(amendment.amendment_id, 'APPROVED')
    engine = engine.apply(amendment.amendment_id, { at_sequence: 2, invariants_passed: true })
    expect(engine.getById(amendment.amendment_id)!.status).toBe('APPLIED')

    const rec = await buildOntologyRecord({
      name: 'HolonicTriad', primitive_mapping: 'HASH', replay_mapping: 'HARMONIZE',
      topology_mapping: 'LINEAGE', epistemic_tier: 'T1', sequence: seq(1),
    })
    const result = await admitAbstraction([], rec)
    expect(result.verdict).toBe('ADMITTED')
  })

  it('mirror → lineage → martingale: 5 observations produce bounded cert', async () => {
    let mirror = MirrorStream.empty()
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 5; i++) {
      const topo = await buildTopology({ ...BASE_TOPO, sequence: seq(i) })
      const { stream, observation } = await mirror.observe(topo)
      mirror = stream
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: observation.observed_topology_hash },
        seq(i),
      )
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.entropy_bounded).toBe(true)
    expect(cert.replay_verifiability).toBe(5)
  })
})

// ─── Holonic constants shared across modules ───────────────

describe('Constitutional Assembly: holonic constants', () => {
  it('MUTATION_RATE_LIMIT === DEFAULT_QUORUM_THRESHOLD (cross-module identity)', () => {
    expect(MUTATION_RATE_LIMIT).toBe(DEFAULT_QUORUM_THRESHOLD)
  })

  it('MartingaleViolation is instanceof Error', () => {
    expect(new MartingaleViolation('test')).toBeInstanceOf(Error)
  })

  it('MartingaleViolation name is "MartingaleViolation"', () => {
    expect(new MartingaleViolation('x').name).toBe('MartingaleViolation')
  })

  it('62/100 ≥ MUTATION_RATE_LIMIT (both boundaries agree)', () => {
    expect(62 / 100 >= MUTATION_RATE_LIMIT).toBe(true)
    expect(61 / 100 >= MUTATION_RATE_LIMIT).toBe(false)
  })
})

// ─── Violation cascade ─────────────────────────────────────

describe('Constitutional Assembly: violation cascade', () => {
  it('tampered lineage → assertMartingaleAnchored throws MartingaleViolation', async () => {
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

  it('entropy exceeded → assertMartingaleAnchored throws with ratio info', async () => {
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
    try {
      assertMartingaleAnchored(cert)
      expect.fail('should have thrown')
    } catch (e) {
      expect((e as MartingaleViolation).message).toMatch(/adaptive_ratio|mutation/i)
    }
  })
})
