import type { AnthropicReasoningProfile, ProviderCognitiveProfile } from '../coordination/provider-cognition.js'

export interface AnthropicMessagesRequest {
  readonly model: string
  readonly max_tokens: number
  readonly thinking: Readonly<{ type: 'adaptive'; display: 'omitted' }>
  readonly output_config: Readonly<{ effort: AnthropicReasoningProfile['effort'] }>
  readonly messages: readonly [Readonly<{ role: 'user'; content: string }>]
  readonly tools?: readonly Readonly<Record<string, unknown>>[]
  readonly tool_choice?: Readonly<{ type: 'auto' }>
}

export interface BuildAnthropicMessagesRequestInput {
  readonly profile: ProviderCognitiveProfile
  readonly input: string
  readonly tools?: readonly Readonly<Record<string, unknown>>[]
}

function maxTokensFor(profile: ProviderCognitiveProfile): number {
  switch (profile.work_class) {
    case 'frontier-research':
    case 'formal-review':
      return 65536
    case 'implementation':
      return 32768
    case 'routine':
      return 8192
  }
}

export function buildAnthropicMessagesRequest(
  input: BuildAnthropicMessagesRequestInput,
): AnthropicMessagesRequest {
  if (input.profile.provider !== 'anthropic' || input.profile.reasoning.kind !== 'anthropic') {
    throw new TypeError('buildAnthropicMessagesRequest requires an Anthropic profile')
  }
  if (!input.input.trim()) throw new TypeError('Anthropic Messages input must not be empty')

  return Object.freeze({
    model: input.profile.model,
    max_tokens: maxTokensFor(input.profile),
    thinking: Object.freeze({ type: 'adaptive' as const, display: 'omitted' as const }),
    output_config: Object.freeze({ effort: input.profile.reasoning.effort }),
    messages: Object.freeze([
      Object.freeze({ role: 'user' as const, content: input.input }),
    ]) as readonly [Readonly<{ role: 'user'; content: string }>],
    ...(input.tools !== undefined
      ? {
          tools: Object.freeze([...input.tools]),
          tool_choice: Object.freeze({ type: 'auto' as const }),
        }
      : {}),
  })
}
