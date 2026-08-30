// ============================================================
// Gate 100 — Schema Registry + Evolution Composition
// ~18 tests: SchemaRegistry + CapabilityEvolution +
//   AdaptiveLineage: version-pinned evolution events are
//   replay-certified; schema fingerprint is deterministic;
//   sealed registry rejects new schemas.
// ============================================================

import { describe, it, expect } from 'vitest'
import { SchemaRegistry, SchemaRegistryError } from '../../src/core/schema-registry.js'
import { buildProposal, assessProposal, EVOLUTION_SCHEMA_VERSION } from '../../src/capsule/evolution.js'
import { AdaptiveLineage, certifyAdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { buildManifest } from '../../src/capsule/kernel.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const DFA_CERT = h('d')

function makeRegistry(): SchemaRegistry {
  const reg = new SchemaRegistry()
  reg.register({
    schema_id: 'CapabilityProposal',
    version: EVOLUTION_SCHEMA_VERSION,
    fields: [
      { name: 'proposal_id', type: 'string', required: true },
      { name: 'capsule_id', type: 'string', required: true },
      { name: 'target', type: 'string', required: true },
    ],
  })
  return reg
}

// ─── Schema Registry ──────────────────────────────────────

describe('SchemaRegistry: registration and validation', () => {
  it('registered schema validates conforming payload', () => {
    const reg = makeRegistry()
    const result = reg.validate(
      { proposal_id: h('p'), capsule_id: 'cap1', target: 'e5' },
      'CapabilityProposal',
      EVOLUTION_SCHEMA_VERSION,
    )
    expect(result.valid).toBe(true)
    expect(result.errors.length).toBe(0)
  })

  it('unknown schema → valid=false (fail closed)', () => {
    const reg = makeRegistry()
    const result = reg.validate({}, 'UnknownSchema', '1.0.0')
    expect(result.valid).toBe(false)
    expect(result.errors[0]).toMatch(/Unknown schema/)
  })

  it('sealed registry rejects new schema', () => {
    const reg = makeRegistry()
    reg.seal()
    expect(() => reg.register({
      schema_id: 'NewSchema', version: '1.0.0', fields: [],
    })).toThrow(SchemaRegistryError)
  })

  it('duplicate schema registration throws', () => {
    const reg = makeRegistry()
    expect(() => reg.register({
      schema_id: 'CapabilityProposal',
      version: EVOLUTION_SCHEMA_VERSION,
      fields: [],
    })).toThrow(SchemaRegistryError)
  })

  it('schema fingerprint is 64-char hex', async () => {
    const reg = makeRegistry()
    const fp = await reg.fingerprint('CapabilityProposal', EVOLUTION_SCHEMA_VERSION)
    expect(fp).not.toBeNull()
    expect(fp!).toHaveLength(64)
    expect(fp!).toMatch(/^[0-9a-f]{64}$/)
  })

  it('schema fingerprint is deterministic ×3', async () => {
    const reg = makeRegistry()
    const [f1, f2, f3] = await Promise.all([
      reg.fingerprint('CapabilityProposal', EVOLUTION_SCHEMA_VERSION),
      reg.fingerprint('CapabilityProposal', EVOLUTION_SCHEMA_VERSION),
      reg.fingerprint('CapabilityProposal', EVOLUTION_SCHEMA_VERSION),
    ])
    expect(f1).toBe(f2)
    expect(f2).toBe(f3)
  })

  it('unknown schema fingerprint → null', async () => {
    const reg = makeRegistry()
    const fp = await reg.fingerprint('NoSuch', '9.9.9')
    expect(fp).toBeNull()
  })
})

// ─── Evolution + AdaptiveLineage ──────────────────────────

describe('SchemaRegistry + Evolution: replay-certified', () => {
  it('APPROVED proposal → entry in AdaptiveLineage', async () => {
    const manifest = await buildManifest({
      capabilities: [{ type: 'READ_STATE', target: 'ledger', is_read_only: true }],
      entropy_budget: 100,
    })
    const proposal = await buildProposal({
      capsule_id: 'cap1',
      proposed_capability: 'EMIT_EVENT',
      target: 'e5',
      dfa_certificate_hash: DFA_CERT,
      sequence: seq(1),
    })
    const result = await assessProposal(proposal, manifest, DFA_CERT)
    expect(result.verdict).toBe('APPROVED')

    let lineage = AdaptiveLineage.empty()
    const { lineage: next } = await lineage.append(
      { kind: 'CAPABILITY_EVOLUTION', proposal_id: proposal.proposal_id, verdict: result.verdict },
      seq(1),
    )
    lineage = next
    const cert = await certifyAdaptiveLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(1)
    expect(lineage.getAll()[0]!.is_replay_reconstructable).toBe(true)
  })

  it('5 proposals → 5 lineage entries → is_valid=true', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 5; i++) {
      const proposal = await buildProposal({
        capsule_id: `cap${i}`,
        proposed_capability: 'EMIT_EVENT',
        target: `tgt${i}`,
        dfa_certificate_hash: DFA_CERT,
        sequence: seq(i),
      })
      const { lineage: next } = await lineage.append(
        { kind: 'CAPABILITY_EVOLUTION', proposal_id: proposal.proposal_id, verdict: 'APPROVED' },
        seq(i),
      )
      lineage = next
    }
    const cert = await certifyAdaptiveLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(5)
  })

  it('stale DFA cert → REJECTED → REJECTED in lineage', async () => {
    const manifest = await buildManifest({
      capabilities: [],
      entropy_budget: 100,
    })
    const proposal = await buildProposal({
      capsule_id: 'cap1',
      proposed_capability: 'EMIT_EVENT',
      target: 'e5',
      dfa_certificate_hash: h('stale'),
      sequence: seq(1),
    })
    const result = await assessProposal(proposal, manifest, DFA_CERT)
    expect(result.verdict).toBe('REJECTED')

    let lineage = AdaptiveLineage.empty()
    const { lineage: next } = await lineage.append(
      { kind: 'CAPABILITY_EVOLUTION', proposal_id: proposal.proposal_id, verdict: result.verdict },
      seq(1),
    )
    lineage = next
    const entry = lineage.getAll()[0]!
    expect((entry.event as any).verdict).toBe('REJECTED')
  })
})

// ─── Schema validation of evolution output ────────────────

describe('SchemaRegistry: validates CapabilityProposal shape', () => {
  it('proposal payload passes schema validation', async () => {
    const reg = makeRegistry()
    const proposal = await buildProposal({
      capsule_id: 'cap1',
      proposed_capability: 'EMIT_EVENT',
      target: 'e5',
      dfa_certificate_hash: DFA_CERT,
      sequence: seq(1),
    })
    const result = reg.validate(
      { proposal_id: proposal.proposal_id, capsule_id: proposal.capsule_id, target: proposal.target },
      'CapabilityProposal',
      EVOLUTION_SCHEMA_VERSION,
    )
    expect(result.valid).toBe(true)
  })

  it('missing required field → valid=false', () => {
    const reg = makeRegistry()
    const result = reg.validate(
      { proposal_id: h('p'), capsule_id: 'cap1' },
      'CapabilityProposal',
      EVOLUTION_SCHEMA_VERSION,
    )
    expect(result.valid).toBe(false)
    expect(result.errors.some(e => e.includes('target'))).toBe(true)
  })

  it('wrong field type → valid=false', () => {
    const reg = makeRegistry()
    const result = reg.validate(
      { proposal_id: 123, capsule_id: 'cap1', target: 'e5' },
      'CapabilityProposal',
      EVOLUTION_SCHEMA_VERSION,
    )
    expect(result.valid).toBe(false)
  })
})
