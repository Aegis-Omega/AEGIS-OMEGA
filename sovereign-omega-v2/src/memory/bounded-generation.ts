// EPISTEMIC TIER: T2 (engineering hypothesis)
// Constitutional mapping:
//   primitive_mapping: SEQUENCE — generation counters advance through sequence space
//   replay_mapping:    LOCK     — generation advance is the LOCK boundary for slot reuse
//   topology_mapping:  DFA      — generation state governs valid/invalid handle transitions
//
// Translation of the Coq/Iris bounded generation CMRA (𝐙_<2^32 exclusive lattice).
// When generation reaches GENERATION_BOUND - 1 = 2^32 - 1, any further increment
// transitions to the permanently-invalid ⊥ state (null). This mirrors the algebraic
// ⊥-contamination rule: once a generation saturates, the associated handle fragment
// is unresolvable within the global invariant — matching the prose spec of absolute
// handle invalidation after integer overflow.
//
// Saturation semantics:
//   g < 2^32 - 1  → increment(g) = g + 1   (valid advance)
//   g = 2^32 - 1  → increment(g) = null (⊥) (permanently contaminated)
//   null           → increment(null) = null  (⊥ propagates)

import { deepFreeze } from '../core/immutable.js'

export const BOUNDED_GENERATION_SCHEMA_VERSION = '1.0.0' as const
export const GENERATION_BOUND = 2 ** 32  // 4_294_967_296

// Branded type — raw number is not a valid generation; only values produced by
// makeGeneration() or incrementGeneration() carry this brand.
export type BoundedGeneration = number & { readonly __brand: 'BoundedGeneration' }

export class BoundedGenerationError extends Error {
  override readonly name = 'BoundedGenerationError'
}

// Construct a valid initial generation from a raw nat.
// Throws BoundedGenerationError if value is not a non-negative integer < GENERATION_BOUND.
export function makeGeneration(value: number): BoundedGeneration {
  if (!Number.isInteger(value) || value < 0 || value >= GENERATION_BOUND) {
    throw new BoundedGenerationError(
      `Generation ${value} out of range [0, ${GENERATION_BOUND})`,
    )
  }
  return value as BoundedGeneration
}

// Advance a generation by one.
// Returns null (⊥) if the result would reach or exceed GENERATION_BOUND.
// ⊥ is permanent: no further increments are possible on a saturated generation.
export function incrementGeneration(g: BoundedGeneration): BoundedGeneration | null {
  const next = g + 1
  if (next >= GENERATION_BOUND) return null
  return next as BoundedGeneration
}

// Compose two generation values: returns the maximum (monotone advancement).
// If either operand is null (⊥), the result is null (⊥-contamination).
// Models the algebraic ⊕ operation on 𝐙_{2^32} ⊎ {⊥}.
export function composeGenerations(
  a: BoundedGeneration | null,
  b: BoundedGeneration | null,
): BoundedGeneration | null {
  if (a === null || b === null) return null
  return Math.max(a, b) as BoundedGeneration
}

// Verify that a candidate generation is strictly greater than a reference.
// Stale handle detection: candidate ≤ reference → handle is stale → reject.
export function isGenerationFresh(
  candidate: BoundedGeneration,
  reference: BoundedGeneration,
): boolean {
  return candidate > reference
}

export interface GenerationRecord {
  readonly value: number
  readonly is_saturated: boolean   // true when value = GENERATION_BOUND − 1: next increment → ⊥
  readonly schema_version: typeof BOUNDED_GENERATION_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

// Produce a frozen, replay-certifiable record from a BoundedGeneration.
export function describeGeneration(g: BoundedGeneration): GenerationRecord {
  return deepFreeze({
    value: g,
    is_saturated: g === GENERATION_BOUND - 1,
    schema_version: BOUNDED_GENERATION_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}
