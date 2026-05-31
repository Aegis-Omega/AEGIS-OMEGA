// ============================================================
// SOVEREIGN OMEGA — SHP Phase-Specific Factories
// EPISTEMIC TIER: T0 · Gate 15
//
// Each factory produces a valid, frozen SHPExecutionIdentity for
// one phase. The temporal constraints are enforced at construction:
//   READ/ASSESS  → no classification field
//   PROPAGATE/HARMONIZE → no constraintResult field
//   LOCK         → commitHash derived from frozen state
// commitHash is computed via FNV-1a of (holonId:sequence:stateKey)
// for determinism — no UUIDv7, no Date.now().
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import type { SHPExecutionIdentity, SHPConstraintResult, SHPClassification } from './types.js'

function fnv1a32(s: string): string {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619) >>> 0
  }
  /* c8 ignore next -- fnv1a32 output is always 8 hex chars (32-bit); padStart(64) always pads, never hits the no-op branch */
  return h.toString(16).padStart(64, '0')
}

function commitHash(holonId: string, seq: SequenceNumber, stateKey: string): SHA256Hex {
  return fnv1a32(`${holonId}:${seq}:${stateKey}`) as SHA256Hex
}

export function createReadIdentity(params: {
  readonly holonId: string
  readonly state: unknown
  readonly eventSlice: readonly unknown[]
  readonly sequence: SequenceNumber
  readonly parentCommitHash: SHA256Hex | null
}): Readonly<SHPExecutionIdentity> {
  const ch = commitHash(params.holonId, params.sequence, 'READ')
  return Object.freeze<SHPExecutionIdentity>({
    holonId: params.holonId,
    phase: 'READ',
    state: params.state,
    eventSlice: Object.freeze([...params.eventSlice]),
    commitHash: ch,
    parentCommitHash: params.parentCommitHash,
    sequence: params.sequence,
    isReplaySafe: true,
  })
}

export function createAssessIdentity(params: {
  readonly holonId: string
  readonly state: unknown
  readonly eventSlice: readonly unknown[]
  readonly constraintResult: SHPConstraintResult
  readonly sequence: SequenceNumber
  readonly parentCommitHash: SHA256Hex | null
}): Readonly<SHPExecutionIdentity> {
  const ch = commitHash(params.holonId, params.sequence, `ASSESS:${params.constraintResult.severity}`)
  return Object.freeze<SHPExecutionIdentity>({
    holonId: params.holonId,
    phase: 'ASSESS',
    state: params.state,
    eventSlice: Object.freeze([...params.eventSlice]),
    constraintResult: Object.freeze(params.constraintResult),
    commitHash: ch,
    parentCommitHash: params.parentCommitHash,
    sequence: params.sequence,
    isReplaySafe: true,
  })
}

export function createLockIdentity(params: {
  readonly holonId: string
  readonly frozenState: unknown
  readonly sequence: SequenceNumber
  readonly parentCommitHash: SHA256Hex | null
}): Readonly<SHPExecutionIdentity> {
  const ch = commitHash(params.holonId, params.sequence, 'LOCK')
  return Object.freeze<SHPExecutionIdentity>({
    holonId: params.holonId,
    phase: 'LOCK',
    state: params.frozenState,
    eventSlice: Object.freeze([]),
    commitHash: ch,
    parentCommitHash: params.parentCommitHash,
    sequence: params.sequence,
    isReplaySafe: true,
  })
}

export function createPropagateIdentity(params: {
  readonly holonId: string
  readonly state: unknown
  readonly commitHash: SHA256Hex
  readonly sequence: SequenceNumber
  readonly parentCommitHash: SHA256Hex | null
}): Readonly<SHPExecutionIdentity> {
  return Object.freeze<SHPExecutionIdentity>({
    holonId: params.holonId,
    phase: 'PROPAGATE',
    state: params.state,
    eventSlice: Object.freeze([]),
    commitHash: params.commitHash,
    parentCommitHash: params.parentCommitHash,
    sequence: params.sequence,
    isReplaySafe: true,
  })
}

export function createHarmonizeIdentity(params: {
  readonly holonId: string
  readonly state: unknown
  readonly classification: SHPClassification
  readonly commitHash: SHA256Hex
  readonly sequence: SequenceNumber
  readonly parentCommitHash: SHA256Hex | null
}): Readonly<SHPExecutionIdentity> {
  return Object.freeze<SHPExecutionIdentity>({
    holonId: params.holonId,
    phase: 'HARMONIZE',
    state: params.state,
    eventSlice: Object.freeze([]),
    classification: Object.freeze(params.classification),
    commitHash: params.commitHash,
    parentCommitHash: params.parentCommitHash,
    sequence: params.sequence,
    isReplaySafe: true,
  })
}
