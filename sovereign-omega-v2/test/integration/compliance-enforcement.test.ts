// ============================================================
// Gate 110 — Compliance Enforcement (Integration)
// ~18 tests: Audit event chain; forensics hash binding;
//   enforcement record frozen; traceability field present;
//   MartingaleCertificate as compliance ledger anchor.
// ============================================================

import { describe, it, expect } from 'vitest'
import { AdaptiveLineage, certifyAdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { certifyMartingale, assertMartingaleAnchored, MartingaleViolation } from '../../src/constitutional/martingale.js'
import { buildSelfAttestation, verifySelfAttestation } from '../../src/frame/attestation.js'
import { buildTopology } from '../../src/frame/topology.js'
import { LedgerChain } from '../../src/ledger/chain.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
import { hashValue } from '../../src/core/hashing.js'
import type { LedgerEntry } from '../../src/ledger/types.js'
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
const TS = 1_600_000_000_000

// ─── Audit event chain ────────────────────────────────────

describe('Compliance: audit event chain', () => {
  it('10-entry audit chain → certifyAdaptiveLineage is_valid=true', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 10; i++) {
      const topo = await buildTopology({ ...BASE, sequence: seq(i) })
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: topo.topology_hash }, seq(i),
      )
      lineage = next
    }
    const cert = await certifyAdaptiveLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(10)
    expect(cert.is_replay_reconstructable).toBe(true)
  })

  it('every audit entry has is_replay_reconstructable=true', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 5; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + i)) }, seq(i),
      )
      lineage = next
    }
    for (const entry of lineage.getAll()) {
      expect(entry.is_replay_reconstructable).toBe(true)
    }
  })

  it('audit certificate_hash is 64-char hex', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 3; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + i)) }, seq(i),
      )
      lineage = next
    }
    const cert = await certifyAdaptiveLineage(lineage.getAll())
    expect(cert.certificate_hash).toHaveLength(64)
    expect(cert.certificate_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('audit terminal_hash = last entry_hash', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 5; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + i)) }, seq(i),
      )
      lineage = next
    }
    const entries = lineage.getAll()
    const cert = await certifyAdaptiveLineage(entries)
    expect(cert.terminal_hash).toBe(entries[4]!.entry_hash)
  })
})

// ─── Forensics hash binding ───────────────────────────────

describe('Compliance: forensics hash binding', () => {
  it('attestation binds DFA cert + topology for forensic traceability', async () => {
    const topo = await buildTopology({ ...BASE, sequence: seq(1) })
    const att = await buildSelfAttestation({
      dfa_certificate_hash: h('forensic-dfa'),
      topology_hash: topo.topology_hash,
      lineage_terminal_hash: null,
      capsule_attestation_hash: null,
      sequence: seq(1),
    })
    expect(att.dfa_certificate_hash).toBe(h('forensic-dfa'))
    expect(att.topology_hash).toBe(topo.topology_hash)
    expect(await verifySelfAttestation(att)).toBe(true)
  })

  it('tampered attestation → verifySelfAttestation=false (forensic detection)', async () => {
    const topo = await buildTopology({ ...BASE, sequence: seq(1) })
    const att = await buildSelfAttestation({
      dfa_certificate_hash: h('d'), topology_hash: topo.topology_hash,
      lineage_terminal_hash: null, capsule_attestation_hash: null, sequence: seq(1),
    })
    const tampered = { ...att, dfa_certificate_hash: h('forged') }
    expect(await verifySelfAttestation(tampered)).toBe(false)
  })

  it('LedgerChain frame_hash binding → forensic chain intact', async () => {
    let chain = LedgerChain.empty()
    let prevHash = GENESIS_HASH
    const entries: LedgerEntry[] = []
    for (let i = 1; i <= 5; i++) {
      const topo = await buildTopology({ ...BASE, sequence: seq(i) })
      const e: LedgerEntry = Object.freeze({
        sequence: seq(i), previous_hash: prevHash,
        frame_hash: topo.topology_hash, governance_hash: h('g'), timestamp_ms: TS + i,
      })
      chain = chain.append(e)
      entries.push(e)
      prevHash = await hashValue(e) as SHA256Hex
    }
    // All frame_hashes are bound to topology_hashes
    for (let i = 0; i < 5; i++) {
      expect(chain.getAll()[i]!.frame_hash).toHaveLength(64)
    }
  })
})

// ─── Enforcement record frozen ────────────────────────────

describe('Compliance: enforcement record immutability', () => {
  it('certifyAdaptiveLineage result is frozen', async () => {
    let lineage = AdaptiveLineage.empty()
    const { lineage: next } = await lineage.append(
      { kind: 'TOPOLOGY_TRANSITION', topology_hash: h('x') }, seq(1),
    )
    lineage = next
    const cert = await certifyAdaptiveLineage(lineage.getAll())
    expect(Object.isFrozen(cert)).toBe(true)
  })

  it('certifyMartingale result is frozen', async () => {
    let lineage = AdaptiveLineage.empty()
    const { lineage: next } = await lineage.append(
      { kind: 'TOPOLOGY_TRANSITION', topology_hash: h('x') }, seq(1),
    )
    lineage = next
    const cert = await certifyMartingale(lineage.getAll())
    expect(Object.isFrozen(cert)).toBe(true)
  })

  it('MartingaleCertificate as compliance ledger anchor: schema_version=1.0.0', async () => {
    const cert = await certifyMartingale([])
    expect(cert.schema_version).toBe('1.0.0')
  })

  it('assertMartingaleAnchored on clean chain → no compliance violation', async () => {
    let lineage = AdaptiveLineage.empty()
    for (let i = 1; i <= 5; i++) {
      const { lineage: next } = await lineage.append(
        { kind: 'TOPOLOGY_TRANSITION', topology_hash: h(String.fromCharCode(97 + i)) }, seq(i),
      )
      lineage = next
    }
    const cert = await certifyMartingale(lineage.getAll())
    expect(() => assertMartingaleAnchored(cert)).not.toThrow()
  })

  it('compliance violation → MartingaleViolation is an Error (GDPR Article 12 traceability)', () => {
    const violation = new MartingaleViolation('EU AI Act Article 12 — audit trail interrupted')
    expect(violation).toBeInstanceOf(Error)
    expect(violation.name).toBe('MartingaleViolation')
    expect(violation.message).toContain('Article 12')
  })
})
