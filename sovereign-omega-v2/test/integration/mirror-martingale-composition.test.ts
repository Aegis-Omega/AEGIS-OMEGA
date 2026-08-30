// ============================================================
// Gate 77 — MirrorStream × Martingale Composition (Integration)
// ~18 tests: 20-observation MirrorStream drives TOPOLOGY_TRANSITION
//   events in AdaptiveLineage → MartingaleCertificate; observations
//   are replay-certifiable; observation_hash deterministic.
// ============================================================

import { describe, it, expect } from 'vitest'
import { MirrorStream } from '../../src/frame/mirror.js'
import { AdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { certifyMartingale, assertMartingaleAnchored } from '../../src/constitutional/martingale.js'
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

async function makeTopology(n: number) {
  return buildTopology({ ...BASE, sequence: seq(n) })
}

// ─── MirrorStream → AdaptiveLineage → Martingale ──────────

describe('MirrorStream → Martingale pipeline', () => {
  it('20-observation mirror drives 20 TOPOLOGY_TRANSITION → martingale bounded', async () => {
    let mirror = MirrorStream.empty()
    let lineage = AdaptiveLineage.empty()

    for (let i = 1; i <= 20; i++) {
      const topo = await makeTopology(i)
      const { stream, observation } = await mirror.observe(topo)
      mirror = stream
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: observation.observed_topology_hash },
        seq(i),
      )
      lineage = next
    }

    expect(mirror.length).toBe(20)
    expect(lineage.length).toBe(20)

    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.is_anchored).toBe(true)
    expect(cert.entropy_bounded).toBe(true)
    expect(cert.adaptive_power).toBe(0)
    expect(cert.replay_verifiability).toBe(20)
  })

  it('20 TOPOLOGY_TRANSITION entries → assertMartingaleAnchored does not throw', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 20; i++) {
      const topo = await makeTopology(i)
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: topo.topology_hash },
        seq(i),
      )
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(() => assertMartingaleAnchored(cert)).not.toThrow()
  })

  it('observation_hash reflects topology_hash (not sitr_state)', async () => {
    const t1 = await makeTopology(1)
    const t2 = await buildTopology({ ...BASE, sequence: seq(1), sitr_state: 'DEGRADED' })
    const { observation: o1 } = await MirrorStream.empty().observe(t1)
    const { observation: o2 } = await MirrorStream.empty().observe(t2)
    // t1 and t2 have different topology_hashes (different sitr_state)
    expect(o1.observed_topology_hash).not.toBe(o2.observed_topology_hash)
    expect(o1.observation_hash).not.toBe(o2.observation_hash)
  })
})

// ─── Observation structural guarantees ────────────────────

describe('MirrorStream: observation structure', () => {
  it('observation is frozen', async () => {
    const topo = await makeTopology(1)
    const { observation } = await MirrorStream.empty().observe(topo)
    expect(Object.isFrozen(observation)).toBe(true)
  })

  it('observation_hash is 64-char hex', async () => {
    const topo = await makeTopology(1)
    const { observation } = await MirrorStream.empty().observe(topo)
    expect(observation.observation_hash).toHaveLength(64)
    expect(observation.observation_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('is_replay_reconstructable=true', async () => {
    const topo = await makeTopology(1)
    const { observation } = await MirrorStream.empty().observe(topo)
    expect(observation.is_replay_reconstructable).toBe(true)
  })

  it('same topology × 3 → identical observation_hash', async () => {
    const topo = await makeTopology(42)
    const [s1, s2, s3] = await Promise.all([
      MirrorStream.empty().observe(topo),
      MirrorStream.empty().observe(topo),
      MirrorStream.empty().observe(topo),
    ])
    expect(s1!.observation.observation_hash).toBe(s2!.observation.observation_hash)
    expect(s2!.observation.observation_hash).toBe(s3!.observation.observation_hash)
  })

  it('getAll returns observations in order', async () => {
    let mirror = MirrorStream.empty()
    const observed_hashes: string[] = []
    for (let i = 1; i <= 5; i++) {
      const topo = await makeTopology(i)
      const { stream, observation } = await mirror.observe(topo)
      mirror = stream
      observed_hashes.push(observation.observed_topology_hash)
    }
    const all = mirror.getAll()
    expect(all).toHaveLength(5)
    for (let i = 0; i < 5; i++) {
      expect(all[i]!.observed_topology_hash).toBe(observed_hashes[i])
    }
  })
})
