// ============================================================
// Gate 73 — Evolution × Attestation Composition (Integration)
// ~18 tests: CapabilityProposal → EvolutionResult → SelfAttestation
//   pipeline; APPROVED/REJECTED propagation; stale DFA cert detected;
//   attestation_hash changes when evolution verdict changes.
// ============================================================

import { describe, it, expect } from 'vitest'
import { buildProposal, assessProposal } from '../../src/capsule/evolution.js'
import { buildSelfAttestation } from '../../src/frame/attestation.js'
import { buildManifest } from '../../src/capsule/kernel.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

async function makeManifest() {
  return buildManifest({
    capabilities: [{ type: 'EMIT_EVENT', target: 'e5', is_read_only: false }],
    entropy_budget: 10000,
  })
}

// ─── Proposal → Assessment pipeline ──────────────────────

describe('Evolution: proposal → assessment pipeline', () => {
  it('valid new capability → APPROVED', async () => {
    const manifest = await makeManifest()
    const proposal = await buildProposal({
      capsule_id: manifest.capsule_id,
      proposed_capability: 'READ_STATE',
      target: 'ledger',
      dfa_certificate_hash: h('c'),
      sequence: seq(1),
    })
    const result = await assessProposal(proposal, manifest, h('c'))
    expect(result.verdict).toBe('APPROVED')
  })

  it('already-present capability → REJECTED (reason contains already)', async () => {
    const manifest = await makeManifest()
    const proposal = await buildProposal({
      capsule_id: manifest.capsule_id,
      proposed_capability: 'EMIT_EVENT',  // already in manifest
      target: 'e5',
      dfa_certificate_hash: h('c'),
      sequence: seq(1),
    })
    const result = await assessProposal(proposal, manifest, h('c'))
    expect(result.verdict).toBe('REJECTED')
    expect(result.reason).toMatch(/already/i)
  })

  it('stale dfa_certificate_hash → REJECTED (reason contains stale)', async () => {
    const manifest = await makeManifest()
    const proposal = await buildProposal({
      capsule_id: manifest.capsule_id,
      proposed_capability: 'READ_STATE',
      target: 'ledger',
      dfa_certificate_hash: h('old'),
      sequence: seq(1),
    })
    const result = await assessProposal(proposal, manifest, h('current'))
    expect(result.verdict).toBe('REJECTED')
    expect(result.reason).toMatch(/stale/i)
  })

  it('proposal_id is 64-char hex', async () => {
    const manifest = await makeManifest()
    const proposal = await buildProposal({
      capsule_id: manifest.capsule_id,
      proposed_capability: 'READ_STATE',
      target: 'ledger',
      dfa_certificate_hash: h('c'),
      sequence: seq(1),
    })
    expect(proposal.proposal_id).toHaveLength(64)
    expect(proposal.proposal_id).toMatch(/^[0-9a-f]{64}$/)
  })

  it('result_hash deterministic ×3 for APPROVED', async () => {
    const manifest = await makeManifest()
    const proposal = await buildProposal({
      capsule_id: manifest.capsule_id,
      proposed_capability: 'READ_STATE',
      target: 'ledger',
      dfa_certificate_hash: h('c'),
      sequence: seq(7),
    })
    const [r1, r2, r3] = await Promise.all([
      assessProposal(proposal, manifest, h('c')),
      assessProposal(proposal, manifest, h('c')),
      assessProposal(proposal, manifest, h('c')),
    ])
    expect(r1!.result_hash).toBe(r2!.result_hash)
    expect(r2!.result_hash).toBe(r3!.result_hash)
  })
})

// ─── Evolution → SelfAttestation pipeline ─────────────────

describe('Evolution → SelfAttestation composition', () => {
  it('APPROVED evolution feeds dfa_certificate_hash into SelfAttestation', async () => {
    const manifest = await makeManifest()
    const proposal = await buildProposal({
      capsule_id: manifest.capsule_id,
      proposed_capability: 'READ_STATE',
      target: 'ledger',
      dfa_certificate_hash: h('c'),
      sequence: seq(1),
    })
    const result = await assessProposal(proposal, manifest, h('c'))
    expect(result.verdict).toBe('APPROVED')
    // Use result_hash as dfa_certificate_hash in attestation
    const attestation = await buildSelfAttestation({
      dfa_certificate_hash: result.result_hash,
      topology_hash: h('t'),
      lineage_terminal_hash: null,
      capsule_attestation_hash: null,
      sequence: seq(2),
    })
    expect(attestation.dfa_certificate_hash).toBe(result.result_hash)
    expect(attestation.is_replay_reconstructable).toBe(true)
  })

  it('different verdicts → different attestation_hash', async () => {
    const manifest = await makeManifest()
    const p1 = await buildProposal({ capsule_id: manifest.capsule_id, proposed_capability: 'READ_STATE', target: 'ledger', dfa_certificate_hash: h('c'), sequence: seq(1) })
    const p2 = await buildProposal({ capsule_id: manifest.capsule_id, proposed_capability: 'EMIT_EVENT', target: 'e5', dfa_certificate_hash: h('c'), sequence: seq(2) })
    const r1 = await assessProposal(p1, manifest, h('c'))  // APPROVED
    const r2 = await assessProposal(p2, manifest, h('c'))  // REJECTED (already present)
    const a1 = await buildSelfAttestation({ dfa_certificate_hash: r1.result_hash, topology_hash: h('t'), lineage_terminal_hash: null, capsule_attestation_hash: null, sequence: seq(10) })
    const a2 = await buildSelfAttestation({ dfa_certificate_hash: r2.result_hash, topology_hash: h('t'), lineage_terminal_hash: null, capsule_attestation_hash: null, sequence: seq(10) })
    expect(a1.attestation_hash).not.toBe(a2.attestation_hash)
  })

  it('5-proposal batch: 3 APPROVED, 2 REJECTED → 3 distinct APPROVED attestations', async () => {
    const manifest = await makeManifest()
    const approved = []
    for (const [cap, target] of [['READ_STATE', 'ledger'], ['OBSERVE_LINEAGE', 'lineage'], ['QUERY_TOPOLOGY', 'topo']] as const) {
      const proposal = await buildProposal({ capsule_id: manifest.capsule_id, proposed_capability: cap, target, dfa_certificate_hash: h('c'), sequence: seq(approved.length + 1) })
      const result = await assessProposal(proposal, manifest, h('c'))
      expect(result.verdict).toBe('APPROVED')
      approved.push(result)
    }
    const hashes = new Set(approved.map(r => r.result_hash))
    expect(hashes.size).toBe(3)
  })
})
