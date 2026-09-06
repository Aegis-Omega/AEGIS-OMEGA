import 'fake-indexeddb/auto'

import { describe, expect, it } from 'vitest'
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
import { IndexedDbQuanPhotonicReplayAuthority } from '../../src/calibration/quanphotonic-replay-store.js'

const HEX_A = 'a'.repeat(64)
const HEX_B = 'b'.repeat(64)
const COMMIT = 'c'.repeat(40)
let databaseCounter = 0

function databaseName(): string {
  databaseCounter += 1
  return `quanphotonic-replay-test-${databaseCounter}`
}

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
    reference_source_ids: ['dark-shutter-01'],
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

async function admissionFixture(database: string, batchId = 'batch-0001', sequence = '11') {
  const signer = await generateKeypair(new Uint8Array(32).fill(7))
  const receipt = await signCalibrationReceipt(payload(), 'calibration-signer-1', signer.privateKey)
  const rawBatch = { counts: ['1', '0', '2'], lane: 'NIR-1270' }
  const batch: MeasurementBatchEnvelopeV1 = {
    schema_version: QUANPHOTONIC_MEASUREMENT_SCHEMA_VERSION,
    measurement_batch_id: batchId,
    measurement_batch_digest: await hashValue(rawBatch),
    calibration_receipt_digest: await calibrationReceiptDigest(receipt),
    calibration_epoch_id: receipt.payload.calibration_epoch_id,
    detector_id: receipt.payload.detector_id,
    detector_configuration_digest: receipt.payload.detector_configuration_digest,
    sequence,
  }
  const authority = new IndexedDbQuanPhotonicReplayAuthority(database)
  await authority.open()
  const gate = new QuanPhotonicCalibrationGate({ 'calibration-signer-1': signer.publicKey }, authority)
  return { signer, receipt, rawBatch, batch, authority, gate }
}

describe('IndexedDbQuanPhotonicReplayAuthority', () => {
  it('rejects replay after the original gate and database connection are replaced', async () => {
    const database = databaseName()
    const first = await admissionFixture(database)
    await expect(first.gate.admit(first.receipt, first.batch, first.rawBatch)).resolves.toMatchObject({ status: 'PASS' })
    first.authority.close()

    const restartedAuthority = new IndexedDbQuanPhotonicReplayAuthority(database)
    await restartedAuthority.open()
    const restartedGate = new QuanPhotonicCalibrationGate(
      { 'calibration-signer-1': first.signer.publicKey },
      restartedAuthority,
    )
    await expect(restartedGate.admit(first.receipt, first.batch, first.rawBatch)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'BATCH_REPLAY',
    })
    restartedAuthority.close()
  })

  it('preserves the epoch sequence watermark across restart', async () => {
    const database = databaseName()
    const first = await admissionFixture(database, 'batch-high', '12')
    await expect(first.gate.admit(first.receipt, first.batch, first.rawBatch)).resolves.toMatchObject({ status: 'PASS' })
    first.authority.close()

    const restartedAuthority = new IndexedDbQuanPhotonicReplayAuthority(database)
    await restartedAuthority.open()
    const restartedGate = new QuanPhotonicCalibrationGate(
      { 'calibration-signer-1': first.signer.publicKey },
      restartedAuthority,
    )
    const rawRollback = { counts: ['9'] }
    const rollbackBatch = {
      ...first.batch,
      measurement_batch_id: 'batch-rollback',
      measurement_batch_digest: await hashValue(rawRollback),
      sequence: '11',
    }
    await expect(restartedGate.admit(first.receipt, rollbackBatch, rawRollback)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'SEQUENCE_ROLLBACK',
    })
    restartedAuthority.close()
  })

  it('atomically admits only one of two concurrent copies', async () => {
    const database = databaseName()
    const fixture = await admissionFixture(database)
    const secondAuthority = new IndexedDbQuanPhotonicReplayAuthority(database)
    await secondAuthority.open()
    const secondGate = new QuanPhotonicCalibrationGate(
      { 'calibration-signer-1': fixture.signer.publicKey },
      secondAuthority,
    )

    const results = await Promise.all([
      fixture.gate.admit(fixture.receipt, fixture.batch, fixture.rawBatch),
      secondGate.admit(fixture.receipt, fixture.batch, fixture.rawBatch),
    ])
    expect(results.filter(result => result.status === 'PASS')).toHaveLength(1)
    expect(results.filter(result => result.status === 'INVALID_CALIBRATION')).toEqual([
      expect.objectContaining({ reason: 'BATCH_REPLAY' }),
    ])
    fixture.authority.close()
    secondAuthority.close()
  })

  it('fails closed instead of falling back to memory when persistence is unavailable', async () => {
    const database = databaseName()
    const fixture = await admissionFixture(database)
    fixture.authority.close()

    await expect(fixture.gate.admit(fixture.receipt, fixture.batch, fixture.rawBatch)).resolves.toMatchObject({
      status: 'INVALID_CALIBRATION', reason: 'PERSISTENCE_UNAVAILABLE',
    })
  })
})
