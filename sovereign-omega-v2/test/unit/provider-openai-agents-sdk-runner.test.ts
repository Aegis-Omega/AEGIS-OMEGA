import { describe, expect, it } from 'vitest'
import {
  createOpenAIAgentsSdkRunnerV1,
  type OpenAIAgentsSdkBindingsV1,
} from '../../src/sovereignty/provider-adapters/openai-agents-sdk-runner.js'

describe('OpenAI Agents SDK runner binding v1', () => {
  it('constructs an SDK Agent and maps run() output into the bounded runner contract', async () => {
    let constructed: Record<string, unknown> | null = null
    const bindings: OpenAIAgentsSdkBindingsV1 = {
      Agent: class {
        constructor(config: Record<string, unknown>) { constructed = config }
      },
      async run(_agent, task) {
        expect(task).toBe('inspect exact-head evidence')
        return {
          finalOutput: 'verified summary',
          lastResponseId: 'resp_test_1',
        }
      },
    }

    const runner = createOpenAIAgentsSdkRunnerV1({
      bindings,
      model: 'gpt-5.6-sol',
    })
    const result = await runner.run({
      agent_name: 'AEGIS OpenAI Provider Agent',
      instructions: 'No external mutation authority.',
      task: 'inspect exact-head evidence',
    })

    expect(constructed).toEqual({
      name: 'AEGIS OpenAI Provider Agent',
      instructions: 'No external mutation authority.',
      model: 'gpt-5.6-sol',
      tools: [],
    })
    expect(result.final_output).toBe('verified summary')
    expect(result.run_id).toBe('resp_test_1')
    expect(result.model).toBe('gpt-5.6-sol')
  })

  it('fails closed when the SDK result has no stable response/run identifier', async () => {
    const bindings: OpenAIAgentsSdkBindingsV1 = {
      Agent: class {},
      async run() { return { finalOutput: 'x' } },
    }
    const runner = createOpenAIAgentsSdkRunnerV1({ bindings, model: 'gpt-5.6-sol' })
    await expect(runner.run({
      agent_name: 'AEGIS OpenAI Provider Agent',
      instructions: 'bounded',
      task: 'test',
    })).rejects.toThrow('stable run identifier')
  })

  it('does not expose tools through the V1 runner', async () => {
    let tools: unknown = null
    const bindings: OpenAIAgentsSdkBindingsV1 = {
      Agent: class {
        constructor(config: Record<string, unknown>) { tools = config.tools }
      },
      async run() { return { finalOutput: 'ok', lastResponseId: 'resp_1' } },
    }
    const runner = createOpenAIAgentsSdkRunnerV1({ bindings, model: 'gpt-5.6-sol' })
    await runner.run({
      agent_name: 'AEGIS OpenAI Provider Agent',
      instructions: 'bounded',
      task: 'test',
    })
    expect(tools).toEqual([])
  })
})
