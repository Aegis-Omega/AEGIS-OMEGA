import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import { selectProviderCognitiveProfile } from '../../src/agents/coordination/provider-cognition.js'
import { buildProviderExecutionReceiptV1 } from '../../src/agents/coordination/provider-execution-receipt.js'

const digest = (c: string): SHA256Hex => c.repeat(64) as SHA256Hex

describe('ProviderExecutionReceiptV1', () => {
  it('is deterministic and binds the effective provider cognition profile', async () => {
    const profile = selectProviderCognitiveProfile('openai', 'frontier-research')
    const input = {
      profile,
      task_digest: digest('a'),
      output_digest: digest('b'),
      tool_policy_digest: digest('c'),
    }

    const first = await buildProviderExecutionReceiptV1(input)
    const second = await buildProviderExecutionReceiptV1(input)

    expect(first.receipt_hash).toBe(second.receipt_hash)
    expect(first.provider).toBe('openai')
    expect(first.model).toBe('gpt-5.6-sol')
    expect(first.reasoning).toEqual(profile.reasoning)
    expect(first.authority_class).toBe('NONE')
  })

  it('changes identity when the bound task changes', async () => {
    const profile = selectProviderCognitiveProfile('anthropic', 'formal-review')
    const common = {
      profile,
      output_digest: digest('b'),
      tool_policy_digest: digest('c'),
    }

    const left = await buildProviderExecutionReceiptV1({ ...common, task_digest: digest('a') })
    const right = await buildProviderExecutionReceiptV1({ ...common, task_digest: digest('d') })

    expect(left.receipt_hash).not.toBe(right.receipt_hash)
  })
})
