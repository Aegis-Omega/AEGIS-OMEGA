import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  buildProviderMeshSnapshotV1,
  type ProviderDescriptorV1,
  type ProviderObservationV1,
} from '../../src/sovereignty/provider-mesh.js'
import { buildProviderNativeAgentRegistryV1 } from '../../src/sovereignty/provider-native-agents.js'
import { createProviderNativeConductorV1 } from '../../src/sovereignty/provider-native-conductor.js'

const h = (c: string): SHA256Hex => c.repeat(64) as SHA256Hex
const descriptors: readonly ProviderDescriptorV1[] = ['openai','anthropic','google-cloud'].map(provider_id => ({
  schema_version: PROVIDER_MESH_SCHEMA_VERSION,
  provider_id,
  planes: ['INTELLIGENCE'],
  declared_capabilities: ['AGENT_EXECUTION','MODEL_INFERENCE'],
  authority_effect: 'NONE',
}))
const observations: readonly ProviderObservationV1[] = descriptors.map((d,i) => ({
  schema_version: PROVIDER_MESH_SCHEMA_VERSION,
  provider_id: d.provider_id,
  state: 'OBSERVED_AVAILABLE',
  observed_capabilities: ['AGENT_EXECUTION','MODEL_INFERENCE'],
  evidence_hash: h(String(i+1)),
  observation_generation: '10',
  authority_effect: 'NONE',
}))

describe('provider-native conductor v1', () => {
  it('selects one fresh provider and executes only its adapter', async () => {
    const snapshot = await buildProviderMeshSnapshotV1(descriptors, observations)
    const registry = await buildProviderNativeAgentRegistryV1(descriptors)
    const called: string[] = []
    const conductor = createProviderNativeConductorV1({ adapters: descriptors.map(d => ({
      provider_id: d.provider_id,
      async execute() { called.push(d.provider_id); return { output: d.provider_id, native_receipt_root: h('a') } },
    }))})
    const result = await conductor.execute({
      snapshot, registry, task: 'inspect evidence',
      required_capabilities: ['AGENT_EXECUTION','MODEL_INFERENCE'],
      preferred_provider_order: ['anthropic','openai','google-cloud'],
      current_generation: '10', max_observation_age_generations: '1',
    })
    expect(called).toEqual(['anthropic'])
    expect(result.output).toBe('anthropic')
    expect(result.receipt.provider_id).toBe('anthropic')
    expect(result.receipt.authority_effect).toBe('NONE')
  })

  it('denies without invoking adapters when evidence is stale', async () => {
    const snapshot = await buildProviderMeshSnapshotV1(descriptors, observations)
    const registry = await buildProviderNativeAgentRegistryV1(descriptors)
    let called = false
    const conductor = createProviderNativeConductorV1({ adapters: [{
      provider_id: 'openai', async execute() { called = true; return { output: 'x', native_receipt_root: h('a') } },
    }]})
    const result = await conductor.execute({
      snapshot, registry, task: 'inspect',
      required_capabilities: ['AGENT_EXECUTION','MODEL_INFERENCE'],
      current_generation: '20', max_observation_age_generations: '1',
    })
    expect(result.receipt.outcome).toBe('DENIED')
    expect(result.output).toBeNull()
    expect(called).toBe(false)
  })
})
