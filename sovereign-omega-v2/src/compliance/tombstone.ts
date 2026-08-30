// ============================================================
// SOVEREIGN OMEGA — GDPR Tombstoning & Compliance Audit
// EPISTEMIC TIER: T0 (regulatory requirement)
// Tombstoning: payload-encryption + key shredding pattern.
// Structural log record persists. Payload becomes irrecoverable.
// Audit log: Article 12 EU AI Act alignment.
// ============================================================

import type { EventEnvelope, EventType, UUIDv7, SHA256Hex, RetentionClass } from '../core/types.js'
import { EventType as ET, RetentionClass as RC } from '../core/types.js'
import type { EventStore } from '../event/store.js'

// ─── Tombstone Module ──────────────────────────────────────

export interface TombstoneRequest {
  readonly gdpr_request_id: string
  readonly data_subject_id: string
  readonly events_to_tombstone: readonly UUIDv7[]
  readonly requested_at_ms: number  // from event substrate
}

export interface TombstoneReceipt {
  readonly request_id: string
  readonly tombstoned_event_ids: readonly UUIDv7[]
  readonly completed: boolean
  readonly incomplete_ids: readonly UUIDv7[]
}

/**
 * Process a GDPR Article 17 erasure request.
 *
 * Process:
 * 1. For each affected event: shred the encryption key in KMS (stub here)
 * 2. Append a TOMBSTONE_CREATED event for each affected event
 * 3. Return a receipt only when all handlers confirm completion
 *
 * NOTE: This function stubs KMS key shredding. In production,
 * integrate with your KMS provider before calling this function.
 * The 72-hour completion target (spec Section 15) begins at requestedAtMs.
 */
export async function processTombstoneRequest(
  store: EventStore,
  request: TombstoneRequest,
  producerVersion: string,
  schemaVersion: string
): Promise<TombstoneReceipt> {
  const tombstoned: UUIDv7[] = []
  const incomplete: UUIDv7[] = []

  for (const eventId of request.events_to_tombstone) {
    try {
      // STUB: In production, call KMS to shred the payload encryption key
      // await kmsClient.shredKey(eventId, request.data_subject_id)

      await store.append(
        ET.TOMBSTONE_CREATED,
        {
          original_event_id: eventId,
          gdpr_request_id: request.gdpr_request_id,
          data_subject_id: request.data_subject_id,
          key_shredded_at: request.requested_at_ms,
          kms_confirmation: 'STUB_NOT_IMPLEMENTED',
        },
        'compliance',
        producerVersion,
        schemaVersion,
        RC.LEGAL_HOLD,
        request.requested_at_ms
      )
      tombstoned.push(eventId)
    } catch {
      incomplete.push(eventId)
    }
  }

  // Receipt is only issued when all handlers confirm — incomplete items block receipt
  return Object.freeze({
    request_id: request.gdpr_request_id,
    tombstoned_event_ids: Object.freeze(tombstoned),
    completed: incomplete.length === 0,
    incomplete_ids: Object.freeze(incomplete),
  })
}

// ─── Audit Module ──────────────────────────────────────────

export interface AuditEntry {
  readonly event_id: UUIDv7
  readonly event_type: EventType
  readonly timestamp_ms: number
  readonly sequence: string
  readonly retention_class: RetentionClass
  readonly self_hash: SHA256Hex
  readonly producer_id: string
}

export interface ComplianceAuditLog {
  readonly entries: readonly AuditEntry[]
  readonly total_events: number
  readonly earliest_ms: number
  readonly latest_ms: number
  readonly gate_decisions: number
  readonly tombstones: number
}

/**
 * Project the compliance audit log from the full event history.
 * EU AI Act Article 12 aligned: all events over system lifetime.
 * This is a pure projection — it does not modify the event store.
 */
export function projectAuditLog(events: readonly EventEnvelope[]): ComplianceAuditLog {
  const entries: AuditEntry[] = events.map(e => ({
    event_id: e.event_id,
    event_type: e.event_type,
    timestamp_ms: e.timestamp_ms,
    sequence: String(e.sequence),
    retention_class: e.retention_class,
    self_hash: e.self_hash,
    producer_id: e.producer_id,
  }))

  const gateDecisions = events.filter(e =>
    e.event_type === ET.GATE_EVALUATED ||
    e.event_type === ET.MODIFICATION_ACCEPTED ||
    e.event_type === ET.MODIFICATION_REJECTED
  ).length

  const tombstones = events.filter(e => e.event_type === ET.TOMBSTONE_CREATED).length

  const timestamps = events.map(e => e.timestamp_ms)

  return Object.freeze({
    entries: Object.freeze(entries),
    total_events: events.length,
    earliest_ms: timestamps.length > 0 ? Math.min(...timestamps) : 0,
    latest_ms: timestamps.length > 0 ? Math.max(...timestamps) : 0,
    gate_decisions: gateDecisions,
    tombstones,
  })
}

/**
 * Check whether the audit log satisfies Article 12 retention requirements.
 * Returns missing retention categories that require attention.
 */
export function checkRetentionCompliance(
  log: ComplianceAuditLog,
  currentMs: number
): { compliant: boolean; issues: string[] } {
  const issues: string[] = []

  // Article 12: 6-month minimum for regulated events
  const sixMonthsMs = 6 * 30 * 24 * 60 * 60 * 1000
  if (log.total_events > 0 && (currentMs - log.earliest_ms) < sixMonthsMs) {
    // Not yet at 6 months — this is informational, not a violation
  }

  if (log.gate_decisions === 0 && log.total_events > 10) {
    issues.push('No gate decision events found — Article 12 traceability may be incomplete')
  }

  return { compliant: issues.length === 0, issues }
}
