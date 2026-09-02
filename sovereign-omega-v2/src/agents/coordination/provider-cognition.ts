// ============================================================
// AEGIS Ω — Provider-Native Cognitive Depth Contract
// EPISTEMIC TIER: T2 engineering policy
//
// Provider intelligence may amplify information quality. It never
// amplifies authority. Every raw provider output remains authority NONE
// until independently verified and admitted by the AEGIS control plane.
// ============================================================

export type ProviderName = 'openai' | 'anthropic' | 'gemini' | 'dashscope' | 'local'

export type CognitiveWorkClass =
  | 'frontier-research'
  | 'formal-review'
  | 'implementation'
  | 'routine'

export type OpenAIReasoningProfile = Readonly<{
  kind: 'openai'
  effort: 'medium' | 'high' | 'xhigh' | 'max'
  mode: 'standard' | 'pro'
  context: 'current_turn' | 'all_turns'
}>

export type AnthropicReasoningProfile = Readonly<{
  kind: 'anthropic'
  thinking: 'adaptive'
  effort: 'medium' | 'high'
}>

export type GeminiReasoningProfile = Readonly<{
  kind: 'gemini'
  thinking_level: 'medium' | 'high'
}>

export type DashScopeReasoningProfile = Readonly<{
  kind: 'dashscope'
  mode: 'standard' | 'deep'
}>

export type LocalReasoningProfile = Readonly<{
  kind: 'local'
  mode: 'standard' | 'deep'
}>

export type ProviderReasoningProfile =
  | OpenAIReasoningProfile
  | AnthropicReasoningProfile
  | GeminiReasoningProfile
  | DashScopeReasoningProfile
  | LocalReasoningProfile

export interface ProviderCognitiveProfile {
  readonly provider: ProviderName
  readonly work_class: CognitiveWorkClass
  readonly model: string
  readonly reasoning: ProviderReasoningProfile
  readonly storage: 'stateless'
  readonly tool_policy: 'AEGIS_CAPABILITY_GATED'
  readonly raw_output_authority: 'NONE'
  readonly schema_version: '1.0.0'
}

export interface ProviderCognitiveOverrides {
  readonly model?: string
}

const DEFAULT_MODELS: Readonly<Record<ProviderName, string>> = Object.freeze({
  openai: 'gpt-5.6-sol',
  anthropic: 'claude-opus-4-8',
  gemini: 'gemini-3.1-pro-preview',
  dashscope: 'qwen3.7-plus',
  local: 'configured-local-reasoner',
})

function openAIReasoning(workClass: CognitiveWorkClass): OpenAIReasoningProfile {
  if (workClass === 'frontier-research' || workClass === 'formal-review') {
    return Object.freeze({
      kind: 'openai',
      effort: 'max',
      mode: 'pro',
      context: 'current_turn',
    })
  }
  if (workClass === 'implementation') {
    return Object.freeze({
      kind: 'openai',
      effort: 'xhigh',
      mode: 'standard',
      context: 'current_turn',
    })
  }
  return Object.freeze({
    kind: 'openai',
    effort: 'medium',
    mode: 'standard',
    context: 'current_turn',
  })
}

function anthropicReasoning(workClass: CognitiveWorkClass): AnthropicReasoningProfile {
  return Object.freeze({
    kind: 'anthropic',
    thinking: 'adaptive',
    effort: workClass === 'routine' ? 'medium' : 'high',
  })
}

function geminiReasoning(workClass: CognitiveWorkClass): GeminiReasoningProfile {
  return Object.freeze({
    kind: 'gemini',
    thinking_level: workClass === 'routine' ? 'medium' : 'high',
  })
}

function dashScopeReasoning(workClass: CognitiveWorkClass): DashScopeReasoningProfile {
  return Object.freeze({
    kind: 'dashscope',
    mode: workClass === 'routine' ? 'standard' : 'deep',
  })
}

function localReasoning(workClass: CognitiveWorkClass): LocalReasoningProfile {
  return Object.freeze({
    kind: 'local',
    mode: workClass === 'routine' ? 'standard' : 'deep',
  })
}

function reasoningFor(provider: ProviderName, workClass: CognitiveWorkClass): ProviderReasoningProfile {
  switch (provider) {
    case 'openai':
      return openAIReasoning(workClass)
    case 'anthropic':
      return anthropicReasoning(workClass)
    case 'gemini':
      return geminiReasoning(workClass)
    case 'dashscope':
      return dashScopeReasoning(workClass)
    case 'local':
      return localReasoning(workClass)
  }
}

export function selectProviderCognitiveProfile(
  provider: ProviderName,
  workClass: CognitiveWorkClass,
  overrides: ProviderCognitiveOverrides = {},
): ProviderCognitiveProfile {
  const model = overrides.model?.trim() || DEFAULT_MODELS[provider]
  return Object.freeze({
    provider,
    work_class: workClass,
    model,
    reasoning: reasoningFor(provider, workClass),
    storage: 'stateless',
    tool_policy: 'AEGIS_CAPABILITY_GATED',
    raw_output_authority: 'NONE',
    schema_version: '1.0.0',
  })
}
