import { describe, expect, it } from 'vitest'
import { hashValue } from '../../src/core/hashing.js'
import type { SHA256Hex } from '../../src/core/types.js'
import { selectProviderCognitiveProfile } from '../../src/agents/coordination/provider-cognition.js'
import type { WorkingCognitiveStateV1 } from '../../src/agents/coordination/cognitive-state.js'
import { buildOpenAIResponsesContinuationRequest } from '../../src/agents/providers/openai-responses.js'

// Cycle 3 CI retrigger only: preserve the preregistered RED semantics verbatim.
const sha = (c: string): SHA256Hex => c.repeat(64) as SHA256Hex

async function replayFixture() {
  const profile = selectProviderCognitiveProfile('openai', 'frontier-research')
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
    schema_version: '1.0.0',
    lineage_root: sha('1'),
    objective: 'continue exact-head proof search',
    active_plan: [],
    hypotheses: [],
    falsified_hypotheses: [],
    unresolved_obligations: ['bind stateless replay payload to digest'],
    evidence_refs: [],
    artifact_refs: [],
    next_actions: [],
    provider_continuation: {
      transport: 'OPENAI_ENCRYPTED_REPLAY',
      stateless_context_item_refs: refs,
      opaque_payload_digest: replayDigest,
    },
    budget_state: {
      token_budget_remaining: 10_000,
      action_budget_remaining: 20,
    },
  }

  return { profile, refs, priorContext, state }
}

describe('OpenAI stateless replay anti-splicing preregistered RED', () => {
  it('ENFORCE_RED_1: rejects same-count substituted replay context', async () => {
    const { profile, priorContext, state } = await replayFixture()
    const substitutedContext = [
      priorContext[0],
      priorContext[1],
      { type: 'message', role: 'assistant', content: [{ type: 'output_text', text: 'spliced answer' }] },
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
    const { profile, priorContext, state } = await replayFixture()
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
