// ============================================================
// Gate 57 — Evolution + Mirror Stream Adversarial
// ~22 tests: rejection cascade (5 proposals same capability →
//   1 APPROVED then 4 REJECTED), proposal_id determinism,
//   stale DFA cert rejection, MirrorStream 10-observation
//   monotonic sequence, observation_hash encoding contract
//   (only topology_hash + sequence encoded — not sitr_state),
//   MirrorError on non-monotonic observe.
//
// Gaps filled vs test/unit/evolution.test.ts + mirror.test.ts:
//   - Rejection cascade: build manifest from APPROVED → re-assess
//     same capability → REJECTED (already registered)
//   - 5-proposal cascade: 1 APPROVED + 4 REJECTED
//   - observation_hash encodes only topology_hash + sequence
//   - Different sitr_state, same topology_hash → same observation_hash
//   - MirrorStream 10-observation chain length/sequence tracking
//   - getAll() order preserved across 10 observations
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  buildProposal, assessProposal,
  EVOLUTION_SCHEMA_VERSION,
} from '../../src/capsule/evolution.js'
import {
  MirrorStream, MirrorError,
  MIRROR_SCHEMA_VERSION,
} from '../../src/frame/mirror.js'
import { TOPOLOGY_SCHEMA_VERSION } from '../../src/frame/topology.js'
import type { GovernanceTopology } from '../../src/frame/topology.js'
import type { CapsuleManifest, CapsuleCapability, CapsuleCapabilityType } from '../../src/capsule/types.js'
import { CAPSULE_SCHEMA_VERSION } from '../../src/capsule/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const DFA_CERT = h('d')
const OTHER_DFA = h('x')
const CAPSULE_ID = 'test-capsule-001'
const TARGET = 'test-target'

function makeManifest(caps: CapsuleCapability[] = []): CapsuleManifest {
  return Object.freeze<CapsuleManifest>({
    capsule_id: CAPSULE_ID,
    capabilities: Object.freeze(caps),
    entropy_budget: 1024,
    is_rollback_safe: true,
    schema_version: CAPSULE_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

function makeTopo(
  n: number,
  topoHash: SHA256Hex,
  sitrState: 'STABLE' | 'DEGRADED' | 'UNSTABLE' | 'CONSTITUTIONAL_RISK' = 'STABLE',
): GovernanceTopology {
  return Object.freeze<GovernanceTopology>({
    sitr_state: sitrState,
    aoie_global_state: 'SECURE',
    constitutional_verdict: 'PERMIT',
    ledger_root: h('l'),
    consensus_qc_hash: null,
    dfa_certificate_hash: DFA_CERT,
    sequence: seq(n),
    topology_hash: topoHash,
    schema_version: TOPOLOGY_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

// ─── Rejection cascade ────────────────────────────────────

describe('Evolution: rejection cascade', () => {
  it('first proposal for READ_STATE → APPROVED with empty manifest', async () => {
    const proposal = await buildProposal({
      capsule_id: CAPSULE_ID,
      proposed_capability: 'READ_STATE',
      target: TARGET,
      dfa_certificate_hash: DFA_CERT,
      sequence: seq(1),
    })
    const result = await assessProposal(proposal, makeManifest(), DFA_CERT)
    expect(result.verdict).toBe('APPROVED')
  })

  it('second proposal for same capability + target → REJECTED (already registered)', async () => {
    const cap: CapsuleCapability = Object.freeze({ type: 'READ_STATE', target: TARGET, is_read_only: true })
    const manifest = makeManifest([cap])
    const proposal = await buildProposal({
      capsule_id: CAPSULE_ID,
      proposed_capability: 'READ_STATE',
      target: TARGET,
      dfa_certificate_hash: DFA_CERT,
      sequence: seq(2),
    })
    const result = await assessProposal(proposal, manifest, DFA_CERT)
    expect(result.verdict).toBe('REJECTED')
    expect(result.reason).toContain('already')
  })

  it('5-proposal cascade: 1 APPROVED + 4 REJECTED for same capability', async () => {
    const cap: CapsuleCapability = Object.freeze({ type: 'EMIT_EVENT', target: TARGET, is_read_only: false })
    const emptyManifest = makeManifest([])
    const fullManifest = makeManifest([cap])

    const proposals = await Promise.all(
      Array.from({ length: 5 }, (_, i) =>
        buildProposal({
          capsule_id: CAPSULE_ID,
          proposed_capability: 'EMIT_EVENT',
          target: TARGET,
          dfa_certificate_hash: DFA_CERT,
          sequence: seq(10 + i),
        }),
      ),
    )

    // First proposal: manifest is empty → APPROVED
    const r0 = await assessProposal(proposals[0]!, emptyManifest, DFA_CERT)
    expect(r0.verdict).toBe('APPROVED')

    // Proposals 1–4: manifest already has the capability → REJECTED
    const rest = await Promise.all(
      proposals.slice(1).map(p => assessProposal(p, fullManifest, DFA_CERT)),
    )
    for (const r of rest) {
      expect(r.verdict).toBe('REJECTED')
    }
  })

  it('stale DFA cert → REJECTED with reason containing "stale"', async () => {
    const proposal = await buildProposal({
      capsule_id: CAPSULE_ID,
      proposed_capability: 'QUERY_TOPOLOGY',
      target: TARGET,
      dfa_certificate_hash: OTHER_DFA,   // stale — doesn't match currentDfaCertHash
      sequence: seq(20),
    })
    const result = await assessProposal(proposal, makeManifest(), DFA_CERT)
    expect(result.verdict).toBe('REJECTED')
    expect(result.reason).toContain('stale')
  })

  it('stale DFA cert takes priority over capability check', async () => {
    // Even if capability is already present, stale DFA cert should still reject
    const cap: CapsuleCapability = Object.freeze({ type: 'READ_STATE', target: TARGET, is_read_only: true })
    const proposal = await buildProposal({
      capsule_id: CAPSULE_ID,
      proposed_capability: 'READ_STATE',
      target: TARGET,
      dfa_certificate_hash: OTHER_DFA,
      sequence: seq(21),
    })
    const result = await assessProposal(proposal, makeManifest([cap]), DFA_CERT)
    expect(result.verdict).toBe('REJECTED')
  })

  it('different capabilities on same target: each first proposal APPROVED', async () => {
    const caps: CapsuleCapabilityType[] = ['READ_STATE', 'EMIT_EVENT', 'QUERY_TOPOLOGY', 'OBSERVE_LINEAGE']
    for (let i = 0; i < caps.length; i++) {
      const proposal = await buildProposal({
        capsule_id: CAPSULE_ID,
        proposed_capability: caps[i]!,
        target: TARGET,
        dfa_certificate_hash: DFA_CERT,
        sequence: seq(30 + i),
      })
      const result = await assessProposal(proposal, makeManifest(), DFA_CERT)
      expect(result.verdict).toBe('APPROVED')
    }
  })
})

// ─── Proposal ID determinism ──────────────────────────────

describe('Evolution: proposal_id determinism', () => {
  it('same inputs × 3 → identical proposal_id', async () => {
    const input = {
      capsule_id: CAPSULE_ID,
      proposed_capability: 'READ_STATE' as CapsuleCapabilityType,
      target: TARGET,
      dfa_certificate_hash: DFA_CERT,
      sequence: seq(50),
    }
    const [p1, p2, p3] = await Promise.all([buildProposal(input), buildProposal(input), buildProposal(input)])
    expect(p1!.proposal_id).toBe(p2!.proposal_id)
    expect(p2!.proposal_id).toBe(p3!.proposal_id)
  })

  it('different sequence → different proposal_id', async () => {
    const base = {
      capsule_id: CAPSULE_ID,
      proposed_capability: 'READ_STATE' as CapsuleCapabilityType,
      target: TARGET,
      dfa_certificate_hash: DFA_CERT,
    }
    const p1 = await buildProposal({ ...base, sequence: seq(1) })
    const p2 = await buildProposal({ ...base, sequence: seq(2) })
    expect(p1.proposal_id).not.toBe(p2.proposal_id)
  })

  it('APPROVED result has no reason field', async () => {
    const proposal = await buildProposal({
      capsule_id: CAPSULE_ID,
      proposed_capability: 'READ_STATE',
      target: TARGET,
      dfa_certificate_hash: DFA_CERT,
      sequence: seq(60),
    })
    const result = await assessProposal(proposal, makeManifest(), DFA_CERT)
    expect(result.verdict).toBe('APPROVED')
    expect(result.reason).toBeUndefined()
  })

  it('schema_version is 1.0.0', async () => {
    const proposal = await buildProposal({
      capsule_id: CAPSULE_ID,
      proposed_capability: 'READ_STATE',
      target: TARGET,
      dfa_certificate_hash: DFA_CERT,
      sequence: seq(61),
    })
    expect(proposal.schema_version).toBe(EVOLUTION_SCHEMA_VERSION)
    expect(EVOLUTION_SCHEMA_VERSION).toBe('1.0.0')
  })
})

// ─── MirrorStream: observation_hash encoding contract ─────

describe('MirrorStream: observation_hash encoding contract', () => {
  it('same topology_hash + sequence → same observation_hash regardless of sitr_state', async () => {
    const topA = makeTopo(1, h('t'), 'STABLE')
    const topB = makeTopo(1, h('t'), 'DEGRADED')   // same hash + seq, different sitr_state
    const { observation: obsA } = await MirrorStream.empty().observe(topA)
    const { observation: obsB } = await MirrorStream.empty().observe(topB)
    expect(obsA.observation_hash).toBe(obsB.observation_hash)
  })

  it('different topology_hash → different observation_hash', async () => {
    const topA = makeTopo(1, h('t'), 'STABLE')
    const topB = makeTopo(1, h('u'), 'STABLE')   // different topology_hash
    const { observation: obsA } = await MirrorStream.empty().observe(topA)
    const { observation: obsB } = await MirrorStream.empty().observe(topB)
    expect(obsA.observation_hash).not.toBe(obsB.observation_hash)
  })

  it('different sequence → different observation_hash (same topology_hash)', async () => {
    const topA = makeTopo(1, h('t'))
    const topB = makeTopo(2, h('t'))
    const { observation: obsA } = await MirrorStream.empty().observe(topA)
    // second stream: first observe with seq 1 to advance, then cannot use seq 2 on fresh...
    // Use separate fresh streams
    const { observation: obsB } = await MirrorStream.empty().observe(topB)
    expect(obsA.observation_hash).not.toBe(obsB.observation_hash)
  })

  it('observation_hash is 64-char hex', async () => {
    const { observation } = await MirrorStream.empty().observe(makeTopo(1, h('t')))
    expect(observation.observation_hash).toHaveLength(64)
    expect(observation.observation_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('observation_hash deterministic × 3 for same input', async () => {
    const top = makeTopo(5, h('t'))
    const [o1, o2, o3] = await Promise.all([
      MirrorStream.empty().observe(top),
      MirrorStream.empty().observe(top),
      MirrorStream.empty().observe(top),
    ])
    expect(o1!.observation.observation_hash).toBe(o2!.observation.observation_hash)
    expect(o2!.observation.observation_hash).toBe(o3!.observation.observation_hash)
  })
})

// ─── MirrorStream: sequence tracking ─────────────────────

describe('MirrorStream: 10-observation sequence tracking', () => {
  it('10 sequential observations → stream.length = 10', async () => {
    let stream = MirrorStream.empty()
    for (let i = 1; i <= 10; i++) {
      const res = await stream.observe(makeTopo(i, h('t')))
      stream = res.stream
    }
    expect(stream.length).toBe(10)
    expect(stream.latestSequence).toBe(seq(10))
  })

  it('getAll() returns observations in insertion order', async () => {
    let stream = MirrorStream.empty()
    for (let i = 1; i <= 5; i++) {
      const res = await stream.observe(makeTopo(i, h('t')))
      stream = res.stream
    }
    const all = stream.getAll()
    for (let i = 0; i < all.length; i++) {
      expect(all[i]!.sequence).toBe(seq(i + 1))
    }
  })

  it('non-monotonic sequence → MirrorError', async () => {
    const { stream } = await MirrorStream.empty().observe(makeTopo(5, h('t')))
    await expect(stream.observe(makeTopo(5, h('u')))).rejects.toThrow(MirrorError)
    await expect(stream.observe(makeTopo(3, h('u')))).rejects.toThrow(MirrorError)
  })

  it('source stream unchanged after observe (immutable)', async () => {
    const initial = MirrorStream.empty()
    await initial.observe(makeTopo(1, h('t')))
    expect(initial.length).toBe(0)
    expect(initial.latestSequence).toBeNull()
  })

  it('sitr_state preserved in observation from topology', async () => {
    const top = makeTopo(1, h('t'), 'DEGRADED')
    const { observation } = await MirrorStream.empty().observe(top)
    expect(observation.sitr_state).toBe('DEGRADED')
    expect(observation.aoie_global_state).toBe('SECURE')
    expect(observation.constitutional_verdict).toBe('PERMIT')
  })

  it('schema_version is 1.0.0 and is_replay_reconstructable=true', async () => {
    const { observation } = await MirrorStream.empty().observe(makeTopo(1, h('t')))
    expect(observation.schema_version).toBe(MIRROR_SCHEMA_VERSION)
    expect(MIRROR_SCHEMA_VERSION).toBe('1.0.0')
    expect(observation.is_replay_reconstructable).toBe(true)
  })

  it('MirrorError is instance of Error', () => {
    const err = new MirrorError('test')
    expect(err).toBeInstanceOf(Error)
    expect(err.name).toBe('MirrorError')
  })
})
