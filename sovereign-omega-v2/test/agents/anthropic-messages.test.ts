import { describe, expect, it } from 'vitest'
import { selectProviderCognitiveProfile } from '../../src/agents/coordination/provider-cognition.js'
import { buildAnthropicMessagesRequest } from '../../src/agents/providers/anthropic-messages.js'

describe('Anthropic Messages execution contract', () => {
  it('maps frontier work to Opus 5 adaptive thinking at maximum effort', () => {
    const profile = selectProviderCognitiveProfile('anthropic', 'frontier-research')
    const request = buildAnthropicMessagesRequest({
      profile,
      input: 'Find the strongest falsifier for this proof strategy.',
      tools: [{ name: 'read_evidence', description: 'Read admitted evidence', input_schema: { type: 'object', properties: {} } }],
    })

    expect(request.model).toBe('claude-opus-5')
    expect(request.thinking).toEqual({ type: 'adaptive', display: 'omitted' })
    expect(request.output_config).toEqual({ effort: 'max' })
    expect(request.max_tokens).toBe(65536)
    expect(request.tool_choice).toEqual({ type: 'auto' })
  })

  it('rejects non-Anthropic profiles', () => {
    expect(() => buildAnthropicMessagesRequest({
      profile: selectProviderCognitiveProfile('openai', 'formal-review'),
      input: 'x',
    })).toThrow(/Anthropic profile/)
  })
})
