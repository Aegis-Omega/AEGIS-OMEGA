import { describe, expect, it } from 'vitest'
import { selectProviderCognitiveProfile } from '../../src/agents/coordination/provider-cognition.js'
import { buildGeminiInteractionRequest } from '../../src/agents/providers/gemini-interactions.js'

describe('Gemini Interactions execution contract', () => {
  it('maps frontier work to Gemini 3.1 Pro high thinking in stateless mode', () => {
    const profile = selectProviderCognitiveProfile('gemini', 'frontier-research')
    const request = buildGeminiInteractionRequest({
      profile,
      input: 'Synthesize the strongest independent evidence graph.',
      tools: [{ type: 'function', name: 'read_evidence', description: 'Read evidence', parameters: { type: 'object', properties: {} } }],
    })

    expect(request.model).toBe('gemini-3.1-pro-preview')
    expect(request.store).toBe(false)
    expect(request.generation_config).toEqual({
      thinking_level: 'high',
      thinking_summaries: 'none',
      tool_choice: 'auto',
    })
  })

  it('rejects non-Gemini profiles', () => {
    expect(() => buildGeminiInteractionRequest({
      profile: selectProviderCognitiveProfile('anthropic', 'formal-review'),
      input: 'x',
    })).toThrow(/Gemini profile/)
  })
})
