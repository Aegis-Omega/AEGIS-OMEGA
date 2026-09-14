import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import { selectProviderCognitiveProfile } from '../../src/agents/coordination/provider-cognition.js'
import {
  bindProviderToolSetV1,
  type BoundProviderToolSetV1,
} from '../../src/agents/coordination/provider-tool-set.js'
import { buildOpenAIResponsesRequest } from '../../src/agents/providers/openai-responses.js'

const policyDigest = 'a'.repeat(64) as SHA256Hex

describe('OpenAI Responses execution contract', () => {
  it('maps frontier cognition to stateless max/pro long-horizon Responses semantics', () => {
    const profile = selectProviderCognitiveProfile('openai', 'frontier-research')
    const toolSet = bindProviderToolSetV1(policyDigest, [{ type: 'web_search' }])
    const request = buildOpenAIResponsesRequest({
      profile,
      input: 'prove or falsify the candidate invariant',
      safety_identifier: 'actor_abc123',
      tool_set: toolSet,
    })

    expect(request.model).toBe('gpt-5.6-sol')
    expect(request.store).toBe(false)
    expect(request.reasoning).toEqual({ effort: 'max', mode: 'pro', context: 'all_turns' })
    expect(request.include).toEqual(['reasoning.encrypted_content'])
    expect(request.safety_identifier).toBe('actor_abc123')
    expect(request.tools).toEqual([{ type: 'web_search' }])
    expect(request.metadata).toEqual({
      aegis_work_class: 'frontier-research',
      aegis_authority: 'NONE',
      aegis_tool_policy: 'AEGIS_CAPABILITY_GATED',
      aegis_tool_policy_digest: policyDigest,
    })
  })

  it('omits pro mode for routine work while keeping stateless provenance', () => {
    const profile = selectProviderCognitiveProfile('openai', 'routine')
    const request = buildOpenAIResponsesRequest({ profile, input: 'classify this event' })
    expect(request.reasoning).toEqual({ effort: 'medium', context: 'current_turn' })
    expect(request.store).toBe(false)
  })

  it('rejects forged tool sets, non-OpenAI profiles and oversized safety identifiers', () => {
    const forged = {
      receipt_kind: 'AEGIS_BOUND_PROVIDER_TOOL_SET_V1',
      schema_version: '1.0.0',
      policy_digest: policyDigest,
      tools: [{ type: 'web_search' }],
    } as unknown as BoundProviderToolSetV1

    expect(() => buildOpenAIResponsesRequest({
      profile: selectProviderCognitiveProfile('openai', 'formal-review'),
      input: 'x',
      tool_set: forged,
    })).toThrow(/not bound/)

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
