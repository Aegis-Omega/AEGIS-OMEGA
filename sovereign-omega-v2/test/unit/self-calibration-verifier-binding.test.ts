import { describe, expect, it } from 'vitest'
import { hashValue } from '../../src/core/hashing.js'
import { CalibrationDomain } from '../../src/core/types.js'
import type { SHA256Hex } from '../../src/core/types.js'
import type { VerifierOutput } from '../../src/verifier/types.js'
import {
  SelfCalibrationError,
  createSelfCalibrationV2,
  createSelfOutcomeObservationFromVerifier,
  createSelfPredictionV2,
} from '../../src/metacognition/self-calibration.js'

const ACTION = '1'.repeat(64) as SHA256Hex
const CLAIM_A = 'self-action-claim-a'
const CLAIM_B = 'self-action-claim-b'

async function makeVerifierOutput(
  claim_id: string,
  passed: boolean,
): Promise<VerifierOutput> {
  const verifier_id = 'self-model-execution-verifier-v1'
  const raw_confidence = passed ? 0.99 : 0.01
  const artifact_hash = await hashValue({
    verifier_id,
    claim_id,
    passed,
    raw_confidence,
  })

  return {
    verifier_id,
    claim_id,
    passed,
    raw_confidence,
    evidence_refs: Object.freeze(['self-model-fixture']),
    latency_ms: 1,
    determinism_flag: true,
    verifier_version: '1.0.0',
    trust_class: CalibrationDomain.GROUND_TRUTH,
    artifact_hash,
  }
}

describe('verifier-bound self-calibration V2', () => {
  it('derives observed outcome from a verifier artifact and remains evidence-only', async () => {
    const prediction = await createSelfPredictionV2({
      action_digest: ACTION,
      verifier_claim_id: CLAIM_A,
      predicted_success_bps: 7500,
    })
    const verifier = await makeVerifierOutput(CLAIM_A, true)

    const observation = await createSelfOutcomeObservationFromVerifier(
      prediction,
      verifier,
    )
    const calibration = await createSelfCalibrationV2(prediction, observation)

    expect(observation.observed_success).toBe(true)
    expect(observation.observation_evidence_digest).toBe(verifier.artifact_hash)
    expect(observation.verifier_claim_id).toBe(CLAIM_A)
    expect(observation.authority).toBe('NONE')
    expect(observation.acceptable_for_effect_truth).toBe(false)
    expect(calibration.absolute_error_bps).toBe(2500)
    expect(calibration.authority).toBe('NONE')
    expect(calibration.acceptable_for_effect_truth).toBe(false)
  })

  it('rejects a verifier verdict changed without recomputing its artifact hash', async () => {
    const prediction = await createSelfPredictionV2({
      action_digest: ACTION,
      verifier_claim_id: CLAIM_A,
      predicted_success_bps: 7500,
    })
    const verifier = await makeVerifierOutput(CLAIM_A, true)
    const forged: VerifierOutput = { ...verifier, passed: false }

    await expect(
      createSelfOutcomeObservationFromVerifier(prediction, forged),
    ).rejects.toThrow(SelfCalibrationError)
  })

  it('rejects a valid verifier artifact produced for another claim', async () => {
    const prediction = await createSelfPredictionV2({
      action_digest: ACTION,
      verifier_claim_id: CLAIM_A,
      predicted_success_bps: 7500,
    })
    const verifierForOtherClaim = await makeVerifierOutput(CLAIM_B, true)

    await expect(
      createSelfOutcomeObservationFromVerifier(prediction, verifierForOtherClaim),
    ).rejects.toThrow(SelfCalibrationError)
  })
})
