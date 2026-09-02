import type { WorkingCognitiveStateV1 } from '../coordination/cognitive-state.js'
import type { ProviderCognitiveProfile, OpenAIReasoningProfile } from '../coordination/provider-cognition.js'
import {
  assertBoundProviderToolSetV1,
  type BoundProviderToolSetV1,
} from '../coordination/provider-tool-set.js'

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
    readonly aegis_tool_policy_digest?: string
  }>
}

export interface BuildOpenAIResponsesRequestInput {
  readonly profile: ProviderCognitiveProfile
  readonly input: string
  readonly safety_identifier?: string
  readonly tool_set?: BoundProviderToolSetV1
}

export function buildOpenAIResponsesRequest(
  input: BuildOpenAIResponsesRequestInput,
): OpenAIResponsesRequest {
  if (input.profile.provider !== 'openai' || input.profile.reasoning.kind !== 'openai') {
    throw new TypeError('buildOpenAIResponsesRequest requires an OpenAI profile')
  }
  if (!input.input.trim()) throw new TypeError('OpenAI Responses input must not be empty')
  if (input.safety_identifier !== undefined && input.safety_identifier.length > 64) {
    throw new RangeError('OpenAI safety_identifier must be at most 64 characters')
  }
  if (input.tool_set !== undefined) assertBoundProviderToolSetV1(input.tool_set)

  const reasoning = input.profile.reasoning.mode === 'pro'
    ? Object.freeze({ effort: input.profile.reasoning.effort, mode: 'pro' as const, context: input.profile.reasoning.context })
    : Object.freeze({ effort: input.profile.reasoning.effort, context: input.profile.reasoning.context })

  return Object.freeze({
    model: input.profile.model,
    input: input.input,
    store: false as const,
    reasoning,
    include: Object.freeze(['reasoning.encrypted_content'] as const),
    ...(input.safety_identifier !== undefined ? { safety_identifier: input.safety_identifier } : {}),
    ...(input.tool_set !== undefined
      ? { tools: input.tool_set.tools, tool_choice: 'auto' as const }
      : {}),
    metadata: Object.freeze({
      aegis_work_class: input.profile.work_class,
      aegis_authority: 'NONE' as const,
      aegis_tool_policy: 'AEGIS_CAPABILITY_GATED' as const,
      ...(input.tool_set !== undefined
        ? { aegis_tool_policy_digest: input.tool_set.policy_digest }
        : {}),
    }),
  })
}

export type OpenAIContinuationRetentionPolicy = 'STATELESS' | 'PROVIDER_RETAINED' | 'ZDR'
export type OpenAIResponsesInputItem = Readonly<Record<string, unknown>>

export interface OpenAIResponsesContinuationRequest {
  readonly model: string
  readonly input: string | readonly OpenAIResponsesInputItem[]
  readonly store: boolean
  readonly reasoning: OpenAIResponsesRequest['reasoning']
  readonly include: OpenAIResponsesRequest['include']
  readonly previous_response_id?: string
  readonly context_management?: readonly Readonly<{
    type: 'compaction'
    compact_threshold: number
  }>[]
  readonly safety_identifier?: string
  readonly tools?: readonly Readonly<Record<string, unknown>>[]
  readonly tool_choice?: 'auto'
  readonly metadata: OpenAIResponsesRequest['metadata']
}

export interface BuildOpenAIResponsesContinuationRequestInput {
  readonly profile: ProviderCognitiveProfile
  readonly state: WorkingCognitiveStateV1
  readonly input: string
  readonly retention_policy: OpenAIContinuationRetentionPolicy
  readonly compact_threshold?: number
  readonly resolved_replay_items?: readonly OpenAIResponsesInputItem[]
  readonly safety_identifier?: string
  readonly tool_set?: BoundProviderToolSetV1
}

function contextManagement(
  compactThreshold: number | undefined,
): OpenAIResponsesContinuationRequest['context_management'] {
  if (compactThreshold === undefined) return undefined
  if (!Number.isSafeInteger(compactThreshold) || compactThreshold <= 0) {
    throw new RangeError('OpenAI compact_threshold must be a positive safe integer')
  }
  return Object.freeze([
    Object.freeze({ type: 'compaction' as const, compact_threshold: compactThreshold }),
  ])
}

function structuredContinuationItem(state: WorkingCognitiveStateV1): OpenAIResponsesInputItem {
  return Object.freeze({
    role: 'developer',
    content: JSON.stringify({
      aegis_continuation_schema: 'AEGIS_STRUCTURED_CONTINUATION_V1',
      objective: state.objective,
      active_plan: state.active_plan,
      falsified_hypotheses: state.falsified_hypotheses,
      unresolved_obligations: state.unresolved_obligations,
      evidence_refs: state.evidence_refs,
      artifact_refs: state.artifact_refs,
      next_actions: state.next_actions,
      budget_state: state.budget_state,
    }),
  })
}

/**
 * Build a provider-native continuation request without promoting provider state
 * into AEGIS authority. The default builder above remains stateless; retained
 * provider state is available only through an explicit retention policy.
 * Encrypted reasoning payloads are resolved ephemerally by the caller and are
 * never persisted inside WorkingCognitiveStateV1.
 */
export function buildOpenAIResponsesContinuationRequest(
  input: BuildOpenAIResponsesContinuationRequestInput,
): OpenAIResponsesContinuationRequest {
  const base = buildOpenAIResponsesRequest({
    profile: input.profile,
    input: input.input,
    ...(input.safety_identifier !== undefined ? { safety_identifier: input.safety_identifier } : {}),
    ...(input.tool_set !== undefined ? { tool_set: input.tool_set } : {}),
  })
  const management = contextManagement(input.compact_threshold)
  const continuation = input.state.provider_continuation

  if (continuation?.transport === 'OPENAI_PREVIOUS_RESPONSE_ID') {
    if (input.retention_policy !== 'PROVIDER_RETAINED') {
      throw new TypeError('OPENAI_PREVIOUS_RESPONSE_ID requires explicit provider retention')
    }
    if (!continuation.previous_response_id.trim()) {
      throw new TypeError('OpenAI previous_response_id must not be empty')
    }
    return Object.freeze({
      ...base,
      store: true,
      previous_response_id: continuation.previous_response_id,
      ...(management !== undefined ? { context_management: management } : {}),
    })
  }

  if (continuation?.transport === 'OPENAI_ENCRYPTED_REPLAY') {
    if (input.retention_policy === 'PROVIDER_RETAINED') {
      throw new TypeError('OPENAI_ENCRYPTED_REPLAY is a stateless/ZDR transport, not provider retention')
    }
    if (continuation.encrypted_reasoning_item_refs.length === 0) {
      throw new TypeError('Encrypted replay requires at least one opaque reasoning item reference')
    }
    if (
      input.resolved_replay_items === undefined
      || input.resolved_replay_items.length !== continuation.encrypted_reasoning_item_refs.length
    ) {
      throw new TypeError('Encrypted reasoning references require one resolved replay item per reference')
    }
    return Object.freeze({
      ...base,
      input: Object.freeze([
        ...input.resolved_replay_items,
        Object.freeze({ role: 'user', content: input.input }),
      ]),
      store: false,
      ...(management !== undefined ? { context_management: management } : {}),
    })
  }

  // Provider-neutral fallback: only structured, inspectable AEGIS continuation
  // surfaces are projected. Hidden chain-of-thought is neither requested nor
  // reconstructed here.
  return Object.freeze({
    ...base,
    input: Object.freeze([
      structuredContinuationItem(input.state),
      Object.freeze({ role: 'user', content: input.input }),
    ]),
    store: input.retention_policy === 'PROVIDER_RETAINED',
    ...(management !== undefined ? { context_management: management } : {}),
  })
}
