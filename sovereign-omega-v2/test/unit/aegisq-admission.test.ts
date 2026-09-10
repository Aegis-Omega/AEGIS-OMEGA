import { describe, expect, it, vi } from 'vitest'
import { generateKeypair, signBytes } from '../../src/consensus/crypto.js'
import { hashValue } from '../../src/core/hashing.js'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  calibrationReceiptDigest, signCalibrationReceipt,
  type CalibrationReceiptPayloadV1, type MeasurementBatchEnvelopeV1,
} from '../../src/calibration/quanphotonic.js'
import {
  AegisQAdmissionGate, AEGISQ_REQUEST_VERSION, signAegisQRequest,
  type AegisQAdmissionConfig, type AegisQRequestPayloadV1,
} from '../../src/research/aegisq-admission.js'

const HEX = 'a'.repeat(64) as SHA256Hex
const VERIFIER = 'f'.repeat(64) as SHA256Hex
const POLICY = {
  eigenvalue_tolerance: 1e-10, hermiticity_tolerance: 1e-10, trace_tolerance: 1e-9,
  midpoint_residual_per_second: 1e-3, transition_residual: 1e-5,
  probability_residual: 1e-3, identifiability_rtol: 1e-9, max_dimension: 16,
}

// Explicit unit fixture; actual pinned Python execution has a separate e2e test.
function physicsFixture(policy: unknown = POLICY) {
  return {
    status: 'PASS_RESEARCH_ONLY', reasons: [] as string[],
    metrics: {
      hamiltonian_hermiticity_error_per_second: 0, max_hermiticity_error: 0,
      max_trace_error: 0, minimum_eigenvalue: 0, measurement_rank: 3,
      required_measurement_rank: 3, max_probability_residual: 0,
      max_midpoint_residual_per_second: 0, max_transition_residual: 0,
    },
    policy, scope: 'FINITE_SAMPLED_MODEL_CONSISTENCY_ONLY',
    calibration_authority: 'NOT_VERIFIED_BY_THIS_MODULE', clinical_admission: false,
    quantum_nonclassicality: 'NOT_TESTED_BY_PHYSICAL_GATE',
  }
}

async function fixture() {
  const calibrationKey = await generateKeypair(new Uint8Array(32).fill(7))
  const producerKey = await generateKeypair(new Uint8Array(32).fill(8))
  const calibrationPayload: CalibrationReceiptPayloadV1 = {
    schema_version: 'QUANPHOTONIC_CALIBRATION_RECEIPT_V1',
    calibration_epoch_id: 'epoch-1', detector_id: 'detector-1',
    detector_configuration_digest: HEX, sequence: '10', valid_from_sequence: '10',
    valid_until_sequence: '99', previous_receipt_digest: null,
    raw_calibration_digest: HEX, calibration_code_commit: 'a'.repeat(40),
    reference_source_ids: ['synthetic-dark-reference'], calibration_status: 'PASS',
    parameters: { background_rate_hz: '0', spectral_efficiency_model_digest: HEX,
      afterpulse_kernel_digest: HEX, dead_time_ps: '0', jitter_ps_rms: '0',
      gain: '1', pileup_model_digest: HEX },
  }
  const receipt = await signCalibrationReceipt(calibrationPayload, 'calibration-1', calibrationKey.privateKey)
  const raw = { counts: [1, 0, 2], provenance: 'SYNTHETIC_UNIT_FIXTURE' }
  const model = { version: 'unit-model-1', hamiltonian: [[0, 0], [0, 0]] }
  const policy = { ...POLICY }
  const batch: MeasurementBatchEnvelopeV1 = {
    schema_version: 'QUANPHOTONIC_MEASUREMENT_BATCH_V1', measurement_batch_id: 'batch-1',
    measurement_batch_digest: await hashValue(raw), calibration_receipt_digest: await calibrationReceiptDigest(receipt),
    calibration_epoch_id: calibrationPayload.calibration_epoch_id,
    detector_id: calibrationPayload.detector_id, detector_configuration_digest: HEX, sequence: '11',
  }
  const payload: AegisQRequestPayloadV1 = {
    schema_version: AEGISQ_REQUEST_VERSION, job_id: 'job-1', scope: 'RESEARCH_ONLY',
    raw_batch_digest: await hashValue(raw), calibration_receipt_digest: await calibrationReceiptDigest(receipt),
    measurement_envelope_digest: await hashValue(batch), model_digest: await hashValue(model),
    policy_digest: await hashValue(policy), verifier_digest: VERIFIER,
  }
  const request = await signAegisQRequest(payload, 'producer-1', producerKey.privateKey)
  const verify = vi.fn(async (_raw: unknown, _model: unknown, p: unknown) => physicsFixture(p))
  const config: AegisQAdmissionConfig = {
    trustedCalibrationKeys: { 'calibration-1': calibrationKey.publicKey },
    trustedProducerKeys: { 'producer-1': producerKey.publicKey },
    modelDigest: payload.model_digest, policyDigest: payload.policy_digest,
    verifier: { digest: VERIFIER, verify },
  }
  return { calibrationKey, producerKey, receipt, raw, model, policy, batch, payload, request, config, verify,
    gate: new AegisQAdmissionGate(config) }
}

describe('AegisQ signed research admission', () => {
  it('binds producer request, calibration, batch, parameters, verifier, and bounded result', async () => {
    const f = await fixture()
    const result = await f.gate.evaluate(f.request, f.receipt, f.batch, f.raw, f.model, f.policy)
    expect(result).toMatchObject({ status: 'PASS_RESEARCH_ONLY', scope: 'RESEARCH_ONLY',
      clinical_admission: false, calibration_consumed: true, replay_protection: 'IN_PROCESS_ONLY',
      reason: 'BOUND_RESEARCH_INFERENCE_VERIFIED',
      bindings: { ...Object.fromEntries(Object.entries(f.payload).filter(([key]) => key.endsWith('_digest'))),
        request_payload_digest: f.request.payload_digest } })
    expect(f.verify).toHaveBeenCalledOnce()
    expect(Object.isFrozen(result)).toBe(true)
    expect(Object.isFrozen(result.bindings)).toBe(true)
    const { receipt_digest: receiptDigest, ...body } = result
    expect(receiptDigest).toBe(await hashValue(body))
    expect(result.physics_result).toEqual(physicsFixture(f.policy))
    expect(Object.isFrozen(result.physics_result)).toBe(true)
    expect(Object.isFrozen(result.physics_result!.metrics)).toBe(true)
    expect(result.physics_result_digest).toBe(await hashValue(result.physics_result))
  })

  it('rejects replay and concurrent replay through the real calibration gate', async () => {
    const f = await fixture()
    const results = await Promise.all([0, 1].map(() => f.gate.evaluate(f.request, f.receipt, f.batch, f.raw, f.model, f.policy)))
    expect(results.map(r => r.status).sort()).toEqual(['DENY', 'PASS_RESEARCH_ONLY'])
    expect(results.find(r => r.status === 'DENY')).toMatchObject({ reason: 'CALIBRATION_DENIED', calibration_reason: 'BATCH_REPLAY' })
    expect(f.verify).toHaveBeenCalledOnce()
  })

  it.each([
    ['raw_batch_digest', 'RAW_BATCH_BINDING_MISMATCH'],
    ['calibration_receipt_digest', 'CALIBRATION_BINDING_MISMATCH'],
    ['measurement_envelope_digest', 'MEASUREMENT_ENVELOPE_BINDING_MISMATCH'],
    ['model_digest', 'MODEL_PIN_MISMATCH'], ['policy_digest', 'POLICY_PIN_MISMATCH'],
    ['verifier_digest', 'VERIFIER_PIN_MISMATCH'],
  ] as const)('rejects signed substitution of %s', async (field, reason) => {
    const f = await fixture()
    const request = await signAegisQRequest({ ...f.payload, [field]: HEX }, 'producer-1', f.producerKey.privateKey)
    expect(await f.gate.evaluate(request, f.receipt, f.batch, f.raw, f.model, f.policy)).toMatchObject({ status: 'DENY', reason, calibration_consumed: false })
    expect(f.verify).not.toHaveBeenCalled()
  })

  it.each([
    ['raw', 'RAW_BATCH_BINDING_MISMATCH'], ['batch', 'MEASUREMENT_ENVELOPE_BINDING_MISMATCH'],
    ['model', 'MODEL_BINDING_MISMATCH'], ['policy', 'POLICY_BINDING_MISMATCH'],
  ] as const)('recomputes %s bytes rather than trusting request digests', async (field, reason) => {
    const f = await fixture()
    const changed = { ...f[field], extra: true }
    expect(await f.gate.evaluate(f.request, f.receipt, field === 'batch' ? changed : f.batch,
      field === 'raw' ? changed : f.raw, field === 'model' ? changed : f.model,
      field === 'policy' ? changed : f.policy)).toMatchObject({ status: 'DENY', reason })
    expect(f.verify).not.toHaveBeenCalled()
  })

  it('denies receipt payload tampering even when its envelope digest is unchanged', async () => {
    const f = await fixture()
    const receipt = { ...f.receipt, payload: { ...f.receipt.payload, detector_id: 'other' } }
    expect(await f.gate.evaluate(f.request, receipt, f.batch, f.raw, f.model, f.policy)).toMatchObject({
      status: 'DENY', reason: 'CALIBRATION_DENIED', calibration_reason: 'PAYLOAD_DIGEST_MISMATCH' })
  })

  it('rejects matching request and caller policy when operator pin differs', async () => {
    const f = await fixture()
    const policy = { ...f.policy, transition_residual: 1e8 }
    const request = await signAegisQRequest({ ...f.payload, policy_digest: await hashValue(policy) }, 'producer-1', f.producerKey.privateKey)
    expect(await f.gate.evaluate(request, f.receipt, f.batch, f.raw, f.model, policy)).toMatchObject({ reason: 'POLICY_PIN_MISMATCH' })
  })

  it('rejects matching request and caller model when operator pin differs', async () => {
    const f = await fixture()
    const model = { ...f.model, version: 'different' }
    const request = await signAegisQRequest({ ...f.payload, model_digest: await hashValue(model) }, 'producer-1', f.producerKey.privateKey)
    expect(await f.gate.evaluate(request, f.receipt, f.batch, f.raw, model, f.policy)).toMatchObject({ reason: 'MODEL_PIN_MISMATCH' })
  })

  it.each(['digest', 'signature', 'unknown-key', 'wrong-key', 'no-domain'] as const)('rejects %s authentication failure', async mode => {
    const f = await fixture()
    let request = { ...f.request }
    if (mode === 'digest') request = { ...request, payload: { ...request.payload, job_id: 'other' } }
    if (mode === 'signature') request.signature = '0'.repeat(128)
    if (mode === 'unknown-key') request.signer_key_id = 'unknown'
    if (mode === 'wrong-key') request.signature = await signBytes(f.calibrationKey.privateKey, new TextEncoder().encode(`${AEGISQ_REQUEST_VERSION}:${request.payload_digest}`))
    if (mode === 'no-domain') request.signature = await signBytes(f.producerKey.privateKey, new TextEncoder().encode(request.payload_digest))
    expect(await f.gate.evaluate(request, f.receipt, f.batch, f.raw, f.model, f.policy)).toMatchObject({ status: 'DENY', calibration_consumed: false })
    expect(f.verify).not.toHaveBeenCalled()
  })

  it.each([
    null, { status: 'PASS_RESEARCH_ONLY' },
    { ...physicsFixture(), status: 'PASS' },
    { ...physicsFixture(), status: 'DENY' },
    { ...physicsFixture(), reasons: ['PSD_VIOLATION'] },
    { ...physicsFixture(), scope: 'CLINICAL' },
    { ...physicsFixture(), clinical_admission: true },
    { ...physicsFixture(), metrics: {} },
    { ...physicsFixture(), metrics: { ...physicsFixture().metrics, minimum_eigenvalue: -0.1 } },
    { ...physicsFixture(), metrics: { ...physicsFixture().metrics, measurement_rank: 2 } },
    { ...physicsFixture(), metrics: { ...physicsFixture().metrics, max_transition_residual: 1 } },
    { ...physicsFixture(), metrics: { ...physicsFixture().metrics, max_trace_error: NaN } },
    { ...physicsFixture(), extra: 'UNREQUESTED_AUTHORITY' },
  ])('fails closed on malformed or contradictory verifier output %#', async output => {
    const f = await fixture()
    const gate = new AegisQAdmissionGate({ ...f.config, verifier: { digest: VERIFIER, verify: async () => output } })
    expect(await gate.evaluate(f.request, f.receipt, f.batch, f.raw, f.model, f.policy)).toMatchObject({
      status: 'DENY', reason: 'MALFORMED_VERIFIER_RESULT', calibration_consumed: true })
  })

  it('checks the actual verifier policy and consumes failed attempts only once', async () => {
    const f = await fixture()
    const gate = new AegisQAdmissionGate({ ...f.config, verifier: { digest: VERIFIER,
      verify: async () => physicsFixture({ ...POLICY, transition_residual: 1 }) } })
    expect(await gate.evaluate(f.request, f.receipt, f.batch, f.raw, f.model, f.policy)).toMatchObject({
      status: 'DENY', reason: 'VERIFIER_POLICY_MISMATCH', calibration_consumed: true })
    expect(await gate.evaluate(f.request, f.receipt, f.batch, f.raw, f.model, f.policy)).toMatchObject({
      status: 'DENY', reason: 'CALIBRATION_DENIED', calibration_reason: 'BATCH_REPLAY' })
  })

  it('records an actual verifier denial without promoting it', async () => {
    const f = await fixture()
    const gate = new AegisQAdmissionGate({ ...f.config, verifier: { digest: VERIFIER,
      verify: async () => ({ ...physicsFixture(), status: 'DENY', reasons: ['PSD_VIOLATION'], metrics: { minimum_eigenvalue: -0.1 } }) } })
    const result = await gate.evaluate(f.request, f.receipt, f.batch, f.raw, f.model, f.policy)
    expect(result).toMatchObject({ status: 'DENY', reason: 'PHYSICS_DENIED',
      calibration_consumed: true, clinical_admission: false,
      physics_result: { reasons: ['PSD_VIOLATION'], metrics: { minimum_eigenvalue: -0.1 } } })
    expect(result.physics_result_digest).toBe(await hashValue(result.physics_result))
  })

  it('denies a verifier exception without rolling back calibration consumption', async () => {
    const f = await fixture()
    const gate = new AegisQAdmissionGate({ ...f.config, verifier: { digest: VERIFIER,
      verify: async () => { throw new Error('fixture crash') } } })
    expect(await gate.evaluate(f.request, f.receipt, f.batch, f.raw, f.model, f.policy)).toMatchObject({
      status: 'DENY', reason: 'VERIFIER_EXECUTION_FAILED', calibration_consumed: true })
    expect(await gate.evaluate(f.request, f.receipt, f.batch, f.raw, f.model, f.policy)).toMatchObject({ calibration_reason: 'BATCH_REPLAY' })
  })

  it.each([
    NaN, Infinity, Number.MAX_SAFE_INTEGER + 1, undefined, 1n,
    { text: '\uD800' }, { text: '\u03c1' }, { '\u03c1': 1 },
    new Date(0), new Uint8Array([1]), [1, , 3], { value: undefined },
    Object.defineProperty({}, 'hidden', { value: 1 }),
    Object.defineProperty({}, 'getter', { get: () => { throw new Error('must not run') }, enumerable: true }),
    { [Symbol('key')]: 1 },
  ])('rejects nonportable JSON before verifier execution %#', async badRaw => {
    const f = await fixture()
    expect(await f.gate.evaluate(f.request, f.receipt, f.batch, badRaw, f.model, f.policy)).toMatchObject({
      status: 'DENY', reason: 'NON_PORTABLE_INPUT', calibration_consumed: false })
    expect(f.verify).not.toHaveBeenCalled()
  })

  it('rejects cycles and custom prototypes', async () => {
    const f = await fixture()
    const cyclic: Record<string, unknown> = {}
    cyclic.self = cyclic
    for (const raw of [cyclic, Object.create({ inherited: 1 }) as unknown]) {
      expect(await f.gate.evaluate(f.request, f.receipt, f.batch, raw, f.model, f.policy)).toMatchObject({ reason: 'NON_PORTABLE_INPUT' })
    }
  })

  it.each([
    { scope: 'CLINICAL' }, { schema_version: 'AEGISQ_INFERENCE_REQUEST_V2' },
    { job_id: '' }, { caller_physics: { status: 'PASS_RESEARCH_ONLY' } },
  ])('rejects unknown request fields, empty identity, scope and version %#', async overrides => {
    const f = await fixture()
    const request = { ...f.request, payload: { ...f.payload, ...overrides } }
    expect(await f.gate.evaluate(request, f.receipt, f.batch, f.raw, f.model, f.policy)).toMatchObject({ reason: 'MALFORMED_REQUEST' })
    await expect(signAegisQRequest(request.payload as AegisQRequestPayloadV1, 'producer-1', f.producerKey.privateKey)).rejects.toThrow()
  })

  it('rejects unknown envelope fields and inherited producer key names', async () => {
    const f = await fixture()
    expect(await f.gate.evaluate({ ...f.request, supplied_pass: true }, f.receipt, f.batch, f.raw, f.model, f.policy)).toMatchObject({ reason: 'MALFORMED_REQUEST' })
    expect(await f.gate.evaluate({ ...f.request, signer_key_id: 'toString' }, f.receipt, f.batch, f.raw, f.model, f.policy)).toMatchObject({ reason: 'UNTRUSTED_PRODUCER' })
  })

  it('snapshots ALL inputs before first await and freezes verifier arguments', async () => {
    const f = await fixture()
    const request = structuredClone(f.request)
    const receipt = structuredClone(f.receipt)
    const batch = { ...f.batch }
    const raw = structuredClone(f.raw)
    const model = structuredClone(f.model)
    const policy = { ...f.policy }
    const pending = f.gate.evaluate(request, receipt, batch, raw, model, policy)
    ;(request as unknown as Record<string, unknown>).signature = '0'.repeat(128)
    ;(receipt.payload as unknown as Record<string, unknown>).detector_id = 'mutated'
    batch.sequence = '12'
    raw.counts[0] = 999
    model.hamiltonian[0]![0] = 999
    policy.transition_residual = 999
    const result = await pending
    expect(result.status).toBe('PASS_RESEARCH_ONLY')
    const [seenRaw, seenModel, seenPolicy] = f.verify.mock.calls[0]!
    expect(seenRaw).toEqual(f.raw)
    expect(seenModel).toEqual(f.model)
    expect(seenPolicy).toEqual(f.policy)
    for (const value of [seenRaw, seenModel, seenPolicy]) expect(Object.isFrozen(value)).toBe(true)
    expect(Object.isFrozen((seenRaw as typeof f.raw).counts)).toBe(true)
  })

  it('holds snapshots while verifier awaits and freezes operator pins/keys/method reference', async () => {
    const f = await fixture()
    let release!: () => void
    const waiting = new Promise<void>(resolve => { release = resolve })
    let entered!: () => void
    const started = new Promise<void>(resolve => { entered = resolve })
    const verifier = { digest: VERIFIER, verify: async (raw: unknown, model: unknown, policy: unknown) => {
      entered()
      await waiting
      expect(raw).toEqual(f.raw)
      expect(model).toEqual(f.model)
      expect(policy).toEqual(f.policy)
      return physicsFixture(policy)
    } }
    const mutableConfig = { ...f.config, trustedProducerKeys: { ...f.config.trustedProducerKeys }, verifier }
    const gate = new AegisQAdmissionGate(mutableConfig)
    mutableConfig.trustedProducerKeys['producer-1'] = '0'.repeat(64)
    mutableConfig.policyDigest = HEX
    verifier.digest = HEX
    const raw = structuredClone(f.raw)
    const model = structuredClone(f.model)
    const policy = { ...f.policy }
    const pending = gate.evaluate(f.request, f.receipt, f.batch, raw, model, policy)
    await started
    raw.counts[0] = 900
    model.version = 'mutated'
    policy.transition_residual = 900
    verifier.verify = async () => { throw new Error('replaced method') }
    release()
    expect((await pending).status).toBe('PASS_RESEARCH_ONLY')
  })

  it('uses injected replay authority and denies persistence failure before verifier', async () => {
    const f = await fixture()
    const admit = vi.fn(async () => { throw new Error('offline') })
    const gate = new AegisQAdmissionGate({ ...f.config, replayAuthority: { admit } })
    expect(await gate.evaluate(f.request, f.receipt, f.batch, f.raw, f.model, f.policy)).toMatchObject({
      status: 'DENY', calibration_reason: 'PERSISTENCE_UNAVAILABLE',
      calibration_consumed: false, replay_protection: 'EXTERNAL_AUTHORITY' })
    expect(admit).toHaveBeenCalledOnce()
    expect(f.verify).not.toHaveBeenCalled()
  })

  it.each([null, false, 1, 'external', {}, { admit: null }, { admit: 'PASS' }])(
    'rejects explicitly malformed external replay authority %# instead of downgrading', async replayAuthority => {
      const f = await fixture()
      expect(() => new AegisQAdmissionGate({ ...f.config, replayAuthority } as unknown as AegisQAdmissionConfig)).toThrow('Invalid replay authority')
    },
  )
})
