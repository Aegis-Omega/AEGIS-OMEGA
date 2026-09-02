import { describe, expect, it } from 'vitest'
import { selectProviderCognitiveProfile } from '../../src/agents/coordination/provider-cognition.js'
import { buildOpenAIResponsesRequest } from '../../src/agents/providers/openai-responses.js'

describe('OpenAI Responses execution contract', () => {
  it('maps frontier cognition to stateless max/pro long-horizon Responses semantics', () => {
    const profile = selectProviderCognitiveProfile('openai', 'frontier-research')
    const request = buildOpenAIResponsesRequest({
      profile,
      input: 'prove or falsify the candidate invariant',
      safety_identifier: 'actor_abc123',
      tools: [{ type: 'web_search' }],
    })

    expect(request.model).toBe('gpt-5.6-sol')
    expect(request.store).toBe(false)
    expect(request.reasoning).toEqual({ effort: 'max', mode: 'pro', context: 'all_turns' })
    expect(request.include).toEqual(['reasoning.encrypted_content'])
    expect(request.safety_identifier).toBe('actor_abc123')
    expect(request.metadata).toEqual({
      aegis_work_class: 'frontier-research',
      aegis_authority: 'NONE',
      aegis_tool_policy: 'AEGIS_CAPABILITY_GATED',
    })
  })

  it('omits pro mode for routine work while keeping stateless provenance', () => {
    const profile = selectProviderCognitiveProfile('openai', 'routine')
    const request = buildOpenAIResponsesRequest({ profile, input: 'classify this event' })
    expect(request.reasoning).toEqual({ effort: 'medium', context: 'current_turn' })
    expect(request.store).toBe(false)
  })

  it('rejects non-OpenAI profiles and oversized safety identifiers', () => {
    expect(() => buildOpenAIResponsesRequest({
      profile: selectProviderCognitiveProfile('anthropic', 'frontier-research'),
      input: 'x',
    })).toThrow(/OpenAI profile/)

    expect(() => buildOpenAIResponsesRequest({
      profile: selectProviderCognitiveProfile('openai', 'frontier-research'),
      input: 'x',
      safety_identifier: 'x'.repeat(65),
    })).toThrow(/64/)
  })
})
