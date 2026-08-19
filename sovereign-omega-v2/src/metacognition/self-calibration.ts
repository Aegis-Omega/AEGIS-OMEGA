// ============================================================
// SOVEREIGN OMEGA — Evidence-Bound Self-Model Calibration
// EPISTEMIC TIER: T2 · evidence only
//
// Prediction, observation, calibration, and ledger artifacts from
// this module never grant authority and are never effect-truth evidence.
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { MetacognitiveObservation } from './loop.js'

export const SELF_CALIBRATION_SCHEMA_VERSION = '1.0.0' as const
export const SELF_CALIBRATION_GENESIS_HASH = '0'.repeat(64) as SHA256Hex

const SHA256_PATTERN = /^[0-9a-f]{64}$/

export interface SelfPredictionInput {
  readonly action_digest: SHA256Hex
  readonly predicted_success_bps: number
}

export interface SelfPredictionRecordV1 {
  readonly receipt_kind: 'SELF_PREDICTION_RECORD_V1'
  readonly schema_version: typeof SELF_CALIBRATION_SCHEMA_VERSION
  readonly action_digest: SHA256Hex
  readonly predicted_success_bps: number
  readonly prediction_hash: SHA256Hex
  readonly authority: 'NONE'
  readonly acceptable_for_effect_truth: false
}

export interface SelfOutcomeObservationInput {
  readonly prediction_hash: SHA256Hex
  readonly action_digest: SHA256Hex
  readonly observation_evidence_digest: SHA256Hex
  readonly observed_success: boolean
}

export interface SelfOutcomeObservationV1 {
  readonly receipt_kind: 'SELF_OUTCOME_OBSERVATION_V1'
  readonly schema_version: typeof SELF_CALIBRATION_SCHEMA_VERSION
  readonly prediction_hash: SHA256Hex
  readonly action_digest: SHA256Hex
  readonly observation_evidence_digest: SHA256Hex
  readonly observed_success: boolean
  readonly authority: 'NONE'
  readonly acceptable_for_effect_truth: false
}

export interface SelfCalibrationRecordV1 {
  readonly receipt_kind: 'SELF_CALIBRATION_RECORD_V1'
  readonly schema_version: typeof SELF_CALIBRATION_SCHEMA_VERSION
  readonly prediction_hash: SHA256Hex
  readonly action_digest: SHA256Hex
  readonly observation_evidence_digest: SHA256Hex
  readonly predicted_success_bps: number
  readonly observed_success: boolean
  readonly absolute_error_bps: number
  readonly calibration_hash: SHA256Hex
  readonly authority: 'NONE'
  readonly acceptable_for_effect_truth: false
}

export interface SelfCalibrationLedgerEntry {
  readonly calibration: SelfCalibrationRecordV1
  readonly previous_entry_hash: SHA256Hex
  readonly sequence: SequenceNumber
  readonly entry_hash: SHA256Hex
  readonly schema_version: typeof SELF_CALIBRATION_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface SelfCalibrationLedgerCertificate {
  readonly is_valid: boolean
  readonly entry_count: number
  readonly terminal_hash: SHA256Hex | null
  readonly certificate_hash: SHA256Hex
  readonly authority: 'NONE'
  readonly acceptable_for_effect_truth: false
  readonly is_replay_reconstructable: true
}

export class SelfCalibrationError extends Error {
  override readonly name = 'SelfCalibrationError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

function assertBasisPoints(value: number): void {
  if (!Number.isInteger(value) || value < 0 || value > 10_000) {
    throw new SelfCalibrationError(
      `predicted_success_bps must be an integer in [0, 10000], got ${value}`,
    )
  }
}

function assertSha256Hex(field: string, value: string): void {
  if (typeof value !== 'string' || !SHA256_PATTERN.test(value)) {
    throw new SelfCalibrationError(`${field} must be lowercase SHA-256 hex`)
  }
}

function assertNonNegativeSequence(sequence: SequenceNumber): void {
  if (sequence < 0n) {
    throw new SelfCalibrationError(`calibration sequence must be >= 0, got ${sequence}`)
  }
}

function predictionBody(input: SelfPredictionInput) {
  return {
    receipt_kind: 'SELF_PREDICTION_RECORD_V1' as const,
    schema_version: SELF_CALIBRATION_SCHEMA_VERSION,
    action_digest: input.action_digest,
    predicted_success_bps: input.predicted_success_bps,
    authority: 'NONE' as const,
    acceptable_for_effect_truth: false as const,
  }
}

function calibrationBody(calibration: Omit<SelfCalibrationRecordV1, 'calibration_hash'>) {
  return {
    receipt_kind: calibration.receipt_kind,
    schema_version: calibration.schema_version,
    prediction_hash: calibration.prediction_hash,
    action_digest: calibration.action_digest,
    observation_evidence_digest: calibration.observation_evidence_digest,
    predicted_success_bps: calibration.predicted_success_bps,
    observed_success: calibration.observed_success,
    absolute_error_bps: calibration.absolute_error_bps,
    authority: calibration.authority,
    acceptable_for_effect_truth: calibration.acceptable_for_effect_truth,
  }
}

export async function createSelfPrediction(
  input: SelfPredictionInput,
): Promise<SelfPredictionRecordV1> {
  assertSha256Hex('action_digest', input.action_digest)
  assertBasisPoints(input.predicted_success_bps)
  const body = predictionBody(input)
  const prediction_hash = await hashValue(body)

  return deepFreeze<SelfPredictionRecordV1>({
    ...body,
    prediction_hash,
  })
}

export function createSelfOutcomeObservation(
  input: SelfOutcomeObservationInput,
): SelfOutcomeObservationV1 {
  assertSha256Hex('prediction_hash', input.prediction_hash)
  assertSha256Hex('action_digest', input.action_digest)
  assertSha256Hex('observation_evidence_digest', input.observation_evidence_digest)

  if (input.observation_evidence_digest === input.prediction_hash) {
    throw new SelfCalibrationError(
      'prediction_hash cannot serve as its own observation evidence',
    )
  }

  return deepFreeze<SelfOutcomeObservationV1>({
    receipt_kind: 'SELF_OUTCOME_OBSERVATION_V1',
    schema_version: SELF_CALIBRATION_SCHEMA_VERSION,
    prediction_hash: input.prediction_hash,
    action_digest: input.action_digest,
    observation_evidence_digest: input.observation_evidence_digest,
    observed_success: input.observed_success,
    authority: 'NONE',
    acceptable_for_effect_truth: false,
  })
}

async function assertPredictionIntegrity(
  prediction: SelfPredictionRecordV1,
): Promise<void> {
  assertSha256Hex('prediction.action_digest', prediction.action_digest)
  assertSha256Hex('prediction.prediction_hash', prediction.prediction_hash)
  assertBasisPoints(prediction.predicted_success_bps)
  if (
    prediction.receipt_kind !== 'SELF_PREDICTION_RECORD_V1' ||
    prediction.schema_version !== SELF_CALIBRATION_SCHEMA_VERSION ||
    prediction.authority !== 'NONE' ||
    prediction.acceptable_for_effect_truth !== false
  ) {
    throw new SelfCalibrationError('prediction record semantics are invalid')
  }

  const expected = await hashValue(predictionBody(prediction))
  if (expected !== prediction.prediction_hash) {
    throw new SelfCalibrationError('prediction body does not match prediction_hash')
  }
}

function assertObservationSemantics(observation: SelfOutcomeObservationV1): void {
  assertSha256Hex('observation.prediction_hash', observation.prediction_hash)
  assertSha256Hex('observation.action_digest', observation.action_digest)
  assertSha256Hex(
    'observation.observation_evidence_digest',
    observation.observation_evidence_digest,
  )
  if (
    observation.receipt_kind !== 'SELF_OUTCOME_OBSERVATION_V1' ||
    observation.schema_version !== SELF_CALIBRATION_SCHEMA_VERSION ||
    observation.authority !== 'NONE' ||
    observation.acceptable_for_effect_truth !== false
  ) {
    throw new SelfCalibrationError('outcome observation semantics are invalid')
  }
  if (observation.observation_evidence_digest === observation.prediction_hash) {
    throw new SelfCalibrationError(
      'prediction_hash cannot serve as its own observation evidence',
    )
  }
}

export async function createSelfCalibration(
  prediction: SelfPredictionRecordV1,
  observation: SelfOutcomeObservationV1,
): Promise<SelfCalibrationRecordV1> {
  await assertPredictionIntegrity(prediction)
  assertObservationSemantics(observation)

  if (observation.prediction_hash !== prediction.prediction_hash) {
    throw new SelfCalibrationError('observation prediction_hash does not match prediction')
  }
  if (observation.action_digest !== prediction.action_digest) {
    throw new SelfCalibrationError('observation action_digest does not match prediction')
  }

  const observed_target_bps = observation.observed_success ? 10_000 : 0
  const absolute_error_bps = Math.abs(
    prediction.predicted_success_bps - observed_target_bps,
  )

  const body = {
    receipt_kind: 'SELF_CALIBRATION_RECORD_V1' as const,
    schema_version: SELF_CALIBRATION_SCHEMA_VERSION,
    prediction_hash: prediction.prediction_hash,
    action_digest: prediction.action_digest,
    observation_evidence_digest: observation.observation_evidence_digest,
    predicted_success_bps: prediction.predicted_success_bps,
    observed_success: observation.observed_success,
    absolute_error_bps,
    authority: 'NONE' as const,
    acceptable_for_effect_truth: false as const,
  }
  const calibration_hash = await hashValue(body)

  return deepFreeze<SelfCalibrationRecordV1>({
    ...body,
    calibration_hash,
  })
}

async function assertCalibrationIntegrity(
  calibration: SelfCalibrationRecordV1,
): Promise<void> {
  assertSha256Hex('calibration.prediction_hash', calibration.prediction_hash)
  assertSha256Hex('calibration.action_digest', calibration.action_digest)
  assertSha256Hex(
    'calibration.observation_evidence_digest',
    calibration.observation_evidence_digest,
  )
  assertSha256Hex('calibration.calibration_hash', calibration.calibration_hash)
  assertBasisPoints(calibration.predicted_success_bps)
  if (
    calibration.receipt_kind !== 'SELF_CALIBRATION_RECORD_V1' ||
    calibration.schema_version !== SELF_CALIBRATION_SCHEMA_VERSION ||
    calibration.authority !== 'NONE' ||
    calibration.acceptable_for_effect_truth !== false
  ) {
    throw new SelfCalibrationError('calibration record semantics are invalid')
  }

  if (calibration.observation_evidence_digest === calibration.prediction_hash) {
    throw new SelfCalibrationError(
      'prediction_hash cannot serve as its own observation evidence',
    )
  }

  const expected_prediction_hash = await hashValue(
    predictionBody({
      action_digest: calibration.action_digest,
      predicted_success_bps: calibration.predicted_success_bps,
    }),
  )
  if (expected_prediction_hash !== calibration.prediction_hash) {
    throw new SelfCalibrationError(
      'calibration prediction_hash does not match its prediction body',
    )
  }

  const expected_error = Math.abs(
    calibration.predicted_success_bps - (calibration.observed_success ? 10_000 : 0),
  )
  if (calibration.absolute_error_bps !== expected_error) {
    throw new SelfCalibrationError('calibration error does not match bound prediction/outcome')
  }

  const expected_hash = await hashValue(calibrationBody(calibration))
  if (expected_hash !== calibration.calibration_hash) {
    throw new SelfCalibrationError('calibration body does not match calibration_hash')
  }
}

function ledgerEntryBody(
  calibration: SelfCalibrationRecordV1,
  previous_entry_hash: SHA256Hex,
  sequence: SequenceNumber,
) {
  return {
    calibration,
    previous_entry_hash,
    sequence: sequence.toString(),
  }
}

export class SelfCalibrationLedger {
  private constructor(
    private readonly _entries: readonly SelfCalibrationLedgerEntry[],
    private readonly _lastSequence: SequenceNumber | null,
  ) {}

  static empty(): SelfCalibrationLedger {
    return new SelfCalibrationLedger([], null)
  }

  get length(): number { return this._entries.length }

  get lastSequence(): SequenceNumber | null { return this._lastSequence }

  get lastHash(): SHA256Hex {
    return this._entries.length === 0
      ? SELF_CALIBRATION_GENESIS_HASH
      : this._entries[this._entries.length - 1]!.entry_hash
  }

  getAll(): readonly SelfCalibrationLedgerEntry[] { return this._entries }

  async append(
    calibration: SelfCalibrationRecordV1,
    sequence: SequenceNumber,
  ): Promise<{ ledger: SelfCalibrationLedger; entry: SelfCalibrationLedgerEntry }> {
    assertNonNegativeSequence(sequence)
    if (this._lastSequence !== null && sequence <= this._lastSequence) {
      throw new SelfCalibrationError(
        `non-monotonic calibration sequence: ${sequence} <= ${this._lastSequence}`,
      )
    }

    await assertCalibrationIntegrity(calibration)
    const previous_entry_hash = this.lastHash
    const entry_hash = await hashValue(
      ledgerEntryBody(calibration, previous_entry_hash, sequence),
    )
    const entry = deepFreeze<SelfCalibrationLedgerEntry>({
      calibration,
      previous_entry_hash,
      sequence,
      entry_hash,
      schema_version: SELF_CALIBRATION_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })

    const ledger = new SelfCalibrationLedger(
      Object.freeze([...this._entries, entry]),
      sequence,
    )
    return { ledger, entry }
  }
}

export async function certifySelfCalibrationLedger(
  entries: readonly SelfCalibrationLedgerEntry[],
): Promise<SelfCalibrationLedgerCertificate> {
  let is_valid = true

  for (let index = 0; index < entries.length; index += 1) {
    const entry = entries[index]!
    const expected_previous = index === 0
      ? SELF_CALIBRATION_GENESIS_HASH
      : entries[index - 1]!.entry_hash

    if (entry.sequence < 0n) {
      is_valid = false
      break
    }
    if (
      !SHA256_PATTERN.test(entry.previous_entry_hash) ||
      !SHA256_PATTERN.test(entry.entry_hash)
    ) {
      is_valid = false
      break
    }
    if (entry.previous_entry_hash !== expected_previous) {
      is_valid = false
      break
    }
    if (index > 0 && entry.sequence <= entries[index - 1]!.sequence) {
      is_valid = false
      break
    }
    if (
      entry.schema_version !== SELF_CALIBRATION_SCHEMA_VERSION ||
      entry.is_replay_reconstructable !== true
    ) {
      is_valid = false
      break
    }

    try {
      await assertCalibrationIntegrity(entry.calibration)
    } catch {
      is_valid = false
      break
    }

    const expected_hash = await hashValue(
      ledgerEntryBody(entry.calibration, entry.previous_entry_hash, entry.sequence),
    )
    if (expected_hash !== entry.entry_hash) {
      is_valid = false
      break
    }
  }

  const terminal_hash = entries.length === 0
    ? null
    : entries[entries.length - 1]!.entry_hash
  const certificate_hash = await hashValue(entries.map(entry => entry.entry_hash))

  return deepFreeze<SelfCalibrationLedgerCertificate>({
    is_valid,
    entry_count: entries.length,
    terminal_hash,
    certificate_hash,
    authority: 'NONE',
    acceptable_for_effect_truth: false,
    is_replay_reconstructable: true,
  })
}

export async function calibrationToMetacognitiveObservation(
  calibration: SelfCalibrationRecordV1,
): Promise<MetacognitiveObservation> {
  await assertCalibrationIntegrity(calibration)
  const observed = calibration.observed_success ? 'success' : 'failure'
  return deepFreeze<MetacognitiveObservation>({
    layer: 'SELF_MODEL',
    tier: 'T2',
    signal: `self-calibration ${calibration.calibration_hash} action=${calibration.action_digest.slice(0, 8)} predicted=${calibration.predicted_success_bps}bps observed=${observed} error=${calibration.absolute_error_bps}bps`,
  })
}
