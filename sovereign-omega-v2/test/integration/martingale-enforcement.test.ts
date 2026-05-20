// ============================================================
// Gate 62 — Constitutional Martingale Enforcement (Integration)
// ~22 tests: certifyMartingale at 100-entry scale; golden ratio
//   boundary (61/100=0.61<1/φ→bounded; 62/100=0.62≥1/φ→not bounded)
//   mirrors swarm quorum boundary exactly; tamper at entry 50 and
//   last; mixed APPROVED/REJECTED/TOPOLOGY counting; holonic triad
//   proven: MUTATION_RATE_LIMIT === DEFAULT_QUORUM_THRESHOLD.
//
// Constitutional claim: the 1/φ threshold governing swarm convergence
// (src/consensus/swarm.ts) and the 1/φ threshold governing adaptive
// mutation rate (src/constitutional/martingale.ts) are the same
// constant — proven here by direct numerical identity test.
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  certifyMartingale, assertMartingaleAnchored,
  MartingaleViolation, MUTATION_RATE_LIMIT,
} from '../../src/constitutional/martingale.js'
import { DEFAULT_QUORUM_THRESHOLD } from '../../src/consensus/swarm.js'
import { AdaptiveLineage, type AdaptiveLineageEntry, type AdaptiveEvent } from '../../src/frame/adaptive-lineage.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

function topoEvent(n: number): AdaptiveEvent {
  return { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + (n % 26))) }
}

function capEvent(n: number, verdict: 'APPROVED' | 'REJECTED'): AdaptiveEvent {
  return { kind: 'CAPABILITY_EVOLUTION', proposal_id: h(String.fromCharCode(97 + (n % 26))), verdict }
}

async function buildEntries(
  specs: Array<'T' | 'A' | 'R'>,
): Promise<readonly AdaptiveLineageEntry[]> {
  let lineage = AdaptiveLineage.empty()
  for (let i = 0; i < specs.length; i++) {
    const s = specs[i]!
    const event: AdaptiveEvent =
      s === 'T' ? topoEvent(i + 1) :
      s === 'A' ? capEvent(i + 1, 'APPROVED') :
                  capEvent(i + 1, 'REJECTED')
    const { lineage: next } = await lineage.append(event, seq(i + 1))
    lineage = next
  }
  return lineage.getAll()
}

async function buildTopoChain(n: number): Promise<readonly AdaptiveLineageEntry[]> {
  return buildEntries(Array.from({ length: n }, () => 'T' as const))
}

// ─── 100-entry all-topology chain ─────────────────────────

describe('Martingale: 100-entry all-topology chain', () => {
  it('is_anchored=true, entropy_bounded=true, adaptive_power=0', async () => {
    const entries = await buildTopoChain(100)
    const cert = await certifyMartingale(entries)
    expect(cert.is_anchored).toBe(true)
    expect(cert.entropy_bounded).toBe(true)
    expect(cert.adaptive_power).toBe(0)
    expect(cert.replay_verifiability).toBe(100)
    expect(cert.adaptive_ratio).toBe(0)
  })

  it('certify × 3 on 100-entry chain → identical certificate_hash', async () => {
    const entries = await buildTopoChain(100)
    const [c1, c2, c3] = await Promise.all([
      certifyMartingale(entries),
      certifyMartingale(entries),
      certifyMartingale(entries),
    ])
    expect(c1!.certificate_hash).toBe(c2!.certificate_hash)
    expect(c2!.certificate_hash).toBe(c3!.certificate_hash)
  })

  it('assertMartingaleAnchored on 100-entry all-topology → no throw', async () => {
    const entries = await buildTopoChain(100)
    const cert = await certifyMartingale(entries)
    expect(() => assertMartingaleAnchored(cert)).not.toThrow()
  })
})

// ─── Golden ratio boundary (mirrors swarm quorum boundary) ─

describe('Martingale: 1/φ boundary at 61/62 per 100 entries', () => {
  it('61 APPROVED / 100 total = 0.61 < 1/φ → entropy_bounded=true', async () => {
    // 61 APPROVED + 39 TOPOLOGY = 100 entries
    const specs: Array<'T' | 'A'> = [
      ...Array.from({ length: 61 }, () => 'A' as const),
      ...Array.from({ length: 39 }, () => 'T' as const),
    ]
    const entries = await buildEntries(specs)
    const cert = await certifyMartingale(entries)
    expect(cert.adaptive_power).toBe(61)
    expect(cert.replay_verifiability).toBe(100)
    expect(cert.entropy_bounded).toBe(true)    // 0.61 < 0.6180...
  })

  it('62 APPROVED / 100 total = 0.62 ≥ 1/φ → entropy_bounded=false', async () => {
    // 62 APPROVED + 38 TOPOLOGY = 100 entries
    const specs: Array<'T' | 'A'> = [
      ...Array.from({ length: 62 }, () => 'A' as const),
      ...Array.from({ length: 38 }, () => 'T' as const),
    ]
    const entries = await buildEntries(specs)
    const cert = await certifyMartingale(entries)
    expect(cert.adaptive_power).toBe(62)
    expect(cert.entropy_bounded).toBe(false)   // 0.62 ≥ 0.6180...
  })

  it('61 APPROVED → assertMartingaleAnchored passes', async () => {
    const specs: Array<'T' | 'A'> = [
      ...Array.from({ length: 61 }, () => 'A' as const),
      ...Array.from({ length: 39 }, () => 'T' as const),
    ]
    const cert = await certifyMartingale(await buildEntries(specs))
    expect(() => assertMartingaleAnchored(cert)).not.toThrow()
  })

  it('62 APPROVED → assertMartingaleAnchored throws MartingaleViolation', async () => {
    const specs: Array<'T' | 'A'> = [
      ...Array.from({ length: 62 }, () => 'A' as const),
      ...Array.from({ length: 38 }, () => 'T' as const),
    ]
    const cert = await certifyMartingale(await buildEntries(specs))
    expect(() => assertMartingaleAnchored(cert)).toThrow(MartingaleViolation)
  })
})

// ─── Tamper at scale ──────────────────────────────────────

describe('Martingale: tamper detection at scale', () => {
  it('tamper entry_hash at position 50 of 100 → is_anchored=false', async () => {
    const entries = [...await buildTopoChain(100)]
    entries[50] = { ...entries[50]!, entry_hash: h('z') }
    const cert = await certifyMartingale(entries)
    expect(cert.is_anchored).toBe(false)
    expect(cert.drift_bounded).toBe(false)
  })

  it('tamper last entry → is_anchored=false', async () => {
    const entries = [...await buildTopoChain(100)]
    entries[99] = { ...entries[99]!, entry_hash: h('z') }
    const cert = await certifyMartingale(entries)
    expect(cert.is_anchored).toBe(false)
  })

  it('tampered chain → assertMartingaleAnchored throws', async () => {
    const entries = [...await buildTopoChain(10)]
    entries[5] = { ...entries[5]!, entry_hash: h('z') }
    const cert = await certifyMartingale(entries)
    expect(() => assertMartingaleAnchored(cert)).toThrow(MartingaleViolation)
  })
})

// ─── Mixed event types ────────────────────────────────────

describe('Martingale: APPROVED / REJECTED / TOPOLOGY counting', () => {
  it('30 APPROVED + 30 REJECTED + 40 TOPOLOGY → adaptive_power=30', async () => {
    const specs: Array<'T' | 'A' | 'R'> = [
      ...Array.from({ length: 30 }, () => 'A' as const),
      ...Array.from({ length: 30 }, () => 'R' as const),
      ...Array.from({ length: 40 }, () => 'T' as const),
    ]
    const entries = await buildEntries(specs)
    const cert = await certifyMartingale(entries)
    expect(cert.adaptive_power).toBe(30)       // only APPROVED counted
    expect(cert.replay_verifiability).toBe(100)
    expect(cert.adaptive_ratio).toBeCloseTo(0.30, 10)
    expect(cert.entropy_bounded).toBe(true)    // 0.30 < 0.618
  })

  it('all 100 REJECTED → adaptive_power=0, entropy_bounded=true', async () => {
    const entries = await buildEntries(Array.from({ length: 100 }, () => 'R' as const))
    const cert = await certifyMartingale(entries)
    expect(cert.adaptive_power).toBe(0)
    expect(cert.entropy_bounded).toBe(true)
  })

  it('all 100 APPROVED → entropy_bounded=false', async () => {
    const entries = await buildEntries(Array.from({ length: 100 }, () => 'A' as const))
    const cert = await certifyMartingale(entries)
    expect(cert.adaptive_power).toBe(100)
    expect(cert.entropy_bounded).toBe(false)
  })

  it('single APPROVED entry → adaptive_ratio=1.0 → entropy_bounded=false', async () => {
    const entries = await buildEntries(['A'])
    const cert = await certifyMartingale(entries)
    expect(cert.adaptive_power).toBe(1)
    expect(cert.adaptive_ratio).toBe(1)
    expect(cert.entropy_bounded).toBe(false)
  })
})

// ─── Holonic triad integration ────────────────────────────

describe('Martingale: holonic triad — 1/φ governs all three scales', () => {
  it('MUTATION_RATE_LIMIT === DEFAULT_QUORUM_THRESHOLD (same 1/φ)', () => {
    // This is the holonic proof: swarm consensus and constitutional mutation rate
    // share the same governing constant, derived independently.
    expect(MUTATION_RATE_LIMIT).toBe(DEFAULT_QUORUM_THRESHOLD)
  })

  it('boundary 62/100 matches swarm quorum boundary (62/100 ≥ 1/φ)', () => {
    // swarm-adversarial.test.ts Gate 58: 62/100 ≥ 1/φ → quorum_reached=true
    // martingale Gate 62: 62/100 ≥ 1/φ → entropy_bounded=false
    // Same numerical threshold, opposite governance consequence.
    expect(62 / 100 >= MUTATION_RATE_LIMIT).toBe(true)
    expect(61 / 100 >= MUTATION_RATE_LIMIT).toBe(false)
  })

  it('MartingaleViolation is instanceof Error', () => {
    expect(new MartingaleViolation('x')).toBeInstanceOf(Error)
  })

  it('schema_version is 1.0.0 and is_replay_reconstructable=true', async () => {
    const cert = await certifyMartingale([])
    expect(cert.schema_version).toBe('1.0.0')
    expect(cert.is_replay_reconstructable).toBe(true)
  })
})

// ─── Structure ────────────────────────────────────────────

describe('Martingale: structural guarantees', () => {
  it('certificate_hash is 64-char hex', async () => {
    const entries = await buildTopoChain(5)
    const cert = await certifyMartingale(entries)
    expect(cert.certificate_hash).toHaveLength(64)
    expect(cert.certificate_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('certificate is frozen', async () => {
    const cert = await certifyMartingale(await buildTopoChain(3))
    expect(Object.isFrozen(cert)).toBe(true)
  })

  it('empty chain → terminal_hash=null', async () => {
    const cert = await certifyMartingale([])
    expect(cert.terminal_hash).toBeNull()
  })

  it('non-empty chain → terminal_hash matches last entry_hash', async () => {
    const entries = await buildTopoChain(5)
    const cert = await certifyMartingale(entries)
    expect(cert.terminal_hash).toBe(entries[4]!.entry_hash)
  })
})
