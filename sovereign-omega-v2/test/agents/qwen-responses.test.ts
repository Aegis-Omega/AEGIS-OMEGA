import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import { selectProviderCognitiveProfile } from '../../src/agents/coordination/provider-cognition.js'
import { bindProviderToolSetV1 } from '../../src/agents/coordination/provider-tool-set.js'
import { buildQwenResponsesRequest } from '../../src/agents/providers/qwen-responses.js'

const policyDigest = 'd'.repeat(64) as SHA256Hex

describe('Qwen Responses execution contract', () => {
  it('maps implementation work to Qwen 3.8 Max at maximum reasoning effort', () => {
    const profile = selectProviderCognitiveProfile('dashscope', 'implementation')
    const toolSet = bindProviderToolSetV1(policyDigest, [
      { type: 'function', name: 'read_file', description: 'Read an allowed file', parameters: { type: 'object', properties: {} } },
    ])
    const request = buildQwenResponsesRequest({
      profile,
      input: 'Implement the smallest verified patch.',
      tool_set: toolSet,
    })

    expect(request.model).toBe('qwen3.8-max')
    expect(request.store).toBe(false)
    expect(request.reasoning).toEqual({ effort: 'xhigh' })
    expect(request.tools).toEqual(toolSet.tools)
    expect(request.tool_choice).toBe('auto')
  })

  it('uses medium reasoning only for routine work', () => {
    const profile = selectProviderCognitiveProfile('dashscope', 'routine')
    expect(buildQwenResponsesRequest({ profile, input: 'Classify this event.' }).reasoning)
      .toEqual({ effort: 'medium' })
  })

  it('rejects non-DashScope profiles', () => {
    expect(() => buildQwenResponsesRequest({
      profile: selectProviderCognitiveProfile('gemini', 'formal-review'),
      input: 'x',
    })).toThrow(/DashScope profile/)
  })
})
