// ============================================================
// SOVEREIGN OMEGA — Remote NVIDIA GPU Evidence Adapter
// EPISTEMIC TIER: T2 · raw provider execution evidence only
//
// Remote providers emit raw GPU facts. This adapter normalizes those facts
// into the existing NvidiaGpuEnvironmentObservation boundary. It never grants
// execution, proof, knowledge-admission, or provider authority.
// ============================================================

import { hashValue } from '../core/hashing.js'
import {
  NVIDIA_GPU_ENVIRONMENT_OBSERVATION_SCHEMA,
  type NvidiaGpuEnvironmentObservation,
} from './nvidia-execution.js'

export const NVIDIA_REMOTE_GPU_PROBE_SCHEMA =
  'AEGIS-NVIDIA-REMOTE-GPU-PROBE-V1' as const

export type RemoteNvidiaGpuProvider = 'GCP_VERTEX'

export interface RemoteNvidiaGpuInventoryEntry {
  readonly uuid: string
  readonly name: string
  readonly driver_version: string
  readonly compute_capability: string
}

export interface RemoteNvidiaGpuProbePayload {
  readonly schema_version: typeof NVIDIA_REMOTE_GPU_PROBE_SCHEMA
  readonly provider: RemoteNvidiaGpuProvider
  readonly provider_job_id: string
  readonly candidate_sha: string
  readonly cuda_driver_version: string
  readonly inventory: readonly RemoteNvidiaGpuInventoryEntry[]
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
}

export class NvidiaRemoteGpuError extends Error {
  override readonly name = 'NvidiaRemoteGpuError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

const GIT_SHA1_RE = /^[0-9a-f]{40}$/

function nonEmpty(value: string, code: string): string {
  const normalized = value.trim()
  if (normalized.length === 0) throw new NvidiaRemoteGpuError(code)
  return normalized
}

function assertCandidateSha(value: string, code: string): void {
  if (!GIT_SHA1_RE.test(value)) throw new NvidiaRemoteGpuError(code)
}

export async function buildRemoteNvidiaGpuObservation(
  payload: RemoteNvidiaGpuProbePayload,
  expected_candidate_sha: string,
): Promise<NvidiaGpuEnvironmentObservation> {
  if (payload.schema_version !== NVIDIA_REMOTE_GPU_PROBE_SCHEMA) {
    throw new NvidiaRemoteGpuError('REMOTE_GPU_SCHEMA_MISMATCH')
  }
  if (payload.provider !== 'GCP_VERTEX') {
    throw new NvidiaRemoteGpuError(`UNSUPPORTED_REMOTE_GPU_PROVIDER:${String(payload.provider)}`)
  }
  if (payload.authority_class !== 'NONE' || payload.authority_effect !== 'NONE') {
    throw new NvidiaRemoteGpuError('AUTHORITY_SPLICE_REJECTED:remote-gpu')
  }

  assertCandidateSha(expected_candidate_sha, 'INVALID_EXPECTED_CANDIDATE_SHA')
  assertCandidateSha(payload.candidate_sha, 'INVALID_REMOTE_CANDIDATE_SHA')
  if (payload.candidate_sha !== expected_candidate_sha) {
    throw new NvidiaRemoteGpuError(
      `CANDIDATE_BINDING_MISMATCH:expected=${expected_candidate_sha}:actual=${payload.candidate_sha}`,
    )
  }

  const providerJobId = nonEmpty(payload.provider_job_id, 'EMPTY_REMOTE_GPU_JOB_ID')
  const cudaDriverVersion = nonEmpty(
    payload.cuda_driver_version,
    'EMPTY_REMOTE_CUDA_DRIVER_VERSION',
  )
  if (payload.inventory.length === 0) {
    throw new NvidiaRemoteGpuError('REMOTE_GPU_INVENTORY_EMPTY')
  }

  const canonicalInventory = payload.inventory.map(entry => ({
    uuid: nonEmpty(entry.uuid, 'INVALID_REMOTE_GPU_UUID'),
    name: nonEmpty(entry.name, 'INVALID_REMOTE_GPU_NAME'),
    driver_version: nonEmpty(entry.driver_version, 'INVALID_REMOTE_GPU_DRIVER_VERSION'),
    compute_capability: nonEmpty(
      entry.compute_capability,
      'INVALID_REMOTE_GPU_COMPUTE_CAPABILITY',
    ),
  })).sort((left, right) => left.uuid.localeCompare(right.uuid))

  const uuids = new Set(canonicalInventory.map(entry => entry.uuid))
  if (uuids.size !== canonicalInventory.length) {
    throw new NvidiaRemoteGpuError('DUPLICATE_REMOTE_GPU_UUID')
  }

  const driverVersions = new Set(canonicalInventory.map(entry => entry.driver_version))
  if (driverVersions.size !== 1) {
    throw new NvidiaRemoteGpuError('REMOTE_GPU_DRIVER_VERSION_INCONSISTENT')
  }

  const inventoryDigest = await hashValue(canonicalInventory)
  const capabilityReceiptDigest = await hashValue({
    schema_version: NVIDIA_REMOTE_GPU_PROBE_SCHEMA,
    provider: payload.provider,
    provider_job_id: providerJobId,
    candidate_sha: payload.candidate_sha,
    cuda_driver_version: cudaDriverVersion,
    inventory_digest_sha256: inventoryDigest,
    inventory: canonicalInventory,
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
  })

  return {
    schema_version: NVIDIA_GPU_ENVIRONMENT_OBSERVATION_SCHEMA,
    detected: true,
    gpu_count: canonicalInventory.length,
    driver_version: canonicalInventory[0]!.driver_version,
    cuda_driver_version: cudaDriverVersion,
    gpu_architectures: canonicalInventory.map(
      entry => `${entry.name}@compute-capability-${entry.compute_capability}`,
    ),
    device_inventory_digest_sha256: inventoryDigest,
    capability_receipt_digest: capabilityReceiptDigest,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
}
