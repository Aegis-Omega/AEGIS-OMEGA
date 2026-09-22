import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  buildProviderMeshSnapshotV1,
  type ProviderDescriptorV1,
  type ProviderObservationV1,
} from '../../src/sovereignty/provider-mesh.js'
import { buildProviderNativeAgentRegistryV1 } from '../../src/sovereignty/provider-native-agents.js'
import { createGoogleAdkNativeAgentAdapterV1 } from '../../src/sovereignty/provider-adapters/google-adk-native-agent.js'

const h = (c: string): SHA256Hex => c.repeat(64) as SHA256Hex
const descriptor: ProviderDescriptorV1 = {
  schema_version: PROVIDER_MESH_SCHEMA_VERSION,
  provider_id: 'google-cloud',
  planes: ['EXECUTION', 'INTELLIGENCE'],
  declared_capabilities: ['AGENT_EXECUTION', 'CONTAINER_RUNTIME', 'DURABLE_RUNNER', 'MODEL_INFERENCE'],
  authority_effect: 'NONE',
}
const observation: ProviderObservationV1 = {
  schema_version: PROVIDER_MESH_SCHEMA_VERSION,
  provider_id: 'google-cloud',
  state: 'OBSERVED_AVAILABLE',
  observed_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'],
  evidence_hash: h('a'),
  observation_generation: '10',
  authority_effect: 'NONE',
}

describe('Google Cloud ADK native agent adapter v1', () => {
  it('binds fresh provider evidence to an injected ADK runner with no tools', async () => {
    const snapshot = await buildProviderMeshSnapshotV1([descriptor], [observation])
    const registry = await buildProviderNativeAgentRegistryV1([descriptor])
    const adapter = createGoogleAdkNativeAgentAdapterV1({
      runner: {
        async run(input) {
          expect(input.tools).toEqual([])
          expect(input.agent_name).toBe('aegis_google_provider_agent')
          return { final_output: 'bounded', session_id: 'adk-session-1', model: 'gemini-agent-model' }
        },
      },
    })
    const result = await adapter.execute({
      snapshot, registry, task: 'inspect evidence',
      current_generation: '10', max_observation_age_generations: '1',
    })
    expect(result.selection.outcome).toBe('SELECTED')
    expect(result.receipt?.provider_id).toBe('google-cloud')
    expect(result.receipt?.deploy_authority).toBe('NOT_GRANTED')
    expect(result.receipt?.authority_effect).toBe('NONE')
  })

  it('does not invoke ADK when provider evidence is unavailable', async () => {
    const snapshot = await buildProviderMeshSnapshotV1([descriptor], [{
      ...observation, state: 'OBSERVED_UNAVAILABLE', observed_capabilities: [],
    }])
    const registry = await buildProviderNativeAgentRegistryV1([descriptor])
    let called = false
    const adapter = createGoogleAdkNativeAgentAdapterV1({
      runner: { async run() { called = true; throw new Error('must not run') } },
    })
    const result = await adapter.execute({
      snapshot, registry, task: 'inspect',
      current_generation: '10', max_observation_age_generations: '1',
    })
    expect(result.selection.outcome).toBe('DENIED')
    expect(result.receipt).toBeNull()
    expect(called).toBe(false)
  })
})
