// ============================================================
// SOVEREIGN OMEGA - Authenticated Outcome Evidence Replay
// EPISTEMIC TIER: T2 - deterministic, tested governance adapter
//
// Replays evidence evaluation against an operator-authenticated verifier
// policy, persists the resulting content-addressed artifact, and proves that
// the artifact can be read back before returning the updated loop. Replay
// never re-executes an action, grants authority, mutates state, or updates
// competence.
// ============================================================

import { canonicalizeJCS } from '../core/canonicalize.js'
import { assertIJsonValue } from '../core/i-json.js'
import { deepFreeze } from '../core/immutable.js'
import type { SequenceNumber, SHA256Hex } from '../core/types.js'
import { MetacognitiveLoop } from './loop.js'
import type { MetacognitiveEntry } from './loop.js'
import type { ReadableOutcomeEvidenceArtifactStore } from './outcome-evidence-artifact-store.js'
import {
  OutcomeComparisonError,
  assessAdaptationOutcome,
  normalizeAdaptationOutcomeInputV1,
  recordOutcomeAssessment,
  verifyOutcomeVerifierTrustPolicyV1,
} from './outcome-comparator.js'
import type {
  AdaptationOutcomeAssessment,
  AdaptationOutcomeInput,
  OutcomeEvidenceArtifactV1,
  OutcomeEvidencePersistenceReceiptV1,
  OutcomeVerifierTrustPolicyV1,
} from './outcome-comparator.js'

export interface TrustedOutcomeReplayContextV1 {
  readonly expected_governed_policy_root: SHA256Hex
  readonly expected_operator_public_key: string
}

export interface OutcomeReplayEvidenceV1 {
  readonly input: AdaptationOutcomeInput
  readonly trust_policy: OutcomeVerifierTrustPolicyV1
}

export interface OutcomeEvidenceReplayResultV1 {
  readonly assessment: AdaptationOutcomeAssessment
  readonly artifact: OutcomeEvidenceArtifactV1
  readonly persistence: OutcomeEvidencePersistenceReceiptV1
  readonly loop: MetacognitiveLoop
  readonly entry: MetacognitiveEntry
}

export async function replayAuthenticatedOutcomeEvidenceV1(
  loop: MetacognitiveLoop,
  artifactStore: ReadableOutcomeEvidenceArtifactStore,
  allocatedSequence: SequenceNumber,
  trustedContext: TrustedOutcomeReplayContextV1,
  evidence: OutcomeReplayEvidenceV1,
): Promise<OutcomeEvidenceReplayResultV1> {
  if (artifactStore === null || typeof artifactStore !== 'object' ||
      typeof artifactStore.persist !== 'function' || typeof artifactStore.read !== 'function') {
    throw new OutcomeComparisonError('readable outcome evidence artifact store is unavailable')
  }
  if (typeof allocatedSequence !== 'bigint' || allocatedSequence < 0n) {
    throw new OutcomeComparisonError('allocated outcome replay sequence must be a non-negative bigint')
  }
  if (loop.lastSequence !== null && allocatedSequence <= loop.lastSequence) {
    throw new OutcomeComparisonError('allocated outcome replay sequence must advance the loop')
  }

  const context = snapshotIJson(trustedContext, 'trusted outcome replay context')
  const evidenceSnapshot = snapshotIJson(evidence, 'outcome replay evidence')
  if (loop.lastHash !== evidenceSnapshot.input.baseline.snapshot.metacognition_root) {
    throw new OutcomeComparisonError('metacognitive loop head does not match evidence baseline')
  }
  if (evidenceSnapshot.input.baseline.snapshot.policy_root !==
      context.expected_governed_policy_root) {
    throw new OutcomeComparisonError(
      'expected governed policy root does not match the evidence baseline',
    )
  }

  const trustAnchor = await verifyOutcomeVerifierTrustPolicyV1(
    evidenceSnapshot.trust_policy,
    context.expected_governed_policy_root,
    context.expected_operator_public_key,
  )
  if (trustAnchor.verifier_trust_root !==
      evidenceSnapshot.input.baseline.snapshot.verifier_trust_root) {
    throw new OutcomeComparisonError(
      'authenticated verifier trust policy is not bound to the evidence baseline',
    )
  }

  const normalizedInput = normalizeAdaptationOutcomeInputV1(evidenceSnapshot.input)
  if (!equalBytes(canonicalizeJCS(evidenceSnapshot.input), canonicalizeJCS(normalizedInput))) {
    throw new OutcomeComparisonError('outcome replay evidence input is not in canonical schema form')
  }
  const preflight = await assessAdaptationOutcome(normalizedInput, trustAnchor)
  if (!preflight.evidence_certificate_authenticated) {
    throw new OutcomeComparisonError('outcome evidence certificate authentication failed')
  }

  const result = await recordOutcomeAssessment(
    loop,
    normalizedInput,
    trustAnchor,
    artifactStore,
    allocatedSequence,
  )
  if (result.assessment.assessment_digest !== preflight.assessment_digest) {
    throw new OutcomeComparisonError('outcome assessment changed across the append boundary')
  }
  const restored = await artifactStore.read(result.artifact.artifact_root)
  if (restored === null) {
    throw new OutcomeComparisonError('persisted outcome evidence artifact cannot be resolved')
  }
  const restoredSnapshot = snapshotIJson(restored, 'persisted outcome evidence artifact')
  if (!equalBytes(canonicalizeJCS(restoredSnapshot), canonicalizeJCS(result.artifact))) {
    throw new OutcomeComparisonError('persisted outcome evidence artifact read-back mismatch')
  }
  return result
}

function snapshotIJson<T>(value: T, label: string): Readonly<T> {
  try {
    assertIJsonValue(value, label)
    const snapshot = structuredClone(value) as T
    assertIJsonValue(snapshot, label)
    return deepFreeze(snapshot)
  } catch (error) {
    throw new OutcomeComparisonError(
      `${label} is not a closed I-JSON value: ${error instanceof Error ? error.message : String(error)}`,
    )
  }
}

function equalBytes(left: Uint8Array, right: Uint8Array): boolean {
  if (left.byteLength !== right.byteLength) return false
  for (let index = 0; index < left.byteLength; index += 1) {
    if (left[index] !== right[index]) return false
  }
  return true
}
