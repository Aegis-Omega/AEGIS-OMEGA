// ============================================================
// SOVEREIGN OMEGA — Self-Calibration V2 -> VCG Adapter
// EPISTEMIC TIER: T2 input adapter into existing E2 calibration
//
// This adapter does not create authority and does not reinterpret
// self-calibration evidence as effect truth. Registry metadata, not
// caller-supplied verifier metadata, determines calibration eligibility.
// ============================================================

import type { VCGTracker } from '../calibration/vcg.js'
import { verifierRegistry } from '../verifier/registry.js'
import type { VerifierOutput } from '../verifier/types.js'
import {
  calibrationV2ToMetacognitiveObservation,
  type SelfCalibrationRecordV2,
} from './self-calibration.js'

export type SelfCalibrationVCGAdmissionStatus = 'ADMITTED' | 'EXCLUDED'

export class SelfCalibrationVCGAdmissionError extends Error {
  override readonly name = 'SelfCalibrationVCGAdmissionError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

function assertEventTimestamp(timestamp_ms: number): void {
  if (!Number.isSafeInteger(timestamp_ms) || timestamp_ms < 0) {
    throw new SelfCalibrationVCGAdmissionError(
      `timestamp_ms must be a non-negative safe integer from the event substrate, got ${timestamp_ms}`,
    )
  }
}

/**
 * Admit a validated V2 self-calibration sample into the existing VCG tracker.
 *
 * Fail-closed boundaries:
 * - timestamp_ms must be an explicit non-negative safe integer from the event substrate;
 * - the V2 calibration must pass its cryptographic/replay integrity checks;
 * - verifier_id must resolve in the canonical verifier registry;
 * - calibration weight comes from the registry definition, never from the
 *   historical VerifierOutput metadata used to construct the V2 artifact;
 * - advisory-excluded verifiers remain excluded from aggregate calibration.
 *
 * The claimed confidence is the system's own pre-action prediction, not the
 * verifier's raw confidence about its verdict.
 */
export async function admitSelfCalibrationV2ToVCG(
  tracker: VCGTracker,
  calibration: SelfCalibrationRecordV2,
  timestamp_ms: number,
): Promise<SelfCalibrationVCGAdmissionStatus> {
  assertEventTimestamp(timestamp_ms)

  // Reuse the already-tested V2 integrity boundary rather than duplicating
  // prediction/verifier/calibration hash projections in this adapter.
  await calibrationV2ToMetacognitiveObservation(calibration)

  const registered = verifierRegistry.get(calibration.verifier_id)
  if (!registered) {
    throw new SelfCalibrationVCGAdmissionError(
      `unregistered verifier cannot enter VCG: ${calibration.verifier_id}`,
    )
  }

  const trust_class = registered.definition.trust_class
  if (verifierRegistry.getCalibrationWeight(trust_class) === 0) {
    return 'EXCLUDED'
  }

  const projectedOutput: VerifierOutput = Object.freeze({
    verifier_id: calibration.verifier_id,
    claim_id: calibration.verifier_claim_id,
    passed: calibration.observed_success,
    raw_confidence: calibration.verifier_raw_confidence,
    evidence_refs: Object.freeze([calibration.observation_evidence_digest]),
    latency_ms: 0,
    determinism_flag: registered.definition.is_deterministic,
    verifier_version: registered.definition.version,
    trust_class,
    artifact_hash: calibration.observation_evidence_digest,
  })

  tracker.addResult(
    projectedOutput,
    calibration.predicted_success_bps / 10_000,
    timestamp_ms,
  )

  return 'ADMITTED'
}
