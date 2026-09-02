import { describe, expect, it } from 'vitest'
import { hashValue } from '../../src/core/hashing.js'
import type { SHA256Hex } from '../../src/core/types.js'
import { selectProviderCognitiveProfile } from '../../src/agents/coordination/provider-cognition.js'
import type { WorkingCognitiveStateV1 } from '../../src/agents/coordination/cognitive-state.js'
import { buildOpenAIResponsesContinuationRequest } from '../../src/agents/providers/openai-responses.js'

const sha = (c: string): SHA256Hex => c.repeat(64) as SHA256Hex

function baseState(): WorkingCognitiveStateV1 {
  return {
    schema_version: '1.0.0',
    lineage_root: sha('1'),
    objective: 'verify OpenAI stateless replay integrity',
    active_plan: [],
    hypotheses: [],
    falsified_hypotheses: [],
    unresolved_obligations: ['reject replay payloads not bound by the stored digest'],
    evidence_refs: [],
    artifact_refs: [],
    next_actions: [],
    budget_state: {
      token_budget_remaining: 10_000,
      action_budget_remaining: 20,
    },
  }
}

async function replayFixture() {
  const refs = [
    'vault://responses/context/user-1',
    'vault://responses/context/reasoning-1',
    'vault://responses/context/message-1',
  ] as const
  const priorContext = [
    { type: 'message', role: 'user', content: 'prior question' },
    { type: 'reasoning', encrypted_content: 'opaque-ciphertext' },
    { type: 'message', role: 'assistant', content: [{ type: 'output_text', text: 'prior answer' }] },
  ] as const
  const replayDigest = await hashValue({
    receipt_kind: 'AEGIS_OPENAI_STATELESS_REPLAY_V1',
    schema_version: '1.0.0',
    stateless_context_item_refs: refs,
    stateless_context_items: priorContext,
  })
  const state: WorkingCognitiveStateV1 = {
    ...baseState(),
    provider_continuation: {
      transport: 'OPENAI_ENCRYPTED_REPLAY',
      stateless_context_item_refs: refs,
      opaque_payload_digest: replayDigest,
    },
  }
  return { refs, priorContext, state }
}

describe('OpenAI stateless replay anti-splicing RED contract', () => {
  it('ENFORCE_RED_1: rejects same-count substituted replay context', async () => {
    const profile = selectProviderCognitiveProfile('openai', 'frontier-research')
    const { priorContext, state } = await replayFixture()
    const substitutedContext = [
      priorContext[0],
      priorContext[1],
      {
        type: 'message',
        role: 'assistant',
        content: [{ type: 'output_text', text: 'spliced answer' }],
      },
    ] as const

    await expect(Promise.resolve().then(() => buildOpenAIResponsesContinuationRequest({
      profile,
      state,
      input: 'continue proof search',
      retention_policy: 'ZDR',
      resolved_stateless_context_items: substitutedContext,
    }))).rejects.toThrow(/digest/i)
  })

  it('ENFORCE_RED_2: rejects reordered replay context', async () => {
    const profile = selectProviderCognitiveProfile('openai', 'frontier-research')
    const { priorContext, state } = await replayFixture()
    const reorderedContext = [priorContext[1], priorContext[0], priorContext[2]] as const

    await expect(Promise.resolve().then(() => buildOpenAIResponsesContinuationRequest({
      profile,
      state,
      input: 'continue proof search',
      retention_policy: 'ZDR',
      resolved_stateless_context_items: reorderedContext,
    }))).rejects.toThrow(/digest/i)
  })
})
