import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { generateKeypair } from '../../src/consensus/crypto.js'
import { hashValue } from '../../src/core/hashing.js'
import {
  QUANPHOTONIC_CALIBRATION_SCHEMA_VERSION,
  QUANPHOTONIC_MEASUREMENT_SCHEMA_VERSION,
  QuanPhotonicCalibrationGate,
  calibrationReceiptDigest,
  signCalibrationReceipt,
  type CalibrationReceiptPayloadV1,
  type MeasurementBatchEnvelopeV1,
} from '../../src/calibration/quanphotonic.js'

const HEX_A = 'a'.repeat(64)
const HEX_B = 'b'.repeat(64)
const COMMIT = 'c'.repeat(40)

function payload(overrides: Partial<CalibrationReceiptPayloadV1> = {}): CalibrationReceiptPayloadV1 {
  return {
    schema_version: QUANPHOTONIC_CALIBRATION_SCHEMA_VERSION,
    calibration_epoch_id: 'qp-epoch-0001',
    detector_id: 'sns-pd-01',
    detector_configuration_digest: HEX_A,
    sequence: '10',
    valid_from_sequence: '10',
    valid_until_sequence: '99',
    previous_receipt_digest: null,
    raw_calibration_digest: HEX_B,
    calibration_code_commit: COMMIT,
    reference_source_ids: ['dark-shutter-01', 'pulse-ref-01', 'nir-ref-1270-01'],
    parameters: {
      background_rate_hz: '0.0012',
      spectral_efficiency_model_digest: 'd'.repeat(64),
      afterpulse_kernel_digest: 'e'.repeat(64),
      dead_time_ps: '42000',
      jitter_ps_rms: '18.5',
      gain: '1.0007',
      pileup_model_digest: 'f'.repeat(64),
    },
    calibration_status: 'PASS',
    ...overrides,
  }
}

async function fixture() {
  const signer = await generateKeypair(new Uint8Array(32).fill(7))
  const receipt = await signCalibrationReceipt(payload(), 'calibration-signer-1', signer.privateKey)
  const receiptDigest = await calibrationReceiptDigest(receipt)
  const rawBatch = { counts: ['1', '0', '2'], lane: 'NIR-1270' }
  const batchDigest = await hashValue(rawBatch)
  const batch: MeasurementBatchEnvelopeV1 = {
    schema_version: 'QUANPHOTONIC_MEASUREMENT_BATCH_V1',
    measurement_batch_id: 'batch-0001',
    measurement_batch_digest: batchDigest,
    calibration_receipt_digest: receiptDigest,
    calibration_epoch_id: receipt.payload.calibration_epoch_id,
    detector_id: receipt.payload.detector_id,
    detector_configuration_digest: receipt.payload.detector_configuration_digest,
    sequence: '11',
  }
  return { signer, receipt, rawBatch, batch }
}

describe('QuanPhotonic CalibrationReceiptV1', () => {
  it('canonically hashes, signs, verifies, and admits one bound batch', async () => {
    const { signer, receipt, rawBatch, batch } = await fixture()
    const gate = new QuanPhotonicCalibrationGate({ 'calibration-signer-1': signer.publicKey })

    const result = await gate.admit(receipt, batch, rawBatch)

    expect(result).toMatchObject({ status: 'PASS', reason: 'CALIBRATION_VERIFIED' })
    expect(result.calibration_receipt_digest).toBe(batch.calibration_receipt_digest)
    expect(receipt.verification_status).toBe('UNVERIFIED')
    expect(Object.isFrozen(receipt)).toBe(true)
    expect(Object.isFrozen(receipt.payload)).toBe(true)
  })

  it('is deterministic for the same payload and signing key', async () => {
    const signer = await generateKeypair(new Uint8Array(32).fill(7))
    const a = await signCalibrationReceipt(payload(), 'calibration-signer-1', signer.privateKey)
    const b = await signCalibrationReceipt(payload(), 'calibration-signer-1', signer.privateKey)
    expect(a).toEqual(b)
    expect(await calibrationReceiptDigest(a)).toBe(await calibrationReceiptDigest(b))
  })

  it('fails closed on payload tampering or an untrusted signer', async () => {
    const { signer, receipt, rawBatch, batch } = await fixture()
    const trusted = new QuanPhotonicCalibrationGate({ 'calibration-signer-1': signer.publicKey })
    const tampered = {
      ...receipt,
      payload: { ...receipt.payload, detector_id: 'attacker-detector' },
    }
    await expect(trusted.admit(tampered, batch, rawBatch)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'PAYLOAD_DIGEST_MISMATCH',
    })

    const untrusted = new QuanPhotonicCalibrationGate({})
    await expect(untrusted.admit(receipt, batch, rawBatch)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'UNTRUSTED_SIGNER',
    })

    const forged = { ...receipt, signature: '0'.repeat(128) }
    await expect(trusted.admit(forged, batch, rawBatch)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'SIGNATURE_INVALID',
    })
  })

  it.each([
    ['detector_id', 'other-detector', 'DETECTOR_MISMATCH'],
    ['detector_configuration_digest', '9'.repeat(64), 'CONFIGURATION_MISMATCH'],
    ['calibration_epoch_id', 'qp-epoch-9999', 'EPOCH_MISMATCH'],
  ] as const)('rejects %s substitution', async (field, value, reason) => {
    const { signer, receipt, rawBatch, batch } = await fixture()
    const gate = new QuanPhotonicCalibrationGate({ 'calibration-signer-1': signer.publicKey })
    const substituted = { ...batch, [field]: value }
    await expect(gate.admit(receipt, substituted, rawBatch)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason,
    })
  })

  it('rejects expired, pre-validity, and invalid-status receipts', async () => {
    const signer = await generateKeypair(new Uint8Array(32).fill(7))
    const gate = new QuanPhotonicCalibrationGate({ 'calibration-signer-1': signer.publicKey })
    for (const [sequence, reason] of [['9', 'NOT_YET_VALID'], ['100', 'CALIBRATION_EXPIRED']] as const) {
      const receipt = await signCalibrationReceipt(payload(), 'calibration-signer-1', signer.privateKey)
      const rawBatch = { counts: [1] }
      const batch: MeasurementBatchEnvelopeV1 = {
        schema_version: 'QUANPHOTONIC_MEASUREMENT_BATCH_V1',
        measurement_batch_id: `batch-${sequence}`,
        measurement_batch_digest: await hashValue(rawBatch),
        calibration_receipt_digest: await calibrationReceiptDigest(receipt),
        calibration_epoch_id: receipt.payload.calibration_epoch_id,
        detector_id: receipt.payload.detector_id,
        detector_configuration_digest: receipt.payload.detector_configuration_digest,
        sequence,
      }
      await expect(gate.admit(receipt, batch, rawBatch)).resolves.toMatchObject({
        status: 'INVALID_CALIBRATION', reason,
      })
    }

    const invalidReceipt = await signCalibrationReceipt(
      payload({ calibration_status: 'INVALID_CALIBRATION' }),
      'calibration-signer-1',
      signer.privateKey,
    )
    const rawBatch = { counts: [1] }
    const invalidBatch: MeasurementBatchEnvelopeV1 = {
      schema_version: 'QUANPHOTONIC_MEASUREMENT_BATCH_V1',
      measurement_batch_id: 'batch-invalid',
      measurement_batch_digest: await hashValue(rawBatch),
      calibration_receipt_digest: await calibrationReceiptDigest(invalidReceipt),
      calibration_epoch_id: invalidReceipt.payload.calibration_epoch_id,
      detector_id: invalidReceipt.payload.detector_id,
      detector_configuration_digest: invalidReceipt.payload.detector_configuration_digest,
      sequence: '11',
    }
    await expect(gate.admit(invalidReceipt, invalidBatch, rawBatch)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'CALIBRATION_GATE_FAILED',
    })
  })

  it('rejects batch digest mismatch, receipt substitution, rollback, and replay', async () => {
    const { signer, receipt, rawBatch, batch } = await fixture()
    const gate = new QuanPhotonicCalibrationGate({ 'calibration-signer-1': signer.publicKey })

    await expect(gate.admit(receipt, { ...batch, measurement_batch_digest: HEX_A }, rawBatch))
      .resolves.toMatchObject({ status: 'INVALID_CALIBRATION', reason: 'BATCH_DIGEST_MISMATCH' })
    await expect(gate.admit(receipt, { ...batch, calibration_receipt_digest: HEX_A }, rawBatch))
      .resolves.toMatchObject({ status: 'INVALID_CALIBRATION', reason: 'RECEIPT_DIGEST_MISMATCH' })

    await expect(gate.admit(receipt, batch, rawBatch)).resolves.toMatchObject({ status: 'PASS' })
    await expect(gate.admit(receipt, batch, rawBatch)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'BATCH_REPLAY',
    })

    await expect(gate.admit(receipt, {
      ...batch,
      measurement_batch_id: 'batch-same-content-new-id',
      sequence: '12',
    }, rawBatch)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'BATCH_DIGEST_REPLAY',
    })

    const rawBatch2 = { counts: [3] }
    const rollback = {
      ...batch,
      measurement_batch_id: 'batch-0002',
      measurement_batch_digest: await hashValue(rawBatch2),
      sequence: '10',
    }
    await expect(gate.admit(receipt, rollback, rawBatch2)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'SEQUENCE_ROLLBACK',
    })
  })

  it('rejects malformed decimal sequences and invalid validity ordering', async () => {
    const signer = await generateKeypair(new Uint8Array(32).fill(7))
    await expect(signCalibrationReceipt(payload({ sequence: '01' }), 'calibration-signer-1', signer.privateKey))
      .rejects.toThrow(/canonical decimal sequence/)
    await expect(signCalibrationReceipt(
      payload({ valid_from_sequence: '50', valid_until_sequence: '49' }),
      'calibration-signer-1',
      signer.privateKey,
    )).rejects.toThrow(/validity interval/)
  })

  it.each([
    ['background_rate_hz', 'NaN'],
    ['dead_time_ps', '042000'],
    ['jitter_ps_rms', '1e3'],
    ['gain', '0'],
    ['gain', '1.0000'],
  ] as const)('rejects non-canonical calibration parameter %s=%s', async (field, value) => {
    const signer = await generateKeypair(new Uint8Array(32).fill(7))
    await expect(signCalibrationReceipt(payload({
      parameters: { ...payload().parameters, [field]: value },
    }), 'calibration-signer-1', signer.privateKey)).rejects.toThrow(/calibration payload/)
  })

  it('enforces a monotonic receipt chain across calibration epochs', async () => {
    const signer = await generateKeypair(new Uint8Array(32).fill(7))
    const gate = new QuanPhotonicCalibrationGate({ 'calibration-signer-1': signer.publicKey })
    const first = await signCalibrationReceipt(payload(), 'calibration-signer-1', signer.privateKey)
    const firstDigest = await calibrationReceiptDigest(first)
    const firstRaw = { counts: [1] }
    const firstBatch: MeasurementBatchEnvelopeV1 = {
      schema_version: 'QUANPHOTONIC_MEASUREMENT_BATCH_V1',
      measurement_batch_id: 'chain-batch-1',
      measurement_batch_digest: await hashValue(firstRaw),
      calibration_receipt_digest: firstDigest,
      calibration_epoch_id: first.payload.calibration_epoch_id,
      detector_id: first.payload.detector_id,
      detector_configuration_digest: first.payload.detector_configuration_digest,
      sequence: '11',
    }
    await expect(gate.admit(first, firstBatch, firstRaw)).resolves.toMatchObject({ status: 'PASS' })

    const second = await signCalibrationReceipt(payload({
      calibration_epoch_id: 'qp-epoch-0002',
      sequence: '100',
      valid_from_sequence: '100',
      valid_until_sequence: '199',
      previous_receipt_digest: firstDigest,
    }), 'calibration-signer-1', signer.privateKey)
    const secondRaw = { counts: [2] }
    const secondBatch: MeasurementBatchEnvelopeV1 = {
      ...firstBatch,
      measurement_batch_id: 'chain-batch-2',
      measurement_batch_digest: await hashValue(secondRaw),
      calibration_receipt_digest: await calibrationReceiptDigest(second),
      calibration_epoch_id: second.payload.calibration_epoch_id,
      sequence: '101',
    }
    await expect(gate.admit(second, secondBatch, secondRaw)).resolves.toMatchObject({ status: 'PASS' })

    const unlinked = await signCalibrationReceipt(payload({
      calibration_epoch_id: 'qp-epoch-0003',
      sequence: '200',
      valid_from_sequence: '200',
      valid_until_sequence: '299',
      previous_receipt_digest: firstDigest,
    }), 'calibration-signer-1', signer.privateKey)
    const thirdRaw = { counts: [3] }
    const thirdBatch: MeasurementBatchEnvelopeV1 = {
      ...secondBatch,
      measurement_batch_id: 'chain-batch-3',
      measurement_batch_digest: await hashValue(thirdRaw),
      calibration_receipt_digest: await calibrationReceiptDigest(unlinked),
      calibration_epoch_id: unlinked.payload.calibration_epoch_id,
      sequence: '201',
    }
    await expect(gate.admit(unlinked, thirdBatch, thirdRaw)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'RECEIPT_CHAIN_MISMATCH',
    })

    const secondDigest = await calibrationReceiptDigest(second)
    const rollbackReceipt = await signCalibrationReceipt(payload({
      calibration_epoch_id: 'qp-epoch-0003',
      sequence: '50',
      valid_from_sequence: '50',
      valid_until_sequence: '299',
      previous_receipt_digest: secondDigest,
    }), 'calibration-signer-1', signer.privateKey)
    await expect(gate.admit(rollbackReceipt, {
      ...thirdBatch,
      calibration_receipt_digest: await calibrationReceiptDigest(rollbackReceipt),
    }, thirdRaw)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'RECEIPT_SEQUENCE_ROLLBACK',
    })

    const reusedEpoch = await signCalibrationReceipt(payload({
      calibration_epoch_id: second.payload.calibration_epoch_id,
      sequence: '200',
      valid_from_sequence: '200',
      valid_until_sequence: '299',
      previous_receipt_digest: secondDigest,
      raw_calibration_digest: '8'.repeat(64),
    }), 'calibration-signer-1', signer.privateKey)
    await expect(gate.admit(reusedEpoch, {
      ...thirdBatch,
      calibration_epoch_id: reusedEpoch.payload.calibration_epoch_id,
      calibration_receipt_digest: await calibrationReceiptDigest(reusedEpoch),
    }, thirdRaw)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'CALIBRATION_EPOCH_REUSE',
    })
  })

  it('fails closed on unexpected receipt, payload, or batch fields', async () => {
    const { signer, receipt, rawBatch, batch } = await fixture()
    const gate = new QuanPhotonicCalibrationGate({ 'calibration-signer-1': signer.publicKey })
    await expect(gate.admit({ ...receipt, unexpected: true }, batch, rawBatch)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'MALFORMED_RECEIPT',
    })
    await expect(gate.admit({
      ...receipt,
      payload: { ...receipt.payload, unexpected: true },
    }, batch, rawBatch)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'MALFORMED_RECEIPT',
    })
    await expect(gate.admit(receipt, { ...batch, unexpected: true }, rawBatch)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'MALFORMED_BATCH',
    })
  })

  it('ships fail-closed JSON schemas aligned with the wire constants', () => {
    const receiptSchema = JSON.parse(readFileSync(
      'schemas/quanphotonic-calibration-receipt.v1.schema.json',
      'utf8',
    )) as Record<string, unknown>
    const batchSchema = JSON.parse(readFileSync(
      'schemas/quanphotonic-measurement-batch.v1.schema.json',
      'utf8',
    )) as Record<string, unknown>
    expect(receiptSchema).toMatchObject({
      additionalProperties: false,
      properties: { signature_algorithm: { const: 'Ed25519' }, verification_status: { const: 'UNVERIFIED' } },
    })
    const receiptDefinitions = receiptSchema.$defs as Record<string, unknown>
    const payloadSchema = receiptDefinitions.payload as { properties: Record<string, unknown> }
    const parametersSchema = payloadSchema.properties.parameters as { properties: Record<string, { pattern: string }> }
    const gainSchema = parametersSchema.properties.gain
    expect(gainSchema).toBeDefined()
    if (!gainSchema) throw new Error('gain schema missing')
    const gainPattern = new RegExp(gainSchema.pattern)
    expect(gainPattern.test('0.001')).toBe(true)
    expect(gainPattern.test('1.0007')).toBe(true)
    expect(gainPattern.test('0')).toBe(false)
    expect(gainPattern.test('0.010')).toBe(false)
    expect(batchSchema).toMatchObject({
      additionalProperties: false,
      properties: { schema_version: { const: QUANPHOTONIC_MEASUREMENT_SCHEMA_VERSION } },
    })
  })
})
