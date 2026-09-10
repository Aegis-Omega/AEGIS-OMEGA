import test from 'node:test';
import assert from 'node:assert/strict';
import { createAgentTools } from '../src/agent-tools.mjs';

const node = {
  node_id: 'agent-7',
  sequence: '8',
  confidence_bps: 6200,
  evidence_freshness_bps: 4100,
  load_bps: 8800,
  reliability_bps: 7300,
  contradiction_count: 2,
  observed_authority_envelope: 'D2',
  state_digest: 'sha256:state-5',
  policy_digest: 'sha256:policy-3',
  authority_epoch: '7',
  previous_receipt_hash: null,
};

function fakeStore() {
  return {
    getNodeState: async (id) => (id === 'missing' ? null : node),
    findEvidence: async ({ epistemicTier, embedding, limit }) => [
      { memory_id: 'm1', epistemic_tier: epistemicTier, distance: 0.1, dimensions: embedding.length, limit },
    ],
  };
}

const embed = async () => Array(1536).fill(0.01);

test('collective state tool emits observation-only MCM routing', async () => {
  const tools = createAgentTools({ store: fakeStore(), embed });
  const result = await tools.observeCollectiveState({ nodeId: 'agent-7' });
  assert.equal(result.observation.authorityEffect, 'OBSERVATION_ONLY');
  assert.equal(result.routing.authorityMutationPermitted, false);
  assert.equal(result.routing.requiresIndependentWitness, true);
});

test('evidence search routes embeddings into Cockroach memory without changing authority', async () => {
  const tools = createAgentTools({ store: fakeStore(), embed });
  const result = await tools.searchEvidence({ query: 'stale state incident', epistemicTier: 'T2', limit: 3 });
  assert.equal(result.matches[0].dimensions, 1536);
  assert.equal(result.authorityEffect, 'EVIDENCE_ONLY');
});

test('action evaluation binds observed action to admitted Cockroach memory', async () => {
  const tools = createAgentTools({ store: fakeStore(), embed });
  const denied = await tools.evaluateAction({
    nodeId: 'agent-7',
    requestId: 'r1',
    actionDigest: 'sha256:a',
    observedStateDigest: 'sha256:state-4',
    observedPolicyDigest: 'sha256:policy-3',
    observedAuthorityEpoch: 7,
    priorReceiptActionDigest: null,
  });
  assert.equal(denied.verdict, 'DENY');
  assert.deepEqual(denied.reasons, ['STALE_STATE']);
});

test('missing persisted node state fails closed', async () => {
  const tools = createAgentTools({ store: fakeStore(), embed });
  const denied = await tools.evaluateAction({
    nodeId: 'missing',
    requestId: 'r1',
    actionDigest: 'sha256:a',
    observedStateDigest: 'sha256:state-5',
    observedPolicyDigest: 'sha256:policy-3',
    observedAuthorityEpoch: 7,
    priorReceiptActionDigest: null,
  });
  assert.equal(denied.verdict, 'DENY');
  assert.deepEqual(denied.reasons, ['MEMORY_STATE_NOT_FOUND']);
});
