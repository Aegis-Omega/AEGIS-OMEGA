// ============================================================
// SOVEREIGN OMEGA — Self-Calibration V2 -> VCG Adapter
// EPISTEMIC TIER: T2 input adapter into existing E2 calibration
//
// This adapter does not create authority and does not reinterpret
// self-calibration evidence as effect truth. Registry metadata, not
// caller-supplied verifier metadata, determines calibration eligibility.
// ============================================================

import type { VCGTracker } from '../calibration/vcg.js'
import { hashValue } from '../core/hashing.js'
import type { CalibrationDomain, SHA256Hex, VerifierClass } from '../core/types.js'
import { verifierRegistry } from '../verifier/registry.js'
import type { VerifierOutput } from '../verifier/types.js'
import {
  calibrationV2ToMetacognitiveObservation,
  type SelfCalibrationRecordV2,
} from './self-calibration.js'

export const SELF_CALIBRATION_VCG_ADMISSION_SCHEMA_VERSION = '1.0.0' as const

export type SelfCalibrationVCGAdmissionStatus = 'ADMITTED' | 'EXCLUDED'

export interface SelfCalibrationVCGVerifierSnapshotV1 {
  readonly verifier_id: string
  readonly verifier_class: VerifierClass
  readonly trust_class: CalibrationDomain
  readonly version: string
  readonly max_latency_ms: number
  readonly is_deterministic: boolean
  readonly definition_digest: SHA256Hex
}

export interface SelfCalibrationVCGAdmissionReceiptV1 {
  readonly receipt_kind: 'SELF_CALIBRATION_VCG_ADMISSION_RECEIPT_V1'
  readonly schema_version: typeof SELF_CALIBRATION_VCG_ADMISSION_SCHEMA_VERSION
  readonly calibration_hash: SHA256Hex
  readonly verifier_snapshot: SelfCalibrationVCGVerifierSnapshotV1
  readonly predicted_success_bps: number
  readonly timestamp_ms: number
  readonly status: SelfCalibrationVCGAdmissionStatus
  readonly receipt_hash: SHA256Hex
  readonly authority: 'NONE'
  readonly acceptable_for_effect_truth: false
}

export interface SelfCalibrationVCGLiveAdmissionResultV1 {
  readonly status: SelfCalibrationVCGAdmissionStatus
  readonly receipt: SelfCalibrationVCGAdmissionReceiptV1
}

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

function verifierSnapshotBody(
  snapshot: Omit<SelfCalibrationVCGVerifierSnapshotV1, 'definition_digest'>,
) {
  return {
    verifier_id: snapshot.verifier_id,
    verifier_class: snapshot.verifier_class,
    trust_class: snapshot.trust_class,
    version: snapshot.version,
    max_latency_ms: snapshot.max_latency_ms,
    is_deterministic: snapshot.is_deterministic,
  }
}

function admissionReceiptBody(
  receipt: Omit<SelfCalibrationVCGAdmissionReceiptV1, 'receipt_hash'>,
) {
  return {
    receipt_kind: receipt.receipt_kind,
    schema_version: receipt.schema_version,
    calibration_hash: receipt.calibration_hash,
    verifier_snapshot: receipt.verifier_snapshot,
    predicted_success_bps: receipt.predicted_success_bps,
    timestamp_ms: receipt.timestamp_ms,
    status: receipt.status,
    authority: receipt.authority,
    acceptable_for_effect_truth: receipt.acceptable_for_effect_truth,
  }
}

function projectedVerifierOutput(
  calibration: SelfCalibrationRecordV2,
  snapshot: SelfCalibrationVCGVerifierSnapshotV1,
): VerifierOutput {
  return Object.freeze({
    verifier_id: calibration.verifier_id,
    claim_id: calibration.verifier_claim_id,
    passed: calibration.observed_success,
    raw_confidence: calibration.verifier_raw_confidence,
    evidence_refs: Object.freeze([calibration.observation_evidence_digest]),
    latency_ms: 0,
    determinism_flag: snapshot.is_deterministic,
    verifier_version: snapshot.version,
    trust_class: snapshot.trust_class,
    artifact_hash: calibration.observation_evidence_digest,
  })
}

/**
 * Create a content-addressed snapshot of the registry state that determined
 * whether this calibration was eligible for aggregate VCG accounting.
 *
 * The receipt remains evidence-only. Its purpose is deterministic historical
 * replay when the live registry later changes; it does not prove that the
 * registry snapshot was externally truthful or grant authority.
 */
export async function createSelfCalibrationVCGAdmissionReceipt(
  calibration: SelfCalibrationRecordV2,
  timestamp_ms: number,
): Promise<SelfCalibrationVCGAdmissionReceiptV1> {
  assertEventTimestamp(timestamp_ms)
  await calibrationV2ToMetacognitiveObservation(calibration)

  const registered = verifierRegistry.get(calibration.verifier_id)
  if (!registered) {
    throw new SelfCalibrationVCGAdmissionError(
      `unregistered verifier cannot enter VCG: ${calibration.verifier_id}`,
    )
  }

  const snapshotWithoutDigest = {
    verifier_id: registered.definition.verifier_id,
    verifier_class: registered.definition.verifier_class,
    trust_class: registered.definition.trust_class,
    version: registered.definition.version,
    max_latency_ms: registered.definition.max_latency_ms,
    is_deterministic: registered.definition.is_deterministic,
  }
  const definition_digest = await hashValue(
    verifierSnapshotBody(snapshotWithoutDigest),
  )
  const verifier_snapshot = Object.freeze<SelfCalibrationVCGVerifierSnapshotV1>({
    ...snapshotWithoutDigest,
    definition_digest,
  })
  const status: SelfCalibrationVCGAdmissionStatus =
    verifierRegistry.getCalibrationWeight(verifier_snapshot.trust_class) === 0
      ? 'EXCLUDED'
      : 'ADMITTED'

  const body = {
    receipt_kind: 'SELF_CALIBRATION_VCG_ADMISSION_RECEIPT_V1' as const,
    schema_version: SELF_CALIBRATION_VCG_ADMISSION_SCHEMA_VERSION,
    calibration_hash: calibration.calibration_hash,
    verifier_snapshot,
    predicted_success_bps: calibration.predicted_success_bps,
    timestamp_ms,
    status,
    authority: 'NONE' as const,
    acceptable_for_effect_truth: false as const,
  }
  const receipt_hash = await hashValue(admissionReceiptBody(body))

  return Object.freeze<SelfCalibrationVCGAdmissionReceiptV1>({
    ...body,
    receipt_hash,
  })
}

/**
 * Replay aggregate calibration from the registry snapshot captured in the
 * admission receipt. The live registry verifier map is intentionally not
 * consulted here.
 */
export async function applySelfCalibrationVCGAdmissionReceipt(
  tracker: VCGTracker,
  calibration: SelfCalibrationRecordV2,
  receipt: SelfCalibrationVCGAdmissionReceiptV1,
): Promise<SelfCalibrationVCGAdmissionStatus> {
  await calibrationV2ToMetacognitiveObservation(calibration)
  assertEventTimestamp(receipt.timestamp_ms)

  if (
    receipt.receipt_kind !== 'SELF_CALIBRATION_VCG_ADMISSION_RECEIPT_V1' ||
    receipt.schema_version !== SELF_CALIBRATION_VCG_ADMISSION_SCHEMA_VERSION ||
    receipt.authority !== 'NONE' ||
    receipt.acceptable_for_effect_truth !== false
  ) {
    throw new SelfCalibrationVCGAdmissionError('VCG admission receipt semantics are invalid')
  }
  if (receipt.calibration_hash !== calibration.calibration_hash) {
    throw new SelfCalibrationVCGAdmissionError(
      'VCG admission receipt calibration_hash does not match calibration',
    )
  }
  if (receipt.predicted_success_bps !== calibration.predicted_success_bps) {
    throw new SelfCalibrationVCGAdmissionError(
      'VCG admission receipt prediction confidence does not match calibration',
    )
  }
  if (receipt.verifier_snapshot.verifier_id !== calibration.verifier_id) {
    throw new SelfCalibrationVCGAdmissionError(
      'VCG admission receipt verifier snapshot does not match calibration',
    )
  }

  const expectedDefinitionDigest = await hashValue(
    verifierSnapshotBody(receipt.verifier_snapshot),
  )
  if (expectedDefinitionDigest !== receipt.verifier_snapshot.definition_digest) {
    throw new SelfCalibrationVCGAdmissionError(
      'VCG admission verifier snapshot does not match definition_digest',
    )
  }

  const expectedStatus: SelfCalibrationVCGAdmissionStatus =
    verifierRegistry.getCalibrationWeight(receipt.verifier_snapshot.trust_class) === 0
      ? 'EXCLUDED'
      : 'ADMITTED'
  if (receipt.status !== expectedStatus) {
    throw new SelfCalibrationVCGAdmissionError(
      'VCG admission receipt status does not match verifier snapshot eligibility',
    )
  }

  const expectedReceiptHash = await hashValue(
    admissionReceiptBody(receipt),
  )
  if (expectedReceiptHash !== receipt.receipt_hash) {
    throw new SelfCalibrationVCGAdmissionError(
      'VCG admission receipt body does not match receipt_hash',
    )
  }

  if (receipt.status === 'EXCLUDED') {
    return 'EXCLUDED'
  }

  tracker.addResult(
    projectedVerifierOutput(calibration, receipt.verifier_snapshot),
    receipt.predicted_success_bps / 10_000,
    receipt.timestamp_ms,
  )
  return 'ADMITTED'
}

/**
 * Canonical live admission path. The exact receipt used to mutate VCG is
 * returned to the caller so it can be persisted and replayed later.
 */
export async function admitSelfCalibrationV2ToVCGWithReceipt(
  tracker: VCGTracker,
  calibration: SelfCalibrationRecordV2,
  timestamp_ms: number,
): Promise<SelfCalibrationVCGLiveAdmissionResultV1> {
  const receipt = await createSelfCalibrationVCGAdmissionReceipt(
    calibration,
    timestamp_ms,
  )
  const status = await applySelfCalibrationVCGAdmissionReceipt(
    tracker,
    calibration,
    receipt,
  )
  return Object.freeze({ status, receipt })
}

/**
 * Backward-compatible status-only wrapper around the canonical receipt path.
 * No VCG sample can enter through this API without a receipt first existing.
 */
export async function admitSelfCalibrationV2ToVCG(
  tracker: VCGTracker,
  calibration: SelfCalibrationRecordV2,
  timestamp_ms: number,
): Promise<SelfCalibrationVCGAdmissionStatus> {
  const result = await admitSelfCalibrationV2ToVCGWithReceipt(
    tracker,
    calibration,
    timestamp_ms,
  )
  return result.status
}
