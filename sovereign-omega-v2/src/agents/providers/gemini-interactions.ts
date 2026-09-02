import type { GeminiReasoningProfile, ProviderCognitiveProfile } from '../coordination/provider-cognition.js'

export interface GeminiInteractionRequest {
  readonly model: string
  readonly input: string
  readonly store: false
  readonly generation_config: Readonly<{
    thinking_level: GeminiReasoningProfile['thinking_level']
    thinking_summaries: 'none'
    tool_choice: 'auto'
  }>
  readonly tools?: readonly Readonly<Record<string, unknown>>[]
}

export interface BuildGeminiInteractionRequestInput {
  readonly profile: ProviderCognitiveProfile
  readonly input: string
  readonly tools?: readonly Readonly<Record<string, unknown>>[]
}

export function buildGeminiInteractionRequest(
  input: BuildGeminiInteractionRequestInput,
): GeminiInteractionRequest {
  if (input.profile.provider !== 'gemini' || input.profile.reasoning.kind !== 'gemini') {
    throw new TypeError('buildGeminiInteractionRequest requires a Gemini profile')
  }
  if (!input.input.trim()) throw new TypeError('Gemini interaction input must not be empty')

  return Object.freeze({
    model: input.profile.model,
    input: input.input,
    store: false as const,
    generation_config: Object.freeze({
      thinking_level: input.profile.reasoning.thinking_level,
      thinking_summaries: 'none' as const,
      tool_choice: 'auto' as const,
    }),
    ...(input.tools !== undefined ? { tools: Object.freeze([...input.tools]) } : {}),
  })
}
