// ============================================================
// SOVEREIGN OMEGA — Compliance Tombstone & Audit tests
// EPISTEMIC TIER: T0 (regulatory requirement)
//
// Tests for compliance/tombstone.ts:
//   processTombstoneRequest — GDPR erasure receipt, partial failure
//   projectAuditLog         — pure projection, entry mapping, counters
//   checkRetentionCompliance — Article 12 gate-decision traceability
// ============================================================

import { describe, it, expect, vi } from 'vitest'
import {
  processTombstoneRequest,
  projectAuditLog,
  checkRetentionCompliance,
} from '../../src/compliance/tombstone.js'
import { EventType, RetentionClass } from '../../src/core/types.js'
import type { EventEnvelope, UUIDv7, SHA256Hex } from '../../src/core/types.js'

const H = '0'.repeat(64) as SHA256Hex

function makeEnvelope(
  eventType: EventType,
  timestampMs = 1_600_000_000_000,
  seq = 1n,
): EventEnvelope {
  return {
    event_id: `evt-${seq}` as UUIDv7,
    stream_id: 'stream-01' as UUIDv7,
    event_type: eventType,
    timestamp_ms: timestampMs,
    sequence: seq as unknown as import('../../src/core/types.js').SequenceNumber,
    producer_id: 'test',
    producer_version: '1.0.0',
    payload_schema_version: '1.0.0',
    payload: {},
    prev_hash: H,
    self_hash: H,
    retention_class: RetentionClass.STANDARD,
  }
}

// ── processTombstoneRequest ───────────────────────────────

describe('processTombstoneRequest', () => {
  it('returns completed receipt when all events are tombstoned successfully', async () => {
    const store = { append: vi.fn().mockResolvedValue(undefined) }
    const receipt = await processTombstoneRequest(
      store as never,
      {
        gdpr_request_id: 'gdpr-001',
        data_subject_id: 'user-42',
        events_to_tombstone: ['evt-1', 'evt-2'] as UUIDv7[],
        requested_at_ms: 1_600_000_000_000,
      },
      '1.0.0',
      '1.0.0',
    )
    expect(receipt.completed).toBe(true)
    expect(receipt.tombstoned_event_ids).toHaveLength(2)
    expect(receipt.incomplete_ids).toHaveLength(0)
    expect(receipt.request_id).toBe('gdpr-001')
  })

  it('result is frozen', async () => {
    const store = { append: vi.fn().mockResolvedValue(undefined) }
    const receipt = await processTombstoneRequest(
      store as never,
      {
        gdpr_request_id: 'gdpr-frozen',
        data_subject_id: 'u',
        events_to_tombstone: ['evt-3'] as UUIDv7[],
        requested_at_ms: 0,
      },
      '1.0.0',
      '1.0.0',
    )
    expect(Object.isFrozen(receipt)).toBe(true)
    expect(Object.isFrozen(receipt.tombstoned_event_ids)).toBe(true)
    expect(Object.isFrozen(receipt.incomplete_ids)).toBe(true)
  })

  it('marks event as incomplete when store.append throws', async () => {
    const store = { append: vi.fn().mockRejectedValue(new Error('write fail')) }
    const receipt = await processTombstoneRequest(
      store as never,
      {
        gdpr_request_id: 'gdpr-002',
        data_subject_id: 'user-99',
        events_to_tombstone: ['evt-fail'] as UUIDv7[],
        requested_at_ms: 0,
      },
      '1.0.0',
      '1.0.0',
    )
    expect(receipt.completed).toBe(false)
    expect(receipt.tombstoned_event_ids).toHaveLength(0)
    expect(receipt.incomplete_ids).toHaveLength(1)
    expect(receipt.incomplete_ids[0]).toBe('evt-fail')
  })

  it('partial failure: first event succeeds, second throws → completed=false', async () => {
    const store = {
      append: vi.fn()
        .mockResolvedValueOnce(undefined)
        .mockRejectedValueOnce(new Error('fail')),
    }
    const receipt = await processTombstoneRequest(
      store as never,
      {
        gdpr_request_id: 'gdpr-003',
        data_subject_id: 'u',
        events_to_tombstone: ['ok-evt', 'fail-evt'] as UUIDv7[],
        requested_at_ms: 0,
      },
      '1.0.0',
      '1.0.0',
    )
    expect(receipt.completed).toBe(false)
    expect(receipt.tombstoned_event_ids).toHaveLength(1)
    expect(receipt.incomplete_ids).toHaveLength(1)
  })

  it('empty events_to_tombstone returns completed receipt with empty arrays', async () => {
    const store = { append: vi.fn() }
    const receipt = await processTombstoneRequest(
      store as never,
      {
        gdpr_request_id: 'gdpr-empty',
        data_subject_id: 'u',
        events_to_tombstone: [],
        requested_at_ms: 0,
      },
      '1.0.0',
      '1.0.0',
    )
    expect(receipt.completed).toBe(true)
    expect(receipt.tombstoned_event_ids).toHaveLength(0)
    expect(store.append).not.toHaveBeenCalled()
  })
})

// ── projectAuditLog ───────────────────────────────────────

describe('projectAuditLog', () => {
  it('returns frozen result for empty event list', () => {
    const log = projectAuditLog([])
    expect(Object.isFrozen(log)).toBe(true)
    expect(log.total_events).toBe(0)
    expect(log.gate_decisions).toBe(0)
    expect(log.tombstones).toBe(0)
    expect(log.earliest_ms).toBe(0)
    expect(log.latest_ms).toBe(0)
  })

  it('maps event fields to audit entries correctly', () => {
    const env = makeEnvelope(EventType.RESPONSE_GENERATED, 1_600_000_001_000, 5n)
    const log = projectAuditLog([env])
    expect(log.total_events).toBe(1)
    expect(log.entries).toHaveLength(1)
    expect(log.entries[0]!.event_id).toBe('evt-5')
    expect(log.entries[0]!.event_type).toBe(EventType.RESPONSE_GENERATED)
    expect(log.entries[0]!.timestamp_ms).toBe(1_600_000_001_000)
    expect(log.entries[0]!.sequence).toBe('5')
  })

  it('counts GATE_EVALUATED in gate_decisions', () => {
    const evs = [
      makeEnvelope(EventType.GATE_EVALUATED, 1_600_000_000_000, 1n),
      makeEnvelope(EventType.MODIFICATION_ACCEPTED, 1_600_000_001_000, 2n),
      makeEnvelope(EventType.MODIFICATION_REJECTED, 1_600_000_002_000, 3n),
      makeEnvelope(EventType.RESPONSE_GENERATED, 1_600_000_003_000, 4n),
    ]
    const log = projectAuditLog(evs)
    expect(log.gate_decisions).toBe(3)
  })

  it('counts TOMBSTONE_CREATED in tombstones', () => {
    const evs = [
      makeEnvelope(EventType.TOMBSTONE_CREATED, 1_600_000_000_000, 1n),
      makeEnvelope(EventType.TOMBSTONE_CREATED, 1_600_000_001_000, 2n),
      makeEnvelope(EventType.GATE_EVALUATED, 1_600_000_002_000, 3n),
    ]
    const log = projectAuditLog(evs)
    expect(log.tombstones).toBe(2)
  })

  it('earliest_ms and latest_ms are min/max of timestamps', () => {
    const evs = [
      makeEnvelope(EventType.RESPONSE_GENERATED, 1_600_000_003_000, 1n),
      makeEnvelope(EventType.RESPONSE_GENERATED, 1_600_000_001_000, 2n),
      makeEnvelope(EventType.RESPONSE_GENERATED, 1_600_000_002_000, 3n),
    ]
    const log = projectAuditLog(evs)
    expect(log.earliest_ms).toBe(1_600_000_001_000)
    expect(log.latest_ms).toBe(1_600_000_003_000)
  })
})

// ── checkRetentionCompliance ──────────────────────────────

describe('checkRetentionCompliance', () => {
  it('compliant when gate_decisions > 0', () => {
    const log = projectAuditLog([
      makeEnvelope(EventType.GATE_EVALUATED, 1_600_000_000_000, 1n),
    ])
    const result = checkRetentionCompliance(log, 1_600_000_000_001)
    expect(result.compliant).toBe(true)
    expect(result.issues).toHaveLength(0)
  })

  it('non-compliant when total_events > 10 and gate_decisions === 0', () => {
    const evs = Array.from({ length: 11 }, (_, i) =>
      makeEnvelope(EventType.RESPONSE_GENERATED, 1_600_000_000_000 + i, BigInt(i + 1)),
    )
    const log = projectAuditLog(evs)
    const result = checkRetentionCompliance(log, 1_600_000_000_100)
    expect(result.compliant).toBe(false)
    expect(result.issues.length).toBeGreaterThan(0)
  })

  it('compliant when total_events ≤ 10 and gate_decisions === 0', () => {
    const evs = Array.from({ length: 5 }, (_, i) =>
      makeEnvelope(EventType.RESPONSE_GENERATED, 1_600_000_000_000 + i, BigInt(i + 1)),
    )
    const log = projectAuditLog(evs)
    const result = checkRetentionCompliance(log, 1_600_000_000_100)
    expect(result.compliant).toBe(true)
  })

  it('compliant for empty log', () => {
    const log = projectAuditLog([])
    const result = checkRetentionCompliance(log, 1_600_000_000_000)
    expect(result.compliant).toBe(true)
    expect(result.issues).toHaveLength(0)
  })
})
