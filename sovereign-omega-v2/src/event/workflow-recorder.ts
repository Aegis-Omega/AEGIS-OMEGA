// ============================================================
// SOVEREIGN OMEGA — Cognitive Workflow Event Recorder (E5)
// EPISTEMIC TIER: T1
// Replay-safety-gated write path for E5 events.
// timestamp_ms MUST come from the caller — never Date.now().
// ============================================================

import { assertReplaySafe } from '../core/semantics.js'
import { EventType, RetentionClass } from '../core/types.js'
import type { EventEnvelope } from '../core/types.js'

export const E5_PRODUCER_ID = 'sovereign-omega-v2:workflow-recorder'
export const E5_PRODUCER_VERSION = '0.5.3'
export const E5_SCHEMA_VERSION = '1.0.0'

/** Structural interface — accepts EventStore or any compatible append-capable object. */
export interface AppendCapable {
  append<T>(
    event_type: EventType,
    payload: T,
    producer_id: string,
    producer_version: string,
    payload_schema_version: string,
    retention_class: RetentionClass,
    timestamp_ms: number
  ): Promise<EventEnvelope<T>>
}

const E5_EVENT_TYPES = new Set<EventType>([
  EventType.AGENT_PATCH_PROPOSED,
  EventType.GATE_RESULT_RECORDED,
  EventType.CORPUS_NODE_ACCESSED,
  EventType.SUBAGENT_DELEGATED,
  EventType.SUBAGENT_RESULT_RECEIVED,
  EventType.GUARDIAN_INVOKED,
  EventType.GUARDIAN_VERDICT_ISSUED,
  EventType.SEMANTIC_NODE_QUERIED,
])

/**
 * Record an E5 cognitive workflow event into the store.
 * Enforces replay safety on the payload before any write occurs.
 *
 * @throws RangeError if event_type is not an E5 type
 * @throws ReplaySafetyViolation if payload contains NaN, Infinity, undefined,
 *         functions, symbols, or circular references
 */
export async function recordWorkflowEvent<T>(
  store: AppendCapable,
  event_type: EventType,
  payload: T,
  timestamp_ms: number
): Promise<EventEnvelope<T>> {
  if (!E5_EVENT_TYPES.has(event_type)) {
    throw new RangeError(
      `recordWorkflowEvent: '${event_type}' is not a cognitive workflow (E5) event type`
    )
  }
  // Safety gate: assertReplaySafe throws ReplaySafetyViolation before any IDB write.
  assertReplaySafe(payload, event_type)
  return store.append(
    event_type,
    payload,
    E5_PRODUCER_ID,
    E5_PRODUCER_VERSION,
    E5_SCHEMA_VERSION,
    RetentionClass.STANDARD,
    timestamp_ms
  )
}
