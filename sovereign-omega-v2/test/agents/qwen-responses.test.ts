import { describe, expect, it } from 'vitest'
import { selectProviderCognitiveProfile } from '../../src/agents/coordination/provider-cognition.js'
import { buildQwenResponsesRequest } from '../../src/agents/providers/qwen-responses.js'

describe('Qwen Responses execution contract', () => {
  it('maps implementation work to Qwen 3.8 Max at maximum reasoning effort', () => {
    const profile = selectProviderCognitiveProfile('dashscope', 'implementation')
    const request = buildQwenResponsesRequest({
      profile,
      input: 'Implement the smallest verified patch.',
      tools: [{ type: 'function', name: 'read_file', description: 'Read an allowed file', parameters: { type: 'object', properties: {} } }],
    })

    expect(request.model).toBe('qwen3.8-max')
    expect(request.store).toBe(false)
    expect(request.reasoning).toEqual({ effort: 'xhigh' })
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
