// ============================================================
// AEGIS OpenAI Agents SDK Runner Binding V1
// EPISTEMIC TIER: T1 — concrete SDK seam, no tools, zero mutation authority
// authority_effect = NONE
// ============================================================

import type {
  OpenAIAgentRunnerInputV1,
  OpenAIAgentRunnerOutputV1,
  OpenAIAgentRunnerV1,
} from './openai-native-agent.js'

export interface OpenAIAgentsSdkResultV1 {
  readonly finalOutput?: unknown
  readonly lastResponseId?: string
}

export interface OpenAIAgentsSdkBindingsV1 {
  readonly Agent: new (config: {
    readonly name: string
    readonly instructions: string
    readonly model: string
    readonly tools: readonly []
  }) => unknown
  run(agent: unknown, task: string): Promise<OpenAIAgentsSdkResultV1>
}

export interface OpenAIAgentsSdkRunnerOptionsV1 {
  readonly bindings: OpenAIAgentsSdkBindingsV1
  readonly model: string
}

/**
 * Binds the official OpenAI Agents SDK Agent + run primitives to the AEGIS
 * provider runner contract. V1 deliberately supplies no tools; repository,
 * deploy, financial, and other external mutations remain impossible through
 * this binding.
 *
 * Production composition should inject:
 *   import { Agent, run } from '@openai/agents'
 * after that package is admitted into package.json/package-lock.json.
 */
export function createOpenAIAgentsSdkRunnerV1(
  options: OpenAIAgentsSdkRunnerOptionsV1,
): OpenAIAgentRunnerV1 {
  if (!options.model.trim()) throw new TypeError('OpenAI Agents SDK model must be non-empty')

  return {
    async run(input: OpenAIAgentRunnerInputV1): Promise<OpenAIAgentRunnerOutputV1> {
      const agent = new options.bindings.Agent({
        name: input.agent_name,
        instructions: input.instructions,
        model: options.model,
        tools: [],
      })

      const result = await options.bindings.run(agent, input.task)
      const runId = result.lastResponseId
      if (typeof runId !== 'string' || !runId.trim()) {
        throw new TypeError('OpenAI Agents SDK result must expose a stable run identifier')
      }

      const finalOutput = result.finalOutput
      const normalizedOutput = typeof finalOutput === 'string'
        ? finalOutput
        : JSON.stringify(finalOutput ?? null)

      return {
        final_output: normalizedOutput,
        run_id: runId,
        model: options.model,
      }
    },
  }
}
