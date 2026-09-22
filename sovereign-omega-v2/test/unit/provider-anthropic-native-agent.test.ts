import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  buildProviderMeshSnapshotV1,
  type ProviderDescriptorV1,
  type ProviderObservationV1,
} from '../../src/sovereignty/provider-mesh.js'
import { buildProviderNativeAgentRegistryV1 } from '../../src/sovereignty/provider-native-agents.js'
import { createAnthropicNativeAgentAdapterV1 } from '../../src/sovereignty/provider-adapters/anthropic-native-agent.js'

const h = (c: string): SHA256Hex => c.repeat(64) as SHA256Hex
const descriptor: ProviderDescriptorV1 = {
  schema_version: PROVIDER_MESH_SCHEMA_VERSION,
  provider_id: 'anthropic',
  planes: ['INTELLIGENCE'],
  declared_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'],
  authority_effect: 'NONE',
}
const observation: ProviderObservationV1 = {
  schema_version: PROVIDER_MESH_SCHEMA_VERSION,
  provider_id: 'anthropic',
  state: 'OBSERVED_AVAILABLE',
  observed_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'],
  evidence_hash: h('a'),
  observation_generation: '10',
  authority_effect: 'NONE',
}

describe('Anthropic native agent adapter v1', () => {
  it('binds fresh provider evidence to an injected Claude Agent SDK runner', async () => {
    const snapshot = await buildProviderMeshSnapshotV1([descriptor], [observation])
    const registry = await buildProviderNativeAgentRegistryV1([descriptor])
    const adapter = createAnthropicNativeAgentAdapterV1({
      runner: {
        async run(input) {
          expect(input.allowed_tools).toEqual([])
          return { final_output: 'bounded', session_id: 'session-1', model: 'claude-opus-5' }
        },
      },
    })
    const result = await adapter.execute({
      snapshot, registry, task: 'inspect evidence',
      current_generation: '10', max_observation_age_generations: '1',
    })
    expect(result.selection.outcome).toBe('SELECTED')
    expect(result.receipt?.provider_id).toBe('anthropic')
    expect(result.receipt?.write_authority).toBe('NOT_GRANTED')
    expect(result.receipt?.authority_effect).toBe('NONE')
  })

  it('does not invoke Claude Agent SDK when provider evidence is unavailable', async () => {
    const snapshot = await buildProviderMeshSnapshotV1([descriptor], [{
      ...observation, state: 'OBSERVED_UNAVAILABLE', observed_capabilities: [],
    }])
    const registry = await buildProviderNativeAgentRegistryV1([descriptor])
    let called = false
    const adapter = createAnthropicNativeAgentAdapterV1({
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
