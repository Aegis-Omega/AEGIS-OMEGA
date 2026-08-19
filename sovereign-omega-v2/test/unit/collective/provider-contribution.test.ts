import { describe, expect, test } from 'vitest';

import type { CollectiveWorkGraphV1, CollectiveWorkNodeV1 } from '../../../src/collective/contracts';
import {
  PROVIDER_SESSION_AUTHORITY,
  validateProviderSessionIdentity,
} from '../../../src/collective/provider-contribution';

const H = 'a'.repeat(64);
const B = 'b'.repeat(64);
const HEAD = 'c'.repeat(40);

const node = (overrides: Partial<CollectiveWorkNodeV1> = {}): CollectiveWorkNodeV1 => ({
  schema_version: '1.0.0',
  work_node_kind: 'COLLECTIVE_WORK_NODE_V1',
  work_node_id: 'node-001',
  objective_digest: H,
  intent_digest: H,
  required_capabilities: [],
  allowed_providers: ['google', 'openai'],
  allowed_tools: ['repo.read'],
  dependency_ids: [],
  input_artifact_digests: [],
  max_cost_microunits: 0,
  max_tokens: 4096,
  max_duration_seconds: 60,
  consequence_class: 'D1',
  authority_epoch: 7,
  policy_commitment: H,
  target_commitment: H,
  pre_state_commitment: H,
  nonce: 'node-nonce-001',
  ...overrides,
});

const graph = (workNode = node()): CollectiveWorkGraphV1 => ({
  schema_version: '1.0.0',
  graph_kind: 'COLLECTIVE_WORK_GRAPH_V1',
  graph_id: 'graph-001',
  intent_digest: H,
  nodes: [workNode],
  policy_commitment: H,
  authority_epoch: 7,
  graph_nonce: 'graph-nonce-001',
});

const session = (overrides: Record<string, unknown> = {}) => ({
  schema_version: '1.0.0',
  session_kind: 'PROVIDER_SESSION_IDENTITY_V1',
  provider: 'openai',
  model: 'gpt-5.6-sol',
  session_id: 'session:s1',
  repository: 'Aegis-Omega/AEGIS-OMEGA',
  head_sha: HEAD,
  capability_ids: ['CODE.TYPESCRIPT', 'WEB.RESEARCH'],
  policy_commitment: H,
  authority_epoch: 7,
  skill_catalog_root: H,
  organism_state_root: H,
  authority: 'IDENTITY_ONLY_NOT_AUTHORIZATION',
  ...overrides,
});

describe('UCI-3 provider session identity boundary', () => {
  test('accepts a provider identity bound to the admitted graph without granting authority', () => {
    const result = validateProviderSessionIdentity(session(), graph(), 'node-001');
    expect(result.provider).toBe('openai');
    expect(result.authority).toBe(PROVIDER_SESSION_AUTHORITY);
    expect(PROVIDER_SESSION_AUTHORITY).toBe('IDENTITY_ONLY_NOT_AUTHORIZATION');
    expect('permit' in result).toBe(false);
    expect('execute' in result).toBe(false);
  });

  test('rejects unknown fields including authority and receipt injection surfaces', () => {
    for (const injected of [
      { permit: true },
      { execute: true },
      { decision_receipt: { outcome: 'PERMIT' } },
      { effect_receipt: { outcome: 'VERIFIED' } },
    ]) {
      expect(() => validateProviderSessionIdentity(session(injected), graph(), 'node-001'))
        .toThrowError('PROVIDER_SESSION_UNKNOWN_FIELD');
    }
  });

  test('rejects a provider that the work node did not admit', () => {
    expect(() => validateProviderSessionIdentity(
      session({ provider: 'anthropic' }),
      graph(),
      'node-001',
    )).toThrowError('PROVIDER_SESSION_PROVIDER_NOT_ALLOWED');
  });

  test('rejects stale policy or authority epoch bindings', () => {
    expect(() => validateProviderSessionIdentity(
      session({ policy_commitment: B }),
      graph(),
      'node-001',
    )).toThrowError('PROVIDER_SESSION_POLICY_MISMATCH');

    expect(() => validateProviderSessionIdentity(
      session({ authority_epoch: 6 }),
      graph(),
      'node-001',
    )).toThrowError('PROVIDER_SESSION_AUTHORITY_EPOCH_MISMATCH');
  });

  test('requires sorted unique capability ids', () => {
    expect(() => validateProviderSessionIdentity(
      session({ capability_ids: ['WEB.RESEARCH', 'CODE.TYPESCRIPT'] }),
      graph(),
      'node-001',
    )).toThrowError('PROVIDER_SESSION_CAPABILITIES_NOT_SORTED');

    expect(() => validateProviderSessionIdentity(
      session({ capability_ids: ['CODE.TYPESCRIPT', 'CODE.TYPESCRIPT'] }),
      graph(),
      'node-001',
    )).toThrowError('PROVIDER_SESSION_CAPABILITIES_NOT_UNIQUE');
  });

  test('rejects malformed identity and provenance roots', () => {
    expect(() => validateProviderSessionIdentity(
      session({ provider: 'open ai\n' }),
      graph(),
      'node-001',
    )).toThrowError('PROVIDER_SESSION_PROVIDER_INVALID');

    expect(() => validateProviderSessionIdentity(
      session({ head_sha: 'abc' }),
      graph(),
      'node-001',
    )).toThrowError('PROVIDER_SESSION_HEAD_INVALID');

    expect(() => validateProviderSessionIdentity(
      session({ skill_catalog_root: 'abc' }),
      graph(),
      'node-001',
    )).toThrowError('PROVIDER_SESSION_SKILL_ROOT_INVALID');
  });

  test('rejects wrong session authority marker', () => {
    expect(() => validateProviderSessionIdentity(
      session({ authority: 'PERMIT' }),
      graph(),
      'node-001',
    )).toThrowError('PROVIDER_SESSION_AUTHORITY_INVALID');
  });

  test('rejects missing work node and malformed graph through the shared graph validator', () => {
    expect(() => validateProviderSessionIdentity(session(), graph(), 'missing'))
      .toThrowError('PROVIDER_SESSION_WORK_NODE_MISSING');

    expect(() => validateProviderSessionIdentity(
      session(),
      { ...graph(), graph_id: '' },
      'node-001',
    )).toThrowError(/PROVIDER_SESSION_GRAPH_INVALID/);
  });
});
