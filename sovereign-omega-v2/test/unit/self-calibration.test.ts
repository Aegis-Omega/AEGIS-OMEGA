import { describe, expect, it } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import {
  MetacognitiveLoop,
  certifyMetacognitiveLoop,
} from '../../src/metacognition/loop.js'
import {
  SELF_CALIBRATION_GENESIS_HASH,
  SelfCalibrationError,
  SelfCalibrationLedger,
  calibrationToMetacognitiveObservation,
  certifySelfCalibrationLedger,
  createSelfCalibration,
  createSelfOutcomeObservation,
  createSelfPrediction,
} from '../../src/metacognition/self-calibration.js'
import type {
  SelfCalibrationLedgerEntry,
  SelfCalibrationRecordV1,
} from '../../src/metacognition/self-calibration.js'

const H1 = '1'.repeat(64) as SHA256Hex
const H2 = '2'.repeat(64) as SHA256Hex
const H3 = '3'.repeat(64) as SHA256Hex
const BAD = 'f'.repeat(64) as SHA256Hex
const SEQ = (value: number) => BigInt(value) as SequenceNumber

async function makeCalibration(
  action_digest: SHA256Hex,
  evidence_digest: SHA256Hex,
  predicted_success_bps: number,
  observed_success: boolean,
): Promise<SelfCalibrationRecordV1> {
  const prediction = await createSelfPrediction({
    action_digest,
    predicted_success_bps,
  })
  const observation = createSelfOutcomeObservation({
    prediction_hash: prediction.prediction_hash,
    action_digest,
    observation_evidence_digest: evidence_digest,
    observed_success,
  })
  return createSelfCalibration(prediction, observation)
}


describe('self-model prediction evidence', () => {
  it('rejects predicted_success_bps outside the closed [0, 10000] interval', async () => {
    await expect(
      createSelfPrediction({ action_digest: H1, predicted_success_bps: -1 }),
    ).rejects.toThrow(SelfCalibrationError)

    await expect(
      createSelfPrediction({ action_digest: H1, predicted_success_bps: 10001 }),
    ).rejects.toThrow(SelfCalibrationError)
  })

  it('hashes identical prediction inputs deterministically and remains evidence-only', async () => {
    const p1 = await createSelfPrediction({
      action_digest: H1,
      predicted_success_bps: 7500,
    })
    const p2 = await createSelfPrediction({
      action_digest: H1,
      predicted_success_bps: 7500,
    })

    expect(p1.prediction_hash).toBe(p2.prediction_hash)
    expect(p1.receipt_kind).toBe('SELF_PREDICTION_RECORD_V1')
    expect(p1.schema_version).toBe('1.0.0')
    expect(p1.authority).toBe('NONE')
    expect(p1.acceptable_for_effect_truth).toBe(false)
    expect(Object.isFrozen(p1)).toBe(true)
  })

  it('rejects a prediction recycled as its own observation evidence', async () => {
    const prediction = await createSelfPrediction({
      action_digest: H1,
      predicted_success_bps: 7500,
    })

    expect(() =>
      createSelfOutcomeObservation({
        prediction_hash: prediction.prediction_hash,
        action_digest: H1,
        observation_evidence_digest: prediction.prediction_hash,
        observed_success: true,
      }),
    ).toThrow(SelfCalibrationError)
  })
})


describe('self-model calibration binding', () => {
  it('rejects prediction-hash and action-digest splicing', async () => {
    const predictionA = await createSelfPrediction({
      action_digest: H1,
      predicted_success_bps: 7500,
    })
    const predictionB = await createSelfPrediction({
      action_digest: H2,
      predicted_success_bps: 7500,
    })

    const observationA = createSelfOutcomeObservation({
      prediction_hash: predictionA.prediction_hash,
      action_digest: H1,
      observation_evidence_digest: H3,
      observed_success: true,
    })

    await expect(
      createSelfCalibration(predictionA, {
        ...observationA,
        prediction_hash: predictionB.prediction_hash,
      }),
    ).rejects.toThrow(SelfCalibrationError)

    await expect(
      createSelfCalibration(predictionA, {
        ...observationA,
        action_digest: H2,
      }),
    ).rejects.toThrow(SelfCalibrationError)
  })

  it('computes deterministic integer calibration error and stays evidence-only', async () => {
    const prediction = await createSelfPrediction({
      action_digest: H1,
      predicted_success_bps: 7500,
    })
    const successObservation = createSelfOutcomeObservation({
      prediction_hash: prediction.prediction_hash,
      action_digest: H1,
      observation_evidence_digest: H2,
      observed_success: true,
    })
    const failureObservation = createSelfOutcomeObservation({
      prediction_hash: prediction.prediction_hash,
      action_digest: H1,
      observation_evidence_digest: H3,
      observed_success: false,
    })

    const success1 = await createSelfCalibration(prediction, successObservation)
    const success2 = await createSelfCalibration(prediction, successObservation)
    const failure = await createSelfCalibration(prediction, failureObservation)

    expect(success1.absolute_error_bps).toBe(2500)
    expect(failure.absolute_error_bps).toBe(7500)
    expect(success1.calibration_hash).toBe(success2.calibration_hash)
    expect(success1.receipt_kind).toBe('SELF_CALIBRATION_RECORD_V1')
    expect(success1.authority).toBe('NONE')
    expect(success1.acceptable_for_effect_truth).toBe(false)
    expect(Object.isFrozen(success1)).toBe(true)
  })

  it('rejects a prediction whose body no longer matches its prediction_hash', async () => {
    const prediction = await createSelfPrediction({
      action_digest: H1,
      predicted_success_bps: 7500,
    })
    const observation = createSelfOutcomeObservation({
      prediction_hash: prediction.prediction_hash,
      action_digest: H1,
      observation_evidence_digest: H2,
      observed_success: true,
    })
    const tamperedPrediction = {
      ...prediction,
      predicted_success_bps: 7600,
    }

    await expect(
      createSelfCalibration(tamperedPrediction, observation),
    ).rejects.toThrow(SelfCalibrationError)
  })
})


describe('self-calibration ledger', () => {
  it('starts from the fixed genesis hash and enforces strictly increasing sequence', async () => {
    const calibration1 = await makeCalibration(H1, H2, 7500, true)
    const calibration2 = await makeCalibration(H1, H3, 6000, false)

    const empty = SelfCalibrationLedger.empty()
    const { ledger: l1, entry: e1 } = await empty.append(calibration1, SEQ(1))

    expect(e1.previous_entry_hash).toBe(SELF_CALIBRATION_GENESIS_HASH)
    expect(e1.sequence).toBe(SEQ(1))
    expect(Object.isFrozen(e1)).toBe(true)

    await expect(l1.append(calibration2, SEQ(1))).rejects.toThrow(SelfCalibrationError)
    await expect(l1.append(calibration2, SEQ(0))).rejects.toThrow(SelfCalibrationError)
  })

  it('produces deterministic entry hashes for identical calibration and sequence', async () => {
    const calibration = await makeCalibration(H1, H2, 7500, true)
    const { entry: e1 } = await SelfCalibrationLedger.empty().append(calibration, SEQ(1))
    const { entry: e2 } = await SelfCalibrationLedger.empty().append(calibration, SEQ(1))

    expect(e1.entry_hash).toBe(e2.entry_hash)
  })

  it('certifies a valid chain and remains evidence-only', async () => {
    const calibration1 = await makeCalibration(H1, H2, 7500, true)
    const calibration2 = await makeCalibration(H1, H3, 6000, false)

    const { ledger: l1 } = await SelfCalibrationLedger.empty().append(calibration1, SEQ(1))
    const { ledger: l2 } = await l1.append(calibration2, SEQ(2))
    const certificate = await certifySelfCalibrationLedger(l2.getAll())

    expect(certificate.is_valid).toBe(true)
    expect(certificate.entry_count).toBe(2)
    expect(certificate.terminal_hash).toBe(l2.lastHash)
    expect(certificate.authority).toBe('NONE')
    expect(certificate.acceptable_for_effect_truth).toBe(false)
    expect(Object.isFrozen(certificate)).toBe(true)
  })

  it('invalidates tampered previous-link, calibration content, or entry hash', async () => {
    const calibration1 = await makeCalibration(H1, H2, 7500, true)
    const calibration2 = await makeCalibration(H1, H3, 6000, false)

    const { ledger: l1 } = await SelfCalibrationLedger.empty().append(calibration1, SEQ(1))
    const { ledger: l2 } = await l1.append(calibration2, SEQ(2))
    const [e1, e2] = l2.getAll()

    const badPrev: readonly SelfCalibrationLedgerEntry[] = [
      e1!,
      { ...e2!, previous_entry_hash: BAD },
    ]
    expect((await certifySelfCalibrationLedger(badPrev)).is_valid).toBe(false)

    const badCalibration: readonly SelfCalibrationLedgerEntry[] = [
      {
        ...e1!,
        calibration: {
          ...e1!.calibration,
          absolute_error_bps: e1!.calibration.absolute_error_bps + 1,
        },
      },
      e2!,
    ]
    expect((await certifySelfCalibrationLedger(badCalibration)).is_valid).toBe(false)

    const badHash: readonly SelfCalibrationLedgerEntry[] = [
      { ...e1!, entry_hash: BAD },
      e2!,
    ]
    expect((await certifySelfCalibrationLedger(badHash)).is_valid).toBe(false)
  })
})


describe('self-calibration metacognitive bridge', () => {
  it('emits exactly SELF_MODEL/T2 evidence and replays in the existing metacognitive loop', async () => {
    const calibration = await makeCalibration(H1, H2, 7500, true)
    const observation = calibrationToMetacognitiveObservation(calibration)

    expect(observation.layer).toBe('SELF_MODEL')
    expect(observation.tier).toBe('T2')
    expect(observation.signal).toContain(calibration.calibration_hash)
    expect(Object.keys(observation).sort()).toEqual(['layer', 'signal', 'tier'])

    const { loop } = await MetacognitiveLoop.empty().observe(observation, SEQ(1))
    const certificate = await certifyMetacognitiveLoop(loop.getAll())

    expect(certificate.is_valid).toBe(true)
    expect(certificate.entry_count).toBe(1)
  })
})
