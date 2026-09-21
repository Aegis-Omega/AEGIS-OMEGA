// ============================================================
// AEGIS Sovereign Provider-Native Agent Contract V1
// EPISTEMIC TIER: T1 — provider-bound selection, zero granted authority
// authority_effect = NONE
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  selectProviderV1,
  type ProviderCapabilityV1,
  type ProviderDescriptorV1,
  type ProviderMeshSnapshotV1,
  type ProviderSelectionRequestV1,
} from './provider-mesh.js'

export const PROVIDER_NATIVE_AGENT_SCHEMA_VERSION = '1.0.0' as const

export type ProviderNativeAgentTransportV1 =
  | 'PROVIDER_NATIVE_AGENT_RUNTIME'
  | 'PROVIDER_NATIVE_SDK'
  | 'PROVIDER_NATIVE_TOOL_SURFACE'

export interface ProviderNativeAgentDescriptorV1 {
  schema_version: typeof PROVIDER_NATIVE_AGENT_SCHEMA_VERSION
  agent_id: string
  provider_id: string
  transport: ProviderNativeAgentTransportV1
  declared_capabilities: readonly ProviderCapabilityV1[]
  write_authority: 'NOT_GRANTED'
  merge_authority: 'NOT_GRANTED'
  deploy_authority: 'NOT_GRANTED'
  financial_authority: 'NOT_GRANTED'
  authority_effect: 'NONE'
}

export interface ProviderNativeAgentRegistryV1 {
  schema_version: typeof PROVIDER_NATIVE_AGENT_SCHEMA_VERSION
  agents: readonly ProviderNativeAgentDescriptorV1[]
  registry_root: SHA256Hex
  authority_effect: 'NONE'
}

export interface ProviderNativeAgentSelectionReceiptV1 {
  schema_version: typeof PROVIDER_NATIVE_AGENT_SCHEMA_VERSION
  outcome: 'SELECTED' | 'DENIED'
  provider_id: string | null
  agent_id: string | null
  provider_selection_receipt_root: SHA256Hex
  registry_root: SHA256Hex
  authority_effect: 'NONE'
  receipt_root: SHA256Hex
}

function nativeTransport(providerId: string): ProviderNativeAgentTransportV1 {
  if (providerId === 'openai' || providerId === 'anthropic' || providerId === 'google-cloud') {
    return 'PROVIDER_NATIVE_AGENT_RUNTIME'
  }
  return 'PROVIDER_NATIVE_SDK'
}

export async function buildProviderNativeAgentRegistryV1(
  descriptors: readonly ProviderDescriptorV1[],
): Promise<ProviderNativeAgentRegistryV1> {
  const agents = descriptors
    .filter(descriptor =>
      descriptor.schema_version === PROVIDER_MESH_SCHEMA_VERSION &&
      descriptor.authority_effect === 'NONE' &&
      descriptor.declared_capabilities.includes('AGENT_EXECUTION'))
    .map(descriptor => ({
      schema_version: PROVIDER_NATIVE_AGENT_SCHEMA_VERSION,
      agent_id: `provider-agent:${descriptor.provider_id}`,
      provider_id: descriptor.provider_id,
      transport: nativeTransport(descriptor.provider_id),
      declared_capabilities: [...descriptor.declared_capabilities].sort(),
      write_authority: 'NOT_GRANTED' as const,
      merge_authority: 'NOT_GRANTED' as const,
      deploy_authority: 'NOT_GRANTED' as const,
      financial_authority: 'NOT_GRANTED' as const,
      authority_effect: 'NONE' as const,
    }))
    .sort((left, right) => left.provider_id.localeCompare(right.provider_id))

  const ids = agents.map(agent => agent.provider_id)
  if (new Set(ids).size !== ids.length) throw new TypeError('duplicate native provider agent')

  const registry_root = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_PROVIDER_NATIVE_AGENT_REGISTRY_V1',
    schema_version: PROVIDER_NATIVE_AGENT_SCHEMA_VERSION,
    agents,
    authority_effect: 'NONE',
  })) as SHA256Hex

  return {
    schema_version: PROVIDER_NATIVE_AGENT_SCHEMA_VERSION,
    agents,
    registry_root,
    authority_effect: 'NONE',
  }
}

export async function selectProviderNativeAgentV1(
  snapshot: ProviderMeshSnapshotV1,
  registry: ProviderNativeAgentRegistryV1,
  request: ProviderSelectionRequestV1,
): Promise<ProviderNativeAgentSelectionReceiptV1> {
  if (registry.schema_version !== PROVIDER_NATIVE_AGENT_SCHEMA_VERSION) {
    throw new TypeError('unsupported native provider agent registry schema')
  }
  if (registry.authority_effect !== 'NONE') {
    throw new TypeError('native provider agent registry authority_effect must be NONE')
  }

  const recomputed = await buildProviderNativeAgentRegistryV1(
    snapshot.descriptors.filter(descriptor =>
      registry.agents.some(agent => agent.provider_id === descriptor.provider_id)),
  )
  if (recomputed.registry_root !== registry.registry_root) {
    throw new TypeError('native provider agent registry_root verification failed')
  }

  const allowedNative = registry.agents.map(agent => agent.provider_id)
  const callerAllowed = request.allowed_providers === undefined
    ? allowedNative
    : request.allowed_providers.filter(provider => allowedNative.includes(provider))

  const providerReceipt = await selectProviderV1(snapshot, {
    ...request,
    required_capabilities: request.required_capabilities.includes('AGENT_EXECUTION')
      ? request.required_capabilities
      : ['AGENT_EXECUTION', ...request.required_capabilities],
    allowed_providers: callerAllowed,
  })

  const selectedAgent = providerReceipt.provider_id === null
    ? null
    : registry.agents.find(agent => agent.provider_id === providerReceipt.provider_id) ?? null

  const body = {
    schema_version: PROVIDER_NATIVE_AGENT_SCHEMA_VERSION,
    outcome: selectedAgent === null ? 'DENIED' as const : 'SELECTED' as const,
    provider_id: selectedAgent?.provider_id ?? null,
    agent_id: selectedAgent?.agent_id ?? null,
    provider_selection_receipt_root: providerReceipt.receipt_root,
    registry_root: registry.registry_root,
    authority_effect: 'NONE' as const,
  }

  const receipt_root = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_PROVIDER_NATIVE_AGENT_SELECTION_RECEIPT_V1',
    receipt: body,
  })) as SHA256Hex

  return { ...body, receipt_root }
}
