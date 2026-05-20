// ============================================================
// Gate 61 — Constitutional Martingale Tests
// ~24 tests: certifyMartingale, assertMartingaleAnchored,
//   MUTATION_RATE_LIMIT = 1/φ = DEFAULT_QUORUM_THRESHOLD,
//   empty chain, all-topology chain, mutation rate boundary
//   (2/5 and 3/5 bounded; 4/5 not), REJECTED evolutions don't
//   count toward adaptive_power, tamper detection.
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  certifyMartingale, assertMartingaleAnchored,
  MartingaleViolation,
  MARTINGALE_SCHEMA_VERSION, MUTATION_RATE_LIMIT,
} from '../../src/constitutional/martingale.js'
import { DEFAULT_QUORUM_THRESHOLD } from '../../src/consensus/swarm.js'
import { AdaptiveLineage, type AdaptiveLineageEntry, type AdaptiveEvent } from '../../src/frame/adaptive-lineage.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

function topoEvent(n: number): AdaptiveEvent {
  return { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + (n % 26))) }
}

async function buildChain(
  specs: Array<{ kind: 'T' } | { kind: 'A'; verdict: 'APPROVED' | 'REJECTED' }>,
): Promise<readonly AdaptiveLineageEntry[]> {
  let lineage = AdaptiveLineage.empty()
  for (let i = 0; i < specs.length; i++) {
    const spec = specs[i]!
    const event: AdaptiveEvent = spec.kind === 'T'
      ? topoEvent(i + 1)
      : { kind: 'CAPABILITY_EVOLUTION', proposal_id: h(String.fromCharCode(97 + (i % 26))), verdict: spec.verdict }
    const { lineage: next } = await lineage.append(event, seq(i + 1))
    lineage = next
  }
  return lineage.getAll()
}

// ─── Constants ────────────────────────────────────────────

describe('Martingale: constants', () => {
  it('MARTINGALE_SCHEMA_VERSION is 1.0.0', () => {
    expect(MARTINGALE_SCHEMA_VERSION).toBe('1.0.0')
  })

  it('MUTATION_RATE_LIMIT equals (√5 − 1) / 2', () => {
    expect(MUTATION_RATE_LIMIT).toBe((Math.sqrt(5) - 1) / 2)
    expect(MUTATION_RATE_LIMIT).toBeCloseTo(0.6180339887, 9)
  })

  it('MUTATION_RATE_LIMIT === DEFAULT_QUORUM_THRESHOLD (holonic triad equality)', () => {
    // Both are 1/φ — the same constant governs swarm consensus and constitutional mutation rate.
    expect(MUTATION_RATE_LIMIT).toBe(DEFAULT_QUORUM_THRESHOLD)
  })
})

// ─── MartingaleViolation ──────────────────────────────────

describe('MartingaleViolation', () => {
  it('is an Error subclass with name MartingaleViolation', () => {
    const e = new MartingaleViolation('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('MartingaleViolation')
    expect(e.message).toBe('test')
  })

  it('is distinct from MartingaleViolation from another Error type', () => {
    const e = new MartingaleViolation('x')
    expect(e).not.toBeInstanceOf(RangeError)
  })
})

// ─── Empty chain ──────────────────────────────────────────

describe('certifyMartingale: empty chain', () => {
  it('is_anchored=true, drift_bounded=true, entropy_bounded=true', async () => {
    const cert = await certifyMartingale([])
    expect(cert.is_anchored).toBe(true)
    expect(cert.drift_bounded).toBe(true)
    expect(cert.entropy_bounded).toBe(true)
  })

  it('adaptive_power=0, replay_verifiability=0, adaptive_ratio=0', async () => {
    const cert = await certifyMartingale([])
    expect(cert.adaptive_power).toBe(0)
    expect(cert.replay_verifiability).toBe(0)
    expect(cert.adaptive_ratio).toBe(0)
  })

  it('terminal_hash is null for empty chain', async () => {
    const cert = await certifyMartingale([])
    expect(cert.terminal_hash).toBeNull()
  })

  it('certificate is frozen and is_replay_reconstructable=true', async () => {
    const cert = await certifyMartingale([])
    expect(Object.isFrozen(cert)).toBe(true)
    expect(cert.is_replay_reconstructable).toBe(true)
  })
})

// ─── All-topology chain ───────────────────────────────────

describe('certifyMartingale: all-topology chain', () => {
  it('5-entry topology chain → is_anchored=true, entropy_bounded=true', async () => {
    const entries = await buildChain([{kind:'T'},{kind:'T'},{kind:'T'},{kind:'T'},{kind:'T'}])
    const cert = await certifyMartingale(entries)
    expect(cert.is_anchored).toBe(true)
    expect(cert.entropy_bounded).toBe(true)
    expect(cert.adaptive_power).toBe(0)
  })

  it('5-entry topology: terminal_hash equals last entry_hash', async () => {
    const entries = await buildChain([{kind:'T'},{kind:'T'},{kind:'T'},{kind:'T'},{kind:'T'}])
    const cert = await certifyMartingale(entries)
    expect(cert.terminal_hash).toBe(entries[4]!.entry_hash)
  })

  it('5-entry topology: certificate_hash deterministic × 3', async () => {
    const entries = await buildChain([{kind:'T'},{kind:'T'},{kind:'T'},{kind:'T'},{kind:'T'}])
    const [c1, c2, c3] = await Promise.all([
      certifyMartingale(entries),
      certifyMartingale(entries),
      certifyMartingale(entries),
    ])
    expect(c1!.certificate_hash).toBe(c2!.certificate_hash)
    expect(c2!.certificate_hash).toBe(c3!.certificate_hash)
  })

  it('mutation_rate_limit field equals MUTATION_RATE_LIMIT constant', async () => {
    const entries = await buildChain([{kind:'T'},{kind:'T'}])
    const cert = await certifyMartingale(entries)
    expect(cert.mutation_rate_limit).toBe(MUTATION_RATE_LIMIT)
  })
})

// ─── Mutation rate boundary ───────────────────────────────

describe('certifyMartingale: mutation rate', () => {
  it('2 of 5 APPROVED (0.40 < 1/φ) → entropy_bounded=true', async () => {
    const entries = await buildChain([
      {kind:'A', verdict:'APPROVED'}, {kind:'A', verdict:'APPROVED'},
      {kind:'T'}, {kind:'T'}, {kind:'T'},
    ])
    const cert = await certifyMartingale(entries)
    expect(cert.adaptive_power).toBe(2)
    expect(cert.adaptive_ratio).toBeCloseTo(0.40, 10)
    expect(cert.entropy_bounded).toBe(true)
  })

  it('3 of 5 APPROVED (0.60 < 1/φ) → entropy_bounded=true', async () => {
    const entries = await buildChain([
      {kind:'A', verdict:'APPROVED'}, {kind:'A', verdict:'APPROVED'}, {kind:'A', verdict:'APPROVED'},
      {kind:'T'}, {kind:'T'},
    ])
    const cert = await certifyMartingale(entries)
    expect(cert.adaptive_power).toBe(3)
    expect(cert.entropy_bounded).toBe(true)
  })

  it('4 of 5 APPROVED (0.80 > 1/φ) → entropy_bounded=false', async () => {
    const entries = await buildChain([
      {kind:'A', verdict:'APPROVED'}, {kind:'A', verdict:'APPROVED'},
      {kind:'A', verdict:'APPROVED'}, {kind:'A', verdict:'APPROVED'}, {kind:'T'},
    ])
    const cert = await certifyMartingale(entries)
    expect(cert.adaptive_power).toBe(4)
    expect(cert.entropy_bounded).toBe(false)
  })

  it('REJECTED evolutions do not count toward adaptive_power', async () => {
    const entries = await buildChain([
      {kind:'A', verdict:'REJECTED'}, {kind:'A', verdict:'REJECTED'},
      {kind:'A', verdict:'REJECTED'}, {kind:'A', verdict:'REJECTED'}, {kind:'T'},
    ])
    const cert = await certifyMartingale(entries)
    expect(cert.adaptive_power).toBe(0)
    expect(cert.entropy_bounded).toBe(true)
  })

  it('certificate_hash is 64-char hex', async () => {
    const entries = await buildChain([{kind:'T'},{kind:'T'},{kind:'T'}])
    const cert = await certifyMartingale(entries)
    expect(cert.certificate_hash).toHaveLength(64)
    expect(cert.certificate_hash).toMatch(/^[0-9a-f]{64}$/)
  })
})

// ─── Tamper detection ─────────────────────────────────────

describe('certifyMartingale: tamper detection', () => {
  it('tampered entry_hash → is_anchored=false, drift_bounded=false', async () => {
    const entries = [...await buildChain([{kind:'T'},{kind:'T'},{kind:'T'}])]
    entries[1] = { ...entries[1]!, entry_hash: h('z') }
    const cert = await certifyMartingale(entries)
    expect(cert.is_anchored).toBe(false)
    expect(cert.drift_bounded).toBe(false)
  })

  it('!is_anchored → assertMartingaleAnchored throws MartingaleViolation', async () => {
    const entries = [...await buildChain([{kind:'T'},{kind:'T'}])]
    entries[0] = { ...entries[0]!, entry_hash: h('z') }
    const cert = await certifyMartingale(entries)
    expect(() => assertMartingaleAnchored(cert)).toThrow(MartingaleViolation)
  })

  it('!entropy_bounded → assertMartingaleAnchored throws MartingaleViolation', async () => {
    const entries = await buildChain([
      {kind:'A', verdict:'APPROVED'}, {kind:'A', verdict:'APPROVED'},
      {kind:'A', verdict:'APPROVED'}, {kind:'A', verdict:'APPROVED'}, {kind:'T'},
    ])
    const cert = await certifyMartingale(entries)
    expect(cert.entropy_bounded).toBe(false)
    expect(() => assertMartingaleAnchored(cert)).toThrow(MartingaleViolation)
  })
})

// ─── assertMartingaleAnchored ─────────────────────────────

describe('assertMartingaleAnchored', () => {
  it('valid anchored + entropy_bounded → no throw', async () => {
    const entries = await buildChain([{kind:'T'},{kind:'T'},{kind:'T'}])
    const cert = await certifyMartingale(entries)
    expect(() => assertMartingaleAnchored(cert)).not.toThrow()
  })

  it('schema_version is 1.0.0', async () => {
    const cert = await certifyMartingale([])
    expect(cert.schema_version).toBe(MARTINGALE_SCHEMA_VERSION)
  })

  it('violation message contains ratio info when entropy exceeded', async () => {
    const entries = await buildChain([
      {kind:'A', verdict:'APPROVED'}, {kind:'A', verdict:'APPROVED'},
      {kind:'A', verdict:'APPROVED'}, {kind:'A', verdict:'APPROVED'}, {kind:'T'},
    ])
    const cert = await certifyMartingale(entries)
    try {
      assertMartingaleAnchored(cert)
      expect.fail('should have thrown')
    } catch (e) {
      expect((e as MartingaleViolation).message).toMatch(/adaptive_ratio|mutation/)
    }
  })
})
