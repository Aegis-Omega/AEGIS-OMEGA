import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, test } from 'vitest';

const schemaRoot = path.resolve(process.cwd(), '..', 'schemas', 'collective');

const loadSchema = (name: string): Record<string, any> =>
  JSON.parse(readFileSync(path.join(schemaRoot, name), 'utf8')) as Record<string, any>;

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

const schemaCases = [
  {
    file: 'provider-session-identity-v1.schema.json',
    kindField: 'session_kind',
    kind: 'PROVIDER_SESSION_IDENTITY_V1',
    authority: 'IDENTITY_ONLY_NOT_AUTHORIZATION',
  },
  {
    file: 'provider-contribution-artifact-v1.schema.json',
    kindField: 'artifact_kind',
    kind: 'PROVIDER_CONTRIBUTION_ARTIFACT_V1',
    authority: 'NON_AUTHORITATIVE_EVIDENCE',
  },
  {
    file: 'provider-contribution-record-v1.schema.json',
    kindField: 'record_kind',
    kind: 'PROVIDER_CONTRIBUTION_RECORD_V1',
    authority: 'NON_AUTHORITATIVE_EVIDENCE',
  },
  {
    file: 'provider-contribution-store-v1.schema.json',
    kindField: 'store_kind',
    kind: 'UCI_PROVIDER_CONTRIBUTION_STORE_V1',
    authority: null,
  },
] as const;

describe('UCI-3 provider contribution schemas', () => {
  test.each(schemaCases)('$file is a closed Draft 2020-12 nominal contract', ({ file, kindField, kind, authority }) => {
    const schema = loadSchema(file);
    expect(schema.$schema).toBe('https://json-schema.org/draft/2020-12/schema');
    expect(schema.type).toBe('object');
    expect(schema.additionalProperties).toBe(false);
    expect(walkClosedObjects(schema)).toEqual([]);
    expect(schema.properties[kindField].const).toBe(kind);
    if (authority !== null) expect(schema.properties.authority.const).toBe(authority);
  });

  test('session schema mirrors the runtime identity surface exactly', () => {
    const schema = loadSchema('provider-session-identity-v1.schema.json');
    expect(new Set(schema.required)).toEqual(new Set([
      'schema_version', 'session_kind', 'provider', 'model', 'session_id', 'repository',
      'head_sha', 'capability_ids', 'policy_commitment', 'authority_epoch',
      'skill_catalog_root', 'organism_state_root', 'authority',
    ]));
    expect(schema.properties.capability_ids.uniqueItems).toBe(true);
    expect(schema.properties.policy_commitment.pattern).toBe('^[0-9a-f]{64}$');
    expect(schema.properties.head_sha.pattern).toBe('^[0-9a-f]{40,64}$');
  });

  test('artifact schema bounds evidence bytes, media types, and raw digest', () => {
    const schema = loadSchema('provider-contribution-artifact-v1.schema.json');
    const p = schema.properties;
    expect(p.sha256.pattern).toBe('^[0-9a-f]{64}$');
    expect(p.byte_length.minimum).toBe(1);
    expect(p.byte_length.maximum).toBe(262144);
    expect(new Set(p.media_type.enum)).toEqual(new Set(['text/plain', 'text/markdown', 'application/json']));
  });

  test('record schema keeps contribution evidence separate from decision/execution/effect authority', () => {
    const schema = loadSchema('provider-contribution-record-v1.schema.json');
    const names = new Set(Object.keys(schema.properties));
    for (const required of [
      'record_hash', 'graph_id', 'work_node_id', 'provider', 'model', 'session_id',
      'session_head_sha', 'lease_owner_identity', 'lease_generation', 'fencing_token',
      'artifact_sha256', 'contribution_store_prestate_root', 'intent_digest',
      'policy_commitment', 'authority_epoch', 'target_commitment', 'pre_state_commitment', 'authority',
    ]) {
      expect(names.has(required)).toBe(true);
    }
    for (const forbidden of [
      'permit', 'authorized', 'execute', 'decision_receipt', 'execution_receipt',
      'effect', 'effect_receipt', 'admission',
    ]) {
      expect(names.has(forbidden)).toBe(false);
    }
  });

  test('store schema closes artifact and record maps against untyped arbitrary values', () => {
    const schema = loadSchema('provider-contribution-store-v1.schema.json');
    expect(schema.properties.artifacts.type).toBe('object');
    expect(schema.properties.records.type).toBe('object');
    expect(schema.properties.artifacts.additionalProperties.$ref).toContain('provider-contribution-artifact-v1.schema.json');
    expect(schema.properties.records.additionalProperties.$ref).toContain('provider-contribution-record-v1.schema.json');
  });
});
