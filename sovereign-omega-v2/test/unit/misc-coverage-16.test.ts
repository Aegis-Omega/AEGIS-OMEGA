// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 16
// EPISTEMIC TIER: T0/T2
//
// Covers paths with zero prior coverage in:
//   ledger/constitutional-audit.ts  — verifyAll() with 2+ entries (line 124)
//   skill-harness/hgt/hgt-scanner.ts — HGTError class name field (line 56)
//   sitr/orchestration.ts           — undefined frame guard (line 18)
//   memory/collapse.ts              — collapseMultiverse winner-lineage replay
//                                     (lines 144-151)
// ============================================================

import { describe, it, expect, beforeAll } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

// ── ledger/constitutional-audit.ts — verifyAll() with 2+ entries ──────────────

import {
  ConstitutionalAuditLog,
  buildAuditEntry,
  AuditLogError,
} from '../../src/ledger/constitutional-audit.js'
import { assembleBlock } from '../../src/ledger/block.js'
import type { CommittedBlock } from '../../src/ledger/block.js'
import type { LedgerEntry } from '../../src/ledger/types.js'

const ZERO_SHA = '0'.repeat(64) as SHA256Hex

let block0: CommittedBlock
let block1: CommittedBlock

beforeAll(async () => {
  const e1: LedgerEntry = {
    sequence: BigInt(1) as unknown as SequenceNumber,
    previous_hash: ZERO_SHA,
    frame_hash: ZERO_SHA,
    governance_hash: ZERO_SHA,
    timestamp_ms: 1_600_000_000_001,
  }
  const e2: LedgerEntry = { ...e1, sequence: BigInt(2) as unknown as SequenceNumber, timestamp_ms: 1_600_000_000_002 }
  block0 = await assembleBlock(null, [e1])
  block1 = await assembleBlock(block0, [e2])
})

describe('ConstitutionalAuditLog.verifyAll — 2 entries', () => {
  it('verifyAll returns true for a valid 2-entry log (covers line 124 condition)', async () => {
    const a1 = await buildAuditEntry('decision-cov16-a', block0, ZERO_SHA)
    const a2 = await buildAuditEntry('decision-cov16-b', block1, ZERO_SHA)
    const log = ConstitutionalAuditLog.empty().append(a1).append(a2)
    const result = await log.verifyAll()
    expect(result).toBe(true)
  })

  it('verifyAll on a 3-entry log iterates the i>0 path multiple times', async () => {
    const a1 = await buildAuditEntry('d-cov16-1', block0, ZERO_SHA)
    const a2 = await buildAuditEntry('d-cov16-2', block0, ZERO_SHA)  // same block is allowed
    const a3 = await buildAuditEntry('d-cov16-3', block1, ZERO_SHA)
    const log = ConstitutionalAuditLog.empty().append(a1).append(a2).append(a3)
    expect(await log.verifyAll()).toBe(true)
  })

  it('AuditLogError is instantiable (class invariant)', () => {
    const err = new AuditLogError('cov16')
    expect(err.name).toBe('AuditLogError')
    expect(err instanceof Error).toBe(true)
  })
})

// ── skill-harness/hgt/hgt-scanner.ts — HGTError class (line 56) ──────────────

import {
  HGTError,
  processRepoFiles,
  buildHGTRecord,
} from '../../src/skill-harness/hgt/hgt-scanner.js'

describe('HGTError — class name field', () => {
  it('is instantiable with name HGTError (covers line 56)', () => {
    const err = new HGTError('cov16 test')
    expect(err.name).toBe('HGTError')
    expect(err instanceof Error).toBe(true)
    expect(err instanceof HGTError).toBe(true)
  })
})

describe('buildHGTRecord — with scan results', () => {
  it('builds an HGTRecord from empty scan results', async () => {
    const SEQ = BigInt(1) as unknown as SequenceNumber
    const result = await processRepoFiles('owner/empty-repo', [])
    const record = await buildHGTRecord([result], SEQ)
    expect(record.total_files_found).toBe(0)
    expect(record.total_admitted).toBe(0)
    expect(record.sources_scanned).toContain('owner/empty-repo')
    expect(record.is_replay_reconstructable).toBe(true)
  })

  it('buildHGTRecord with no results produces valid record', async () => {
    const SEQ = BigInt(2) as unknown as SequenceNumber
    const record = await buildHGTRecord([], SEQ)
    expect(record.total_files_found).toBe(0)
    expect(record.sources_scanned).toHaveLength(0)
  })
})

// ── sitr/orchestration.ts — undefined frame guard (line 18) ──────────────────

import { detectOrchestrationAnomalies } from '../../src/sitr/orchestration.js'
import type { CoordinationFrame } from '../../src/agents/types.js'

describe('detectOrchestrationAnomalies — undefined frame guard', () => {
  it('skips undefined frames without crashing (covers line 18 true branch)', () => {
    const frames = [undefined] as unknown as readonly CoordinationFrame[]
    const anomalies = detectOrchestrationAnomalies(frames, 1)
    expect(anomalies).toHaveLength(0)
  })

  it('mixed array with undefined and valid frame skips undefined', () => {
    const validFrame: CoordinationFrame = {
      frame_id: 'f1',
      agent_id: 'agent-a',
      sequence: 1,
      action_type: 'test',
      mutation_ids: [],
      replay_safe: true,
    }
    const frames = [undefined, validFrame] as unknown as readonly CoordinationFrame[]
    const anomalies = detectOrchestrationAnomalies(frames, 2)
    // undefined is skipped; validFrame has no anomalies
    expect(anomalies).toHaveLength(0)
  })
})

// ── memory/collapse.ts — winner-lineage replay loop (lines 144-151) ──────────

import { collapseMultiverse } from '../../src/memory/collapse.js'
import { MultiverseRegistry } from '../../src/memory/multiverse.js'
import type { AdaptiveEvent } from '../../src/frame/adaptive-lineage.js'

describe('collapseMultiverse — winner lineage replay loop', () => {
  it('replays winner entries into canonical registry (covers lines 144-151)', async () => {
    const SEQ1 = BigInt(1) as unknown as SequenceNumber
    const SEQ2 = BigInt(2) as unknown as SequenceNumber
    const SEQ3 = BigInt(3) as unknown as SequenceNumber

    // Fork universe 'u1' and append one event
    const { registry: r1 } = await MultiverseRegistry.empty().fork('u1', ZERO_SHA, SEQ1)
    const event: AdaptiveEvent = { kind: 'TOPOLOGY_TRANSITION', topology_hash: ZERO_SHA }
    const { registry: r2 } = await r1.appendToUniverse('u1', event, SEQ2)

    // With 1 universe, convergence is always reached (1.0 >= φ ≈ 0.618)
    const convergence = await r2.checkConvergence(SEQ2)
    expect(convergence.swarm_record.quorum_reached).toBe(true)
    expect(convergence.converged_universe_ids).toContain('u1')

    // Collapse — this triggers the winner-lineage replay loop
    const result = await collapseMultiverse(r2, convergence, SEQ3)

    expect(result.canonical_id).toBe('canonical')
    expect(result.record.winner_id).toBe('u1')
    expect(result.record.total_collapsed).toBe(0)  // no losing universes
    expect(result.record.is_replay_reconstructable).toBe(true)
  })

  it('collapsed canonical registry contains the winner entry', async () => {
    const SEQ1 = BigInt(1) as unknown as SequenceNumber
    const SEQ2 = BigInt(2) as unknown as SequenceNumber
    const SEQ3 = BigInt(3) as unknown as SequenceNumber

    const { registry: r1 } = await MultiverseRegistry.empty().fork('u1', ZERO_SHA, SEQ1)
    const event: AdaptiveEvent = { kind: 'TOPOLOGY_TRANSITION', topology_hash: ZERO_SHA }
    const { registry: r2 } = await r1.appendToUniverse('u1', event, SEQ2)

    const convergence = await r2.checkConvergence(SEQ2)
    const result = await collapseMultiverse(r2, convergence, SEQ3)

    // The canonical lineage should have 1 replayed entry
    const canonicalLineage = result.registry.getLineage('canonical')
    expect(canonicalLineage).not.toBeNull()
    expect(canonicalLineage!.length).toBe(1)
  })
})
