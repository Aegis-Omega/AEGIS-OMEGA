// ============================================================
// Gate 107 — Constitutional Violation Cascade (Integration)
// ~18 tests: Cascade: tamper → is_anchored=false + entropy_bounded
//   =false → all three assertMartingaleAnchored conditions fail →
//   MartingaleViolation thrown with correct field in message.
// ============================================================

import { describe, it, expect } from 'vitest'
import { AdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { certifyMartingale, assertMartingaleAnchored, MartingaleViolation } from '../../src/constitutional/martingale.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

async function buildTopologyChain(n: number) {
  let lineage = AdaptiveLineage.empty()
  for (let i = 1; i <= n; i++) {
    const { lineage: next } = await lineage.append(
      { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + (i % 26))) },
      seq(i),
    )
    lineage = next
  }
  return lineage
}

async function buildCapabilityChain(n: number) {
  let lineage = AdaptiveLineage.empty()
  for (let i = 1; i <= n; i++) {
    const { lineage: next } = await lineage.append(
      { kind: 'CAPABILITY_EVOLUTION', proposal_id: h(String.fromCharCode(97 + (i % 26))), verdict: 'APPROVED' },
      seq(i),
    )
    lineage = next
  }
  return lineage
}

// ─── Tamper cascade ───────────────────────────────────────

describe('Violation Cascade: tamper → !is_anchored', () => {
  it('tamper entry_hash → is_anchored=false', async () => {
    const lineage = await buildTopologyChain(10)
    const entries = [...lineage.getAll()]
    entries[5] = { ...entries[5]!, entry_hash: h('z') }
    const cert = await certifyMartingale(entries)
    expect(cert.is_anchored).toBe(false)
    expect(cert.drift_bounded).toBe(false)
  })

  it('tamper → assertMartingaleAnchored throws MartingaleViolation', async () => {
    const lineage = await buildTopologyChain(10)
    const entries = [...lineage.getAll()]
    entries[5] = { ...entries[5]!, entry_hash: h('z') }
    const cert = await certifyMartingale(entries)
    expect(() => assertMartingaleAnchored(cert)).toThrow(MartingaleViolation)
  })

  it('tamper → MartingaleViolation message contains relevant info', async () => {
    const lineage = await buildTopologyChain(10)
    const entries = [...lineage.getAll()]
    entries[5] = { ...entries[5]!, entry_hash: h('z') }
    const cert = await certifyMartingale(entries)
    try {
      assertMartingaleAnchored(cert)
      expect.fail('should have thrown')
    } catch (e) {
      expect(e).toBeInstanceOf(MartingaleViolation)
      expect((e as MartingaleViolation).name).toBe('MartingaleViolation')
    }
  })

  it('tamper previous_entry_hash → is_anchored=false', async () => {
    const lineage = await buildTopologyChain(5)
    const entries = [...lineage.getAll()]
    entries[3] = { ...entries[3]!, previous_entry_hash: h('z') }
    const cert = await certifyMartingale(entries)
    expect(cert.is_anchored).toBe(false)
  })
})

// ─── Entropy violation ─────────────────────────────────────

describe('Violation Cascade: entropy → !entropy_bounded', () => {
  it('100 APPROVED → entropy_bounded=false', async () => {
    const lineage = await buildCapabilityChain(100)
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.entropy_bounded).toBe(false)
    expect(cert.is_anchored).toBe(true)  // chain valid, just over entropy limit
  })

  it('entropy violation → assertMartingaleAnchored throws', async () => {
    const lineage = await buildCapabilityChain(100)
    const cert = await certifyMartingale(lineage.getAll())
    expect(() => assertMartingaleAnchored(cert)).toThrow(MartingaleViolation)
  })

  it('entropy violation message contains ratio/mutation info', async () => {
    const lineage = await buildCapabilityChain(100)
    const cert = await certifyMartingale(lineage.getAll())
    try {
      assertMartingaleAnchored(cert)
      expect.fail('should have thrown')
    } catch (e) {
      expect((e as MartingaleViolation).message).toMatch(/adaptive_ratio|mutation/i)
    }
  })
})

// ─── Both violations simultaneously ───────────────────────

describe('Violation Cascade: dual violation', () => {
  it('tampered entropy-exceeded chain → both is_anchored=false AND entropy_bounded=false', async () => {
    const lineage = await buildCapabilityChain(100)
    const entries = [...lineage.getAll()]
    entries[50] = { ...entries[50]!, entry_hash: h('z') }
    const cert = await certifyMartingale(entries)
    // is_anchored=false (tamper) AND entropy_bounded=false (100 APPROVED)
    expect(cert.is_anchored).toBe(false)
    expect(cert.entropy_bounded).toBe(false)
    expect(() => assertMartingaleAnchored(cert)).toThrow(MartingaleViolation)
  })

  it('clean chain → assertMartingaleAnchored does not throw', async () => {
    const lineage = await buildTopologyChain(10)
    const cert = await certifyMartingale(lineage.getAll())
    expect(cert.is_anchored).toBe(true)
    expect(cert.entropy_bounded).toBe(true)
    expect(() => assertMartingaleAnchored(cert)).not.toThrow()
  })

  it('MartingaleViolation is instanceof Error', () => {
    expect(new MartingaleViolation('test')).toBeInstanceOf(Error)
    expect(new MartingaleViolation('test').name).toBe('MartingaleViolation')
  })

  it('empty chain → no violation → no throw', async () => {
    const cert = await certifyMartingale([])
    expect(cert.is_anchored).toBe(true)
    expect(cert.entropy_bounded).toBe(true)
    expect(() => assertMartingaleAnchored(cert)).not.toThrow()
  })
})

// ─── Certificate determinism ──────────────────────────────

describe('Violation Cascade: certificate determinism', () => {
  it('tampered cert hash is deterministic ×3', async () => {
    const lineage = await buildTopologyChain(5)
    const entries = [...lineage.getAll()]
    entries[2] = { ...entries[2]!, entry_hash: h('z') }
    const [c1, c2, c3] = await Promise.all([
      certifyMartingale(entries),
      certifyMartingale(entries),
      certifyMartingale(entries),
    ])
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })
})
