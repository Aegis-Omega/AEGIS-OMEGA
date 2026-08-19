import { describe, expect, test } from 'vitest';

import {
  CAPABILITY_STATUSES,
  CONSEQUENCE_CLASSES,
  type CollectiveWorkGraphV1,
  type CollectiveWorkNodeV1,
  type IntentEnvelopeV1,
} from '../../../src/collective/contracts';
import {
  validateCollectiveWorkGraph,
  validateIntentEnvelope,
} from '../../../src/collective/validate';

const H = 'a'.repeat(64);
const B = 'b'.repeat(64);

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

const clone = <T>(value: T): T => structuredClone(value);

const expectInvalid = (value: unknown, prefix: string) => {
  const result = validateCollectiveWorkGraph(value);
  expect(result.ok).toBe(false);
  if (!result.ok) {
    expect(result.errors.some((error) => error.startsWith(prefix))).toBe(true);
  }
};

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
  });

  test('accepts a valid intent and graph', () => {
    expect(validateIntentEnvelope(intentFixture)).toEqual({ ok: true, value: intentFixture });
    expect(validateCollectiveWorkGraph(graphFixture)).toEqual({ ok: true, value: graphFixture });
  });

  test('rejects unknown top-level graph fields', () => {
    expectInvalid({ ...graphFixture, authority: 'PERMIT' }, 'UNKNOWN_FIELD:graph.authority');
  });

  test('rejects unknown nested capability fields', () => {
    const graph = clone(graphFixture) as unknown as Record<string, unknown>;
    const node = (graph.nodes as Array<Record<string, unknown>>)[0];
    const capability = (node.required_capabilities as Array<Record<string, unknown>>)[0];
    capability.authority = 'PERMIT';
    expectInvalid(graph, 'UNKNOWN_FIELD:graph.nodes[0].required_capabilities[0].authority');
  });

  test('rejects malformed SHA-256 digests', () => {
    expectInvalid({ ...graphFixture, intent_digest: 'abc' }, 'INVALID_HASH:graph.intent_digest');
  });

  test('rejects empty provider tool and capability identifiers', () => {
    const graph = clone(graphFixture);
    graph.nodes[0].allowed_providers = [''];
    graph.nodes[0].allowed_tools = [''];
    graph.nodes[0].required_capabilities[0].capability_id = '';
    const result = validateCollectiveWorkGraph(graph);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors).toContain('INVALID_NONEMPTY:graph.nodes[0].allowed_providers[0]');
      expect(result.errors).toContain('INVALID_NONEMPTY:graph.nodes[0].allowed_tools[0]');
      expect(result.errors).toContain('INVALID_NONEMPTY:graph.nodes[0].required_capabilities[0].capability_id');
    }
  });

  test('rejects duplicate work node IDs', () => {
    const graph = clone(graphFixture);
    graph.nodes.push({ ...clone(nodeFixture), nonce: 'node-nonce-002' });
    expectInvalid(graph, 'DUPLICATE_NODE_ID:node-001');
  });

  test('rejects missing dependencies', () => {
    const graph = clone(graphFixture);
    graph.nodes[0].dependency_ids = ['missing-node'];
    expectInvalid(graph, 'MISSING_DEPENDENCY:node-001->missing-node');
  });

  test('rejects self-dependency', () => {
    const graph = clone(graphFixture);
    graph.nodes[0].dependency_ids = ['node-001'];
    expectInvalid(graph, 'SELF_DEPENDENCY:node-001');
  });

  test('rejects graph cycles', () => {
    const graph = clone(graphFixture);
    graph.nodes[0].dependency_ids = ['node-002'];
    graph.nodes.push({
      ...clone(nodeFixture),
      work_node_id: 'node-002',
      dependency_ids: ['node-001'],
      nonce: 'node-nonce-002',
    });
    expectInvalid(graph, 'GRAPH_CYCLE:');
  });

  test('rejects node intent digest mismatch', () => {
    const graph = clone(graphFixture);
    graph.nodes[0].intent_digest = B;
    expectInvalid(graph, 'INTENT_BINDING_MISMATCH:node-001');
  });

  test('rejects node policy commitment mismatch', () => {
    const graph = clone(graphFixture);
    graph.nodes[0].policy_commitment = B;
    expectInvalid(graph, 'POLICY_BINDING_MISMATCH:node-001');
  });

  test('rejects node authority epoch mismatch', () => {
    const graph = clone(graphFixture);
    graph.nodes[0].authority_epoch = 8;
    expectInvalid(graph, 'AUTHORITY_EPOCH_MISMATCH:node-001');
  });

  test('accepts D3 and D4 only as declarations with no authority fields', () => {
    for (const consequence_class of ['D3', 'D4'] as const) {
      const graph = clone(graphFixture);
      graph.nodes[0].consequence_class = consequence_class;
      const result = validateCollectiveWorkGraph(graph);
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect('authority' in result.value.nodes[0]).toBe(false);
        expect('authorized' in result.value.nodes[0]).toBe(false);
        expect('execute' in result.value.nodes[0]).toBe(false);
      }
    }
  });

  test('rejects negative and non-integer numeric bounds', () => {
    const graph = clone(graphFixture);
    graph.authority_epoch = 1.5;
    graph.nodes[0].max_cost_microunits = -1;
    graph.nodes[0].max_tokens = 1.5;
    graph.nodes[0].max_duration_seconds = -2;
    const result = validateCollectiveWorkGraph(graph);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors).toContain('INVALID_NONNEGATIVE_INTEGER:graph.authority_epoch');
      expect(result.errors).toContain('INVALID_NONNEGATIVE_INTEGER:graph.nodes[0].max_cost_microunits');
      expect(result.errors).toContain('INVALID_NONNEGATIVE_INTEGER:graph.nodes[0].max_tokens');
      expect(result.errors).toContain('INVALID_NONNEGATIVE_INTEGER:graph.nodes[0].max_duration_seconds');
    }
  });

  test('rejects duplicate provider tool and capability entries', () => {
    const graph = clone(graphFixture);
    graph.nodes[0].allowed_providers = ['openai', 'openai'];
    graph.nodes[0].allowed_tools = ['repo.read', 'repo.read'];
    graph.nodes[0].required_capabilities.push(clone(graph.nodes[0].required_capabilities[0]));
    const result = validateCollectiveWorkGraph(graph);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors).toContain('DUPLICATE_VALUE:graph.nodes[0].allowed_providers:openai');
      expect(result.errors).toContain('DUPLICATE_VALUE:graph.nodes[0].allowed_tools:repo.read');
      expect(result.errors).toContain('DUPLICATE_CAPABILITY:graph.nodes[0].required_capabilities:CODE.TYPESCRIPT');
    }
  });

  test('returns the same verdict when independent node order is reversed', () => {
    const node2: CollectiveWorkNodeV1 = {
      ...clone(nodeFixture),
      work_node_id: 'node-002',
      nonce: 'node-nonce-002',
    };
    const forward = { ...clone(graphFixture), nodes: [clone(nodeFixture), node2] };
    const reverse = { ...clone(graphFixture), nodes: [node2, clone(nodeFixture)] };
    expect(validateCollectiveWorkGraph(forward).ok).toBe(true);
    expect(validateCollectiveWorkGraph(reverse).ok).toBe(true);
  });
});
