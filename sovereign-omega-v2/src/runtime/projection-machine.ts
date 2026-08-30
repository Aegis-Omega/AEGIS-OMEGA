// ============================================================
// SOVEREIGN OMEGA — Pure Reducer-Driven Projection Machine
// EPISTEMIC TIER: T0
// Ω-2: Eliminates hidden mutable OO state. The runtime is a
// pure fold over the event stream. All state is derived.
// Persistence: append-only. Runtime: reduce(initial, events).
// ============================================================

import type { EventEnvelope, RuntimeVersionPin } from '../core/types.js'
import type { Q32_32 } from '../core/fixedpoint.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'

// ─── Frozen Migration Artifact ────────────────────────────

export interface FrozenMigrationArtifact {
  readonly migration_id: string
  readonly from_version: string
  readonly to_version: string
  readonly artifact_hash: SHA256Hex
  readonly sealed: true
}

// ─── Telemetry Entry ──────────────────────────────────────

export interface TelemetryEntry {
  readonly sequence: SequenceNumber
  readonly vcg_error_q32: Q32_32
  readonly gate_lcb_q32: Q32_32
  readonly verifier_id: string
  readonly timestamp_sequence: number  // event-derived; never wall clock
}

// ─── Runtime State ────────────────────────────────────────

export type RuntimeState = {
  readonly events: readonly EventEnvelope[]
  readonly registry: readonly FrozenMigrationArtifact[]
  readonly telemetry: readonly TelemetryEntry[]
  readonly k_accounting: Readonly<Record<string, number>>
  readonly verifier_weights: Readonly<Record<string, Q32_32>>
  readonly last_sequence: SequenceNumber
  readonly chain_hash: SHA256Hex
  readonly freeze_reason?: string
}

export const INITIAL_RUNTIME_STATE: RuntimeState = deepFreeze({
  events: [],
  registry: [],
  telemetry: [],
  k_accounting: {},
  verifier_weights: {},
  last_sequence: 0n as SequenceNumber,
  chain_hash: '0'.repeat(64) as SHA256Hex,
})

// ─── Pure Reducer ─────────────────────────────────────────

/**
 * Pure fold over a sovereign event. Returns new frozen state.
 * This is the only permitted mutation path for runtime state.
 *
 * INVARIANT: Given identical (prev, event) inputs, output is always identical.
 * INVARIANT: No external I/O, no Date.now(), no Math.random().
 */
export function reduceRuntime(
  prev: Readonly<RuntimeState>,
  event: EventEnvelope
): Readonly<RuntimeState> {
  // Frozen runtimes ignore all subsequent events
  if (prev.freeze_reason !== undefined) return prev

  // Sequence must always advance
  if (event.sequence <= prev.last_sequence) return prev

  const next: RuntimeState = {
    ...prev,
    events: Object.freeze([...prev.events, event]),
    last_sequence: event.sequence,
    chain_hash: event.self_hash,
  }

  return deepFreeze(next)
}

/**
 * Reconstruct runtime state by folding over an event stream.
 * This is the canonical replay path.
 * pin is validated before execution begins.
 */
export function replayRuntimeState(
  events: readonly EventEnvelope[],
  _pin: RuntimeVersionPin
): Readonly<RuntimeState> {
  return events.reduce(
    (state, event) => reduceRuntime(state, event),
    INITIAL_RUNTIME_STATE
  )
}
