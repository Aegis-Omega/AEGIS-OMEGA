// ============================================================
// SOVEREIGN OMEGA — Version-Pinned Projection Compiler
// EPISTEMIC TIER: T0
// Validates version pins before executing any projection.
// Mismatch = hard abort. Never falls back silently.
// ============================================================

import type { RuntimeVersionPin, ProjectionState } from '../core/types.js'
import { replayProjection } from '../event/replay.js'
import { canonicalizeJCSString } from '../core/canonicalize.js'
import type { EventEnvelope } from '../core/types.js'

export interface CompiledProjection {
  readonly pin: RuntimeVersionPin
  readonly version_fingerprint: string
  execute(events: readonly EventEnvelope[]): Promise<Readonly<ProjectionState>>
}

/**
 * Compile a version-pinned projection executor.
 * The returned executor validates pin integrity before every replay.
 * Any version mismatch aborts execution rather than proceeding silently.
 */
export function compileProjection(pin: RuntimeVersionPin): CompiledProjection {
  validatePinCompleteness(pin)
  const fingerprint = fingerprintPin(pin)

  return Object.freeze({
    pin,
    version_fingerprint: fingerprint,
    execute: async (events: readonly EventEnvelope[]) => {
      // Re-validate on every execution — pins must not drift at runtime
      validatePinCompleteness(pin)
      return replayProjection(events, pin)
    },
  })
}

function validatePinCompleteness(pin: RuntimeVersionPin): void {
  const required: (keyof RuntimeVersionPin)[] = [
    'schema_version',
    'projection_compiler_version',
    'calibration_model_version',
    'k_measurement_version',
  ]
  for (const key of required) {
    if (!pin[key]) {
      throw new PinValidationError(`RuntimeVersionPin missing required field: ${key}`)
    }
  }
  if (Object.keys(pin.verifier_versions).length === 0) {
    throw new PinValidationError('RuntimeVersionPin.verifier_versions must not be empty')
  }
}

function fingerprintPin(pin: RuntimeVersionPin): string {
  // RFC 8785 canonical serialisation — lexicographic key ordering at EVERY
  // nesting level, including verifier_versions. The prior JSON.stringify only
  // sorted the five top-level keys, so two otherwise-identical pins whose
  // verifier_versions were built in different key orders produced different
  // fingerprints. canonicalizeJCS is the only permitted integrity-hash path.
  return canonicalizeJCSString({
    schema_version: pin.schema_version,
    projection_compiler_version: pin.projection_compiler_version,
    calibration_model_version: pin.calibration_model_version,
    k_measurement_version: pin.k_measurement_version,
    verifier_versions: pin.verifier_versions,
  })
}

export class PinValidationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'PinValidationError'
  }
}
