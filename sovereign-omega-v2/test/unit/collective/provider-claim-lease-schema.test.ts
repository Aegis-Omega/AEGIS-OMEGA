import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, test } from 'vitest';

const schemaPath = path.resolve(
  process.cwd(),
  '..',
  'schemas',
  'collective',
  'durable-provider-claim-lease-v1.schema.json',
);

const loadSchema = (): Record<string, any> =>
  JSON.parse(readFileSync(schemaPath, 'utf8')) as Record<string, any>;

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

describe('UCI-2 durable provider claim lease schema', () => {
  test('is a closed Draft 2020-12 nominal contract', () => {
    const schema = loadSchema();
    expect(schema.$schema).toBe('https://json-schema.org/draft/2020-12/schema');
    expect(schema.type).toBe('object');
    expect(schema.additionalProperties).toBe(false);
    expect(walkClosedObjects(schema)).toEqual([]);
    expect(schema.properties.claim_kind.const).toBe('DURABLE_PROVIDER_CLAIM_LEASE_V1');
    expect(schema.properties.authority.const).toBe('SCHEDULING_LEASE_ONLY');
  });

  test('requires exactly the serialized runtime lease fields', () => {
    const schema = loadSchema();
    expect(new Set(schema.required)).toEqual(new Set([
      'schema_version',
      'claim_kind',
      'graph_id',
      'work_node_id',
      'owner_identity',
      'generation',
      'fencing_token',
      'issued_ms',
      'expires_ms',
      'intent_digest',
      'policy_commitment',
      'authority_epoch',
      'target_commitment',
      'pre_state_commitment',
      'authority',
    ]));
  });

  test('locks hashes, generations, times, and owner identity fail closed', () => {
    const schema = loadSchema();
    const p = schema.properties;
    expect(p.generation.type).toBe('integer');
    expect(p.generation.minimum).toBe(1);
    expect(p.issued_ms.type).toBe('integer');
    expect(p.issued_ms.minimum).toBe(0);
    expect(p.expires_ms.type).toBe('integer');
    expect(p.expires_ms.minimum).toBe(0);
    expect(p.authority_epoch.type).toBe('integer');
    expect(p.authority_epoch.minimum).toBe(0);
    expect(p.owner_identity.pattern).toBe('^[A-Za-z0-9._:/@+\\-]{1,128}$');
    for (const field of [
      'fencing_token',
      'intent_digest',
      'policy_commitment',
      'target_commitment',
      'pre_state_commitment',
    ]) {
      expect(p[field].pattern).toBe('^[0-9a-f]{64}$');
    }
  });

  test('does not serialize execution, effect, admission, or receipt authority', () => {
    const schema = loadSchema();
    const names = new Set(Object.keys(schema.properties));
    for (const forbidden of [
      'authorized',
      'execute',
      'execution_receipt',
      'effect',
      'effect_receipt',
      'admission',
      'decision_receipt',
    ]) {
      expect(names.has(forbidden)).toBe(false);
    }
  });
});
