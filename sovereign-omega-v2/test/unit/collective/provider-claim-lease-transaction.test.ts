import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterEach, describe, expect, test } from 'vitest';

import type { CollectiveWorkGraphV1, CollectiveWorkNodeV1 } from '../../../src/collective/contracts';
import { FileProviderClaimLeaseStoreV1 } from '../../../src/collective/provider-claim-lease';

const H = 'a'.repeat(64);
const B = 'b'.repeat(64);
const roots: string[] = [];

const node = (overrides: Partial<CollectiveWorkNodeV1> = {}): CollectiveWorkNodeV1 => ({
  schema_version: '1.0.0',
  work_node_kind: 'COLLECTIVE_WORK_NODE_V1',
  work_node_id: 'node-001',
  objective_digest: H,
  intent_digest: H,
  required_capabilities: [],
  allowed_providers: ['openai', 'google'],
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

const makeLease = () => {
  const root = mkdtempSync(join(tmpdir(), 'aegis-uci3-lease-lock-'));
  roots.push(root);
  const store = new FileProviderClaimLeaseStoreV1(join(root, 'claims.json'));
  const g = graph();
  const prepared = store.prepareClaim(g, 'node-001');
  const lease = store.claimWork({
    graph: g,
    work_node_id: 'node-001',
    owner_identity: 'provider:openai:session:s1',
    expected_store_root: prepared.store_root,
    lease_ms: 10_000,
    now_ms: 1_000,
  });
  return { store, g, lease };
};

afterEach(() => {
  while (roots.length > 0) rmSync(roots.pop()!, { recursive: true, force: true });
});

describe('UCI-3 lease-locked contribution primitive', () => {
  test('runs callback only while the exact current lease is valid', () => {
    const { store, g, lease } = makeLease();
    const result = store.withCurrentLease({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: lease.owner_identity,
      generation: lease.generation,
      fencing_token: lease.fencing_token,
      now_ms: 2_000,
    }, (current) => `${current.owner_identity}:${current.generation}`);

    expect(result).toBe('provider:openai:session:s1:1');
  });

  test('never enters callback for a stale or tampered lease', () => {
    const { store, g, lease } = makeLease();
    let entered = false;

    expect(() => store.withCurrentLease({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: lease.owner_identity,
      generation: lease.generation,
      fencing_token: B,
      now_ms: 2_000,
    }, () => {
      entered = true;
    })).toThrowError('PROVIDER_CLAIM_FENCE_MISMATCH');

    expect(entered).toBe(false);
  });

  test('holds the lease-store lock across callback so replacement cannot interleave', () => {
    const { store, g, lease } = makeLease();
    const replacementPrestate = store.prepareClaim(g, 'node-001');

    store.withCurrentLease({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: lease.owner_identity,
      generation: lease.generation,
      fencing_token: lease.fencing_token,
      now_ms: 2_000,
    }, () => {
      expect(() => store.claimWork({
        graph: g,
        work_node_id: 'node-001',
        owner_identity: 'provider:google:session:s2',
        expected_store_root: replacementPrestate.store_root,
        lease_ms: 10_000,
        now_ms: 20_001,
      })).toThrowError('PROVIDER_CLAIM_STORE_LOCKED');
    });
  });
});
