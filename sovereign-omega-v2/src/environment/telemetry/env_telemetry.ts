// ============================================================
// Environment Telemetry Extensions — constitutional metrics
// EPISTEMIC TIER: T1 (empirically validated against host state)
// Admissible under TELEMETRY_SPEC.md admissibility rule.
// ============================================================

import type { EnvironmentState, EnvironmentBinding } from '../types'

export interface EnvironmentTelemetrySnapshot {
  readonly environment_entropy: number
  readonly capability_surface_area: number
  readonly mutation_velocity: number
  readonly replay_reconstruction_integrity: number
  readonly adaptation_pressure_index: number
  readonly constitutional_stability_score: number
  readonly environmental_drift_rate: number
  readonly replay_identity_integrity: number
}

// environment_entropy: normalized entropy across governed paths.
// Deterministic: derived from mutation count and binding count.
// No wall-clock time. Returns Q16.16 divided back to float for display only.
export function computeEnvironmentEntropy(
  state: EnvironmentState
): number {
  if (state.mutation_count === 0) return 0
  // Entropy proxy: log2(mutation_count) / log2(max_expected_mutations=1000)
  const raw = Math.log2(state.mutation_count + 1) / Math.log2(1001)
  return Math.min(1, raw)
}

// capability_surface_area: count of registered host capabilities.
export function computeCapabilitySurfaceArea(
  bindings: readonly EnvironmentBinding[]
): number {
  return bindings.length
}

// mutation_velocity: recent mutations per sequence window.
// windowSize is a sequence-span, not wall-clock duration.
export function computeMutationVelocity(
  mutationCount: number,
  sequenceSpan: number
): number {
  if (sequenceSpan <= 0) return 0
  return mutationCount / sequenceSpan
}

// replay_reconstruction_integrity: fraction of mutations that are replay-reconstructable.
export function computeReplayReconstructionIntegrity(
  reconstructableMutations: number,
  totalMutations: number
): number {
  if (totalMutations === 0) return 1  // vacuously 1.0 — no mutations = perfect integrity
  return reconstructableMutations / totalMutations
}

// adaptation_pressure_index: composite of surface area + mutation velocity + entropy.
// All inputs are normalized [0,1]. Returns [0,1].
export function computeAdaptationPressureIndex(
  entropy: number,
  surfaceAreaNormalized: number,  // surface_area / max_expected (e.g. 16)
  mutationVelocityNormalized: number
): number {
  const raw = (entropy + surfaceAreaNormalized + mutationVelocityNormalized) / 3
  return Math.min(1, Math.max(0, raw))
}

// constitutional_stability_score: inverse of adaptation pressure.
// 1.0 = maximum stability. Degrades as pressure increases.
export function computeConstitutionalStabilityScore(
  adaptationPressureIndex: number
): number {
  return Math.max(0, 1 - adaptationPressureIndex)
}

// environmental_drift_rate: rate at which environment hash changes per sequence unit.
// Returns 0 if no sequence span elapsed.
export function computeEnvironmentalDriftRate(
  uniqueEnvironmentHashes: number,
  sequenceSpan: number
): number {
  if (sequenceSpan <= 0) return 0
  return uniqueEnvironmentHashes / sequenceSpan
}

// replay_identity_integrity: whether the environment can reconstruct its prior states.
// Returns the fraction of replay frames that pass structural verification.
export function computeReplayIdentityIntegrity(
  validFrames: number,
  totalFrames: number
): number {
  if (totalFrames === 0) return 1
  return validFrames / totalFrames
}

export function buildEnvironmentTelemetry(params: {
  state: EnvironmentState
  bindings: readonly EnvironmentBinding[]
  mutationCount: number
  reconstructableMutations: number
  totalMutations: number
  sequenceSpan: number
  uniqueEnvironmentHashes: number
  validFrames: number
  totalFrames: number
}): EnvironmentTelemetrySnapshot {
  const entropy = computeEnvironmentEntropy(params.state)
  const surfaceArea = computeCapabilitySurfaceArea(params.bindings)
  const velocity = computeMutationVelocity(params.mutationCount, params.sequenceSpan)
  const replayIntegrity = computeReplayReconstructionIntegrity(
    params.reconstructableMutations,
    params.totalMutations
  )
  const surfaceNormalized = Math.min(1, surfaceArea / 16)
  const velocityNormalized = Math.min(1, velocity / 100)
  const pressure = computeAdaptationPressureIndex(entropy, surfaceNormalized, velocityNormalized)

  return Object.freeze({
    environment_entropy: entropy,
    capability_surface_area: surfaceArea,
    mutation_velocity: velocity,
    replay_reconstruction_integrity: replayIntegrity,
    adaptation_pressure_index: pressure,
    constitutional_stability_score: computeConstitutionalStabilityScore(pressure),
    environmental_drift_rate: computeEnvironmentalDriftRate(
      params.uniqueEnvironmentHashes,
      params.sequenceSpan
    ),
    replay_identity_integrity: computeReplayIdentityIntegrity(params.validFrames, params.totalFrames),
  })
}
