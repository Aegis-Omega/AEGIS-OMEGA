// ============================================================
// SOVEREIGN OMEGA — QuanPhotonic CalibrationReceiptV1
// EPISTEMIC TIER: T1 target implementation; admission remains
// claim-ledger governed until an exact-head machine receipt exists.
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import { signBytes, verifyBytes } from '../consensus/crypto.js'

export const QUANPHOTONIC_CALIBRATION_SCHEMA_VERSION = 'QUANPHOTONIC_CALIBRATION_RECEIPT_V1' as const
export const QUANPHOTONIC_MEASUREMENT_SCHEMA_VERSION = 'QUANPHOTONIC_MEASUREMENT_BATCH_V1' as const

export interface QuanPhotonicCalibrationParametersV1 {
  readonly background_rate_hz: string
  readonly spectral_efficiency_model_digest: string
  readonly afterpulse_kernel_digest: string
  readonly dead_time_ps: string
  readonly jitter_ps_rms: string
  readonly gain: string
  readonly pileup_model_digest: string
}

export interface CalibrationReceiptPayloadV1 {
  readonly schema_version: typeof QUANPHOTONIC_CALIBRATION_SCHEMA_VERSION
  readonly calibration_epoch_id: string
  readonly detector_id: string
  readonly detector_configuration_digest: string
  readonly sequence: string
  readonly valid_from_sequence: string
  readonly valid_until_sequence: string
  readonly previous_receipt_digest: string | null
  readonly raw_calibration_digest: string
  readonly calibration_code_commit: string
  readonly reference_source_ids: readonly string[]
  readonly parameters: QuanPhotonicCalibrationParametersV1
  readonly calibration_status: 'PASS' | 'INVALID_CALIBRATION'
}

export interface SignedCalibrationReceiptV1 {
  readonly payload: CalibrationReceiptPayloadV1
  readonly payload_digest: SHA256Hex
  readonly signature_algorithm: 'Ed25519'
  readonly signer_key_id: string
  readonly signature: string
  /** Informational only. Trust is established by QuanPhotonicCalibrationGate. */
  readonly verification_status: 'UNVERIFIED'
}

export interface MeasurementBatchEnvelopeV1 {
  readonly schema_version: typeof QUANPHOTONIC_MEASUREMENT_SCHEMA_VERSION
  readonly measurement_batch_id: string
  readonly measurement_batch_digest: string
  readonly calibration_receipt_digest: string
  readonly calibration_epoch_id: string
  readonly detector_id: string
  readonly detector_configuration_digest: string
  readonly sequence: string
}

export type CalibrationRejectionReason =
  | 'MALFORMED_RECEIPT'
  | 'PAYLOAD_DIGEST_MISMATCH'
  | 'UNTRUSTED_SIGNER'
  | 'SIGNATURE_INVALID'
  | 'CALIBRATION_GATE_FAILED'
  | 'MALFORMED_BATCH'
  | 'RECEIPT_DIGEST_MISMATCH'
  | 'BATCH_DIGEST_MISMATCH'
  | 'DETECTOR_MISMATCH'
  | 'CONFIGURATION_MISMATCH'
  | 'EPOCH_MISMATCH'
  | 'NOT_YET_VALID'
  | 'CALIBRATION_EXPIRED'
  | 'BATCH_REPLAY'
  | 'BATCH_DIGEST_REPLAY'
  | 'SEQUENCE_ROLLBACK'
  | 'RECEIPT_CHAIN_MISMATCH'
  | 'RECEIPT_SEQUENCE_ROLLBACK'
  | 'CALIBRATION_EPOCH_REUSE'
  | 'PERSISTENCE_UNAVAILABLE'

export interface QuanPhotonicReplayAdmissionV1 {
  readonly measurement_batch_id: string
  readonly measurement_batch_digest: SHA256Hex
  readonly calibration_epoch_id: string
  readonly measurement_sequence: string
  readonly detector_id: string
  readonly calibration_receipt_digest: SHA256Hex
  readonly calibration_receipt_sequence: string
  readonly previous_calibration_receipt_digest: SHA256Hex | null
}

export interface QuanPhotonicReplayAuthority {
  admit(admission: QuanPhotonicReplayAdmissionV1): Promise<CalibrationRejectionReason | null>
}

export type CalibrationAdmissionResult = Readonly<
  | {
      status: 'PASS'
      reason: 'CALIBRATION_VERIFIED'
      calibration_receipt_digest: SHA256Hex
      measurement_batch_digest: SHA256Hex
    }
  | {
      status: 'INVALID_CALIBRATION'
      reason: CalibrationRejectionReason
      calibration_receipt_digest: SHA256Hex | null
    }
>

const SHA256_RE = /^[0-9a-f]{64}$/
const COMMIT_RE = /^[0-9a-f]{40}$/
const SEQUENCE_RE = /^(0|[1-9][0-9]*)$/
const NONNEGATIVE_DECIMAL_RE = /^(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$/

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
}

function isSha256(value: unknown): value is SHA256Hex {
  return typeof value === 'string' && SHA256_RE.test(value)
}

function hasExactKeys(value: Record<string, unknown>, expected: readonly string[]): boolean {
  return Object.keys(value).sort().join('|') === [...expected].sort().join('|')
}

function isCanonicalSequence(value: unknown): value is string {
  return typeof value === 'string' && SEQUENCE_RE.test(value)
}

function isCanonicalNonnegativeDecimal(value: unknown): value is string {
  return typeof value === 'string' && NONNEGATIVE_DECIMAL_RE.test(value)
}

function validateParameters(value: unknown): value is QuanPhotonicCalibrationParametersV1 {
  if (!isRecord(value)) return false
  const keys = [
    'background_rate_hz',
    'spectral_efficiency_model_digest',
    'afterpulse_kernel_digest',
    'dead_time_ps',
    'jitter_ps_rms',
    'gain',
    'pileup_model_digest',
  ] as const
  if (Object.keys(value).sort().join('|') !== [...keys].sort().join('|')) return false
  if (!isCanonicalNonnegativeDecimal(value.background_rate_hz)
      || !isCanonicalNonnegativeDecimal(value.dead_time_ps)
      || !isCanonicalNonnegativeDecimal(value.jitter_ps_rms)
      || !isCanonicalNonnegativeDecimal(value.gain)
      || value.gain === '0') return false
  return isSha256(value.spectral_efficiency_model_digest)
    && isSha256(value.afterpulse_kernel_digest)
    && isSha256(value.pileup_model_digest)
}

function validatePayload(value: unknown): value is CalibrationReceiptPayloadV1 {
  if (!isRecord(value)) return false
  if (!hasExactKeys(value, [
    'schema_version',
    'calibration_epoch_id',
    'detector_id',
    'detector_configuration_digest',
    'sequence',
    'valid_from_sequence',
    'valid_until_sequence',
    'previous_receipt_digest',
    'raw_calibration_digest',
    'calibration_code_commit',
    'reference_source_ids',
    'parameters',
    'calibration_status',
  ])) return false
  if (value.schema_version !== QUANPHOTONIC_CALIBRATION_SCHEMA_VERSION) return false
  if (!isNonEmptyString(value.calibration_epoch_id) || !isNonEmptyString(value.detector_id)) return false
  if (!isSha256(value.detector_configuration_digest) || !isSha256(value.raw_calibration_digest)) return false
  if (!isCanonicalSequence(value.sequence)
      || !isCanonicalSequence(value.valid_from_sequence)
      || !isCanonicalSequence(value.valid_until_sequence)) return false
  if (BigInt(value.valid_from_sequence) > BigInt(value.valid_until_sequence)) return false
  if (BigInt(value.sequence) > BigInt(value.valid_from_sequence)) return false
  if (value.previous_receipt_digest !== null && !isSha256(value.previous_receipt_digest)) return false
  if (typeof value.calibration_code_commit !== 'string' || !COMMIT_RE.test(value.calibration_code_commit)) return false
  if (!Array.isArray(value.reference_source_ids) || value.reference_source_ids.length === 0) return false
  if (!value.reference_source_ids.every(isNonEmptyString)) return false
  if (new Set(value.reference_source_ids).size !== value.reference_source_ids.length) return false
  if (!validateParameters(value.parameters)) return false
  return value.calibration_status === 'PASS' || value.calibration_status === 'INVALID_CALIBRATION'
}

function validateReceiptShape(value: unknown): value is SignedCalibrationReceiptV1 {
  if (!isRecord(value) || !validatePayload(value.payload)) return false
  if (!hasExactKeys(value, [
    'payload',
    'payload_digest',
    'signature_algorithm',
    'signer_key_id',
    'signature',
    'verification_status',
  ])) return false
  return isSha256(value.payload_digest)
    && value.signature_algorithm === 'Ed25519'
    && isNonEmptyString(value.signer_key_id)
    && typeof value.signature === 'string'
    && /^[0-9a-f]{128}$/.test(value.signature)
    && value.verification_status === 'UNVERIFIED'
}

function validateBatch(value: unknown): value is MeasurementBatchEnvelopeV1 {
  if (!isRecord(value) || value.schema_version !== QUANPHOTONIC_MEASUREMENT_SCHEMA_VERSION) return false
  if (!hasExactKeys(value, [
    'schema_version',
    'measurement_batch_id',
    'measurement_batch_digest',
    'calibration_receipt_digest',
    'calibration_epoch_id',
    'detector_id',
    'detector_configuration_digest',
    'sequence',
  ])) return false
  return isNonEmptyString(value.measurement_batch_id)
    && isSha256(value.measurement_batch_digest)
    && isSha256(value.calibration_receipt_digest)
    && isNonEmptyString(value.calibration_epoch_id)
    && isNonEmptyString(value.detector_id)
    && isSha256(value.detector_configuration_digest)
    && isCanonicalSequence(value.sequence)
}

function clonePayload(payload: CalibrationReceiptPayloadV1): CalibrationReceiptPayloadV1 {
  return {
    ...payload,
    reference_source_ids: [...payload.reference_source_ids],
    parameters: { ...payload.parameters },
  }
}

export async function signCalibrationReceipt(
  payload: CalibrationReceiptPayloadV1,
  signerKeyId: string,
  privateKey: Uint8Array,
): Promise<SignedCalibrationReceiptV1> {
  const cloned = clonePayload(payload)
  if (!isCanonicalSequence(cloned.sequence)
      || !isCanonicalSequence(cloned.valid_from_sequence)
      || !isCanonicalSequence(cloned.valid_until_sequence)) {
    throw new Error('QuanPhotonic sequences must use canonical decimal sequence encoding')
  }
  if (BigInt(cloned.valid_from_sequence) > BigInt(cloned.valid_until_sequence)) {
    throw new Error('QuanPhotonic validity interval is inverted')
  }
  if (!validatePayload(cloned)) throw new Error('Malformed QuanPhotonic calibration payload')
  if (!isNonEmptyString(signerKeyId)) throw new Error('signer_key_id is required')

  const frozenPayload = deepFreeze(cloned) as CalibrationReceiptPayloadV1
  const payloadDigest = await hashValue(frozenPayload)
  const signature = await signBytes(privateKey, new TextEncoder().encode(payloadDigest))
  return deepFreeze({
    payload: frozenPayload,
    payload_digest: payloadDigest,
    signature_algorithm: 'Ed25519' as const,
    signer_key_id: signerKeyId,
    signature,
    verification_status: 'UNVERIFIED' as const,
  }) as SignedCalibrationReceiptV1
}

export async function calibrationReceiptDigest(receipt: SignedCalibrationReceiptV1): Promise<SHA256Hex> {
  return hashValue({
    payload_digest: receipt.payload_digest,
    signature_algorithm: receipt.signature_algorithm,
    signer_key_id: receipt.signer_key_id,
    signature: receipt.signature,
  })
}

function reject(reason: CalibrationRejectionReason, digest: SHA256Hex | null = null): CalibrationAdmissionResult {
  return deepFreeze({ status: 'INVALID_CALIBRATION' as const, reason, calibration_receipt_digest: digest })
}

export class QuanPhotonicCalibrationGate {
  private readonly trustedKeys: Readonly<Record<string, string>>
  private readonly replayAuthority: QuanPhotonicReplayAuthority | null
  private readonly lastSequenceByEpoch: Record<string, bigint> = Object.create(null) as Record<string, bigint>
  private readonly admittedBatchIds: string[] = []
  private readonly admittedBatchDigests: string[] = []
  private readonly lastReceiptByDetector: Record<string, {
    readonly digest: SHA256Hex
    readonly sequence: bigint
    readonly epochId: string
  }> = Object.create(null) as Record<string, {
    readonly digest: SHA256Hex
    readonly sequence: bigint
    readonly epochId: string
  }>

  constructor(
    trustedKeys: Readonly<Record<string, string>>,
    replayAuthority: QuanPhotonicReplayAuthority | null = null,
  ) {
    this.trustedKeys = deepFreeze({ ...trustedKeys })
    this.replayAuthority = replayAuthority
  }

  async admit(
    receiptCandidate: unknown,
    batchCandidate: unknown,
    rawBatch: unknown,
  ): Promise<CalibrationAdmissionResult> {
    if (!validateReceiptShape(receiptCandidate)) return reject('MALFORMED_RECEIPT')
    const receipt = receiptCandidate
    const receiptDigest = await calibrationReceiptDigest(receipt)
    const recomputedPayloadDigest = await hashValue(receipt.payload)
    if (recomputedPayloadDigest !== receipt.payload_digest) return reject('PAYLOAD_DIGEST_MISMATCH', receiptDigest)

    const trustedPublicKey = this.trustedKeys[receipt.signer_key_id]
    if (trustedPublicKey === undefined) return reject('UNTRUSTED_SIGNER', receiptDigest)
    const signatureValid = await verifyBytes(
      trustedPublicKey,
      new TextEncoder().encode(receipt.payload_digest),
      receipt.signature,
    )
    if (!signatureValid) return reject('SIGNATURE_INVALID', receiptDigest)
    if (receipt.payload.calibration_status !== 'PASS') return reject('CALIBRATION_GATE_FAILED', receiptDigest)
    if (!validateBatch(batchCandidate)) return reject('MALFORMED_BATCH', receiptDigest)
    const batch = batchCandidate

    if (batch.calibration_receipt_digest !== receiptDigest) return reject('RECEIPT_DIGEST_MISMATCH', receiptDigest)
    const recomputedBatchDigest = await hashValue(rawBatch)
    if (batch.measurement_batch_digest !== recomputedBatchDigest) return reject('BATCH_DIGEST_MISMATCH', receiptDigest)
    if (batch.detector_id !== receipt.payload.detector_id) return reject('DETECTOR_MISMATCH', receiptDigest)
    if (batch.detector_configuration_digest !== receipt.payload.detector_configuration_digest) {
      return reject('CONFIGURATION_MISMATCH', receiptDigest)
    }
    if (batch.calibration_epoch_id !== receipt.payload.calibration_epoch_id) return reject('EPOCH_MISMATCH', receiptDigest)

    const sequence = BigInt(batch.sequence)
    if (sequence < BigInt(receipt.payload.valid_from_sequence)) return reject('NOT_YET_VALID', receiptDigest)
    if (sequence > BigInt(receipt.payload.valid_until_sequence)) return reject('CALIBRATION_EXPIRED', receiptDigest)

    if (this.replayAuthority !== null) {
      let persistenceRejection: CalibrationRejectionReason | null
      try {
        persistenceRejection = await this.replayAuthority.admit({
          measurement_batch_id: batch.measurement_batch_id,
          measurement_batch_digest: batch.measurement_batch_digest as SHA256Hex,
          calibration_epoch_id: batch.calibration_epoch_id,
          measurement_sequence: batch.sequence,
          detector_id: batch.detector_id,
          calibration_receipt_digest: receiptDigest,
          calibration_receipt_sequence: receipt.payload.sequence,
          previous_calibration_receipt_digest: receipt.payload.previous_receipt_digest as SHA256Hex | null,
        })
      } catch {
        return reject('PERSISTENCE_UNAVAILABLE', receiptDigest)
      }
      if (persistenceRejection !== null) return reject(persistenceRejection, receiptDigest)
      return deepFreeze({
        status: 'PASS' as const,
        reason: 'CALIBRATION_VERIFIED' as const,
        calibration_receipt_digest: receiptDigest,
        measurement_batch_digest: recomputedBatchDigest,
      })
    }

    if (this.admittedBatchIds.includes(batch.measurement_batch_id)) return reject('BATCH_REPLAY', receiptDigest)
    if (this.admittedBatchDigests.includes(batch.measurement_batch_digest)) return reject('BATCH_DIGEST_REPLAY', receiptDigest)

    const lastReceipt = this.lastReceiptByDetector[receipt.payload.detector_id]
    if (lastReceipt === undefined) {
      if (receipt.payload.previous_receipt_digest !== null) return reject('RECEIPT_CHAIN_MISMATCH', receiptDigest)
    } else if (lastReceipt.digest !== receiptDigest) {
      if (receipt.payload.previous_receipt_digest !== lastReceipt.digest) {
        return reject('RECEIPT_CHAIN_MISMATCH', receiptDigest)
      }
      const receiptSequence = BigInt(receipt.payload.sequence)
      if (receiptSequence <= lastReceipt.sequence) return reject('RECEIPT_SEQUENCE_ROLLBACK', receiptDigest)
      if (receipt.payload.calibration_epoch_id === lastReceipt.epochId) {
        return reject('CALIBRATION_EPOCH_REUSE', receiptDigest)
      }
    }
    const lastSequence = this.lastSequenceByEpoch[batch.calibration_epoch_id]
    if (lastSequence !== undefined && sequence <= lastSequence) return reject('SEQUENCE_ROLLBACK', receiptDigest)

    this.admittedBatchIds.push(batch.measurement_batch_id)
    this.admittedBatchDigests.push(batch.measurement_batch_digest)
    this.lastSequenceByEpoch[batch.calibration_epoch_id] = sequence
    this.lastReceiptByDetector[receipt.payload.detector_id] = deepFreeze({
      digest: receiptDigest,
      sequence: BigInt(receipt.payload.sequence),
      epochId: receipt.payload.calibration_epoch_id,
    })
    return deepFreeze({
      status: 'PASS' as const,
      reason: 'CALIBRATION_VERIFIED' as const,
      calibration_receipt_digest: receiptDigest,
      measurement_batch_digest: recomputedBatchDigest,
    })
  }
}
