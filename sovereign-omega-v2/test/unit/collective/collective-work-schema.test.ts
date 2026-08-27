import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, test } from 'vitest';

const schemaPath = (name: string) => path.resolve(process.cwd(), '..', 'schemas', name);
const load = (name: string): Record<string, any> =>
  JSON.parse(readFileSync(schemaPath(name), 'utf8')) as Record<string, any>;

const forbiddenWritable = new Set([
  'authority',
  'authorized',
  'execute',
  'effect',
  'admission',
  'receipt',
]);

function walkClosedObjects(value: unknown, pathLabel = '$'): string[] {
  const errors: string[] = [];
  if (!value || typeof value !== 'object') return errors;
  const obj = value as Record<string, unknown>;
  if (obj.type === 'object' && obj.additionalProperties !== false) {
    errors.push(`${pathLabel}:object_not_closed`);
  }
  for (const [key, child] of Object.entries(obj)) {
    if (child && typeof child === 'object') {
      errors.push(...walkClosedObjects(child, `${pathLabel}.${key}`));
    }
  }
  return errors;
}

function collectPropertyNames(value: unknown): string[] {
  if (!value || typeof value !== 'object') return [];
  const obj = value as Record<string, unknown>;
  const names = new Set<string>();
  if (obj.properties && typeof obj.properties === 'object') {
    for (const key of Object.keys(obj.properties as Record<string, unknown>)) names.add(key);
  }
  for (const child of Object.values(obj)) {
    for (const key of collectPropertyNames(child)) names.add(key);
  }
  return [...names].sort();
}

describe('UCI-1 JSON Schema contracts', () => {
  test('publishes four closed draft-2020-12 schemas', () => {
    const names = [
      'intent-envelope.v1.schema.json',
      'capability-ref.v1.schema.json',
      'collective-work-node.v1.schema.json',
      'collective-work-graph.v1.schema.json',
    ];
    for (const name of names) {
      const schema = load(name);
      expect(schema.$schema).toBe('https://json-schema.org/draft/2020-12/schema');
      expect(walkClosedObjects(schema)).toEqual([]);
    }
  });

  test('uses exact nominal discriminators and enums', () => {
    const intent = load('intent-envelope.v1.schema.json');
    const capability = load('capability-ref.v1.schema.json');
    const node = load('collective-work-node.v1.schema.json');
    const graph = load('collective-work-graph.v1.schema.json');

    expect(intent.properties.intent_kind.const).toBe('INTENT_ENVELOPE_V1');
    expect(node.properties.work_node_kind.const).toBe('COLLECTIVE_WORK_NODE_V1');
    expect(graph.properties.graph_kind.const).toBe('COLLECTIVE_WORK_GRAPH_V1');
    expect(capability.properties.capability_kind.const).toBe('CAPABILITY_REF_V1');
    expect(intent.properties.consequence_ceiling.enum).toEqual(['D0', 'D1', 'D2', 'D3', 'D4']);
    expect(node.properties.consequence_class.enum).toEqual(['D0', 'D1', 'D2', 'D3', 'D4']);
    expect(capability.properties.status.enum).toEqual([
      'NOT_TESTED',
      'PARTIAL',
      'TESTED_REFERENCE',
      'VERIFIED_FOR_PROFILE',
      'REVOKED',
    ]);
  });

  test('requires the runtime contract fields and SHA-256 commitments', () => {
    const intent = load('intent-envelope.v1.schema.json');
    const node = load('collective-work-node.v1.schema.json');
    const graph = load('collective-work-graph.v1.schema.json');

    expect(new Set(intent.required)).toEqual(
      new Set([
        'schema_version','intent_kind','intent_id','intent_digest','actor_identity','session_identity',
        'policy_commitment','authority_epoch','input_artifact_digests','requested_capability_ids',
        'max_cost_microunits','max_tokens','max_duration_seconds','consequence_ceiling','deterministic_nonce',
      ]),
    );
    expect(new Set(node.required)).toEqual(
      new Set([
        'schema_version','work_node_kind','work_node_id','objective_digest','intent_digest',
        'required_capabilities','allowed_providers','allowed_tools','dependency_ids','input_artifact_digests',
        'max_cost_microunits','max_tokens','max_duration_seconds','consequence_class','authority_epoch',
        'policy_commitment','target_commitment','pre_state_commitment','nonce',
      ]),
    );
    expect(new Set(graph.required)).toEqual(
      new Set(['schema_version','graph_kind','graph_id','intent_digest','nodes','policy_commitment','authority_epoch','graph_nonce']),
    );
    expect(intent.$defs.hash.pattern).toBe('^[0-9a-f]{64}$');
    expect(node.$defs.hash.pattern).toBe('^[0-9a-f]{64}$');
    expect(graph.$defs.hash.pattern).toBe('^[0-9a-f]{64}$');
  });

  test('does not expose authority execution effect admission or receipt fields', () => {
    for (const name of [
      'intent-envelope.v1.schema.json',
      'capability-ref.v1.schema.json',
      'collective-work-node.v1.schema.json',
      'collective-work-graph.v1.schema.json',
    ]) {
      const names = collectPropertyNames(load(name));
      expect(names.filter((key) => forbiddenWritable.has(key))).toEqual([]);
    }
  });
});
