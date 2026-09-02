import type { ProviderCognitiveProfile, OpenAIReasoningProfile } from '../coordination/provider-cognition.js'

export interface OpenAIResponsesRequest {
  readonly model: string
  readonly input: string
  readonly store: false
  readonly reasoning: Readonly<{
    readonly effort: OpenAIReasoningProfile['effort']
    readonly mode?: 'pro'
    readonly context: OpenAIReasoningProfile['context']
  }>
  readonly include: readonly ['reasoning.encrypted_content']
  readonly safety_identifier?: string
  readonly tools?: readonly Readonly<Record<string, unknown>>[]
  readonly tool_choice?: 'auto'
  readonly metadata: Readonly<{
    readonly aegis_work_class: ProviderCognitiveProfile['work_class']
    readonly aegis_authority: 'NONE'
    readonly aegis_tool_policy: 'AEGIS_CAPABILITY_GATED'
  }>
}

export interface BuildOpenAIResponsesRequestInput {
  readonly profile: ProviderCognitiveProfile
  readonly input: string
  readonly safety_identifier?: string
  readonly tools?: readonly Readonly<Record<string, unknown>>[]
}

export function buildOpenAIResponsesRequest(
  input: BuildOpenAIResponsesRequestInput,
): OpenAIResponsesRequest {
  if (input.profile.provider !== 'openai' || input.profile.reasoning.kind !== 'openai') {
    throw new TypeError('buildOpenAIResponsesRequest requires an OpenAI profile')
  }
  if (!input.input.trim()) {
    throw new TypeError('OpenAI Responses input must not be empty')
  }
  if (input.safety_identifier !== undefined && input.safety_identifier.length > 64) {
    throw new RangeError('OpenAI safety_identifier must be at most 64 characters')
  }

  const reasoning = input.profile.reasoning.mode === 'pro'
    ? Object.freeze({
        effort: input.profile.reasoning.effort,
        mode: 'pro' as const,
        context: input.profile.reasoning.context,
      })
    : Object.freeze({
        effort: input.profile.reasoning.effort,
        context: input.profile.reasoning.context,
      })

  return Object.freeze({
    model: input.profile.model,
    input: input.input,
    store: false as const,
    reasoning,
    include: Object.freeze(['reasoning.encrypted_content'] as const),
    ...(input.safety_identifier !== undefined
      ? { safety_identifier: input.safety_identifier }
      : {}),
    ...(input.tools !== undefined
      ? { tools: Object.freeze([...input.tools]), tool_choice: 'auto' as const }
      : {}),
    metadata: Object.freeze({
      aegis_work_class: input.profile.work_class,
      aegis_authority: 'NONE' as const,
      aegis_tool_policy: 'AEGIS_CAPABILITY_GATED' as const,
    }),
  })
}
