import { describe, expect, test } from 'vitest';

import type {
  CollectiveWorkGraphV1,
  CollectiveWorkNodeV1,
  IntentEnvelopeV1,
} from '../../../src/collective/contracts.js';
import {
  validateCollectiveWorkGraph,
  validateIntentEnvelope,
} from '../../../src/collective/validate.js';

const H = 'a'.repeat(64);

const intentFixture = (): IntentEnvelopeV1 => ({
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
});

const nodeFixture = (): CollectiveWorkNodeV1 => ({
  schema_version: '1.0.0',
  work_node_kind: 'COLLECTIVE_WORK_NODE_V1',
  work_node_id: 'node-001',
  objective_digest: H,
  intent_digest: H,
  required_capabilities: [{
    capability_kind: 'CAPABILITY_REF_V1',
    capability_id: 'CODE.TYPESCRIPT',
    status: 'TESTED_REFERENCE',
  }],
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
});

const graphFixture = (): CollectiveWorkGraphV1 => ({
  schema_version: '1.0.0',
  graph_kind: 'COLLECTIVE_WORK_GRAPH_V1',
  graph_id: 'graph-001',
  intent_digest: H,
  nodes: [nodeFixture()],
  policy_commitment: H,
  authority_epoch: 7,
  graph_nonce: 'graph-nonce-001',
});

const expectGraphError = (value: unknown, error: string): void => {
  const validation = validateCollectiveWorkGraph(value);
  expect(validation.ok).toBe(false);
  if (!validation.ok) expect(validation.errors).toContain(error);
};

const expectIntentError = (value: unknown, error: string): void => {
  const validation = validateIntentEnvelope(value);
  expect(validation.ok).toBe(false);
  if (!validation.ok) expect(validation.errors).toContain(error);
};

describe('UCI-1 validator structural hardening', () => {
  test('rejects sparse arrays at every intent and graph array boundary', () => {
    const intentCases = [
      ['input_artifact_digests', 'intent.input_artifact_digests'],
      ['requested_capability_ids', 'intent.requested_capability_ids'],
    ] as const;
    for (const [field, path] of intentCases) {
      const intent = intentFixture() as unknown as Record<string, unknown>;
      intent[field] = new Array(1);
      expectIntentError(intent, `SPARSE_ARRAY:${path}`);
    }

    const graph = graphFixture() as unknown as Record<string, unknown>;
    graph.nodes = new Array(1);
    expectGraphError(graph, 'SPARSE_ARRAY:graph.nodes');

    const nodeCases = [
      ['required_capabilities', 'graph.nodes[0].required_capabilities'],
      ['allowed_providers', 'graph.nodes[0].allowed_providers'],
      ['allowed_tools', 'graph.nodes[0].allowed_tools'],
      ['dependency_ids', 'graph.nodes[0].dependency_ids'],
      ['input_artifact_digests', 'graph.nodes[0].input_artifact_digests'],
    ] as const;
    for (const [field, path] of nodeCases) {
      const candidate = graphFixture() as unknown as Record<string, unknown>;
      const node = (candidate.nodes as Array<Record<string, unknown>>)[0]!;
      node[field] = new Array(1);
      expectGraphError(candidate, `SPARSE_ARRAY:${path}`);
    }
  });

  test('rejects inherited records instead of validating inherited authority-bearing data', () => {
    const inherited = Object.create({ ...graphFixture(), authority: 'PERMIT' }) as unknown;
    const validation = validateCollectiveWorkGraph(inherited);
    expect(validation.ok).toBe(false);
  });

  test('rejects accessors without invoking them', () => {
    let reads = 0;
    const graph = graphFixture();
    Object.defineProperty(graph, 'graph_id', {
      enumerable: true,
      get: () => {
        reads += 1;
        return 'graph-001';
      },
    });

    const validation = validateCollectiveWorkGraph(graph);
    expect(validation.ok).toBe(false);
    expect(reads).toBe(0);
  });

  test('rejects accessor array elements without invoking them', () => {
    let reads = 0;
    const graph = graphFixture();
    Object.defineProperty(graph.nodes, '0', {
      enumerable: true,
      get: () => {
        reads += 1;
        return nodeFixture();
      },
    });

    const validation = validateCollectiveWorkGraph(graph);
    expect(validation.ok).toBe(false);
    expect(reads).toBe(0);
  });

  test('rejects symbol keys and extra array properties', () => {
    const symbolGraph = graphFixture() as CollectiveWorkGraphV1 & { [key: symbol]: string };
    symbolGraph[Symbol('authority')] = 'PERMIT';
    expectGraphError(symbolGraph, 'NON_JSON_SYMBOL_KEY:graph');

    const arrayPropertyGraph = graphFixture();
    (arrayPropertyGraph.nodes as unknown as Record<string, unknown>).authority = 'PERMIT';
    expectGraphError(arrayPropertyGraph, 'NON_JSON_ARRAY_PROPERTY:graph.nodes.authority');
  });

  test('denies reflection failures instead of throwing or accepting', () => {
    const hostile = new Proxy(graphFixture(), {
      ownKeys: () => {
        throw new Error('reflection denied');
      },
    });

    expect(() => validateCollectiveWorkGraph(hostile)).not.toThrow();
    expect(validateCollectiveWorkGraph(hostile).ok).toBe(false);
  });

  test('rejects transparent proxy wrappers as non-plain input', () => {
    const proxied = new Proxy(graphFixture(), {});
    expect(validateCollectiveWorkGraph(proxied).ok).toBe(false);
  });

  test('rejects a present-but-undefined optional capability profile', () => {
    const graph = graphFixture() as unknown as Record<string, unknown>;
    const node = (graph.nodes as Array<Record<string, unknown>>)[0]!;
    const capability = (node.required_capabilities as Array<Record<string, unknown>>)[0]!;
    capability.profile = undefined;
    expectGraphError(graph, 'INVALID_NONEMPTY:graph.nodes[0].required_capabilities[0].profile');
  });
});

describe('UCI-1 validator scalar hardening', () => {
  test('accepts 512-code-point strings and rejects 513-code-point strings', () => {
    const intentCases = [
      (value: string) => Object.assign(intentFixture(), { intent_id: value }),
      (value: string) => Object.assign(intentFixture(), { deterministic_nonce: value }),
    ];
    for (const candidate of intentCases) {
      expect(validateIntentEnvelope(candidate('x'.repeat(512))).ok).toBe(true);
      expect(validateIntentEnvelope(candidate('x'.repeat(513))).ok).toBe(false);
    }

    const graphCases = [
      (value: string) => Object.assign(graphFixture(), { graph_id: value }),
      (value: string) => {
        const graph = graphFixture();
        graph.nodes[0]!.work_node_id = value;
        return graph;
      },
      (value: string) => {
        const graph = graphFixture();
        graph.nodes[0]!.required_capabilities[0]!.capability_id = value;
        return graph;
      },
      (value: string) => {
        const graph = graphFixture();
        graph.nodes[0]!.allowed_providers = [value];
        return graph;
      },
      (value: string) => {
        const graph = graphFixture();
        graph.nodes[0]!.allowed_tools = [value];
        return graph;
      },
      (value: string) => {
        const graph = graphFixture();
        graph.nodes[0]!.nonce = value;
        return graph;
      },
      (value: string) => {
        const graph = graphFixture();
        graph.nodes[0]!.required_capabilities[0]!.profile = value;
        return graph;
      },
    ];
    for (const candidate of graphCases) {
      expect(validateCollectiveWorkGraph(candidate('x'.repeat(512))).ok).toBe(true);
      expect(validateCollectiveWorkGraph(candidate('x'.repeat(513))).ok).toBe(false);
    }
  });

  test('counts schema string length in Unicode code points', () => {
    expect(validateIntentEnvelope({ ...intentFixture(), intent_id: '🚀'.repeat(512) }).ok).toBe(true);
    expect(validateIntentEnvelope({ ...intentFixture(), intent_id: '🚀'.repeat(513) }).ok).toBe(false);
  });

  test('rejects unsafe integers and negative zero at every intent integer field', () => {
    const fields = [
      'authority_epoch',
      'max_cost_microunits',
      'max_tokens',
      'max_duration_seconds',
    ] as const;
    for (const field of fields) {
      for (const invalid of [Number.MAX_SAFE_INTEGER + 1, -0]) {
        const intent = intentFixture();
        intent[field] = invalid;
        expectIntentError(intent, `INVALID_NONNEGATIVE_INTEGER:intent.${field}`);
      }
    }
  });

  test('rejects unsafe integers and negative zero at every graph and node integer field', () => {
    for (const invalid of [Number.MAX_SAFE_INTEGER + 1, -0]) {
      const graph = graphFixture();
      graph.authority_epoch = invalid;
      graph.nodes[0]!.authority_epoch = invalid;
      expectGraphError(graph, 'INVALID_NONNEGATIVE_INTEGER:graph.authority_epoch');
      expectGraphError(graph, 'INVALID_NONNEGATIVE_INTEGER:graph.nodes[0].authority_epoch');

      for (const field of ['max_cost_microunits', 'max_tokens', 'max_duration_seconds'] as const) {
        const candidate = graphFixture();
        candidate.nodes[0]![field] = invalid;
        expectGraphError(candidate, `INVALID_NONNEGATIVE_INTEGER:graph.nodes[0].${field}`);
      }
    }
  });
});

describe('UCI-1 validator snapshot and ordering hardening', () => {
  test('returns a detached recursively frozen graph snapshot', () => {
    const caller = graphFixture();
    const validation = validateCollectiveWorkGraph(caller);
    expect(validation.ok).toBe(true);
    if (!validation.ok) return;

    const snapshot = validation.value;
    expect(snapshot).not.toBe(caller);
    expect(snapshot.nodes).not.toBe(caller.nodes);
    expect(snapshot.nodes[0]).not.toBe(caller.nodes[0]);
    expect(snapshot.nodes[0]!.required_capabilities[0]).not.toBe(
      caller.nodes[0]!.required_capabilities[0],
    );
    expect(Object.isFrozen(snapshot)).toBe(true);
    expect(Object.isFrozen(snapshot.nodes)).toBe(true);
    expect(Object.isFrozen(snapshot.nodes[0])).toBe(true);
    expect(Object.isFrozen(snapshot.nodes[0]!.required_capabilities)).toBe(true);
    expect(Object.isFrozen(snapshot.nodes[0]!.required_capabilities[0])).toBe(true);

    caller.graph_id = 'mutated';
    caller.nodes.push(nodeFixture());
    caller.nodes[0]!.allowed_tools[0] = 'authority.inject';
    (caller.nodes[0] as CollectiveWorkNodeV1 & { authority?: string }).authority = 'PERMIT';
    expect(snapshot.graph_id).toBe('graph-001');
    expect(snapshot.nodes).toHaveLength(1);
    expect(snapshot.nodes[0]!.allowed_tools).toEqual(['repo.read']);
    expect('authority' in snapshot.nodes[0]!).toBe(false);

    expect(Reflect.set(snapshot, 'graph_id', 'mutated')).toBe(false);
    expect(Reflect.set(snapshot.nodes[0]!, 'nonce', 'mutated')).toBe(false);
    expect(Reflect.deleteProperty(snapshot.nodes, '0')).toBe(false);
  });

  test('returns a detached recursively frozen intent snapshot', () => {
    const caller = intentFixture();
    const validation = validateIntentEnvelope(caller);
    expect(validation.ok).toBe(true);
    if (!validation.ok) return;

    expect(validation.value).not.toBe(caller);
    expect(validation.value.requested_capability_ids).not.toBe(caller.requested_capability_ids);
    expect(Object.isFrozen(validation.value)).toBe(true);
    expect(Object.isFrozen(validation.value.requested_capability_ids)).toBe(true);
    caller.requested_capability_ids[0] = 'MUTATED';
    expect(validation.value.requested_capability_ids).toEqual(['CODE.TYPESCRIPT']);
  });

  test('does not depend on localeCompare for deterministic validation', () => {
    const original = String.prototype.localeCompare;
    String.prototype.localeCompare = () => {
      throw new Error('locale-dependent ordering used');
    };
    try {
      const graph = graphFixture();
      graph.nodes.push({ ...nodeFixture(), nonce: 'duplicate' });
      expect(() => validateCollectiveWorkGraph(graph)).not.toThrow();
      expect(validateCollectiveWorkGraph(graph).ok).toBe(false);
    } finally {
      String.prototype.localeCompare = original;
    }
  });

  test('sorts validation errors by UTF-16 code units', () => {
    const graph = graphFixture() as CollectiveWorkGraphV1 & Record<string, unknown>;
    graph['ä'] = true;
    graph.Z = true;
    const validation = validateCollectiveWorkGraph(graph);
    expect(validation).toEqual({
      ok: false,
      errors: ['UNKNOWN_FIELD:graph.Z', 'UNKNOWN_FIELD:graph.ä'],
    });
  });
});
