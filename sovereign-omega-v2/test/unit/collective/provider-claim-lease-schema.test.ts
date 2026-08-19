import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import Ajv2020 from 'ajv/dist/2020.js';
import { describe, expect, test } from 'vitest';

const schemaPath = resolve(
  process.cwd(),
  '../schemas/collective/durable-provider-claim-lease-v1.schema.json',
);

const loadSchema = () => JSON.parse(readFileSync(schemaPath, 'utf8')) as Record<string, unknown>;

const H = 'a'.repeat(64);

const validLease = {
  schema_version: '1.0.0',
  claim_kind: 'DURABLE_PROVIDER_CLAIM_LEASE_V1',
  graph_id: 'graph-001',
  work_node_id: 'node-001',
  owner_identity: 'provider:openai:session:s1',
  generation: 1,
  fencing_token: H,
  issued_ms: 1000,
  expires_ms: 11000,
  intent_digest: H,
  policy_commitment: H,
  authority_epoch: 7,
  target_commitment: H,
  pre_state_commitment: H,
  authority: 'SCHEDULING_LEASE_ONLY',
};

describe('UCI-2 durable provider claim lease schema', () => {
  test('is a closed Draft 2020-12 nominal contract', () => {
    const schema = loadSchema();
    expect(schema.$schema).toBe('https://json-schema.org/draft/2020-12/schema');
    expect(schema.additionalProperties).toBe(false);
    expect((schema.properties as Record<string, any>).claim_kind.const).toBe(
      'DURABLE_PROVIDER_CLAIM_LEASE_V1',
    );
    expect((schema.properties as Record<string, any>).authority.const).toBe(
      'SCHEDULING_LEASE_ONLY',
    );
  });

  test('accepts the canonical lease shape', () => {
    const ajv = new Ajv2020({ allErrors: true, strict: true });
    const validate = ajv.compile(loadSchema());
    expect(validate(validLease), JSON.stringify(validate.errors)).toBe(true);
  });

  test.each([
    ['authority injection', { ...validLease, execute: true }],
    ['wrong authority marker', { ...validLease, authority: 'PERMIT' }],
    ['wrong nominal kind', { ...validLease, claim_kind: 'AUTHORITY_LEASE_V1' }],
    ['zero generation', { ...validLease, generation: 0 }],
    ['fractional generation', { ...validLease, generation: 1.5 }],
    ['malformed fence', { ...validLease, fencing_token: 'abc' }],
    ['negative issued time', { ...validLease, issued_ms: -1 }],
    ['malformed policy commitment', { ...validLease, policy_commitment: 'abc' }],
  ])('rejects %s', (_label, candidate) => {
    const ajv = new Ajv2020({ allErrors: true, strict: true });
    const validate = ajv.compile(loadSchema());
    expect(validate(candidate)).toBe(false);
  });
});
