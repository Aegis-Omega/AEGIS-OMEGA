// ============================================================
// SOVEREIGN OMEGA — NVIDIA Scientific Substrate Extension
// EPISTEMIC TIER: T2 · authority-neutral capability substrate
//
// This module catalogues and admits digest-bound evidence for NVIDIA
// scientific/agent runtimes. It never launches external tools, never claims
// GPU/QPU availability from catalogue presence, and never admits knowledge.
// ============================================================

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const NVIDIA_CONNECTOR_EVIDENCE_SCHEMA =
  'AEGIS-NVIDIA-CONNECTOR-EVIDENCE-V1' as const
export const NVIDIA_DETECTION_OBSERVATION_SCHEMA =
  'AEGIS-NVIDIA-DETECTION-OBSERVATION-V1' as const
export const NVIDIA_SUBSTRATE_RECEIPT_SCHEMA =
  'AEGIS-NVIDIA-SUBSTRATE-RECEIPT-V1' as const

export type NvidiaConnectorId =
  | 'nvidia-agent-toolkit'
  | 'nemo-platform'
  | 'nemo-fabric'
  | 'bionemo-ir'
  | 'cudaq'
  | 'cuquantum'

export type NvidiaCapabilityKind =
  | 'AGENT_ORCHESTRATION'
  | 'AGENT_PLATFORM'
  | 'AGENT_RUNTIME_FABRIC'
  | 'BIOMOLECULAR_AI'
  | 'QUANTUM_PROGRAMMING'
  | 'QUANTUM_SIMULATION'

export interface NvidiaConnectorDescriptor {
  readonly connector_id: NvidiaConnectorId
  readonly capability_kind: NvidiaCapabilityKind
  readonly runtime_family: string
  readonly probe_locator: string
  readonly version_probe: readonly string[]
  readonly digest_algorithm: 'SHA-256'
  readonly capability_receipt_required: true
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly default_state: 'CATALOGUED_NOT_VERIFIED'
}

export const NVIDIA_CONNECTOR_CATALOG: readonly NvidiaConnectorDescriptor[] = deepFreeze([
  {
    connector_id: 'nvidia-agent-toolkit',
    capability_kind: 'AGENT_ORCHESTRATION',
    runtime_family: 'nvidia-agent-intelligence-toolkit',
    probe_locator: 'nat',
    version_probe: ['--version'],
    digest_algorithm: 'SHA-256',
    capability_receipt_required: true,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    connector_id: 'nemo-platform',
    capability_kind: 'AGENT_PLATFORM',
    runtime_family: 'nvidia-nemo-platform',
    probe_locator: 'nemo',
    version_probe: ['--version'],
    digest_algorithm: 'SHA-256',
    capability_receipt_required: true,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    connector_id: 'nemo-fabric',
    capability_kind: 'AGENT_RUNTIME_FABRIC',
    runtime_family: 'nvidia-nemo-fabric',
    probe_locator: 'python:nemo_fabric',
    version_probe: ['package-version', 'nemo-fabric'],
    digest_algorithm: 'SHA-256',
    capability_receipt_required: true,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    connector_id: 'bionemo-ir',
    capability_kind: 'BIOMOLECULAR_AI',
    runtime_family: 'nvidia-bionemo-inference-runtime',
    probe_locator: 'python:bionemo_ir',
    version_probe: ['import-version', 'bionemo_ir'],
    digest_algorithm: 'SHA-256',
    capability_receipt_required: true,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    connector_id: 'cudaq',
    capability_kind: 'QUANTUM_PROGRAMMING',
    runtime_family: 'nvidia-cuda-q',
    probe_locator: 'python:cudaq',
    version_probe: ['package-version', 'cudaq'],
    digest_algorithm: 'SHA-256',
    capability_receipt_required: true,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    connector_id: 'cuquantum',
    capability_kind: 'QUANTUM_SIMULATION',
    runtime_family: 'nvidia-cuquantum',
    probe_locator: 'python:cuquantum',
    version_probe: ['package-version', 'cuquantum-python'],
    digest_algorithm: 'SHA-256',
    capability_receipt_required: true,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
])

const CONNECTOR_BY_ID = new Map(
  NVIDIA_CONNECTOR_CATALOG.map(descriptor => [descriptor.connector_id, descriptor] as const),
)
const SHA256_RE = /^[0-9a-f]{64}$/

export interface NvidiaDetectionObservation {
  readonly schema_version: typeof NVIDIA_DETECTION_OBSERVATION_SCHEMA
  readonly connector_id: NvidiaConnectorId
  readonly detected: boolean
  readonly connector_version: string | null
  readonly executable_digest_sha256: string | null
  readonly capability_receipt_digest: string | null
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
}

export interface NvidiaConnectorEvidence {
  readonly schema_version: typeof NVIDIA_CONNECTOR_EVIDENCE_SCHEMA
  readonly connector_id: NvidiaConnectorId
  readonly capability_kind: NvidiaCapabilityKind
  readonly status: 'VERIFIED_AVAILABLE' | 'EXECUTION_ADMITTED'
  readonly connector_version: string
  readonly executable_digest_sha256: string
  readonly source_receipt_digest: string
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
}

export interface NvidiaScientificSubstrateRequest {
  readonly task_id: string
  readonly evidence: readonly NvidiaConnectorEvidence[]
}

export interface NvidiaScientificSubstrateReceipt {
  readonly schema_version: typeof NVIDIA_SUBSTRATE_RECEIPT_SCHEMA
  readonly task_id: string
  readonly verified_connectors: readonly NvidiaConnectorId[]
  readonly agent_platform: {
    readonly state: 'READY' | 'NOT_ESTABLISHED'
    readonly required_connectors: readonly ['nemo-platform', 'nemo-fabric']
    readonly missing_connectors: readonly NvidiaConnectorId[]
    readonly execution: 'NOT_ESTABLISHED'
    readonly authority_scope: 'EXECUTION_EVIDENCE_ONLY'
  }
  readonly biomolecular_agent_fabric: {
    readonly state: 'READY' | 'NOT_ESTABLISHED'
    readonly required_connectors: readonly ['nvidia-agent-toolkit', 'bionemo-ir']
    readonly missing_connectors: readonly NvidiaConnectorId[]
    readonly gpu_execution: 'NOT_ESTABLISHED'
  }
  readonly quantum_manifold: {
    readonly state: 'CUDAQ_CUQUANTUM_SIMULATION_READY' | 'NOT_ESTABLISHED'
    readonly required_connectors: readonly ['cudaq', 'cuquantum']
    readonly missing_connectors: readonly NvidiaConnectorId[]
    readonly qpu_access: 'NOT_ESTABLISHED'
    readonly quantum_advantage: 'NOT_ESTABLISHED'
    readonly authority_scope: 'DIAGNOSTIC_ONLY'
  }
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly receipt_digest: string
  readonly is_replay_reconstructable: true
}

export class NvidiaSubstrateError extends Error {
  override readonly name: string = 'NvidiaSubstrateError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export class NvidiaConnectorUnavailableError extends NvidiaSubstrateError {
  override readonly name = 'NvidiaConnectorUnavailableError'
  readonly code = 'TOOLCHAIN_UNAVAILABLE' as const

  constructor(connector_id: NvidiaConnectorId) {
    super(`TOOLCHAIN_UNAVAILABLE:${connector_id}`)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export function buildNvidiaDetectionSpec(
  connector_id: NvidiaConnectorId,
): NvidiaConnectorDescriptor {
  const descriptor = CONNECTOR_BY_ID.get(connector_id)
  if (!descriptor) {
    throw new NvidiaSubstrateError(`UNKNOWN_NVIDIA_CONNECTOR:${String(connector_id)}`)
  }
  return descriptor
}

export function admitNvidiaConnector(
  observation: NvidiaDetectionObservation,
): NvidiaConnectorEvidence {
  if (observation.schema_version !== NVIDIA_DETECTION_OBSERVATION_SCHEMA) {
    throw new NvidiaSubstrateError(`SCHEMA_MISMATCH:${observation.connector_id}`)
  }

  const descriptor = CONNECTOR_BY_ID.get(observation.connector_id)
  if (!descriptor) {
    throw new NvidiaSubstrateError(`UNKNOWN_NVIDIA_CONNECTOR:${String(observation.connector_id)}`)
  }
  if (observation.authority_class !== 'NONE' || observation.authority_effect !== 'NONE') {
    throw new NvidiaSubstrateError(`AUTHORITY_SPLICE_REJECTED:${observation.connector_id}`)
  }
  if (!observation.detected) {
    throw new NvidiaConnectorUnavailableError(observation.connector_id)
  }
  if (observation.connector_version === null || observation.connector_version.trim().length === 0) {
    throw new NvidiaSubstrateError(`INVALID_CONNECTOR_VERSION:${observation.connector_id}`)
  }
  if (
    observation.executable_digest_sha256 === null ||
    !SHA256_RE.test(observation.executable_digest_sha256)
  ) {
    throw new NvidiaSubstrateError(`INVALID_EXECUTABLE_DIGEST:${observation.connector_id}`)
  }
  if (
    observation.capability_receipt_digest === null ||
    !SHA256_RE.test(observation.capability_receipt_digest)
  ) {
    throw new NvidiaSubstrateError(`INVALID_CAPABILITY_RECEIPT:${observation.connector_id}`)
  }

  return deepFreeze<NvidiaConnectorEvidence>({
    schema_version: NVIDIA_CONNECTOR_EVIDENCE_SCHEMA,
    connector_id: observation.connector_id,
    capability_kind: descriptor.capability_kind,
    status: 'VERIFIED_AVAILABLE',
    connector_version: observation.connector_version,
    executable_digest_sha256: observation.executable_digest_sha256,
    source_receipt_digest: observation.capability_receipt_digest,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  })
}

function assertEvidence(evidence: NvidiaConnectorEvidence): void {
  const descriptor = CONNECTOR_BY_ID.get(evidence.connector_id)
  if (!descriptor) {
    throw new NvidiaSubstrateError(`UNKNOWN_NVIDIA_CONNECTOR:${String(evidence.connector_id)}`)
  }
  if (evidence.schema_version !== NVIDIA_CONNECTOR_EVIDENCE_SCHEMA) {
    throw new NvidiaSubstrateError(`SCHEMA_MISMATCH:${evidence.connector_id}`)
  }
  if (evidence.capability_kind !== descriptor.capability_kind) {
    throw new NvidiaSubstrateError(`CAPABILITY_KIND_MISMATCH:${evidence.connector_id}`)
  }
  if (evidence.status !== 'VERIFIED_AVAILABLE' && evidence.status !== 'EXECUTION_ADMITTED') {
    throw new NvidiaSubstrateError(`UNVERIFIED_CONNECTOR:${evidence.connector_id}`)
  }
  if (evidence.authority_class !== 'NONE' || evidence.authority_effect !== 'NONE') {
    throw new NvidiaSubstrateError(`AUTHORITY_SPLICE_REJECTED:${evidence.connector_id}`)
  }
  if (evidence.connector_version.trim().length === 0) {
    throw new NvidiaSubstrateError(`INVALID_CONNECTOR_VERSION:${evidence.connector_id}`)
  }
  if (!SHA256_RE.test(evidence.executable_digest_sha256)) {
    throw new NvidiaSubstrateError(`INVALID_EXECUTABLE_DIGEST:${evidence.connector_id}`)
  }
  if (!SHA256_RE.test(evidence.source_receipt_digest)) {
    throw new NvidiaSubstrateError(`INVALID_CAPABILITY_RECEIPT:${evidence.connector_id}`)
  }
}

function missingConnectors(
  required: readonly NvidiaConnectorId[],
  available: ReadonlySet<NvidiaConnectorId>,
): NvidiaConnectorId[] {
  return required.filter(connector => !available.has(connector))
}

export async function buildNvidiaScientificSubstrateReceipt(
  request: NvidiaScientificSubstrateRequest,
): Promise<NvidiaScientificSubstrateReceipt> {
  if (request.task_id.trim().length === 0) {
    throw new NvidiaSubstrateError('EMPTY_TASK_ID')
  }

  const evidenceById = new Map<NvidiaConnectorId, NvidiaConnectorEvidence>()
  for (const evidence of request.evidence) {
    assertEvidence(evidence)
    if (evidenceById.has(evidence.connector_id)) {
      throw new NvidiaSubstrateError(`DUPLICATE_CONNECTOR_EVIDENCE:${evidence.connector_id}`)
    }
    evidenceById.set(evidence.connector_id, evidence)
  }

  const available = new Set(evidenceById.keys())
  const verified_connectors = NVIDIA_CONNECTOR_CATALOG
    .map(descriptor => descriptor.connector_id)
    .filter(connector => available.has(connector))

  const platformRequired = ['nemo-platform', 'nemo-fabric'] as const
  const biomolecularRequired = ['nvidia-agent-toolkit', 'bionemo-ir'] as const
  const quantumRequired = ['cudaq', 'cuquantum'] as const
  const platformMissing = missingConnectors(platformRequired, available)
  const biomolecularMissing = missingConnectors(biomolecularRequired, available)
  const quantumMissing = missingConnectors(quantumRequired, available)

  const digestPayload = {
    schema_version: NVIDIA_SUBSTRATE_RECEIPT_SCHEMA,
    task_id: request.task_id,
    verified_connectors,
    agent_platform: {
      state: platformMissing.length === 0 ? 'READY' as const : 'NOT_ESTABLISHED' as const,
      required_connectors: platformRequired,
      missing_connectors: platformMissing,
      execution: 'NOT_ESTABLISHED' as const,
      authority_scope: 'EXECUTION_EVIDENCE_ONLY' as const,
    },
    biomolecular_agent_fabric: {
      state: biomolecularMissing.length === 0 ? 'READY' as const : 'NOT_ESTABLISHED' as const,
      required_connectors: biomolecularRequired,
      missing_connectors: biomolecularMissing,
      gpu_execution: 'NOT_ESTABLISHED' as const,
    },
    quantum_manifold: {
      state: quantumMissing.length === 0
        ? 'CUDAQ_CUQUANTUM_SIMULATION_READY' as const
        : 'NOT_ESTABLISHED' as const,
      required_connectors: quantumRequired,
      missing_connectors: quantumMissing,
      qpu_access: 'NOT_ESTABLISHED' as const,
      quantum_advantage: 'NOT_ESTABLISHED' as const,
      authority_scope: 'DIAGNOSTIC_ONLY' as const,
    },
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
    is_replay_reconstructable: true as const,
  }

  const receipt_digest = await hashValue(digestPayload)
  return deepFreeze<NvidiaScientificSubstrateReceipt>({
    ...digestPayload,
    receipt_digest,
  })
}
