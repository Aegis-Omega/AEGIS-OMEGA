// ============================================================
// Gate 37 — Capability Evolution Protocol Tests
// ~26 tests: buildProposal, assessProposal, APPROVED/REJECTED
//   verdicts, staleness check, duplicate check, hash determinism.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { buildManifest } from '../../src/capsule/kernel.js'
import type { CapsuleManifest } from '../../src/capsule/types.js'
import {
  buildProposal,
  assessProposal,
  EvolutionError,
  EVOLUTION_SCHEMA_VERSION,
} from '../../src/capsule/evolution.js'

// ─── Helpers ───────────────────────────────────────────────

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }
function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }

const DFA_CERT = h('d')

async function emptyManifest(): Promise<CapsuleManifest> {
  return buildManifest({ capabilities: [], entropy_budget: 0 })
}

async function manifestWithReadState(): Promise<CapsuleManifest> {
  return buildManifest({
    capabilities: [{ type: 'READ_STATE', target: 'governance', is_read_only: true }],
    entropy_budget: 0,
  })
}

const BASE_INPUT = {
  capsule_id: 'cap-001',
  proposed_capability: 'READ_STATE' as const,
  target: 'governance',
  dfa_certificate_hash: DFA_CERT,
  sequence: seq(1),
}

// ─── Constants ─────────────────────────────────────────────

describe('constants', () => {
  it('EVOLUTION_SCHEMA_VERSION is 1.0.0', () => {
    expect(EVOLUTION_SCHEMA_VERSION).toBe('1.0.0')
  })
})

// ─── EvolutionError ────────────────────────────────────────

describe('EvolutionError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new EvolutionError('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('EvolutionError')
    expect(e.message).toBe('test')
  })
})

// ─── buildProposal ─────────────────────────────────────────

describe('buildProposal', () => {
  it('produces a frozen proposal', async () => {
    const p = await buildProposal(BASE_INPUT)
    expect(Object.isFrozen(p)).toBe(true)
  })

  it('proposal_id is 64-char hex', async () => {
    const p = await buildProposal(BASE_INPUT)
    expect(p.proposal_id).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(p.proposal_id)).toBe(true)
  })

  it('is_replay_reconstructable is true', async () => {
    const p = await buildProposal(BASE_INPUT)
    expect(p.is_replay_reconstructable).toBe(true)
  })

  it('schema_version is 1.0.0', async () => {
    const p = await buildProposal(BASE_INPUT)
    expect(p.schema_version).toBe('1.0.0')
  })

  it('all fields preserved verbatim', async () => {
    const p = await buildProposal(BASE_INPUT)
    expect(p.capsule_id).toBe(BASE_INPUT.capsule_id)
    expect(p.proposed_capability).toBe(BASE_INPUT.proposed_capability)
    expect(p.target).toBe(BASE_INPUT.target)
    expect(p.dfa_certificate_hash).toBe(BASE_INPUT.dfa_certificate_hash)
    expect(p.sequence).toBe(BASE_INPUT.sequence)
  })

  it('proposal_id is deterministic × 3', async () => {
    const p1 = (await buildProposal(BASE_INPUT)).proposal_id
    const p2 = (await buildProposal(BASE_INPUT)).proposal_id
    const p3 = (await buildProposal(BASE_INPUT)).proposal_id
    expect(p1).toBe(p2)
    expect(p2).toBe(p3)
  })

  it('different capsule_id → different proposal_id', async () => {
    const p1 = await buildProposal(BASE_INPUT)
    const p2 = await buildProposal({ ...BASE_INPUT, capsule_id: 'cap-002' })
    expect(p1.proposal_id).not.toBe(p2.proposal_id)
  })

  it('different sequence → different proposal_id', async () => {
    const p1 = await buildProposal(BASE_INPUT)
    const p2 = await buildProposal({ ...BASE_INPUT, sequence: seq(99) })
    expect(p1.proposal_id).not.toBe(p2.proposal_id)
  })

  it('different capability → different proposal_id', async () => {
    const p1 = await buildProposal(BASE_INPUT)
    const p2 = await buildProposal({ ...BASE_INPUT, proposed_capability: 'EMIT_EVENT' })
    expect(p1.proposal_id).not.toBe(p2.proposal_id)
  })
})

// ─── assessProposal — APPROVED ─────────────────────────────

describe('assessProposal — APPROVED', () => {
  it('valid new capability on empty manifest → APPROVED', async () => {
    const p = await buildProposal(BASE_INPUT)
    const m = await emptyManifest()
    const result = await assessProposal(p, m, DFA_CERT)
    expect(result.verdict).toBe('APPROVED')
  })

  it('APPROVED result is frozen', async () => {
    const p = await buildProposal(BASE_INPUT)
    const m = await emptyManifest()
    const result = await assessProposal(p, m, DFA_CERT)
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('APPROVED result has no reason field', async () => {
    const p = await buildProposal(BASE_INPUT)
    const m = await emptyManifest()
    const result = await assessProposal(p, m, DFA_CERT)
    expect('reason' in result).toBe(false)
  })

  it('result_hash is 64-char hex', async () => {
    const p = await buildProposal(BASE_INPUT)
    const m = await emptyManifest()
    const result = await assessProposal(p, m, DFA_CERT)
    expect(result.result_hash).toHaveLength(64)
  })

  it('is_replay_reconstructable is true', async () => {
    const p = await buildProposal(BASE_INPUT)
    const m = await emptyManifest()
    const result = await assessProposal(p, m, DFA_CERT)
    expect(result.is_replay_reconstructable).toBe(true)
  })

  it('result_hash is deterministic × 3', async () => {
    const p = await buildProposal(BASE_INPUT)
    const m = await emptyManifest()
    const h1 = (await assessProposal(p, m, DFA_CERT)).result_hash
    const h2 = (await assessProposal(p, m, DFA_CERT)).result_hash
    const h3 = (await assessProposal(p, m, DFA_CERT)).result_hash
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })
})

// ─── assessProposal — REJECTED ─────────────────────────────

describe('assessProposal — REJECTED', () => {
  it('stale dfa_certificate_hash → REJECTED', async () => {
    const p = await buildProposal(BASE_INPUT)
    const m = await emptyManifest()
    const result = await assessProposal(p, m, h('x'))  // different cert
    expect(result.verdict).toBe('REJECTED')
    expect(result.reason).toContain('stale')
  })

  it('capability already in manifest → REJECTED', async () => {
    const p = await buildProposal(BASE_INPUT)
    const m = await manifestWithReadState()  // already has READ_STATE:governance
    const result = await assessProposal(p, m, DFA_CERT)
    expect(result.verdict).toBe('REJECTED')
    expect(result.reason).toContain('already')
  })

  it('REJECTED result is frozen', async () => {
    const p = await buildProposal(BASE_INPUT)
    const m = await emptyManifest()
    const result = await assessProposal(p, m, h('x'))
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('REJECTED result_hash is deterministic × 3', async () => {
    const p = await buildProposal(BASE_INPUT)
    const m = await emptyManifest()
    const h1 = (await assessProposal(p, m, h('x'))).result_hash
    const h2 = (await assessProposal(p, m, h('x'))).result_hash
    const h3 = (await assessProposal(p, m, h('x'))).result_hash
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('different capability type on same target is APPROVED', async () => {
    const p = await buildProposal({ ...BASE_INPUT, proposed_capability: 'EMIT_EVENT' })
    const m = await manifestWithReadState()  // has READ_STATE:governance, not EMIT_EVENT
    const result = await assessProposal(p, m, DFA_CERT)
    expect(result.verdict).toBe('APPROVED')
  })
})
