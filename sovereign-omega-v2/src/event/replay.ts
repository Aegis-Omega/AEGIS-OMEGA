// ============================================================
// SOVEREIGN OMEGA — Deterministic Replay Engine
// EPISTEMIC TIER: T0
// BUILD GATE 7: byte-identical DecisionSchema across runs
// PRIMITIVE 2: Deterministic Replayability
// ============================================================

import type { EventEnvelope, RuntimeVersionPin, SequenceNumber } from '../core/types.js'
import type { ProjectionState } from '../core/types.js'
import { createInitialState } from '../core/immutable.js'
import { INITIAL_PROJECTION_STATE, applyEvent } from '../projection/reducer.js'

export interface ReplayCheckpoint {
  readonly last_sequence: SequenceNumber
  readonly state: Readonly<ProjectionState>
  readonly state_hash: string
  readonly pin: RuntimeVersionPin
}

/**
 * Replay an ordered event stream against a projection, producing
 * a deterministic final state. Given identical inputs and pins,
 * always produces identical output.
 *
 * INVARIANT: No side effects. No external I/O.
 * INVARIANT: event.timestamp_ms is used for all temporal operations.
 */
export async function replayProjection(
  events: readonly EventEnvelope[],
  pin: RuntimeVersionPin,
  fromCheckpoint?: ReplayCheckpoint
): Promise<Readonly<ProjectionState>> {
  validateVersionPin(pin)

  let state: Readonly<ProjectionState> = fromCheckpoint?.state
    ?? createInitialState<ProjectionState>({ ...INITIAL_PROJECTION_STATE, projection_version: pin.projection_compiler_version })

  const startSequence = fromCheckpoint?.last_sequence ?? BigInt(-1)

  for (const event of events) {
    if (event.sequence <= startSequence) continue

    // Schema version check — mismatch = abort
    if (event.payload_schema_version !== pin.schema_version) {
      const upcasted = attemptUpcast(event, pin.schema_version)
      if (!upcasted) {
        throw new ReplayVersionMismatchError(
          `Schema version mismatch at sequence ${event.sequence}: ` +
          `expected ${pin.schema_version}, got ${event.payload_schema_version}`
        )
      }
      state = applyEvent(state, upcasted)
    } else {
      state = applyEvent(state, event)
    }
  }

  return state
}

/**
 * Validate that all required version pins are present.
 * Missing pins cause a hard abort — never fall back silently.
 */
function validateVersionPin(pin: RuntimeVersionPin): void {
  if (!pin.schema_version) throw new ReplayVersionMismatchError('Missing schema_version in RuntimeVersionPin')
  if (!pin.projection_compiler_version) throw new ReplayVersionMismatchError('Missing projection_compiler_version')
  if (!pin.calibration_model_version) throw new ReplayVersionMismatchError('Missing calibration_model_version')
  if (Object.keys(pin.verifier_versions).length === 0) throw new ReplayVersionMismatchError('Empty verifier_versions map')
}

/**
 * Attempt to upcast an event from an older schema version.
 * Returns null if no upcast function is registered for this type/version pair.
 */
function attemptUpcast(event: EventEnvelope, targetVersion: string): EventEnvelope | null {
  const key = `${event.event_type}:${event.payload_schema_version}:${targetVersion}`
  const upcastFn = UPCAST_REGISTRY.get(key)
  if (!upcastFn) return null
  return upcastFn(event)
}

// ─── Upcast Registry ───────────────────────────────────────

type UpcastFn = (event: EventEnvelope) => EventEnvelope

const UPCAST_REGISTRY = new Map<string, UpcastFn>()

export function registerUpcast(
  eventType: string,
  fromVersion: string,
  toVersion: string,
  fn: UpcastFn
): void {
  UPCAST_REGISTRY.set(`${eventType}:${fromVersion}:${toVersion}`, fn)
}

// ─── Error Types ───────────────────────────────────────────

export class ReplayVersionMismatchError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ReplayVersionMismatchError'
  }
}

export class ReplayDivergenceError extends Error {
  constructor(
    public readonly sequence: SequenceNumber,
    public readonly expected_hash: string,
    public readonly actual_hash: string
  ) {
    super(`Replay divergence at sequence ${sequence}: expected ${expected_hash}, got ${actual_hash}`)
    this.name = 'ReplayDivergenceError'
  }
}
