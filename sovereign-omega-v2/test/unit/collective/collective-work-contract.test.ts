import { describe, expect, test } from 'vitest';

import {
  CAPABILITY_STATUSES,
  CONSEQUENCE_CLASSES,
  type CollectiveWorkGraphV1,
  type CollectiveWorkNodeV1,
  type IntentEnvelopeV1,
} from '../../../src/collective/contracts';

const H = 'a'.repeat(64);

const intentFixture = {
  schema_version: '1.0.0',
  intent_kind: 'INTENT_ENVELOPE_V1',
  intent_id: 'intent-001',
  intent_digest: H,
  actor_identity: 'operator:tarik',
  session_identity: 'session:test',
  policy_commitment: H,
  authority_epoch: 7,
  input_artifact_digests: [H],
  requested_capability_ids: ['CODE.TYPESCRIPT'],
  max_cost_microunits: 0,
  max_tokens: 4096,
  max_duration_seconds: 60,
  consequence_ceiling: 'D1',
  deterministic_nonce: 'nonce-001',
} satisfies IntentEnvelopeV1;

const nodeFixture = {
  schema_version: '1.0.0',
  work_node_kind: 'COLLECTIVE_WORK_NODE_V1',
  work_node_id: 'node-001',
  objective_digest: H,
  intent_digest: H,
  required_capabilities: [
    {
      capability_kind: 'CAPABILITY_REF_V1',
      capability_id: 'CODE.TYPESCRIPT',
      status: 'TESTED_REFERENCE',
    },
  ],
  allowed_providers: ['openai'],
  allowed_tools: ['repo.read'],
  dependency_ids: [],
  input_artifact_digests: [H],
  max_cost_microunits: 0,
  max_tokens: 4096,
  max_duration_seconds: 60,
  consequence_class: 'D1',
  authority_epoch: 7,
  policy_commitment: H,
  target_commitment: H,
  pre_state_commitment: H,
  nonce: 'node-nonce-001',
} satisfies CollectiveWorkNodeV1;

const graphFixture = {
  schema_version: '1.0.0',
  graph_kind: 'COLLECTIVE_WORK_GRAPH_V1',
  graph_id: 'graph-001',
  intent_digest: H,
  nodes: [nodeFixture],
  policy_commitment: H,
  authority_epoch: 7,
  graph_nonce: 'graph-nonce-001',
} satisfies CollectiveWorkGraphV1;

describe('UCI-1 collective work contracts', () => {
  test('uses exact consequence classes', () => {
    expect(CONSEQUENCE_CLASSES).toEqual(['D0', 'D1', 'D2', 'D3', 'D4']);
  });

  test('uses exact capability statuses', () => {
    expect(CAPABILITY_STATUSES).toEqual([
      'NOT_TESTED',
      'PARTIAL',
      'TESTED_REFERENCE',
      'VERIFIED_FOR_PROFILE',
      'REVOKED',
    ]);
  });

  test('requires nominal discriminators in typed fixtures', () => {
    expect(intentFixture.intent_kind).toBe('INTENT_ENVELOPE_V1');
    expect(nodeFixture.work_node_kind).toBe('COLLECTIVE_WORK_NODE_V1');
    expect(graphFixture.graph_kind).toBe('COLLECTIVE_WORK_GRAPH_V1');
    expect(intentFixture.schema_version).toBe('1.0.0');
    expect(nodeFixture.schema_version).toBe('1.0.0');
    expect(graphFixture.schema_version).toBe('1.0.0');
  });
});
