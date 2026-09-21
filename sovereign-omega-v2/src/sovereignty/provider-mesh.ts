// ============================================================
// AEGIS Sovereign Provider Mesh V1
// EPISTEMIC TIER: T1 — deterministic provider-selection contract
// authority_effect = NONE
// ============================================================
//
// Declared provider capability is not evidence of account access, credits,
// service reachability, or execution authority. Selection requires a fresh
// OBSERVED_AVAILABLE observation. The resulting receipt does not grant
// repository, cloud, model, billing, or data-movement authority.

import type { SHA256Hex } from '../core/types.js'
import type { DurableExecutionRecordV1 } from './contracts.js'
import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'

export const PROVIDER_MESH_SCHEMA_VERSION = '1.0.0' as const
export type ProviderMeshSchemaVersion = typeof PROVIDER_MESH_SCHEMA_VERSION

export type ProviderPlaneV1 = 'EXECUTION' | 'INTELLIGENCE'

export type ProviderCapabilityV1 =
  | 'AGENT_EXECUTION'
  | 'CONTAINER_RUNTIME'
  | 'DURABLE_RUNNER'
  | 'GPU_COMPUTE'
  | 'MODEL_INFERENCE'
  | 'REPOSITORY_AGENT'
  | 'REPOSITORY_WORKFLOW'
  | 'WEB_RESEARCH'
  | 'SERVERLESS_FUNCTION'
  | 'DATABASE'
  | 'HTTP_EGRESS'
  | 'SYMBOLIC_COMPUTE'
  | 'REPOSITORY_READ'
  | 'DOCUMENT_RETRIEVAL'
  | 'EMAIL_RETRIEVAL'
  | 'CALENDAR_READ'
  | 'COLLABORATION_READ'
  | 'KNOWLEDGE_BASE_READ'
  | 'WORK_TRACKING_READ'
  | 'CRM_READ'

export type ProviderObservationStateV1 =
  | 'UNKNOWN'
  | 'CONFIGURED'
  | 'ACCOUNT_CONFIGURED'
  | 'NETWORK_REACHABLE'
  | 'CREDENTIAL_MISSING'
  | 'BILLING_BLOCKED'
  | 'OBSERVED_AVAILABLE'
  | 'OBSERVED_UNAVAILABLE'
  | 'DISABLED'

export interface ProviderDescriptorV1 {
  schema_version: ProviderMeshSchemaVersion
  provider_id: string
  planes: readonly ProviderPlaneV1[]
  declared_capabilities: readonly ProviderCapabilityV1[]
  authority_effect: 'NONE'
}

export interface ProviderObservationV1 {
  schema_version: ProviderMeshSchemaVersion
  provider_id: string
  state: ProviderObservationStateV1
  observed_capabilities: readonly ProviderCapabilityV1[]
  evidence_hash: SHA256Hex
  observation_generation: string
  authority_effect: 'NONE'
}

export interface ProviderMeshSnapshotV1 {
  schema_version: ProviderMeshSchemaVersion
  descriptors: readonly ProviderDescriptorV1[]
  observations: readonly ProviderObservationV1[]
  snapshot_root: SHA256Hex
  authority_effect: 'NONE'
}

export interface ProviderSelectionRequestV1 {
  required_capabilities: readonly ProviderCapabilityV1[]
  allowed_providers?: readonly string[]
  preferred_provider_order?: readonly string[]
  current_generation: string
  max_observation_age_generations: string
}

export type ProviderSelectionDenialCodeV1 =
  | 'NO_PROVIDER_DECLARED'
  | 'NO_PROVIDER_ALLOWED'
  | 'PROVIDER_NOT_OBSERVED_AVAILABLE'
  | 'OBSERVATION_FROM_FUTURE'
  | 'OBSERVATION_STALE'
  | 'REQUIRED_CAPABILITY_UNOBSERVED'

export interface ProviderSelectionReceiptV1 {
  schema_version: ProviderMeshSchemaVersion
  outcome: 'SELECTED' | 'DENIED'
  provider_id: string | null
  snapshot_root: SHA256Hex
  required_capabilities: readonly ProviderCapabilityV1[]
  evidence_hashes: readonly SHA256Hex[]
  denial_codes: readonly ProviderSelectionDenialCodeV1[]
  authority_effect: 'NONE'
  receipt_root: SHA256Hex
}

export interface ProviderBoundExecutionV1 {
  durable_execution: DurableExecutionRecordV1
  provider_selection_receipt_root: SHA256Hex
  authority_effect: 'NONE'
}

export function observeProviderFromDurableExecutionV1(
  record: DurableExecutionRecordV1,
  observed_capabilities: readonly ProviderCapabilityV1[],
  observation_generation: string,
): ProviderObservationV1 {
  assertProviderId('durable_execution.provider', record.provider)
  assertDecimal('observation_generation', observation_generation)
  if (record.status !== 'SUCCEEDED' && record.status !== 'FAILED' && record.status !== 'CANCELLED' && record.status !== 'EXPIRED') {
    throw new TypeError('durable execution must be terminal before provider observation')
  }
  if (record.terminal_receipt_hash === null) {
    throw new TypeError('terminal durable execution must carry terminal_receipt_hash')
  }
  assertHash('terminal_receipt_hash', record.terminal_receipt_hash)
  observed_capabilities.forEach((capability) => {
    if (!ALL_CAPABILITIES.has(capability)) throw new TypeError(`unknown observed capability: ${capability}`)
  })
  assertNoDuplicates('observed_capabilities', observed_capabilities)

  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: record.provider,
    state: record.status === 'SUCCEEDED' ? 'OBSERVED_AVAILABLE' : 'OBSERVED_UNAVAILABLE',
    observed_capabilities: sortedUnique(observed_capabilities),
    evidence_hash: record.terminal_receipt_hash,
    observation_generation,
    authority_effect: 'NONE',
  }
}

const SHA256_PATTERN = /^[0-9a-f]{64}$/
const DECIMAL_PATTERN = /^(0|[1-9][0-9]*)$/
const PROVIDER_ID_PATTERN = /^[a-z0-9][a-z0-9._-]{1,63}$/

const ALL_PLANES = new Set<ProviderPlaneV1>(['EXECUTION', 'INTELLIGENCE'])
const ALL_CAPABILITIES = new Set<ProviderCapabilityV1>([
  'AGENT_EXECUTION',
  'CONTAINER_RUNTIME',
  'DURABLE_RUNNER',
  'GPU_COMPUTE',
  'MODEL_INFERENCE',
  'REPOSITORY_AGENT',
  'REPOSITORY_WORKFLOW',
  'WEB_RESEARCH',
  'SERVERLESS_FUNCTION',
  'DATABASE',
  'HTTP_EGRESS',
  'SYMBOLIC_COMPUTE',
  'REPOSITORY_READ',
  'DOCUMENT_RETRIEVAL',
  'EMAIL_RETRIEVAL',
  'CALENDAR_READ',
  'COLLABORATION_READ',
  'KNOWLEDGE_BASE_READ',
  'WORK_TRACKING_READ',
  'CRM_READ',
])
const ALL_STATES = new Set<ProviderObservationStateV1>([
  'UNKNOWN',
  'CONFIGURED',
  'ACCOUNT_CONFIGURED',
  'NETWORK_REACHABLE',
  'CREDENTIAL_MISSING',
  'BILLING_BLOCKED',
  'OBSERVED_AVAILABLE',
  'OBSERVED_UNAVAILABLE',
  'DISABLED',
])

function assertProviderId(field: string, value: string): void {
  if (!PROVIDER_ID_PATTERN.test(value)) throw new TypeError(`${field} is invalid`)
}

function assertHash(field: string, value: string): asserts value is SHA256Hex {
  if (!SHA256_PATTERN.test(value)) throw new TypeError(`${field} must be lowercase SHA-256 hex`)
}

function assertDecimal(field: string, value: string): void {
  if (!DECIMAL_PATTERN.test(value)) throw new TypeError(`${field} must be canonical unsigned decimal`)
}

function sortedUnique<T extends string>(values: readonly T[]): T[] {
  return [...new Set(values)].sort() as T[]
}

function assertNoDuplicates<T extends string>(field: string, values: readonly T[]): void {
  if (new Set(values).size !== values.length) throw new TypeError(`${field} must not contain duplicates`)
}

function normalizeDescriptor(descriptor: ProviderDescriptorV1): ProviderDescriptorV1 {
  if (descriptor.schema_version !== PROVIDER_MESH_SCHEMA_VERSION) {
    throw new TypeError(`unsupported provider mesh schema: ${descriptor.schema_version}`)
  }
  assertProviderId('provider_id', descriptor.provider_id)
  if (descriptor.authority_effect !== 'NONE') throw new TypeError('provider descriptor authority_effect must be NONE')
  if (!Array.isArray(descriptor.planes) || descriptor.planes.length === 0) {
    throw new TypeError('planes must be a non-empty array')
  }
  if (!Array.isArray(descriptor.declared_capabilities) || descriptor.declared_capabilities.length === 0) {
    throw new TypeError('declared_capabilities must be a non-empty array')
  }
  descriptor.planes.forEach((plane) => {
    if (!ALL_PLANES.has(plane)) throw new TypeError(`unknown provider plane: ${plane}`)
  })
  descriptor.declared_capabilities.forEach((capability) => {
    if (!ALL_CAPABILITIES.has(capability)) throw new TypeError(`unknown provider capability: ${capability}`)
  })
  assertNoDuplicates('planes', descriptor.planes)
  assertNoDuplicates('declared_capabilities', descriptor.declared_capabilities)
  return {
    ...descriptor,
    planes: sortedUnique(descriptor.planes),
    declared_capabilities: sortedUnique(descriptor.declared_capabilities),
  }
}

function normalizeObservation(
  observation: ProviderObservationV1,
  descriptors: ReadonlyMap<string, ProviderDescriptorV1>,
): ProviderObservationV1 {
  if (observation.schema_version !== PROVIDER_MESH_SCHEMA_VERSION) {
    throw new TypeError(`unsupported provider observation schema: ${observation.schema_version}`)
  }
  assertProviderId('provider_id', observation.provider_id)
  if (!ALL_STATES.has(observation.state)) throw new TypeError(`unknown provider observation state: ${observation.state}`)
  if (observation.authority_effect !== 'NONE') throw new TypeError('provider observation authority_effect must be NONE')
  assertHash('evidence_hash', observation.evidence_hash)
  assertDecimal('observation_generation', observation.observation_generation)
  if (!Array.isArray(observation.observed_capabilities)) {
    throw new TypeError('observed_capabilities must be an array')
  }
  observation.observed_capabilities.forEach((capability) => {
    if (!ALL_CAPABILITIES.has(capability)) throw new TypeError(`unknown observed capability: ${capability}`)
  })
  assertNoDuplicates('observed_capabilities', observation.observed_capabilities)

  const descriptor = descriptors.get(observation.provider_id)
  if (!descriptor) throw new TypeError(`observation provider is not declared: ${observation.provider_id}`)
  const declared = new Set(descriptor.declared_capabilities)
  for (const capability of observation.observed_capabilities) {
    if (!declared.has(capability)) {
      throw new TypeError(`observed capability is not declared for ${observation.provider_id}: ${capability}`)
    }
  }

  return {
    ...observation,
    observed_capabilities: sortedUnique(observation.observed_capabilities),
  }
}

function snapshotPayload(
  descriptors: readonly ProviderDescriptorV1[],
  observations: readonly ProviderObservationV1[],
): Record<string, unknown> {
  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    descriptors,
    observations,
    authority_effect: 'NONE',
  }
}

export async function buildProviderMeshSnapshotV1(
  descriptors: readonly ProviderDescriptorV1[],
  observations: readonly ProviderObservationV1[],
): Promise<ProviderMeshSnapshotV1> {
  const normalizedDescriptors = descriptors
    .map(normalizeDescriptor)
    .sort((left, right) => left.provider_id.localeCompare(right.provider_id))

  const descriptorIds = normalizedDescriptors.map((item) => item.provider_id)
  assertNoDuplicates('provider descriptors', descriptorIds)
  const descriptorMap = new Map(normalizedDescriptors.map((item) => [item.provider_id, item]))

  const normalizedObservations = observations
    .map((item) => normalizeObservation(item, descriptorMap))
    .sort((left, right) => left.provider_id.localeCompare(right.provider_id))

  const observationIds = normalizedObservations.map((item) => item.provider_id)
  assertNoDuplicates('provider observations', observationIds)

  const snapshot_root = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_PROVIDER_MESH_SNAPSHOT_V1',
    snapshot: snapshotPayload(normalizedDescriptors, normalizedObservations),
  }))

  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    descriptors: normalizedDescriptors,
    observations: normalizedObservations,
    snapshot_root,
    authority_effect: 'NONE',
  }
}

function validateSelectionRequest(request: ProviderSelectionRequestV1): {
  required: ProviderCapabilityV1[]
  allowed: string[] | null
  preferred: string[]
  current: bigint
  maxAge: bigint
} {
  if (!Array.isArray(request.required_capabilities) || request.required_capabilities.length === 0) {
    throw new TypeError('required_capabilities must be a non-empty array')
  }
  request.required_capabilities.forEach((capability) => {
    if (!ALL_CAPABILITIES.has(capability)) throw new TypeError(`unknown required capability: ${capability}`)
  })
  assertNoDuplicates('required_capabilities', request.required_capabilities)

  const allowed = request.allowed_providers === undefined
    ? null
    : sortedUnique(request.allowed_providers)
  if (allowed) {
    request.allowed_providers?.forEach((provider) => assertProviderId('allowed_provider', provider))
    assertNoDuplicates('allowed_providers', request.allowed_providers ?? [])
  }

  const preferred = request.preferred_provider_order === undefined
    ? []
    : [...request.preferred_provider_order]
  preferred.forEach((provider) => assertProviderId('preferred_provider', provider))
  assertNoDuplicates('preferred_provider_order', preferred)

  assertDecimal('current_generation', request.current_generation)
  assertDecimal('max_observation_age_generations', request.max_observation_age_generations)

  return {
    required: sortedUnique(request.required_capabilities),
    allowed,
    preferred,
    current: BigInt(request.current_generation),
    maxAge: BigInt(request.max_observation_age_generations),
  }
}

async function makeReceipt(
  body: Omit<ProviderSelectionReceiptV1, 'receipt_root'>,
): Promise<ProviderSelectionReceiptV1> {
  const receipt_root = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_PROVIDER_SELECTION_RECEIPT_V1',
    receipt: body,
  }))
  return { ...body, receipt_root }
}

export async function selectProviderV1(
  snapshot: ProviderMeshSnapshotV1,
  request: ProviderSelectionRequestV1,
): Promise<ProviderSelectionReceiptV1> {
  if (snapshot.schema_version !== PROVIDER_MESH_SCHEMA_VERSION) {
    throw new TypeError(`unsupported provider mesh schema: ${snapshot.schema_version}`)
  }
  if (snapshot.authority_effect !== 'NONE') throw new TypeError('snapshot authority_effect must be NONE')
  assertHash('snapshot_root', snapshot.snapshot_root)

  const verifiedSnapshot = await buildProviderMeshSnapshotV1(snapshot.descriptors, snapshot.observations)
  if (verifiedSnapshot.snapshot_root !== snapshot.snapshot_root) {
    throw new TypeError('snapshot_root verification failed')
  }

  const normalized = validateSelectionRequest(request)
  const observations = new Map(verifiedSnapshot.observations.map((item) => [item.provider_id, item]))
  const allowedSet = normalized.allowed === null ? null : new Set(normalized.allowed)

  const declared = verifiedSnapshot.descriptors.filter((descriptor) => (
    allowedSet === null || allowedSet.has(descriptor.provider_id)
  ))

  if (verifiedSnapshot.descriptors.length === 0) {
    return makeReceipt({
      schema_version: PROVIDER_MESH_SCHEMA_VERSION,
      outcome: 'DENIED',
      provider_id: null,
      snapshot_root: snapshot.snapshot_root,
      required_capabilities: normalized.required,
      evidence_hashes: [],
      denial_codes: ['NO_PROVIDER_DECLARED'],
      authority_effect: 'NONE',
    })
  }

  if (declared.length === 0) {
    return makeReceipt({
      schema_version: PROVIDER_MESH_SCHEMA_VERSION,
      outcome: 'DENIED',
      provider_id: null,
      snapshot_root: snapshot.snapshot_root,
      required_capabilities: normalized.required,
      evidence_hashes: [],
      denial_codes: ['NO_PROVIDER_ALLOWED'],
      authority_effect: 'NONE',
    })
  }

  const denialCodes = new Set<ProviderSelectionDenialCodeV1>()
  const candidates: Array<{ descriptor: ProviderDescriptorV1; observation: ProviderObservationV1 }> = []

  for (const descriptor of declared) {
    const observation = observations.get(descriptor.provider_id)
    if (!observation || observation.state !== 'OBSERVED_AVAILABLE') {
      denialCodes.add('PROVIDER_NOT_OBSERVED_AVAILABLE')
      continue
    }

    const observedGeneration = BigInt(observation.observation_generation)
    if (observedGeneration > normalized.current) {
      denialCodes.add('OBSERVATION_FROM_FUTURE')
      continue
    }
    if (normalized.current - observedGeneration > normalized.maxAge) {
      denialCodes.add('OBSERVATION_STALE')
      continue
    }

    const observed = new Set(observation.observed_capabilities)
    if (normalized.required.some((capability) => !observed.has(capability))) {
      denialCodes.add('REQUIRED_CAPABILITY_UNOBSERVED')
      continue
    }

    candidates.push({ descriptor, observation })
  }

  if (candidates.length === 0) {
    return makeReceipt({
      schema_version: PROVIDER_MESH_SCHEMA_VERSION,
      outcome: 'DENIED',
      provider_id: null,
      snapshot_root: snapshot.snapshot_root,
      required_capabilities: normalized.required,
      evidence_hashes: [],
      denial_codes: [...denialCodes].sort(),
      authority_effect: 'NONE',
    })
  }

  const preferredRank = new Map(normalized.preferred.map((provider, index) => [provider, index]))
  candidates.sort((left, right) => {
    const leftRank = preferredRank.get(left.descriptor.provider_id) ?? Number.MAX_SAFE_INTEGER
    const rightRank = preferredRank.get(right.descriptor.provider_id) ?? Number.MAX_SAFE_INTEGER
    if (leftRank !== rightRank) return leftRank - rightRank
    return left.descriptor.provider_id.localeCompare(right.descriptor.provider_id)
  })

  const selected = candidates[0]
  if (!selected) throw new Error('provider selection candidate disappeared')

  return makeReceipt({
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    outcome: 'SELECTED',
    provider_id: selected.descriptor.provider_id,
    snapshot_root: snapshot.snapshot_root,
    required_capabilities: normalized.required,
    evidence_hashes: [selected.observation.evidence_hash],
    denial_codes: [],
    authority_effect: 'NONE',
  })
}

export function bindProviderSelectionToDurableExecutionV1(
  record: DurableExecutionRecordV1,
  receipt: ProviderSelectionReceiptV1,
  executor_id: string,
): ProviderBoundExecutionV1 {
  if (receipt.schema_version !== PROVIDER_MESH_SCHEMA_VERSION) {
    throw new TypeError(`unsupported provider selection schema: ${receipt.schema_version}`)
  }
  if (receipt.outcome !== 'SELECTED' || receipt.provider_id === null) {
    throw new TypeError('provider selection receipt is not selected')
  }
  if (receipt.authority_effect !== 'NONE') {
    throw new TypeError('provider selection receipt authority_effect must be NONE')
  }
  if (receipt.denial_codes.length !== 0) {
    throw new TypeError('selected provider receipt must not contain denial codes')
  }
  assertHash('provider_selection_receipt_root', receipt.receipt_root)
  assertProviderId('selected_provider_id', receipt.provider_id)
  assertProviderId('executor_id', executor_id)

  return {
    durable_execution: {
      ...record,
      provider: receipt.provider_id,
      executor_id,
    },
    provider_selection_receipt_root: receipt.receipt_root,
    authority_effect: 'NONE',
  }
}

// This catalog describes product/service capability classes only.
// It does not assert that the operator has an account, credits, quota,
// a reachable endpoint, or permission to use any provider.
export const DECLARED_PROVIDER_CATALOG_V1: readonly ProviderDescriptorV1[] = [
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'anthropic',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'cloudflare-anthropic',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'cloudflare-worker',
    planes: ['EXECUTION'],
    declared_capabilities: ['SERVERLESS_FUNCTION', 'HTTP_EGRESS'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'dashscope',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['MODEL_INFERENCE'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'fireworks',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['MODEL_INFERENCE'],
    authority_effect: 'NONE',
  },
    {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'github-actions',
    planes: ['EXECUTION'],
    declared_capabilities: ['DURABLE_RUNNER', 'REPOSITORY_WORKFLOW'],
    authority_effect: 'NONE',
  },

  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'google-cloud',
    planes: ['EXECUTION', 'INTELLIGENCE'],
    declared_capabilities: ['AGENT_EXECUTION', 'CONTAINER_RUNTIME', 'DURABLE_RUNNER', 'MODEL_INFERENCE'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'hugging-face-jobs',
    planes: ['EXECUTION'],
    declared_capabilities: ['CONTAINER_RUNTIME', 'DURABLE_RUNNER', 'GPU_COMPUTE'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'nebius-ai-cloud',
    planes: ['EXECUTION'],
    declared_capabilities: ['CONTAINER_RUNTIME', 'DURABLE_RUNNER', 'GPU_COMPUTE'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'nebius-token-factory',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['MODEL_INFERENCE'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'openai',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE', 'REPOSITORY_AGENT'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'openrouter',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['MODEL_INFERENCE'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'railway',
    planes: ['EXECUTION'],
    declared_capabilities: ['CONTAINER_RUNTIME', 'DURABLE_RUNNER'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'supabase-edge',
    planes: ['EXECUTION'],
    declared_capabilities: ['SERVERLESS_FUNCTION', 'DATABASE', 'HTTP_EGRESS'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'tavily',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['WEB_RESEARCH'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'wolfram',
    planes: ['EXECUTION'],
    declared_capabilities: ['SYMBOLIC_COMPUTE'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'chatgpt-github',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['REPOSITORY_READ'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'chatgpt-google-drive',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['DOCUMENT_RETRIEVAL'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'chatgpt-gmail',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['EMAIL_RETRIEVAL'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'chatgpt-google-calendar',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['CALENDAR_READ'],
    authority_effect: 'NONE',
  },
]  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'chatgpt-slack',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['COLLABORATION_READ'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'chatgpt-notion',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['KNOWLEDGE_BASE_READ'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'chatgpt-linear',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['WORK_TRACKING_READ'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'chatgpt-hubspot',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['CRM_READ'],
    authority_effect: 'NONE',
  },

