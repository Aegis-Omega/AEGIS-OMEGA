import type { DashScopeReasoningProfile, ProviderCognitiveProfile } from '../coordination/provider-cognition.js'
import {
  assertBoundProviderToolSetV1,
  type BoundProviderToolSetV1,
} from '../coordination/provider-tool-set.js'

export interface QwenResponsesRequest {
  readonly model: string
  readonly input: string
  readonly store: false
  readonly reasoning: Readonly<{ effort: DashScopeReasoningProfile['effort'] }>
  readonly tools?: readonly Readonly<Record<string, unknown>>[]
  readonly tool_choice?: 'auto'
}

export interface BuildQwenResponsesRequestInput {
  readonly profile: ProviderCognitiveProfile
  readonly input: string
  readonly tool_set?: BoundProviderToolSetV1
}

export function buildQwenResponsesRequest(
  input: BuildQwenResponsesRequestInput,
): QwenResponsesRequest {
  if (input.profile.provider !== 'dashscope' || input.profile.reasoning.kind !== 'dashscope') {
    throw new TypeError('buildQwenResponsesRequest requires a DashScope profile')
  }
  if (!input.input.trim()) throw new TypeError('Qwen Responses input must not be empty')
  if (input.tool_set !== undefined) assertBoundProviderToolSetV1(input.tool_set)

  return Object.freeze({
    model: input.profile.model,
    input: input.input,
    store: false as const,
    reasoning: Object.freeze({ effort: input.profile.reasoning.effort }),
    ...(input.tool_set !== undefined
      ? { tools: input.tool_set.tools, tool_choice: 'auto' as const }
      : {}),
  })
}
