import { createHash } from 'node:crypto';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterEach, describe, expect, test } from 'vitest';

import type { CollectiveWorkGraphV1, CollectiveWorkNodeV1 } from '../../../src/collective/contracts';
import {
  FileProviderClaimLeaseStoreV1,
  ProviderClaimLeaseError,
} from '../../../src/collective/provider-claim-lease';

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

const makeStore = () => {
  const root = mkdtempSync(join(tmpdir(), 'aegis-uci2-'));
  roots.push(root);
  const path = join(root, 'claims.json');
  return { path, store: new FileProviderClaimLeaseStoreV1(path) };
};

const fence = (workNodeId: string, owner: string, generation: number) =>
  createHash('sha256').update(`${workNodeId}\0${owner}\0${generation}`, 'utf8').digest('hex');

afterEach(() => {
  while (roots.length > 0) rmSync(roots.pop()!, { recursive: true, force: true });
});

describe('UCI-2 durable provider claim lease', () => {
  test('issues generation one with deterministic frontier-compatible fence and no authority', () => {
    const { store } = makeStore();
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

    expect(lease.claim_kind).toBe('DURABLE_PROVIDER_CLAIM_LEASE_V1');
    expect(lease.generation).toBe(1);
    expect(lease.fencing_token).toBe(fence('node-001', 'provider:openai:session:s1', 1));
    expect(lease.expires_ms).toBe(11_000);
    expect(lease.authority).toBe('SCHEDULING_LEASE_ONLY');
    expect('authorized' in lease).toBe(false);
    expect('execute' in lease).toBe(false);
  });

  test('rejects stale pre-state after another claimant mutates the durable store', () => {
    const { store } = makeStore();
    const g = graph();
    const stale = store.prepareClaim(g, 'node-001');
    store.claimWork({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: 'provider:openai:session:s1',
      expected_store_root: stale.store_root,
      lease_ms: 10_000,
      now_ms: 1_000,
    });

    expect(() => store.claimWork({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: 'provider:google:session:s2',
      expected_store_root: stale.store_root,
      lease_ms: 10_000,
      now_ms: 2_000,
    })).toThrowError('PROVIDER_CLAIM_PRESTATE_STALE');
  });

  test('rejects a second provider while an active lease exists', () => {
    const { store } = makeStore();
    const g = graph();
    let prepared = store.prepareClaim(g, 'node-001');
    store.claimWork({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: 'provider:openai:session:s1',
      expected_store_root: prepared.store_root,
      lease_ms: 10_000,
      now_ms: 1_000,
    });
    prepared = store.prepareClaim(g, 'node-001');

    expect(() => store.claimWork({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: 'provider:google:session:s2',
      expected_store_root: prepared.store_root,
      lease_ms: 10_000,
      now_ms: 2_000,
    })).toThrowError('PROVIDER_CLAIM_ACTIVE');
  });

  test('same owner retry is idempotent and does not advance generation', () => {
    const { store } = makeStore();
    const g = graph();
    let prepared = store.prepareClaim(g, 'node-001');
    const first = store.claimWork({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: 'provider:openai:session:s1',
      expected_store_root: prepared.store_root,
      lease_ms: 10_000,
      now_ms: 1_000,
    });
    prepared = store.prepareClaim(g, 'node-001');
    const second = store.claimWork({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: 'provider:openai:session:s1',
      expected_store_root: prepared.store_root,
      lease_ms: 10_000,
      now_ms: 2_000,
    });

    expect(second).toEqual(first);
    expect(store.prepareClaim(g, 'node-001').next_generation).toBe(2);
  });

  test('expired lease can be reclaimed only with a higher generation', () => {
    const { store } = makeStore();
    const g = graph();
    let prepared = store.prepareClaim(g, 'node-001');
    const first = store.claimWork({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: 'provider:openai:session:s1',
      expected_store_root: prepared.store_root,
      lease_ms: 1_000,
      now_ms: 1_000,
    });
    prepared = store.prepareClaim(g, 'node-001');
    const second = store.claimWork({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: 'provider:google:session:s2',
      expected_store_root: prepared.store_root,
      lease_ms: 1_000,
      now_ms: 2_001,
    });

    expect(first.generation).toBe(1);
    expect(second.generation).toBe(2);
    expect(second.fencing_token).not.toBe(first.fencing_token);
  });

  test('stale owner generation or fence can never satisfy current-lease verification', () => {
    const { store } = makeStore();
    const g = graph();
    let prepared = store.prepareClaim(g, 'node-001');
    const first = store.claimWork({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: 'provider:openai:session:s1',
      expected_store_root: prepared.store_root,
      lease_ms: 1_000,
      now_ms: 1_000,
    });
    prepared = store.prepareClaim(g, 'node-001');
    store.claimWork({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: 'provider:google:session:s2',
      expected_store_root: prepared.store_root,
      lease_ms: 10_000,
      now_ms: 2_001,
    });

    expect(() => store.assertCurrentLease({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: first.owner_identity,
      generation: first.generation,
      fencing_token: first.fencing_token,
      now_ms: 2_100,
    })).toThrowError(/PROVIDER_CLAIM_(OWNER|GENERATION|FENCE)_MISMATCH/);
  });

  test('exact lease survives store restart and remains verifiable', () => {
    const { path, store } = makeStore();
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

    const restored = new FileProviderClaimLeaseStoreV1(path);
    expect(restored.assertCurrentLease({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: lease.owner_identity,
      generation: lease.generation,
      fencing_token: lease.fencing_token,
      now_ms: 2_000,
    })).toEqual(lease);
  });

  test('release requires exact owner generation and fence while preserving generation history', () => {
    const { store } = makeStore();
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

    expect(() => store.releaseClaim({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: lease.owner_identity,
      generation: lease.generation,
      fencing_token: B,
      now_ms: 2_000,
    })).toThrowError('PROVIDER_CLAIM_FENCE_MISMATCH');

    expect(store.releaseClaim({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: lease.owner_identity,
      generation: lease.generation,
      fencing_token: lease.fencing_token,
      now_ms: 2_000,
    })).toBe(true);
    expect(store.prepareClaim(g, 'node-001').next_generation).toBe(2);
  });

  test.each(['D3', 'D4'] as const)('%s work is not claimable in UCI-2', (consequenceClass) => {
    const { store } = makeStore();
    const g = graph(node({ consequence_class: consequenceClass }));
    const prepared = store.prepareClaim(g, 'node-001');

    expect(() => store.claimWork({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: 'provider:openai:session:s1',
      expected_store_root: prepared.store_root,
      lease_ms: 10_000,
      now_ms: 1_000,
    })).toThrowError('PROVIDER_CLAIM_CONSEQUENCE_NOT_CLAIMABLE');
  });

  test('claim is bound to exact graph policy epoch target and pre-state', () => {
    const { store } = makeStore();
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

    expect(lease.graph_id).toBe(g.graph_id);
    expect(lease.policy_commitment).toBe(H);
    expect(lease.authority_epoch).toBe(7);
    expect(lease.target_commitment).toBe(H);
    expect(lease.pre_state_commitment).toBe(H);

    const changed = graph(node({ target_commitment: B }));
    expect(() => store.assertCurrentLease({
      graph: changed,
      work_node_id: 'node-001',
      owner_identity: lease.owner_identity,
      generation: lease.generation,
      fencing_token: lease.fencing_token,
      now_ms: 2_000,
    })).toThrowError('PROVIDER_CLAIM_BINDING_MISMATCH');
  });

  test('malformed persisted state fails closed instead of being repaired or guessed', () => {
    const { path } = makeStore();
    const { writeFileSync } = require('node:fs') as typeof import('node:fs');
    writeFileSync(path, '{"store_kind":"WRONG"}', 'utf8');
    expect(() => new FileProviderClaimLeaseStoreV1(path)).toThrowError(ProviderClaimLeaseError);
  });
});
