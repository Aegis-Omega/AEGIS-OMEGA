// ============================================================
// SOVEREIGN OMEGA — NVIDIA Execution Receipt Boundaries
// EPISTEMIC TIER: T2 · authority-neutral execution evidence
//
// This module admits externally observed GPU/BioNeMo/CUDA-Q execution
// evidence. It never launches processes, never infers hardware from catalogue
// presence, and never grants proof or knowledge-admission authority.
// ============================================================

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import {
  NVIDIA_CONNECTOR_EVIDENCE_SCHEMA,
  type NvidiaConnectorEvidence,
  type NvidiaConnectorId,
} from './nvidia.js'

export const NVIDIA_GPU_ENVIRONMENT_OBSERVATION_SCHEMA =
  'AEGIS-NVIDIA-GPU-ENVIRONMENT-OBSERVATION-V1' as const
export const NVIDIA_GPU_ENVIRONMENT_RECEIPT_SCHEMA =
  'AEGIS-NVIDIA-GPU-ENVIRONMENT-RECEIPT-V1' as const
export const BIONEMO_EXECUTION_OBSERVATION_SCHEMA =
  'AEGIS-BIONEMO-EXECUTION-OBSERVATION-V1' as const
export const BIONEMO_EXECUTION_RECEIPT_SCHEMA =
  'AEGIS-BIONEMO-EXECUTION-RECEIPT-V1' as const
export const CUDAQ_BACKEND_OBSERVATION_SCHEMA =
  'AEGIS-CUDAQ-BACKEND-OBSERVATION-V1' as const
export const CUDAQ_BACKEND_RECEIPT_SCHEMA =
  'AEGIS-CUDAQ-BACKEND-RECEIPT-V1' as const
export const NVIDIA_QUANTUM_EXECUTION_OBSERVATION_SCHEMA =
  'AEGIS-NVIDIA-QUANTUM-EXECUTION-OBSERVATION-V1' as const
export const NVIDIA_QUANTUM_EXECUTION_RECEIPT_SCHEMA =
  'AEGIS-NVIDIA-QUANTUM-EXECUTION-RECEIPT-V1' as const

// BioNeMo Inference Runtime release wheels currently require NVIDIA driver 580+.
// The constant is deliberately explicit so a future upstream requirement change
// becomes a reviewable contract change rather than an implicit parser behavior.
export const BIOIR_MIN_DRIVER_MAJOR = 580 as const

const SHA256_RE = /^[0-9a-f]{64}$/

export class NvidiaExecutionError extends Error {
  override readonly name = 'NvidiaExecutionError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export class NvidiaGpuEnvironmentUnavailableError extends NvidiaExecutionError {
  override readonly name = 'NvidiaGpuEnvironmentUnavailableError'
  readonly code = 'GPU_ENVIRONMENT_UNAVAILABLE' as const

  constructor() {
    super('GPU_ENVIRONMENT_UNAVAILABLE')
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

function assertSha256(value: string | null, code: string): asserts value is string {
  if (value === null || !SHA256_RE.test(value)) {
    throw new NvidiaExecutionError(code)
  }
}

function assertAuthorityNeutral(
  value: { readonly authority_class: 'NONE'; readonly authority_effect: 'NONE' },
  subject: string,
): void {
  if (value.authority_class !== 'NONE' || value.authority_effect !== 'NONE') {
    throw new NvidiaExecutionError(`AUTHORITY_SPLICE_REJECTED:${subject}`)
  }
}

function parseLeadingMajor(version: string, subject: string): number {
  const match = version.trim().match(/^(\d+)/)
  if (!match) {
    throw new NvidiaExecutionError(`INVALID_VERSION:${subject}`)
  }
  const major = Number.parseInt(match[1], 10)
  if (!Number.isSafeInteger(major) || major < 0) {
    throw new NvidiaExecutionError(`INVALID_VERSION:${subject}`)
  }
  return major
}

function assertConnectorEvidence(
  evidence: NvidiaConnectorEvidence,
  expected_id: NvidiaConnectorId,
): void {
  if (evidence.schema_version !== NVIDIA_CONNECTOR_EVIDENCE_SCHEMA) {
    throw new NvidiaExecutionError(`CONNECTOR_SCHEMA_MISMATCH:${expected_id}`)
  }
  if (evidence.connector_id !== expected_id) {
    throw new NvidiaExecutionError(
      `CONNECTOR_BINDING_MISMATCH:expected=${expected_id}:actual=${evidence.connector_id}`,
    )
  }
  if (evidence.status !== 'VERIFIED_AVAILABLE' && evidence.status !== 'EXECUTION_ADMITTED') {
    throw new NvidiaExecutionError(`UNVERIFIED_CONNECTOR:${expected_id}`)
  }
  if (evidence.connector_version.trim().length === 0) {
    throw new NvidiaExecutionError(`INVALID_CONNECTOR_VERSION:${expected_id}`)
  }
  assertSha256(evidence.executable_digest_sha256, `INVALID_EXECUTABLE_DIGEST:${expected_id}`)
  assertSha256(evidence.source_receipt_digest, `INVALID_CAPABILITY_RECEIPT:${expected_id}`)
  assertAuthorityNeutral(evidence, expected_id)
}

export interface NvidiaGpuEnvironmentObservation {
  readonly schema_version: typeof NVIDIA_GPU_ENVIRONMENT_OBSERVATION_SCHEMA
  readonly detected: boolean
  readonly gpu_count: number
  readonly driver_version: string | null
  readonly cuda_driver_version: string | null
  readonly gpu_architectures: readonly string[]
  readonly device_inventory_digest_sha256: string | null
  readonly capability_receipt_digest: string | null
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
}

export interface NvidiaGpuEnvironmentReceipt {
  readonly schema_version: typeof NVIDIA_GPU_ENVIRONMENT_RECEIPT_SCHEMA
  readonly status: 'VERIFIED_AVAILABLE'
  readonly gpu_count: number
  readonly driver_version: string
  readonly cuda_driver_version: string
  readonly gpu_architectures: readonly string[]
  readonly device_inventory_digest_sha256: string
  readonly source_receipt_digest: string
  readonly bioir_driver_compatible: boolean
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly is_replay_reconstructable: true
  readonly receipt_digest: string
}

function gpuEnvironmentDigestPayload(
  receipt: Omit<NvidiaGpuEnvironmentReceipt, 'receipt_digest'>,
): Omit<NvidiaGpuEnvironmentReceipt, 'receipt_digest'> {
  return receipt
}

export async function admitNvidiaGpuEnvironment(
  observation: NvidiaGpuEnvironmentObservation,
): Promise<NvidiaGpuEnvironmentReceipt> {
  if (observation.schema_version !== NVIDIA_GPU_ENVIRONMENT_OBSERVATION_SCHEMA) {
    throw new NvidiaExecutionError('GPU_ENVIRONMENT_SCHEMA_MISMATCH')
  }
  assertAuthorityNeutral(observation, 'gpu-environment')

  if (!observation.detected) {
    throw new NvidiaGpuEnvironmentUnavailableError()
  }
  if (!Number.isInteger(observation.gpu_count) || observation.gpu_count <= 0) {
    throw new NvidiaExecutionError('INVALID_GPU_COUNT')
  }
  if (observation.driver_version === null || observation.driver_version.trim().length === 0) {
    throw new NvidiaExecutionError('INVALID_NVIDIA_DRIVER_VERSION')
  }
  if (
    observation.cuda_driver_version === null ||
    observation.cuda_driver_version.trim().length === 0
  ) {
    throw new NvidiaExecutionError('INVALID_CUDA_DRIVER_VERSION')
  }
  if (
    observation.gpu_architectures.length === 0 ||
    observation.gpu_architectures.some(architecture => architecture.trim().length === 0)
  ) {
    throw new NvidiaExecutionError('INVALID_GPU_ARCHITECTURE_SET')
  }
  assertSha256(
    observation.device_inventory_digest_sha256,
    'INVALID_GPU_DEVICE_INVENTORY_DIGEST',
  )
  assertSha256(
    observation.capability_receipt_digest,
    'INVALID_GPU_CAPABILITY_RECEIPT',
  )

  const driverMajor = parseLeadingMajor(observation.driver_version, 'nvidia-driver')
  const payload = gpuEnvironmentDigestPayload({
    schema_version: NVIDIA_GPU_ENVIRONMENT_RECEIPT_SCHEMA,
    status: 'VERIFIED_AVAILABLE',
    gpu_count: observation.gpu_count,
    driver_version: observation.driver_version,
    cuda_driver_version: observation.cuda_driver_version,
    gpu_architectures: [...observation.gpu_architectures].sort(),
    device_inventory_digest_sha256: observation.device_inventory_digest_sha256,
    source_receipt_digest: observation.capability_receipt_digest,
    bioir_driver_compatible: driverMajor >= BIOIR_MIN_DRIVER_MAJOR,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    is_replay_reconstructable: true,
  })

  return deepFreeze<NvidiaGpuEnvironmentReceipt>({
    ...payload,
    receipt_digest: await hashValue(payload),
  })
}

async function assertGpuEnvironmentReceipt(
  receipt: NvidiaGpuEnvironmentReceipt,
): Promise<void> {
  if (receipt.schema_version !== NVIDIA_GPU_ENVIRONMENT_RECEIPT_SCHEMA) {
    throw new NvidiaExecutionError('GPU_ENVIRONMENT_RECEIPT_SCHEMA_MISMATCH')
  }
  assertAuthorityNeutral(receipt, 'gpu-environment-receipt')
  assertSha256(receipt.receipt_digest, 'INVALID_GPU_ENVIRONMENT_RECEIPT_DIGEST')
  const { receipt_digest, ...payload } = receipt
  if (await hashValue(payload) !== receipt_digest) {
    throw new NvidiaExecutionError('GPU_ENVIRONMENT_RECEIPT_DIGEST_MISMATCH')
  }
}

export interface BioNemoExecutionObservation {
  readonly schema_version: typeof BIONEMO_EXECUTION_OBSERVATION_SCHEMA
  readonly task_id: string
  readonly completed: boolean
  readonly gpu_environment_receipt_digest: string
  readonly model_id: string
  readonly model_artifact_digest_sha256: string
  readonly input_digest_sha256: string
  readonly output_digest_sha256: string
  readonly execution_receipt_digest: string
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
}

export interface BioNemoExecutionReceipt {
  readonly schema_version: typeof BIONEMO_EXECUTION_RECEIPT_SCHEMA
  readonly task_id: string
  readonly status: 'EXECUTED'
  readonly gpu_execution: 'ESTABLISHED_FOR_THIS_RECEIPT'
  readonly gpu_environment_receipt_digest: string
  readonly bionemo_connector_version: string
  readonly bionemo_executable_digest_sha256: string
  readonly bionemo_capability_receipt_digest: string
  readonly model_id: string
  readonly model_artifact_digest_sha256: string
  readonly input_digest_sha256: string
  readonly output_digest_sha256: string
  readonly source_execution_receipt_digest: string
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly is_replay_reconstructable: true
  readonly receipt_digest: string
}

export interface BioNemoExecutionAdmissionRequest {
  readonly observation: BioNemoExecutionObservation
  readonly bionemo_evidence: NvidiaConnectorEvidence
  readonly gpu_environment: NvidiaGpuEnvironmentReceipt
}

export async function admitBioNemoExecution(
  request: BioNemoExecutionAdmissionRequest,
): Promise<BioNemoExecutionReceipt> {
  const { observation, bionemo_evidence, gpu_environment } = request
  if (observation.schema_version !== BIONEMO_EXECUTION_OBSERVATION_SCHEMA) {
    throw new NvidiaExecutionError('BIONEMO_EXECUTION_SCHEMA_MISMATCH')
  }
  assertAuthorityNeutral(observation, 'bionemo-execution')
  assertConnectorEvidence(bionemo_evidence, 'bionemo-ir')
  await assertGpuEnvironmentReceipt(gpu_environment)

  if (!observation.completed) {
    throw new NvidiaExecutionError('BIONEMO_EXECUTION_NOT_COMPLETED')
  }
  if (!gpu_environment.bioir_driver_compatible) {
    throw new NvidiaExecutionError('BIOIR_GPU_ENVIRONMENT_UNSUPPORTED')
  }
  if (observation.task_id.trim().length === 0) {
    throw new NvidiaExecutionError('EMPTY_BIONEMO_TASK_ID')
  }
  if (observation.gpu_environment_receipt_digest !== gpu_environment.receipt_digest) {
    throw new NvidiaExecutionError('GPU_ENVIRONMENT_BINDING_MISMATCH')
  }
  if (observation.model_id.trim().length === 0) {
    throw new NvidiaExecutionError('EMPTY_BIONEMO_MODEL_ID')
  }
  assertSha256(observation.model_artifact_digest_sha256, 'INVALID_BIONEMO_MODEL_DIGEST')
  assertSha256(observation.input_digest_sha256, 'INVALID_BIONEMO_INPUT_DIGEST')
  assertSha256(observation.output_digest_sha256, 'INVALID_BIONEMO_OUTPUT_DIGEST')
  assertSha256(observation.execution_receipt_digest, 'INVALID_BIONEMO_EXECUTION_RECEIPT')

  const payload: Omit<BioNemoExecutionReceipt, 'receipt_digest'> = {
    schema_version: BIONEMO_EXECUTION_RECEIPT_SCHEMA,
    task_id: observation.task_id,
    status: 'EXECUTED',
    gpu_execution: 'ESTABLISHED_FOR_THIS_RECEIPT',
    gpu_environment_receipt_digest: gpu_environment.receipt_digest,
    bionemo_connector_version: bionemo_evidence.connector_version,
    bionemo_executable_digest_sha256: bionemo_evidence.executable_digest_sha256,
    bionemo_capability_receipt_digest: bionemo_evidence.source_receipt_digest,
    model_id: observation.model_id,
    model_artifact_digest_sha256: observation.model_artifact_digest_sha256,
    input_digest_sha256: observation.input_digest_sha256,
    output_digest_sha256: observation.output_digest_sha256,
    source_execution_receipt_digest: observation.execution_receipt_digest,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    is_replay_reconstructable: true,
  }

  return deepFreeze<BioNemoExecutionReceipt>({
    ...payload,
    receipt_digest: await hashValue(payload),
  })
}

export type CudaQBackendKind = 'SIMULATOR' | 'HARDWARE'

export interface CudaQBackendObservation {
  readonly schema_version: typeof CUDAQ_BACKEND_OBSERVATION_SCHEMA
  readonly target_name: string
  readonly backend_kind: CudaQBackendKind
  readonly qpu_count: number
  readonly is_remote: boolean
  readonly is_emulated: boolean
  readonly platform_properties_digest_sha256: string
  readonly capability_receipt_digest: string
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
}

export interface CudaQBackendReceipt {
  readonly schema_version: typeof CUDAQ_BACKEND_RECEIPT_SCHEMA
  readonly status: 'VERIFIED_AVAILABLE'
  readonly target_name: string
  readonly backend_kind: CudaQBackendKind
  readonly qpu_count: number
  readonly is_remote: boolean
  readonly is_emulated: boolean
  readonly platform_properties_digest_sha256: string
  readonly source_backend_receipt_digest: string
  readonly cudaq_connector_version: string
  readonly cudaq_executable_digest_sha256: string
  readonly cudaq_capability_receipt_digest: string
  readonly qpu_access: 'ESTABLISHED_FOR_THIS_RECEIPT' | 'NOT_ESTABLISHED'
  readonly quantum_advantage: 'NOT_ESTABLISHED'
  readonly authority_scope: 'DIAGNOSTIC_ONLY'
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly is_replay_reconstructable: true
  readonly receipt_digest: string
}

export interface CudaQBackendAdmissionRequest {
  readonly observation: CudaQBackendObservation
  readonly cudaq_evidence: NvidiaConnectorEvidence
}

export async function admitCudaQBackend(
  request: CudaQBackendAdmissionRequest,
): Promise<CudaQBackendReceipt> {
  const { observation, cudaq_evidence } = request
  if (observation.schema_version !== CUDAQ_BACKEND_OBSERVATION_SCHEMA) {
    throw new NvidiaExecutionError('CUDAQ_BACKEND_SCHEMA_MISMATCH')
  }
  assertAuthorityNeutral(observation, 'cudaq-backend')
  assertConnectorEvidence(cudaq_evidence, 'cudaq')

  if (observation.target_name.trim().length === 0) {
    throw new NvidiaExecutionError('EMPTY_CUDAQ_TARGET')
  }
  if (observation.backend_kind !== 'SIMULATOR' && observation.backend_kind !== 'HARDWARE') {
    throw new NvidiaExecutionError('INVALID_CUDAQ_BACKEND_KIND')
  }
  if (!Number.isInteger(observation.qpu_count) || observation.qpu_count <= 0) {
    throw new NvidiaExecutionError('INVALID_CUDAQ_QPU_COUNT')
  }
  if (observation.backend_kind === 'HARDWARE' && observation.is_emulated) {
    throw new NvidiaExecutionError('HARDWARE_BACKEND_EMULATED')
  }
  assertSha256(
    observation.platform_properties_digest_sha256,
    'INVALID_CUDAQ_PLATFORM_PROPERTIES_DIGEST',
  )
  assertSha256(observation.capability_receipt_digest, 'INVALID_CUDAQ_BACKEND_RECEIPT')

  const payload: Omit<CudaQBackendReceipt, 'receipt_digest'> = {
    schema_version: CUDAQ_BACKEND_RECEIPT_SCHEMA,
    status: 'VERIFIED_AVAILABLE',
    target_name: observation.target_name,
    backend_kind: observation.backend_kind,
    qpu_count: observation.qpu_count,
    is_remote: observation.is_remote,
    is_emulated: observation.is_emulated,
    platform_properties_digest_sha256: observation.platform_properties_digest_sha256,
    source_backend_receipt_digest: observation.capability_receipt_digest,
    cudaq_connector_version: cudaq_evidence.connector_version,
    cudaq_executable_digest_sha256: cudaq_evidence.executable_digest_sha256,
    cudaq_capability_receipt_digest: cudaq_evidence.source_receipt_digest,
    qpu_access: observation.backend_kind === 'HARDWARE'
      ? 'ESTABLISHED_FOR_THIS_RECEIPT'
      : 'NOT_ESTABLISHED',
    quantum_advantage: 'NOT_ESTABLISHED',
    authority_scope: 'DIAGNOSTIC_ONLY',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    is_replay_reconstructable: true,
  }

  return deepFreeze<CudaQBackendReceipt>({
    ...payload,
    receipt_digest: await hashValue(payload),
  })
}

async function assertCudaQBackendReceipt(receipt: CudaQBackendReceipt): Promise<void> {
  if (receipt.schema_version !== CUDAQ_BACKEND_RECEIPT_SCHEMA) {
    throw new NvidiaExecutionError('CUDAQ_BACKEND_RECEIPT_SCHEMA_MISMATCH')
  }
  assertAuthorityNeutral(receipt, 'cudaq-backend-receipt')
  assertSha256(receipt.receipt_digest, 'INVALID_CUDAQ_BACKEND_RECEIPT_DIGEST')
  const { receipt_digest, ...payload } = receipt
  if (await hashValue(payload) !== receipt_digest) {
    throw new NvidiaExecutionError('CUDAQ_BACKEND_RECEIPT_DIGEST_MISMATCH')
  }
}

export type NvidiaQuantumExecutionKind = 'SAMPLE' | 'OBSERVE' | 'STATE'

export interface NvidiaQuantumExecutionObservation {
  readonly schema_version: typeof NVIDIA_QUANTUM_EXECUTION_OBSERVATION_SCHEMA
  readonly task_id: string
  readonly completed: boolean
  readonly backend_receipt_digest: string
  readonly execution_kind: NvidiaQuantumExecutionKind
  readonly kernel_digest_sha256: string
  readonly input_digest_sha256: string
  readonly output_digest_sha256: string
  readonly execution_receipt_digest: string
  readonly shots_count: number
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
}

export type NvidiaQuantumManifoldBinding =
  | 'CUDAQ_CUQUANTUM_SIMULATION'
  | 'CUDAQ_SIMULATION'
  | 'CUDAQ_HARDWARE_BACKEND'

export interface NvidiaQuantumExecutionReceipt {
  readonly schema_version: typeof NVIDIA_QUANTUM_EXECUTION_RECEIPT_SCHEMA
  readonly task_id: string
  readonly status: 'EXECUTED'
  readonly backend_receipt_digest: string
  readonly target_name: string
  readonly backend_kind: CudaQBackendKind
  readonly manifold_binding: NvidiaQuantumManifoldBinding
  readonly execution_kind: NvidiaQuantumExecutionKind
  readonly kernel_digest_sha256: string
  readonly input_digest_sha256: string
  readonly output_digest_sha256: string
  readonly source_execution_receipt_digest: string
  readonly shots_count: number
  readonly qpu_access: 'ESTABLISHED_FOR_THIS_RECEIPT' | 'NOT_ESTABLISHED'
  readonly quantum_advantage: 'NOT_ESTABLISHED'
  readonly authority_scope: 'DIAGNOSTIC_ONLY'
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly is_replay_reconstructable: true
  readonly receipt_digest: string
}

export interface NvidiaQuantumExecutionAdmissionRequest {
  readonly observation: NvidiaQuantumExecutionObservation
  readonly backend: CudaQBackendReceipt
  readonly cudaq_evidence: NvidiaConnectorEvidence
  readonly cuquantum_evidence: NvidiaConnectorEvidence | null
}

export async function admitNvidiaQuantumExecution(
  request: NvidiaQuantumExecutionAdmissionRequest,
): Promise<NvidiaQuantumExecutionReceipt> {
  const { observation, backend, cudaq_evidence, cuquantum_evidence } = request
  if (observation.schema_version !== NVIDIA_QUANTUM_EXECUTION_OBSERVATION_SCHEMA) {
    throw new NvidiaExecutionError('NVIDIA_QUANTUM_EXECUTION_SCHEMA_MISMATCH')
  }
  assertAuthorityNeutral(observation, 'nvidia-quantum-execution')
  assertConnectorEvidence(cudaq_evidence, 'cudaq')
  await assertCudaQBackendReceipt(backend)

  if (!observation.completed) {
    throw new NvidiaExecutionError('NVIDIA_QUANTUM_EXECUTION_NOT_COMPLETED')
  }
  if (observation.task_id.trim().length === 0) {
    throw new NvidiaExecutionError('EMPTY_NVIDIA_QUANTUM_TASK_ID')
  }
  if (observation.backend_receipt_digest !== backend.receipt_digest) {
    throw new NvidiaExecutionError('BACKEND_BINDING_MISMATCH')
  }
  if (
    observation.execution_kind !== 'SAMPLE' &&
    observation.execution_kind !== 'OBSERVE' &&
    observation.execution_kind !== 'STATE'
  ) {
    throw new NvidiaExecutionError('INVALID_NVIDIA_QUANTUM_EXECUTION_KIND')
  }
  if (!Number.isInteger(observation.shots_count) || observation.shots_count < 0) {
    throw new NvidiaExecutionError('INVALID_SHOTS_COUNT')
  }
  if (observation.execution_kind === 'SAMPLE' && observation.shots_count <= 0) {
    throw new NvidiaExecutionError('SAMPLE_REQUIRES_POSITIVE_SHOTS')
  }
  assertSha256(observation.kernel_digest_sha256, 'INVALID_QUANTUM_KERNEL_DIGEST')
  assertSha256(observation.input_digest_sha256, 'INVALID_QUANTUM_INPUT_DIGEST')
  assertSha256(observation.output_digest_sha256, 'INVALID_QUANTUM_OUTPUT_DIGEST')
  assertSha256(observation.execution_receipt_digest, 'INVALID_QUANTUM_EXECUTION_RECEIPT')

  let manifold_binding: NvidiaQuantumManifoldBinding
  if (backend.backend_kind === 'HARDWARE') {
    manifold_binding = 'CUDAQ_HARDWARE_BACKEND'
  } else if (backend.target_name === 'nvidia') {
    if (cuquantum_evidence === null) {
      throw new NvidiaExecutionError('CUQUANTUM_EVIDENCE_REQUIRED')
    }
    assertConnectorEvidence(cuquantum_evidence, 'cuquantum')
    manifold_binding = 'CUDAQ_CUQUANTUM_SIMULATION'
  } else {
    manifold_binding = 'CUDAQ_SIMULATION'
  }

  const payload: Omit<NvidiaQuantumExecutionReceipt, 'receipt_digest'> = {
    schema_version: NVIDIA_QUANTUM_EXECUTION_RECEIPT_SCHEMA,
    task_id: observation.task_id,
    status: 'EXECUTED',
    backend_receipt_digest: backend.receipt_digest,
    target_name: backend.target_name,
    backend_kind: backend.backend_kind,
    manifold_binding,
    execution_kind: observation.execution_kind,
    kernel_digest_sha256: observation.kernel_digest_sha256,
    input_digest_sha256: observation.input_digest_sha256,
    output_digest_sha256: observation.output_digest_sha256,
    source_execution_receipt_digest: observation.execution_receipt_digest,
    shots_count: observation.shots_count,
    qpu_access: backend.qpu_access,
    quantum_advantage: 'NOT_ESTABLISHED',
    authority_scope: 'DIAGNOSTIC_ONLY',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    is_replay_reconstructable: true,
  }

  return deepFreeze<NvidiaQuantumExecutionReceipt>({
    ...payload,
    receipt_digest: await hashValue(payload),
  })
}
