import type { DashScopeReasoningProfile, ProviderCognitiveProfile } from '../coordination/provider-cognition.js'

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
  readonly tools?: readonly Readonly<Record<string, unknown>>[]
}

export function buildQwenResponsesRequest(
  input: BuildQwenResponsesRequestInput,
): QwenResponsesRequest {
  if (input.profile.provider !== 'dashscope' || input.profile.reasoning.kind !== 'dashscope') {
    throw new TypeError('buildQwenResponsesRequest requires a DashScope profile')
  }
  if (!input.input.trim()) throw new TypeError('Qwen Responses input must not be empty')

  return Object.freeze({
    model: input.profile.model,
    input: input.input,
    store: false as const,
    reasoning: Object.freeze({ effort: input.profile.reasoning.effort }),
    ...(input.tools !== undefined
      ? { tools: Object.freeze([...input.tools]), tool_choice: 'auto' as const }
      : {}),
  })
}
