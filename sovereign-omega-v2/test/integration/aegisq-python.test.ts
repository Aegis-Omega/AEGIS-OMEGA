// @vitest-environment node
// Real subprocess integration: missing Python/numpy/scipy is a failure, never a skip.
import { beforeAll, describe, expect, it } from 'vitest'
import { execFileSync } from 'node:child_process'
import { access, chmod, cp, mkdtemp, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { generateKeypair } from '../../src/consensus/crypto.js'
import { hashValue } from '../../src/core/hashing.js'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  calibrationReceiptDigest,
  signCalibrationReceipt,
  type CalibrationReceiptPayloadV1,
  type MeasurementBatchEnvelopeV1,
} from '../../src/calibration/quanphotonic.js'
import {
  AEGISQ_REQUEST_VERSION,
  AegisQAdmissionGate,
  signAegisQRequest,
  type AegisQVerifier,
} from '../../src/research/aegisq-admission.js'
import {
  createPinnedPythonVerifier,
  inspectPythonVerifier,
  type PythonVerifierLocation,
} from '../../src/research/aegisq-python.js'

const TIMEOUT = 60_000
const PACKAGE_DIRECTORY = fileURLToPath(new URL('../../../packages/aegisq-ifg/', import.meta.url))
const POLICY = {
  eigenvalue_tolerance: 1e-10,
  hermiticity_tolerance: 1e-10,
  trace_tolerance: 1e-9,
  midpoint_residual_per_second: 1e-3,
  transition_residual: 1e-5,
  probability_residual: 1e-3,
  identifiability_rtol: 1e-9,
  max_dimension: 16,
}

function zeroMatrix(): number[][] { return [[0, 0], [0, 0]] }

// Informationally complete six-outcome POVM, E_{axis,+/-} = (I +/- sigma_axis)/6.
const MODEL = {
  schema_version: 'AEGISQ_GKSL_MODEL_V1',
  hamiltonian: { real: zeroMatrix(), imag: zeroMatrix() },
  jumps: { real: [], imag: [] },
  povm: {
    real: [
      [[1 / 6, 1 / 6], [1 / 6, 1 / 6]],
      [[1 / 6, -1 / 6], [-1 / 6, 1 / 6]],
      [[1 / 6, 0], [0, 1 / 6]],
      [[1 / 6, 0], [0, 1 / 6]],
      [[1 / 3, 0], [0, 0]],
      [[0, 0], [0, 1 / 3]],
    ],
    imag: [
      zeroMatrix(), zeroMatrix(),
      [[0, -1 / 6], [1 / 6, 0]],
      [[0, 1 / 6], [-1 / 6, 0]],
      zeroMatrix(), zeroMatrix(),
    ],
  },
}

function observation(invalidDensity = false) {
  const state = invalidDensity ? [[-0.1, 0], [0, 1.1]] : [[0, 0], [0, 1]]
  return {
    schema_version: 'AEGISQ_STATE_OBSERVATION_V1',
    source_kind: 'SYNTHETIC_VALIDATION',
    time_unit: 'second',
    times_seconds: [0, 0.01, 0.02],
    rho: { real: [state, state, state], imag: [zeroMatrix(), zeroMatrix(), zeroMatrix()] },
    probabilities: [0, 1, 2].map(() => [1 / 6, 1 / 6, 1 / 6, 1 / 6, 0, 1 / 3]),
  }
}

function calibrationPayload(): CalibrationReceiptPayloadV1 {
  return {
    schema_version: 'QUANPHOTONIC_CALIBRATION_RECEIPT_V1',
    calibration_epoch_id: 'aegisq-synthetic-epoch-1',
    detector_id: 'aegisq-synthetic-detector-1',
    detector_configuration_digest: 'a'.repeat(64),
    sequence: '10',
    valid_from_sequence: '10',
    valid_until_sequence: '99',
    previous_receipt_digest: null,
    raw_calibration_digest: 'b'.repeat(64),
    calibration_code_commit: 'c'.repeat(40),
    reference_source_ids: ['synthetic-dark-reference', 'synthetic-timing-reference'],
    parameters: {
      background_rate_hz: '0',
      spectral_efficiency_model_digest: 'd'.repeat(64),
      afterpulse_kernel_digest: 'e'.repeat(64),
      dead_time_ps: '1',
      jitter_ps_rms: '1',
      gain: '1',
      pileup_model_digest: 'f'.repeat(64),
    },
    calibration_status: 'PASS',
  }
}

let location: PythonVerifierLocation
let verifier: AegisQVerifier
let approvedIdentity: Awaited<ReturnType<typeof inspectPythonVerifier>>['identity']

async function fixture(raw = observation()) {
  const calibrationKey = await generateKeypair(new Uint8Array(32).fill(31))
  const producerKey = await generateKeypair(new Uint8Array(32).fill(32))
  const receipt = await signCalibrationReceipt(calibrationPayload(), 'synthetic-calibration-key', calibrationKey.privateKey)
  const receiptDigest = await calibrationReceiptDigest(receipt)
  const rawDigest = await hashValue(raw)
  const batch: MeasurementBatchEnvelopeV1 = {
    schema_version: 'QUANPHOTONIC_MEASUREMENT_BATCH_V1',
    measurement_batch_id: 'aegisq-synthetic-batch-1',
    measurement_batch_digest: rawDigest,
    calibration_receipt_digest: receiptDigest,
    calibration_epoch_id: receipt.payload.calibration_epoch_id,
    detector_id: receipt.payload.detector_id,
    detector_configuration_digest: receipt.payload.detector_configuration_digest,
    sequence: '11',
  }
  const modelDigest = await hashValue(MODEL)
  const policyDigest = await hashValue(POLICY)
  const signed = await signAegisQRequest({
    schema_version: AEGISQ_REQUEST_VERSION,
    job_id: 'aegisq-synthetic-job-1',
    scope: 'RESEARCH_ONLY',
    raw_batch_digest: rawDigest,
    calibration_receipt_digest: receiptDigest,
    measurement_envelope_digest: await hashValue(batch),
    model_digest: modelDigest,
    policy_digest: policyDigest,
    verifier_digest: verifier.digest,
  }, 'synthetic-producer-key', producerKey.privateKey)
  const gate = new AegisQAdmissionGate({
    trustedCalibrationKeys: { 'synthetic-calibration-key': calibrationKey.publicKey },
    trustedProducerKeys: { 'synthetic-producer-key': producerKey.publicKey },
    modelDigest,
    policyDigest,
    verifier,
  })
  return { raw, signed, receipt, batch, gate }
}

describe('AegisQ signed admission with pinned real Python IFG', () => {
  beforeAll(async () => {
    // Explicit fixture bootstrap: this observation creates test pins only, and
    // is not a production policy authorizing an arbitrary installed verifier.
    const candidate = process.env.AEGISQ_PYTHON_EXECUTABLE
      ?? execFileSync('python3', ['-c', 'import sys; print(sys.executable)'], { encoding: 'utf8' }).trim()
    location = {
      pythonExecutable: await realpath(candidate),
      packageDirectory: await realpath(PACKAGE_DIRECTORY),
    }
    const inspected = await inspectPythonVerifier(location)
    approvedIdentity = inspected.identity
    verifier = await createPinnedPythonVerifier({
      ...location, expectedIdentityDigest: inspected.digest, expectedIdentity: approvedIdentity,
    })
  }, TIMEOUT)

  it('admits a genuinely signed |1> trajectory and binds the actual numerical result', async () => {
    const f = await fixture()
    // |1> has negative Wigner parity at the origin; it remains a physical state.
    const numerical = await verifier.verify(f.raw, MODEL, POLICY)
    expect(numerical).toMatchObject({
      status: 'PASS_RESEARCH_ONLY', reasons: [],
      metrics: { minimum_eigenvalue: 0, measurement_rank: 3, required_measurement_rank: 3 },
      clinical_admission: false,
    })
    const result = await f.gate.evaluate(f.signed, f.receipt, f.batch, f.raw, MODEL, POLICY)
    expect(result).toMatchObject({
      status: 'PASS_RESEARCH_ONLY', reason: 'BOUND_RESEARCH_INFERENCE_VERIFIED',
      clinical_admission: false, calibration_consumed: true,
      replay_protection: 'IN_PROCESS_ONLY',
      physics_result_digest: await hashValue(numerical),
      bindings: {
        request_payload_digest: f.signed.payload_digest,
        raw_batch_digest: f.batch.measurement_batch_digest,
        calibration_receipt_digest: f.batch.calibration_receipt_digest,
        verifier_digest: verifier.digest,
      },
    })
    const { receipt_digest, ...payload } = result
    expect(receipt_digest).toBe(await hashValue(payload))
    expect(Object.isFrozen(result)).toBe(true)
  }, TIMEOUT)

  it('denies a genuinely signed negative density eigenvalue and consumes its replay token', async () => {
    const f = await fixture(observation(true))
    const numerical = await verifier.verify(f.raw, MODEL, POLICY)
    expect(numerical).toMatchObject({
      status: 'DENY', reasons: ['PSD_VIOLATION'], metrics: { minimum_eigenvalue: -0.1 },
    })
    await expect(f.gate.evaluate(f.signed, f.receipt, f.batch, f.raw, MODEL, POLICY)).resolves.toMatchObject({
      status: 'DENY', reason: 'PHYSICS_DENIED', calibration_consumed: true,
      physics_result_digest: await hashValue(numerical),
    })
    await expect(f.gate.evaluate(f.signed, f.receipt, f.batch, f.raw, MODEL, POLICY)).resolves.toMatchObject({
      status: 'DENY', reason: 'CALIBRATION_DENIED', calibration_reason: 'BATCH_REPLAY',
      calibration_consumed: false, physics_result_digest: null,
    })
  }, TIMEOUT)

  it('rejects replay after a successful physics evaluation', async () => {
    const f = await fixture()
    await expect(f.gate.evaluate(f.signed, f.receipt, f.batch, f.raw, MODEL, POLICY))
      .resolves.toMatchObject({ status: 'PASS_RESEARCH_ONLY' })
    await expect(f.gate.evaluate(f.signed, f.receipt, f.batch, f.raw, MODEL, POLICY)).resolves.toMatchObject({
      status: 'DENY', reason: 'CALIBRATION_DENIED', calibration_reason: 'BATCH_REPLAY',
      calibration_consumed: false, physics_result_digest: null,
    })
  }, TIMEOUT)

  it('rejects modified signed data before calibration consumption or numerical admission', async () => {
    const f = await fixture()
    const altered = { ...f.raw, times_seconds: [0, 0.02, 0.04] }
    await expect(f.gate.evaluate(f.signed, f.receipt, f.batch, altered, MODEL, POLICY)).resolves.toMatchObject({
      status: 'DENY', reason: 'RAW_BATCH_BINDING_MISMATCH',
      calibration_consumed: false, physics_result_digest: null,
    })
    await expect(f.gate.evaluate(f.signed, f.receipt, f.batch, f.raw, MODEL, POLICY))
      .resolves.toMatchObject({ status: 'PASS_RESEARCH_ONLY' })
  }, TIMEOUT)

  it('refuses to construct a verifier against the wrong explicit identity pin', async () => {
    const wrong = (verifier.digest.startsWith('0') ? '1' : '0').repeat(64) as SHA256Hex
    await expect(createPinnedPythonVerifier({
      ...location, expectedIdentityDigest: wrong, expectedIdentity: approvedIdentity,
    }))
      .rejects.toThrow('IFG_IDENTITY_PIN_MISMATCH')
  }, TIMEOUT)

  it('rejects changed runner bytes before executing them during verification or construction', async () => {
    const temporary = await mkdtemp(join(tmpdir(), 'aegisq-ifg-pin-test-'))
    try {
      const copied = join(temporary, 'aegisq-ifg')
      await cp(location.packageDirectory, copied, { recursive: true })
      const copiedVerifier = await createPinnedPythonVerifier({
        pythonExecutable: location.pythonExecutable,
        packageDirectory: copied,
        expectedIdentityDigest: verifier.digest,
        expectedIdentity: approvedIdentity,
      })
      const sentinel = join(copied, 'unapproved-source-executed')
      await writeFile(join(copied, 'run_ifg.py'), [
        'from pathlib import Path',
        "Path(__file__).with_name('unapproved-source-executed').write_text('EXECUTED')",
        "print('{}')",
        '',
      ].join('\n'))
      await expect(copiedVerifier.verify(observation(), MODEL, POLICY))
        .rejects.toThrow('IFG_IDENTITY_PIN_MISMATCH')
      await expect(access(sentinel)).rejects.toMatchObject({ code: 'ENOENT' })
      await expect(createPinnedPythonVerifier({
        pythonExecutable: location.pythonExecutable,
        packageDirectory: copied,
        expectedIdentityDigest: verifier.digest,
        expectedIdentity: approvedIdentity,
      })).rejects.toThrow('IFG_IDENTITY_PIN_MISMATCH')
      await expect(access(sentinel)).rejects.toMatchObject({ code: 'ENOENT' })
    } finally {
      await rm(temporary, { recursive: true, force: true })
    }
  }, TIMEOUT)

  it('rejects a substituted executable before it can create a sentinel', async () => {
    const temporary = await mkdtemp(join(tmpdir(), 'aegisq-ifg-executable-test-'))
    try {
      const executable = join(temporary, 'unapproved-python')
      const sentinel = join(temporary, 'unapproved-executable-ran')
      await writeFile(executable, [
        `#!${location.pythonExecutable}`,
        'from pathlib import Path',
        "Path(__file__).with_name('unapproved-executable-ran').write_text('EXECUTED')",
        "print('{}')",
        '',
      ].join('\n'))
      await chmod(executable, 0o755)
      await expect(createPinnedPythonVerifier({
        pythonExecutable: executable,
        packageDirectory: location.packageDirectory,
        expectedIdentityDigest: verifier.digest,
        expectedIdentity: approvedIdentity,
      })).rejects.toThrow('IFG_IDENTITY_PIN_MISMATCH')
      await expect(access(sentinel)).rejects.toMatchObject({ code: 'ENOENT' })
    } finally {
      await rm(temporary, { recursive: true, force: true })
    }
  }, TIMEOUT)

  it('fails closed on unexpected fields at the Python wire boundary', async () => {
    await expect(verifier.verify({ ...observation(), unexpected_field: true }, MODEL, POLICY))
      .rejects.toThrow('IFG_TOOLCHAIN_EXECUTION_FAILED')
  }, TIMEOUT)
})
