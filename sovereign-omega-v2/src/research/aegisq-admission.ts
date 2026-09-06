// Research integration only: authenticates a producer's request and invokes an
// operator-pinned verifier. Ed25519 is not PQC; signatures do not establish
// instrument accuracy, independent experimentation, or clinical validity.
import type { SHA256Hex } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import { signBytes, verifyBytes } from '../consensus/crypto.js'
import {
  QuanPhotonicCalibrationGate,
  calibrationReceiptDigest,
  type SignedCalibrationReceiptV1,
  type QuanPhotonicReplayAuthority,
  type CalibrationRejectionReason,
} from '../calibration/quanphotonic.js'

export const AEGISQ_REQUEST_VERSION = 'AEGISQ_INFERENCE_REQUEST_V1' as const

export interface AegisQRequestPayloadV1 {
  readonly schema_version: typeof AEGISQ_REQUEST_VERSION
  readonly job_id: string
  readonly scope: 'RESEARCH_ONLY'
  readonly raw_batch_digest: SHA256Hex
  readonly calibration_receipt_digest: SHA256Hex
  readonly measurement_envelope_digest: SHA256Hex
  readonly model_digest: SHA256Hex
  readonly policy_digest: SHA256Hex
  readonly verifier_digest: SHA256Hex
}

export interface SignedAegisQRequestV1 {
  readonly payload: AegisQRequestPayloadV1
  readonly payload_digest: SHA256Hex
  readonly signature_algorithm: 'Ed25519'
  readonly signer_key_id: string
  readonly signature: string
}

/** Trusted operator injection, never accepted from an inference request. */
export interface AegisQVerifier {
  readonly digest: SHA256Hex
  verify(raw: unknown, model: unknown, policy: unknown): Promise<unknown>
}

export interface AegisQAdmissionConfig {
  readonly trustedCalibrationKeys: Readonly<Record<string, string>>
  readonly trustedProducerKeys: Readonly<Record<string, string>>
  readonly modelDigest: SHA256Hex
  readonly policyDigest: SHA256Hex
  readonly verifier: AegisQVerifier
  readonly replayAuthority?: QuanPhotonicReplayAuthority
}

export type AegisQAdmissionReason =
  | 'BOUND_RESEARCH_INFERENCE_VERIFIED'
  | 'NON_PORTABLE_INPUT' | 'MALFORMED_REQUEST' | 'REQUEST_DIGEST_MISMATCH'
  | 'UNTRUSTED_PRODUCER' | 'REQUEST_SIGNATURE_INVALID'
  | 'MODEL_PIN_MISMATCH' | 'POLICY_PIN_MISMATCH' | 'VERIFIER_PIN_MISMATCH'
  | 'RAW_BATCH_BINDING_MISMATCH' | 'CALIBRATION_BINDING_MISMATCH'
  | 'MEASUREMENT_ENVELOPE_BINDING_MISMATCH' | 'MODEL_BINDING_MISMATCH'
  | 'POLICY_BINDING_MISMATCH' | 'CALIBRATION_DENIED'
  | 'VERIFIER_EXECUTION_FAILED' | 'MALFORMED_VERIFIER_RESULT'
  | 'VERIFIER_POLICY_MISMATCH' | 'PHYSICS_DENIED' | 'INPUT_PROCESSING_FAILED'

export interface AegisQBoundDigestsV1 {
  readonly request_payload_digest: SHA256Hex
  readonly raw_batch_digest: SHA256Hex
  readonly calibration_receipt_digest: SHA256Hex
  readonly measurement_envelope_digest: SHA256Hex
  readonly model_digest: SHA256Hex
  readonly policy_digest: SHA256Hex
  readonly verifier_digest: SHA256Hex
}

export interface AegisQAdmissionResultV1 {
  readonly schema_version: 'AEGISQ_ADMISSION_RESULT_V1'
  readonly status: 'PASS_RESEARCH_ONLY' | 'DENY'
  readonly reason: AegisQAdmissionReason
  readonly scope: 'RESEARCH_ONLY'
  readonly clinical_admission: false
  readonly bindings: AegisQBoundDigestsV1 | null
  readonly physics_result: Readonly<Record<string, unknown>> | null
  readonly physics_result_digest: SHA256Hex | null
  readonly calibration_reason: CalibrationRejectionReason | null
  readonly calibration_consumed: boolean
  readonly replay_protection: 'IN_PROCESS_ONLY' | 'EXTERNAL_AUTHORITY'
  readonly receipt_digest: SHA256Hex
}

const DIGEST = /^[0-9a-f]{64}$/
const ASCII = /^[\x00-\x7f]*$/
const PAYLOAD_KEYS = [
  'schema_version', 'job_id', 'scope', 'raw_batch_digest',
  'calibration_receipt_digest', 'measurement_envelope_digest',
  'model_digest', 'policy_digest', 'verifier_digest',
] as const
const DIGEST_KEYS = PAYLOAD_KEYS.slice(3)
const POLICY_KEYS = [
  'eigenvalue_tolerance', 'hermiticity_tolerance', 'trace_tolerance',
  'midpoint_residual_per_second', 'transition_residual', 'probability_residual',
  'identifiability_rtol', 'max_dimension',
] as const
const METRIC_KEYS = [
  'hamiltonian_hermiticity_error_per_second', 'max_hermiticity_error',
  'max_trace_error', 'minimum_eigenvalue', 'measurement_rank',
  'required_measurement_rank', 'max_probability_residual',
  'max_midpoint_residual_per_second', 'max_transition_residual',
] as const
const PHYSICS_REASONS = [
  'NON_NUMERIC_OR_WRONG_DTYPE', 'NONFINITE_INPUT', 'NUMERICAL_OR_INPUT_FAILURE',
  'NONFINITE_METRIC', 'INVALID_STATE_SHAPE', 'INVALID_TIME_GRID',
  'INVALID_HAMILTONIAN_SHAPE', 'INVALID_JUMP_SHAPE', 'NON_HERMITIAN_HAMILTONIAN',
  'NON_HERMITIAN_STATE', 'TRACE_VIOLATION', 'PSD_VIOLATION', 'INVALID_POVM_SHAPE',
  'INVALID_PROBABILITY_SHAPE', 'INVALID_POVM', 'NOT_IDENTIFIABLE',
  'INVALID_PROBABILITIES', 'MEASUREMENT_MISMATCH', 'LINDBLAD_RESIDUAL',
  'TRANSITION_MISMATCH',
] as const

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}
function exactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).sort().join('|') === [...keys].sort().join('|')
}
function digest(value: unknown): value is SHA256Hex {
  return typeof value === 'string' && DIGEST.test(value)
}
function nonempty(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0 && ASCII.test(value)
}

/**
 * Synchronous copy before any await. This restricts the existing canonicalizer
 * to its ASCII, finite-number JCS subset. No getters, sparse arrays, custom
 * prototypes, hidden properties, symbols, cycles, or undefined are admitted.
 * Negative zero is normalized to zero. Bounds cap local traversal work.
 */
function snapshot(value: unknown): unknown {
  const active = new WeakSet<object>()
  let remaining = 1_000_000
  function copy(input: unknown, depth: number): unknown {
    if (--remaining < 0 || depth > 64) throw new Error('INPUT_LIMIT')
    if (input === null || typeof input === 'boolean') return input
    if (typeof input === 'string') {
      if (input.length > 1_000_000 || !ASCII.test(input)) throw new Error('NON_ASCII')
      return input
    }
    if (typeof input === 'number') {
      if (!Number.isFinite(input) || Math.abs(input) > Number.MAX_SAFE_INTEGER) throw new Error('UNSAFE_NUMBER')
      return Object.is(input, -0) ? 0 : input
    }
    if (typeof input !== 'object') throw new Error('NON_JSON')
    if (active.has(input)) throw new Error('CYCLE')
    const array = Array.isArray(input)
    const proto: unknown = Object.getPrototypeOf(input)
    if (proto !== (array ? Array.prototype : Object.prototype) && (array || proto !== null)) throw new Error('PROTOTYPE')
    active.add(input)
    const keys = Reflect.ownKeys(input)
    const output: unknown[] | Record<string, unknown> = array ? [] : Object.create(null) as Record<string, unknown>
    if (array && keys.length !== input.length + 1) throw new Error('SPARSE_OR_EXTRA_ARRAY_PROPERTIES')
    for (const key of keys) {
      if (typeof key !== 'string' || !ASCII.test(key)) throw new Error('NON_ASCII_KEY')
      const descriptor = Object.getOwnPropertyDescriptor(input, key)
      if (!descriptor || !('value' in descriptor)) throw new Error('ACCESSOR')
      if (array && key === 'length') continue
      if (!descriptor.enumerable) throw new Error('HIDDEN_PROPERTY')
      if (array && !/^(0|[1-9][0-9]*)$/.test(key)) throw new Error('ARRAY_PROPERTY')
      Object.defineProperty(output, key, {
        value: copy(descriptor.value, depth + 1), enumerable: true,
        configurable: false, writable: false,
      })
    }
    if (array && (output as unknown[]).length !== input.length) throw new Error('SPARSE_ARRAY')
    active.delete(input)
    return Object.freeze(output)
  }
  return copy(value, 0)
}

function payloadShape(value: unknown): value is AegisQRequestPayloadV1 {
  return record(value) && exactKeys(value, PAYLOAD_KEYS)
    && value.schema_version === AEGISQ_REQUEST_VERSION && nonempty(value.job_id)
    && value.scope === 'RESEARCH_ONLY' && DIGEST_KEYS.every(key => digest(value[key]))
}
function requestShape(value: unknown): value is SignedAegisQRequestV1 {
  return record(value) && exactKeys(value, ['payload', 'payload_digest', 'signature_algorithm', 'signer_key_id', 'signature'])
    && payloadShape(value.payload) && digest(value.payload_digest)
    && value.signature_algorithm === 'Ed25519' && nonempty(value.signer_key_id)
    && typeof value.signature === 'string' && /^[0-9a-f]{128}$/.test(value.signature)
}
function requestMessage(payloadDigest: SHA256Hex): Uint8Array {
  return new TextEncoder().encode(`${AEGISQ_REQUEST_VERSION}:${payloadDigest}`)
}

export async function signAegisQRequest(
  payload: AegisQRequestPayloadV1, signerKeyId: string, privateKey: Uint8Array,
): Promise<SignedAegisQRequestV1> {
  const stable = snapshot(payload)
  const stableKey = privateKey.slice()
  if (!payloadShape(stable) || !nonempty(signerKeyId)) throw new Error('Malformed AegisQ request')
  const payloadDigest = await hashValue(stable)
  const signature = await signBytes(stableKey, requestMessage(payloadDigest))
  return deepFreeze({ payload: stable, payload_digest: payloadDigest,
    signature_algorithm: 'Ed25519' as const, signer_key_id: signerKeyId, signature })
}

function physicsShape(value: unknown): value is Record<string, unknown> & { policy: Record<string, number> } {
  if (!record(value) || !exactKeys(value, [
    'status', 'reasons', 'metrics', 'policy', 'scope', 'calibration_authority',
    'clinical_admission', 'quantum_nonclassicality',
  ]) || value.scope !== 'FINITE_SAMPLED_MODEL_CONSISTENCY_ONLY'
    || value.calibration_authority !== 'NOT_VERIFIED_BY_THIS_MODULE'
    || value.clinical_admission !== false
    || value.quantum_nonclassicality !== 'NOT_TESTED_BY_PHYSICAL_GATE'
    || !Array.isArray(value.reasons) || !record(value.metrics) || !record(value.policy)) return false
  if (!exactKeys(value.policy, POLICY_KEYS)
    || !POLICY_KEYS.every(key => typeof value.policy === 'object'
      && (value.policy as Record<string, unknown>)[key] !== undefined
      && typeof (value.policy as Record<string, unknown>)[key] === 'number'
      && ((value.policy as Record<string, number>)[key] ?? 0) > 0)) return false
  const p = value.policy as Record<string, number>
  if (!Number.isInteger(p.max_dimension) || p.max_dimension! < 2 || p.max_dimension! > 32
    || p.identifiability_rtol! >= 1) return false
  if (!value.reasons.every(reason => typeof reason === 'string' && (PHYSICS_REASONS as readonly string[]).includes(reason))
    || new Set(value.reasons).size !== value.reasons.length) return false
  const m = value.metrics
  if (!Object.keys(m).every(key => (METRIC_KEYS as readonly string[]).includes(key)
    && (m[key] === null || typeof m[key] === 'number'))) return false
  if (value.status === 'DENY') return value.reasons.length > 0
  if (value.status !== 'PASS_RESEARCH_ONLY' || value.reasons.length !== 0 || !exactKeys(m, METRIC_KEYS)
    || !METRIC_KEYS.every(key => typeof m[key] === 'number')) return false
  const n = m as Record<string, number>
  if (!METRIC_KEYS.every(key => key === 'minimum_eigenvalue' || n[key]! >= 0)) return false
  const d = Math.sqrt(n.required_measurement_rank! + 1)
  return Number.isInteger(d) && d >= 2 && d <= p.max_dimension!
    && n.measurement_rank === n.required_measurement_rank
    && n.minimum_eigenvalue! >= -p.eigenvalue_tolerance!
    && n.hamiltonian_hermiticity_error_per_second! <= p.hermiticity_tolerance!
    && n.max_hermiticity_error! <= p.hermiticity_tolerance!
    && n.max_trace_error! <= p.trace_tolerance!
    && n.max_probability_residual! <= p.probability_residual!
    && n.max_midpoint_residual_per_second! <= p.midpoint_residual_per_second!
    && n.max_transition_residual! <= p.transition_residual!
}

export class AegisQAdmissionGate {
  private readonly calibration: QuanPhotonicCalibrationGate
  private readonly producerKeys: Readonly<Record<string, string>>
  private readonly modelDigest: SHA256Hex
  private readonly policyDigest: SHA256Hex
  private readonly verifierDigest: SHA256Hex
  private readonly verify: AegisQVerifier['verify']
  private readonly replayProtection: AegisQAdmissionResultV1['replay_protection']

  constructor(config: AegisQAdmissionConfig) {
    if (!digest(config.modelDigest) || !digest(config.policyDigest) || !digest(config.verifier.digest)
      || typeof config.verifier.verify !== 'function') throw new Error('Invalid operator pins')
    const replay: unknown = config.replayAuthority
    if (replay !== undefined && (replay === null || typeof replay !== 'object'
      || typeof (replay as { admit?: unknown }).admit !== 'function')) {
      throw new Error('Invalid replay authority; omit it for IN_PROCESS_ONLY replay protection')
    }
    const calibrationKeys = snapshot(config.trustedCalibrationKeys)
    const producerKeys = snapshot(config.trustedProducerKeys)
    for (const keys of [calibrationKeys, producerKeys]) {
      if (!record(keys) || !Object.entries(keys).every(([key, value]) => nonempty(key) && digest(value))) {
        throw new Error('Invalid trusted Ed25519 keys')
      }
    }
    this.producerKeys = producerKeys as Readonly<Record<string, string>>
    this.calibration = new QuanPhotonicCalibrationGate(calibrationKeys as Readonly<Record<string, string>>,
      config.replayAuthority === undefined ? null : config.replayAuthority)
    this.modelDigest = config.modelDigest
    this.policyDigest = config.policyDigest
    this.verifierDigest = config.verifier.digest
    this.verify = config.verifier.verify.bind(config.verifier)
    this.replayProtection = config.replayAuthority === undefined ? 'IN_PROCESS_ONLY' : 'EXTERNAL_AUTHORITY'
  }

  /**
   * Calibration replay state is consumed BEFORE verifier execution. A verifier
   * denial/crash does not roll it back; reuse requires a new measurement batch.
   * In-process replay state does not survive restart or coordinate other workers.
   */
  async evaluate(signedRequest: unknown, calibrationReceipt: unknown, batch: unknown,
    raw: unknown, model: unknown, policy: unknown): Promise<AegisQAdmissionResultV1> {
    let bindings: AegisQBoundDigestsV1 | null = null
    let consumed = false
    let physicsResult: Readonly<Record<string, unknown>> | null = null
    let physicsDigest: SHA256Hex | null = null
    const finish = async (reason: AegisQAdmissionReason, calibrationReason: CalibrationRejectionReason | null = null): Promise<AegisQAdmissionResultV1> => {
      const payload = deepFreeze({ schema_version: 'AEGISQ_ADMISSION_RESULT_V1' as const,
        status: reason === 'BOUND_RESEARCH_INFERENCE_VERIFIED' ? 'PASS_RESEARCH_ONLY' as const : 'DENY' as const,
        reason, scope: 'RESEARCH_ONLY' as const, clinical_admission: false as const,
        bindings, physics_result: physicsResult, physics_result_digest: physicsDigest, calibration_reason: calibrationReason,
        calibration_consumed: consumed, replay_protection: this.replayProtection })
      return deepFreeze({ ...payload, receipt_digest: await hashValue(payload) })
    }
    let inputs: unknown[]
    try {
      // Every input is copied before the first await anywhere in this method.
      inputs = [signedRequest, calibrationReceipt, batch, raw, model, policy].map(snapshot)
    } catch { return finish('NON_PORTABLE_INPUT') }
    const [request, receipt, envelope, stableRaw, stableModel, stablePolicy] = inputs
    if (!requestShape(request)) return finish('MALFORMED_REQUEST')
    try {
      const p = request.payload
      const requestDigest = await hashValue(p)
      if (requestDigest !== request.payload_digest) return finish('REQUEST_DIGEST_MISMATCH')
      const key = this.producerKeys[request.signer_key_id]
      if (key === undefined) return finish('UNTRUSTED_PRODUCER')
      if (!await verifyBytes(key, requestMessage(requestDigest), request.signature)) return finish('REQUEST_SIGNATURE_INVALID')
      if (p.model_digest !== this.modelDigest) return finish('MODEL_PIN_MISMATCH')
      if (p.policy_digest !== this.policyDigest) return finish('POLICY_PIN_MISMATCH')
      if (p.verifier_digest !== this.verifierDigest) return finish('VERIFIER_PIN_MISMATCH')
      if (!record(receipt)) return finish('CALIBRATION_BINDING_MISMATCH')
      const [rawDigest, receiptDigest, envelopeDigest, modelDigest, policyDigest] = await Promise.all([
        hashValue(stableRaw), calibrationReceiptDigest(receipt as unknown as SignedCalibrationReceiptV1),
        hashValue(envelope), hashValue(stableModel), hashValue(stablePolicy),
      ])
      if (p.raw_batch_digest !== rawDigest) return finish('RAW_BATCH_BINDING_MISMATCH')
      if (p.calibration_receipt_digest !== receiptDigest) return finish('CALIBRATION_BINDING_MISMATCH')
      if (p.measurement_envelope_digest !== envelopeDigest) return finish('MEASUREMENT_ENVELOPE_BINDING_MISMATCH')
      if (p.model_digest !== modelDigest) return finish('MODEL_BINDING_MISMATCH')
      if (p.policy_digest !== policyDigest) return finish('POLICY_BINDING_MISMATCH')
      bindings = deepFreeze({ request_payload_digest: requestDigest, raw_batch_digest: rawDigest,
        calibration_receipt_digest: receiptDigest, measurement_envelope_digest: envelopeDigest,
        model_digest: modelDigest, policy_digest: policyDigest, verifier_digest: this.verifierDigest })
      const calibrationResult = await this.calibration.admit(receipt, envelope, stableRaw)
      if (calibrationResult.status !== 'PASS') return finish('CALIBRATION_DENIED', calibrationResult.reason)
      consumed = true
      let output: unknown
      try { output = await this.verify(stableRaw, stableModel, stablePolicy) }
      catch { return finish('VERIFIER_EXECUTION_FAILED') }
      try { output = snapshot(output) }
      catch { return finish('MALFORMED_VERIFIER_RESULT') }
      if (!physicsShape(output)) return finish('MALFORMED_VERIFIER_RESULT')
      if (await hashValue(output.policy) !== policyDigest) return finish('VERIFIER_POLICY_MISMATCH')
      physicsResult = deepFreeze(output)
      physicsDigest = await hashValue(output)
      return finish(output.status === 'PASS_RESEARCH_ONLY' ? 'BOUND_RESEARCH_INFERENCE_VERIFIED' : 'PHYSICS_DENIED')
    } catch { return finish('INPUT_PROCESSING_FAILED') }
  }
}
