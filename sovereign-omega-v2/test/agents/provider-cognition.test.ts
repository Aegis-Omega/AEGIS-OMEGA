import { describe, expect, it } from 'vitest'
import { selectProviderCognitiveProfile } from '../../src/agents/coordination/provider-cognition.js'

describe('provider-native cognitive depth', () => {
  it('uses the quality-first OpenAI profile for frontier research without minting authority', () => {
    const profile = selectProviderCognitiveProfile('openai', 'frontier-research')
    expect(profile.model).toBe('gpt-5.6-sol')
    expect(profile.reasoning).toEqual({
      kind: 'openai',
      effort: 'max',
      mode: 'pro',
      context: 'current_turn',
    })
    expect(profile.storage).toBe('stateless')
    expect(profile.raw_output_authority).toBe('NONE')
  })

  it('uses adaptive high-effort Anthropic reasoning for formal review', () => {
    const profile = selectProviderCognitiveProfile('anthropic', 'formal-review')
    expect(profile.reasoning).toEqual({
      kind: 'anthropic',
      thinking: 'adaptive',
      effort: 'high',
    })
    expect(profile.raw_output_authority).toBe('NONE')
  })

  it('uses high Gemini thinking for frontier research', () => {
    const profile = selectProviderCognitiveProfile('gemini', 'frontier-research')
    expect(profile.reasoning).toEqual({ kind: 'gemini', thinking_level: 'high' })
    expect(profile.raw_output_authority).toBe('NONE')
  })

  it('allows lower-cost routine cognition without weakening authority conservation', () => {
    const profile = selectProviderCognitiveProfile('openai', 'routine')
    expect(profile.reasoning).toEqual({
      kind: 'openai',
      effort: 'medium',
      mode: 'standard',
      context: 'current_turn',
    })
    expect(profile.raw_output_authority).toBe('NONE')
  })

  it('records model overrides as provenance inputs instead of constitutional identity', () => {
    const profile = selectProviderCognitiveProfile('openai', 'formal-review', {
      model: 'future-openai-reasoner',
    })
    expect(profile.model).toBe('future-openai-reasoner')
    expect(profile.raw_output_authority).toBe('NONE')
  })
})
