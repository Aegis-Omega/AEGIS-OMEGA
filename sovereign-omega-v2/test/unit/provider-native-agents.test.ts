import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  buildProviderMeshSnapshotV1,
  type ProviderDescriptorV1,
  type ProviderObservationV1,
} from '../../src/sovereignty/provider-mesh.js'
import {
  buildProviderNativeAgentRegistryV1,
  selectProviderNativeAgentV1,
} from '../../src/sovereignty/provider-native-agents.js'

const h = (c: string): SHA256Hex => c.repeat(64) as SHA256Hex

const descriptors: readonly ProviderDescriptorV1[] = [
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'openai',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE', 'REPOSITORY_AGENT'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'anthropic',
    planes: ['INTELLIGENCE'],
    declared_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'],
    authority_effect: 'NONE',
  },
  {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'google-cloud',
    planes: ['EXECUTION', 'INTELLIGENCE'],
    declared_capabilities: ['AGENT_EXECUTION', 'CONTAINER_RUNTIME', 'DURABLE_RUNNER', 'MODEL_INFERENCE'],
    authority_effect: 'NONE',
  },
]

const observations: readonly ProviderObservationV1[] = descriptors.map((d, index) => ({
  schema_version: PROVIDER_MESH_SCHEMA_VERSION,
  provider_id: d.provider_id,
  state: 'OBSERVED_AVAILABLE',
  observed_capabilities: d.declared_capabilities,
  evidence_hash: h(String(index + 1)),
  observation_generation: '10',
  authority_effect: 'NONE',
}))

describe('provider-native agent contract v1', () => {
  it('builds one authority-neutral native agent descriptor per declared agent provider', async () => {
    const registry = await buildProviderNativeAgentRegistryV1(descriptors)
    expect(registry.agents.map(a => a.provider_id)).toEqual(['anthropic', 'google-cloud', 'openai'])
    expect(registry.agents.every(a => a.authority_effect === 'NONE')).toBe(true)
    expect(registry.agents.every(a => a.write_authority === 'NOT_GRANTED')).toBe(true)
    expect(registry.registry_root).toMatch(/^[0-9a-f]{64}$/)
  })

  it('selects a native agent only through fresh provider-mesh evidence', async () => {
    const snapshot = await buildProviderMeshSnapshotV1(descriptors, observations)
    const registry = await buildProviderNativeAgentRegistryV1(descriptors)
    const receipt = await selectProviderNativeAgentV1(snapshot, registry, {
      required_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'],
      preferred_provider_order: ['openai', 'anthropic'],
      current_generation: '10',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('SELECTED')
    expect(receipt.provider_id).toBe('openai')
    expect(receipt.agent_id).toBe('provider-agent:openai')
    expect(receipt.authority_effect).toBe('NONE')
    expect(receipt.provider_selection_receipt_root).toMatch(/^[0-9a-f]{64}$/)
  })

  it('fails closed when a caller asks the native agent layer for mutation authority', async () => {
    const registry = await buildProviderNativeAgentRegistryV1(descriptors)
    const openai = registry.agents.find(a => a.provider_id === 'openai')
    expect(openai?.write_authority).toBe('NOT_GRANTED')
    expect(openai?.merge_authority).toBe('NOT_GRANTED')
    expect(openai?.deploy_authority).toBe('NOT_GRANTED')
    expect(openai?.financial_authority).toBe('NOT_GRANTED')
  })

  it('does not manufacture an agent for a provider without AGENT_EXECUTION', async () => {
    const registry = await buildProviderNativeAgentRegistryV1([
      {
        schema_version: PROVIDER_MESH_SCHEMA_VERSION,
        provider_id: 'tavily',
        planes: ['INTELLIGENCE'],
        declared_capabilities: ['WEB_RESEARCH'],
        authority_effect: 'NONE',
      },
    ])
    expect(registry.agents).toEqual([])
  })
})
