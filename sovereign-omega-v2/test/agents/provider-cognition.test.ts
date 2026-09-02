import { describe, expect, it } from 'vitest'
import {
  selectAllianceProviderProfile,
  selectProviderCognitiveProfile,
} from '../../src/agents/coordination/provider-cognition.js'

describe('provider-native cognitive depth', () => {
  it('uses the quality-first OpenAI profile for frontier research without minting authority', () => {
    const profile = selectProviderCognitiveProfile('openai', 'frontier-research')
    expect(profile.model).toBe('gpt-5.6-sol')
    expect(profile.reasoning).toEqual({
      kind: 'openai', effort: 'max', mode: 'pro', context: 'current_turn',
    })
    expect(profile.storage).toBe('stateless')
    expect(profile.raw_output_authority).toBe('NONE')
  })

  it('uses the active deepest Anthropic model with adaptive maximum-effort reasoning', () => {
    const profile = selectProviderCognitiveProfile('anthropic', 'formal-review')
    expect(profile.model).toBe('claude-opus-5')
    expect(profile.reasoning).toEqual({ kind: 'anthropic', thinking: 'adaptive', effort: 'max' })
    expect(profile.raw_output_authority).toBe('NONE')
  })

  it('uses high Gemini thinking for frontier research', () => {
    const profile = selectProviderCognitiveProfile('gemini', 'frontier-research')
    expect(profile.model).toBe('gemini-3.1-pro-preview')
    expect(profile.reasoning).toEqual({ kind: 'gemini', thinking_level: 'high' })
    expect(profile.raw_output_authority).toBe('NONE')
  })

  it('uses Qwen flagship maximum-intensity reasoning with preserved thinking provenance', () => {
    const profile = selectProviderCognitiveProfile('dashscope', 'implementation')
    expect(profile.model).toBe('qwen3.8-max')
    expect(profile.reasoning).toEqual({ kind: 'dashscope', effort: 'xhigh', preserve_thinking: true })
    expect(profile.raw_output_authority).toBe('NONE')
  })

  it('allows lower-cost routine OpenAI cognition without weakening authority conservation', () => {
    const profile = selectProviderCognitiveProfile('openai', 'routine')
    expect(profile.reasoning).toEqual({ kind: 'openai', effort: 'medium', mode: 'standard', context: 'current_turn' })
    expect(profile.raw_output_authority).toBe('NONE')
  })

  it('records model overrides as provenance inputs instead of constitutional identity', () => {
    const profile = selectProviderCognitiveProfile('openai', 'formal-review', { model: 'future-openai-reasoner' })
    expect(profile.model).toBe('future-openai-reasoner')
    expect(profile.raw_output_authority).toBe('NONE')
  })

  it('maps orchestration roles to provider-native deep work profiles', () => {
    const coordinator = selectAllianceProviderProfile('coordinator')
    expect(coordinator.provider).toBe('anthropic')
    expect(coordinator.model).toBe('claude-opus-5')
    expect(coordinator.reasoning).toEqual({ kind: 'anthropic', thinking: 'adaptive', effort: 'max' })

    const audit = selectAllianceProviderProfile('adversarial-audit')
    expect(audit.provider).toBe('openai')
    expect(audit.model).toBe('gpt-5.6-sol')
    expect(audit.reasoning).toEqual({ kind: 'openai', effort: 'max', mode: 'pro', context: 'current_turn' })

    const implementation = selectAllianceProviderProfile('implementation')
    expect(implementation.provider).toBe('dashscope')
    expect(implementation.model).toBe('qwen3.8-max')
    expect(implementation.reasoning).toEqual({ kind: 'dashscope', effort: 'xhigh', preserve_thinking: true })
  })
})
