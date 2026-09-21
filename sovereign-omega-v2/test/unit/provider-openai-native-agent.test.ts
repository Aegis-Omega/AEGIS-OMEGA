import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  buildProviderMeshSnapshotV1,
  type ProviderDescriptorV1,
  type ProviderObservationV1,
} from '../../src/sovereignty/provider-mesh.js'
import { buildProviderNativeAgentRegistryV1 } from '../../src/sovereignty/provider-native-agents.js'
import {
  createOpenAINativeAgentAdapterV1,
  type OpenAIAgentRunnerV1,
} from '../../src/sovereignty/provider-adapters/openai-native-agent.js'

const h = (c: string): SHA256Hex => c.repeat(64) as SHA256Hex

const openai: ProviderDescriptorV1 = {
  schema_version: PROVIDER_MESH_SCHEMA_VERSION,
  provider_id: 'openai',
  planes: ['INTELLIGENCE'],
  declared_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE', 'REPOSITORY_AGENT'],
  authority_effect: 'NONE',
}

const observation: ProviderObservationV1 = {
  schema_version: PROVIDER_MESH_SCHEMA_VERSION,
  provider_id: 'openai',
  state: 'OBSERVED_AVAILABLE',
  observed_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'],
  evidence_hash: h('a'),
  observation_generation: '10',
  authority_effect: 'NONE',
}

describe('OpenAI native agent adapter v1', () => {
  it('binds an injected native runner to provider selection and emits an evidence receipt', async () => {
    const snapshot = await buildProviderMeshSnapshotV1([openai], [observation])
    const registry = await buildProviderNativeAgentRegistryV1([openai])

    const runner: OpenAIAgentRunnerV1 = {
      async run(input) {
        expect(input.agent_name).toBe('AEGIS OpenAI Provider Agent')
        expect(input.instructions).toContain('authority')
        return {
          final_output: 'bounded result',
          run_id: 'run-test-1',
          model: 'gpt-5.6-sol',
        }
      },
    }

    const adapter = createOpenAINativeAgentAdapterV1({ runner })
    const result = await adapter.execute({
      snapshot,
      registry,
      task: 'Inspect evidence and return a bounded summary.',
      current_generation: '10',
      max_observation_age_generations: '1',
    })

    expect(result.selection.outcome).toBe('SELECTED')
    expect(result.selection.provider_id).toBe('openai')
    expect(result.output.final_output).toBe('bounded result')
    expect(result.receipt.provider_id).toBe('openai')
    expect(result.receipt.native_run_id).toBe('run-test-1')
    expect(result.receipt.authority_effect).toBe('NONE')
    expect(result.receipt.write_authority).toBe('NOT_GRANTED')
    expect(result.receipt.receipt_root).toMatch(/^[0-9a-f]{64}$/)
  })

  it('does not call the native runner when OpenAI lacks fresh AGENT_EXECUTION evidence', async () => {
    const unavailable = { ...observation, state: 'OBSERVED_UNAVAILABLE' as const, observed_capabilities: [] }
    const snapshot = await buildProviderMeshSnapshotV1([openai], [unavailable])
    const registry = await buildProviderNativeAgentRegistryV1([openai])
    let called = false
    const adapter = createOpenAINativeAgentAdapterV1({
      runner: { async run() { called = true; throw new Error('must not run') } },
    })

    const result = await adapter.execute({
      snapshot,
      registry,
      task: 'test',
      current_generation: '10',
      max_observation_age_generations: '1',
    })

    expect(result.selection.outcome).toBe('DENIED')
    expect(result.output).toBeNull()
    expect(result.receipt).toBeNull()
    expect(called).toBe(false)
  })

  it('rejects blank tasks before native execution', async () => {
    const snapshot = await buildProviderMeshSnapshotV1([openai], [observation])
    const registry = await buildProviderNativeAgentRegistryV1([openai])
    const adapter = createOpenAINativeAgentAdapterV1({
      runner: { async run() { throw new Error('must not run') } },
    })

    await expect(adapter.execute({
      snapshot,
      registry,
      task: '   ',
      current_generation: '10',
      max_observation_age_generations: '1',
    })).rejects.toThrow('task must be non-empty')
  })
})
