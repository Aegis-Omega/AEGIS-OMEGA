import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import { selectProviderCognitiveProfile } from '../../src/agents/coordination/provider-cognition.js'
import {
  computeCognitiveStateDigest,
  type WorkingCognitiveStateV1,
} from '../../src/agents/coordination/cognitive-state.js'
import {
  CognitiveLineageManager,
  buildCognitiveCompactionReceiptV1,
} from '../../src/agents/coordination/cognitive-lineage.js'
import { CRWEvaluator } from '../../src/agents/evaluation/cognitive-reconstruction-waste.js'
import {
  buildOpenAIResponsesContinuationRequest,
  buildOpenAIResponsesRequest,
} from '../../src/agents/providers/openai-responses.js'

const sha = (c: string): SHA256Hex => c.repeat(64) as SHA256Hex

function state(): WorkingCognitiveStateV1 {
  return {
    schema_version: '1.0.0',
    lineage_root: sha('1'),
    objective: 'prove or falsify the candidate invariant',
    active_plan: ['inspect exact artifact', 'compile candidate proof'],
    hypotheses: ['candidate lemma closes the obligation'],
    falsified_hypotheses: ['stale head was sufficient'],
    unresolved_obligations: ['close theorem under exact imports'],
    evidence_refs: [{
      receipt_hash: sha('2'),
      admission_root: sha('3'),
      artifact_digest: sha('4'),
    }],
    artifact_refs: [sha('5')],
    next_actions: ['run coqc on the exact proof file'],
    provider_continuation: {
      transport: 'OPENAI_PREVIOUS_RESPONSE_ID',
      previous_response_id: 'resp_123',
      opaque_payload_digest: sha('6'),
    },
    budget_state: {
      token_budget_remaining: 50_000,
      action_budget_remaining: 100,
    },
  }
}

describe('AEGIS cognitive state firewall', () => {
  it('forbids portable plaintext chain-of-thought and embedded canonical knowledge at the type boundary', () => {
    const base = state()
    const illegalCot: WorkingCognitiveStateV1 = {
      ...base,
      // @ts-expect-error Tier 2 must never contain portable plaintext chain-of-thought.
      portable_plaintext_chain_of_thought: 'private reasoning',
    }
    const illegalCanonical: WorkingCognitiveStateV1 = {
      ...base,
      // @ts-expect-error Tier 4 knowledge is referenced, never embedded or minted here.
      canonical_knowledge: [{ theorem: 'unverified' }],
    }
    expect(illegalCot.objective).toBe(base.objective)
    expect(illegalCanonical.objective).toBe(base.objective)
  })

  it('uses canonical hashing for deterministic state identity', async () => {
    const a = state()
    const b: WorkingCognitiveStateV1 = {
      ...a,
      evidence_refs: [{
        artifact_digest: sha('4'),
        receipt_hash: sha('2'),
        admission_root: sha('3'),
      }],
    }
    await expect(computeCognitiveStateDigest(a)).resolves.toBe(await computeCognitiveStateDigest(b))
  })
})

describe('cognitive lineage isolation and receipts', () => {
  it('removes builder-bias surfaces for falsifier and clean-room forks', async () => {
    const raw = await CognitiveLineageManager.fork(state(), 'RAW_EVIDENCE_ONLY')
    expect(raw.child.active_plan).toEqual([])
    expect(raw.child.hypotheses).toEqual([])
    expect(raw.child.next_actions).toEqual([])
    expect(raw.child.provider_continuation).toBeUndefined()
    expect(raw.child.falsified_hypotheses).toEqual(['stale head was sufficient'])
    expect(raw.receipt.authority_class).toBe('NONE')

    const clean = await CognitiveLineageManager.fork(state(), 'CLEAN_ROOM')
    expect(clean.child.falsified_hypotheses).toEqual([])
    expect(clean.child.evidence_refs).toEqual(state().evidence_refs)
    expect(clean.child.artifact_refs).toEqual(state().artifact_refs)
  })

  it('SELECTIVE inherits only explicitly whitelisted cognitive surfaces', async () => {
    const forked = await CognitiveLineageManager.fork(state(), 'SELECTIVE', ['unresolved_obligations'])
    expect(forked.child.unresolved_obligations).toEqual(state().unresolved_obligations)
    expect(forked.child.active_plan).toEqual([])
    expect(forked.child.hypotheses).toEqual([])
    expect(forked.child.next_actions).toEqual([])
    expect(forked.child.provider_continuation).toBeUndefined()
  })

  it('joins only verified evidence references and emits authority-none compaction receipts', async () => {
    const parent = state()
    const forked = await CognitiveLineageManager.fork(parent, 'CLEAN_ROOM')
    const extraEvidence = [{
      receipt_hash: sha('7'),
      admission_root: sha('8'),
      artifact_digest: sha('9'),
    }]
    const joined = await CognitiveLineageManager.join(parent, [forked.receipt], extraEvidence)
    expect(joined.evidence_refs).toHaveLength(2)
    expect(joined.lineage_root).not.toBe(parent.lineage_root)

    const receipt = await buildCognitiveCompactionReceiptV1({
      source_lineage_root: parent.lineage_root,
      source_event_range: { from_seq: 10, to_seq: 20 },
      source_state_digest: await computeCognitiveStateDigest(parent),
      compaction_policy_digest: sha('a'),
      retained_surface_digest: sha('b'),
      discarded_surface_classes: ['redundant_prose', 'superseded_plan_steps'],
      result_state_digest: sha('c'),
    })
    expect(receipt.authority_class).toBe('NONE')
    expect(receipt.receipt_hash).toMatch(/^[0-9a-f]{64}$/)
  })
})

describe('OpenAI continuation transports', () => {
  it('preserves the existing stateless builder by default', () => {
    const profile = selectProviderCognitiveProfile('openai', 'frontier-research')
    const request = buildOpenAIResponsesRequest({ profile, input: 'continue proof search' })
    expect(request.store).toBe(false)
    expect(request.include).toEqual(['reasoning.encrypted_content'])
  })

  it('requires explicit retention for previous_response_id and emits API-native compaction fields', () => {
    const profile = selectProviderCognitiveProfile('openai', 'frontier-research')
    expect(() => buildOpenAIResponsesContinuationRequest({
      profile,
      state: state(),
      input: 'continue proof search',
      retention_policy: 'STATELESS',
    })).toThrow(/retention/i)

    const request = buildOpenAIResponsesContinuationRequest({
      profile,
      state: state(),
      input: 'continue proof search',
      retention_policy: 'PROVIDER_RETAINED',
      compact_threshold: 20_000,
    })
    expect(request.store).toBe(true)
    expect(request.previous_response_id).toBe('resp_123')
    expect(request.context_management).toEqual([{ type: 'compaction', compact_threshold: 20_000 }])
  })

  it('fails closed when encrypted replay references are unresolved', () => {
    const profile = selectProviderCognitiveProfile('openai', 'frontier-research')
    const replayState: WorkingCognitiveStateV1 = {
      ...state(),
      provider_continuation: {
        transport: 'OPENAI_ENCRYPTED_REPLAY',
        encrypted_reasoning_item_refs: ['vault://reasoning/item-1'],
        opaque_payload_digest: sha('d'),
      },
    }
    expect(() => buildOpenAIResponsesContinuationRequest({
      profile,
      state: replayState,
      input: 'continue proof search',
      retention_policy: 'ZDR',
    })).toThrow(/resolved replay/i)

    const request = buildOpenAIResponsesContinuationRequest({
      profile,
      state: replayState,
      input: 'continue proof search',
      retention_policy: 'ZDR',
      resolved_replay_items: [{ type: 'reasoning', encrypted_content: 'opaque-ciphertext' }],
    })
    expect(request.store).toBe(false)
    expect(Array.isArray(request.input)).toBe(true)
  })
})

describe('COGNITIVE_RECONSTRUCTION_WASTE', () => {
  it('normalizes rediscovery by exact source/artifact/symbol/operation/purpose identity', () => {
    const metrics = CRWEvaluator.calculate({
      discoveries: [
        { source_commit: 'abc', artifact_digest: 'artifact', symbol: 'lemma_x', operation: 'inspect', purpose: 'proof', tokens_consumed: 100 },
        { source_commit: 'abc', artifact_digest: 'artifact', symbol: 'lemma_x', operation: 'inspect', purpose: 'proof', tokens_consumed: 120 },
        { source_commit: 'def', artifact_digest: 'artifact', symbol: 'lemma_x', operation: 'inspect', purpose: 'proof', tokens_consumed: 90 },
      ],
      hypotheses: [
        { id: 'h1', is_redundant: false },
        { id: 'h2', is_redundant: true },
      ],
      total_reasoning_tokens: 1_000,
      total_actions: 10,
      redundant_action_count: 2,
      verified_effects: [{ effect_class: 'FORMAL_THEOREM_ADMISSION', count: 2 }],
    })
    expect(metrics.Rd).toBeCloseTo(1 / 3)
    expect(metrics.Rh).toBe(0.5)
    expect(metrics.Rt).toBe(0.12)
    expect(metrics.Ra).toBe(0.2)
    expect(metrics.tokens_per_verified_effect.FORMAL_THEOREM_ADMISSION).toBe(500)
    expect(metrics.actions_per_verified_effect.FORMAL_THEOREM_ADMISSION).toBe(5)
  })
})
