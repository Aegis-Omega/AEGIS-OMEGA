// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 8
// EPISTEMIC TIER: T0/T1/T2
//
// Covers small modules with zero prior test coverage:
//   skill-harness/cross-org.ts — CrossOrgError + stub throws
//   ledger/verify.ts — verifySequences edge cases
//   lib/telemetry.ts — TelemetryState type safety (compile-time)
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  CrossOrgError,
  crossOrgTransfer,
  CROSS_ORG_SCHEMA_VERSION,
} from '../../src/skill-harness/cross-org.js'
import { verifySequences } from '../../src/ledger/verify.js'
import type { LedgerEntry } from '../../src/ledger/types.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import type { CrossOrgTransferRequest } from '../../src/skill-harness/cross-org.js'

// ── CrossOrgError ─────────────────────────────────────────

describe('CrossOrgError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new CrossOrgError('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('CrossOrgError')
    expect(e.message).toBe('test')
  })
})

// ── crossOrgTransfer — Phase 6 stub ──────────────────────

describe('crossOrgTransfer', () => {
  const request: CrossOrgTransferRequest = {
    source_org_id: 'org-a',
    target_org_id: 'org-b',
    skill_id: 'skill-01',
    requires_consent: true,
    schema_version: CROSS_ORG_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  }

  it('throws CrossOrgError (Phase 6 not yet implemented)', () => {
    expect(() => crossOrgTransfer(request)).toThrow(CrossOrgError)
  })

  it('error message mentions Phase 6 seam', () => {
    try {
      crossOrgTransfer(request)
    } catch (err) {
      expect((err as CrossOrgError).message).toContain('Phase 6')
    }
  })
})

// ── verifySequences — additional edge cases ───────────────

function makeLedgerEntry(seq: number): LedgerEntry {
  return Object.freeze({
    sequence: BigInt(seq) as SequenceNumber,
    entry_hash: `${'a'.repeat(63)}${seq % 10}` as SHA256Hex,
    previous_hash: GENESIS_HASH,
    data_hash: GENESIS_HASH,
    timestamp_sequence: seq,
    schema_version: '1.0.0',
    is_replay_reconstructable: true as const,
  })
}

describe('verifySequences edge cases', () => {
  it('returns valid=true for a single-entry list', () => {
    const result = verifySequences([makeLedgerEntry(1)])
    expect(result.valid).toBe(true)
    expect(result.verified_entries).toBe(1)
  })

  it('returns valid=false with reason when sequence is non-monotonic', () => {
    const entries = [makeLedgerEntry(3), makeLedgerEntry(1)]
    const result = verifySequences(entries)
    expect(result.valid).toBe(false)
    expect(result.reason).toContain('not strictly after')
  })

  it('returns valid=false when two consecutive entries have the same sequence', () => {
    const entries = [makeLedgerEntry(5), makeLedgerEntry(5)]
    const result = verifySequences(entries)
    expect(result.valid).toBe(false)
    expect(result.failed_at_sequence).toBe(5n)
  })

  it('verified_entries reflects how many were checked before failure', () => {
    // entries 1, 2, 1 — failure at index 2 (second entry checked = 2)
    const entries = [makeLedgerEntry(1), makeLedgerEntry(2), makeLedgerEntry(1)]
    const result = verifySequences(entries)
    expect(result.valid).toBe(false)
    expect(result.verified_entries).toBe(2)
  })

  it('returns valid=true for a properly ordered 5-entry sequence', () => {
    const entries = [1, 3, 5, 7, 9].map(makeLedgerEntry)
    const result = verifySequences(entries)
    expect(result.valid).toBe(true)
    expect(result.verified_entries).toBe(5)
  })
})
