// ============================================================
// AEGIS Ω — Provider-Native Cognitive Depth Contract
// EPISTEMIC TIER: T2 engineering policy
//
// Provider intelligence may amplify information quality. It never
// amplifies authority. Every raw provider output remains authority NONE
// until independently verified and admitted by the AEGIS control plane.
// ============================================================

export type ProviderName = 'openai' | 'anthropic' | 'gemini' | 'dashscope' | 'local'
export type CognitiveWorkClass = 'frontier-research' | 'formal-review' | 'implementation' | 'routine'
export type AllianceRole = 'coordinator' | 'adversarial-audit' | 'implementation'

export type OpenAIReasoningProfile = Readonly<{
  kind: 'openai'
  effort: 'medium' | 'high' | 'xhigh' | 'max'
  mode: 'standard' | 'pro'
  context: 'current_turn' | 'all_turns'
}>
export type AnthropicReasoningProfile = Readonly<{
  kind: 'anthropic'
  thinking: 'adaptive'
  effort: 'medium' | 'high' | 'xhigh' | 'max'
}>
export type GeminiReasoningProfile = Readonly<{ kind: 'gemini'; thinking_level: 'medium' | 'high' }>
export type DashScopeReasoningProfile = Readonly<{ kind: 'dashscope'; effort: 'medium' | 'xhigh' }>
export type LocalReasoningProfile = Readonly<{ kind: 'local'; mode: 'standard' | 'deep' }>
export type ProviderReasoningProfile = OpenAIReasoningProfile | AnthropicReasoningProfile | GeminiReasoningProfile | DashScopeReasoningProfile | LocalReasoningProfile

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

export interface ProviderCognitiveOverrides { readonly model?: string }
export type ProviderModelOverrides = Readonly<Partial<Record<ProviderName, string>>>

const PROVIDER_ORDER: readonly ProviderName[] = Object.freeze([
  'anthropic', 'dashscope', 'gemini', 'local', 'openai',
])

const DEFAULT_MODELS: Readonly<Record<ProviderName, string>> = Object.freeze({
  openai: 'gpt-5.6-sol',
  anthropic: 'claude-opus-5',
  gemini: 'gemini-3.1-pro-preview',
  dashscope: 'qwen3.8-max',
  local: 'configured-local-reasoner',
})

function openAIReasoning(workClass: CognitiveWorkClass): OpenAIReasoningProfile {
  if (workClass === 'frontier-research' || workClass === 'formal-review') {
    return Object.freeze({ kind: 'openai', effort: 'max', mode: 'pro', context: 'all_turns' })
  }
  if (workClass === 'implementation') {
    return Object.freeze({ kind: 'openai', effort: 'xhigh', mode: 'standard', context: 'all_turns' })
  }
  return Object.freeze({ kind: 'openai', effort: 'medium', mode: 'standard', context: 'current_turn' })
}

function anthropicReasoning(workClass: CognitiveWorkClass): AnthropicReasoningProfile {
  if (workClass === 'frontier-research' || workClass === 'formal-review') {
    return Object.freeze({ kind: 'anthropic', thinking: 'adaptive', effort: 'max' })
  }
  if (workClass === 'implementation') {
    return Object.freeze({ kind: 'anthropic', thinking: 'adaptive', effort: 'xhigh' })
  }
  return Object.freeze({ kind: 'anthropic', thinking: 'adaptive', effort: 'medium' })
}

function geminiReasoning(workClass: CognitiveWorkClass): GeminiReasoningProfile {
  return Object.freeze({ kind: 'gemini', thinking_level: workClass === 'routine' ? 'medium' : 'high' })
}
function dashScopeReasoning(workClass: CognitiveWorkClass): DashScopeReasoningProfile {
  return Object.freeze({ kind: 'dashscope', effort: workClass === 'routine' ? 'medium' : 'xhigh' })
}
function localReasoning(workClass: CognitiveWorkClass): LocalReasoningProfile {
  return Object.freeze({ kind: 'local', mode: workClass === 'routine' ? 'standard' : 'deep' })
}

function reasoningFor(provider: ProviderName, workClass: CognitiveWorkClass): ProviderReasoningProfile {
  switch (provider) {
    case 'openai': return openAIReasoning(workClass)
    case 'anthropic': return anthropicReasoning(workClass)
    case 'gemini': return geminiReasoning(workClass)
    case 'dashscope': return dashScopeReasoning(workClass)
    case 'local': return localReasoning(workClass)
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

/**
 * Information-amplifying, authority-neutral council. Every configured provider
 * may attack the same task from its deepest appropriate cognitive profile.
 * The returned profiles are candidates only; this function never changes
 * constitutional quorum topology or admission authority.
 */
export function buildProviderCognitiveCouncil(
  workClass: CognitiveWorkClass,
  modelOverrides: ProviderModelOverrides = {},
): readonly ProviderCognitiveProfile[] {
  return Object.freeze(PROVIDER_ORDER.map(provider =>
    selectProviderCognitiveProfile(provider, workClass, { model: modelOverrides[provider] }),
  ))
}

export function selectAllianceProviderProfile(role: AllianceRole): ProviderCognitiveProfile {
  switch (role) {
    case 'coordinator': return selectProviderCognitiveProfile('anthropic', 'frontier-research')
    case 'adversarial-audit': return selectProviderCognitiveProfile('openai', 'formal-review')
    case 'implementation': return selectProviderCognitiveProfile('dashscope', 'implementation')
  }
}
