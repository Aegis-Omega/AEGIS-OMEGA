import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterEach, describe, expect, test } from 'vitest';

import type { CollectiveWorkGraphV1, CollectiveWorkNodeV1 } from '../../../src/collective/contracts';
import { FileProviderClaimLeaseStoreV1 } from '../../../src/collective/provider-claim-lease';
import {
  FileProviderContributionStoreV1,
  MAX_PROVIDER_CONTRIBUTION_BYTES,
  PROVIDER_CONTRIBUTION_AUTHORITY,
  type ProviderSessionIdentityV1,
} from '../../../src/collective/provider-contribution';

const H = 'a'.repeat(64);
const B = 'b'.repeat(64);
const HEAD = 'c'.repeat(40);
const roots: string[] = [];

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

const session = (overrides: Partial<ProviderSessionIdentityV1> = {}): ProviderSessionIdentityV1 => ({
  schema_version: '1.0.0',
  session_kind: 'PROVIDER_SESSION_IDENTITY_V1',
  provider: 'openai',
  model: 'gpt-5.6-sol',
  session_id: 'session:s1',
  repository: 'Aegis-Omega/AEGIS-OMEGA',
  head_sha: HEAD,
  capability_ids: ['CODE.TYPESCRIPT'],
  policy_commitment: H,
  authority_epoch: 7,
  skill_catalog_root: H,
  organism_state_root: H,
  authority: 'IDENTITY_ONLY_NOT_AUTHORIZATION',
  ...overrides,
});

const setup = (workNode = node()) => {
  const root = mkdtempSync(join(tmpdir(), 'aegis-uci3-contrib-'));
  roots.push(root);
  const leaseStore = new FileProviderClaimLeaseStoreV1(join(root, 'leases.json'));
  const contributionPath = join(root, 'contributions.json');
  const contributionStore = new FileProviderContributionStoreV1(contributionPath);
  const g = graph(workNode);
  const preparedLease = leaseStore.prepareClaim(g, 'node-001');
  const lease = leaseStore.claimWork({
    graph: g,
    work_node_id: 'node-001',
    owner_identity: 'provider:openai:session:s1',
    expected_store_root: preparedLease.store_root,
    lease_ms: 10_000,
    now_ms: 1_000,
  });
  return { root, leaseStore, contributionStore, contributionPath, g, lease };
};

afterEach(() => {
  while (roots.length > 0) rmSync(roots.pop()!, { recursive: true, force: true });
});

describe('UCI-3 provider contribution evidence store', () => {
  test('records UTF-8 evidence content-addressed under the exact current lease without authority promotion', () => {
    const { leaseStore, contributionStore, g, lease } = setup();
    const prepared = contributionStore.prepareContribution();
    const record = contributionStore.recordTextContribution({
      graph: g,
      work_node_id: 'node-001',
      session: session(),
      lease_store: leaseStore,
      generation: lease.generation,
      fencing_token: lease.fencing_token,
      now_ms: 2_000,
      expected_store_root: prepared.store_root,
      media_type: 'text/markdown',
      text: '# evidence\nhello',
    });

    const artifact = contributionStore.getArtifact(record.artifact_sha256);
    expect(artifact.text).toBe('# evidence\nhello');
    expect(artifact.byte_length).toBe(Buffer.byteLength('# evidence\nhello', 'utf8'));
    expect(artifact.authority).toBe(PROVIDER_CONTRIBUTION_AUTHORITY);
    expect(record.authority).toBe(PROVIDER_CONTRIBUTION_AUTHORITY);
    expect(record.graph_id).toBe('graph-001');
    expect(record.work_node_id).toBe('node-001');
    expect(record.lease_generation).toBe(lease.generation);
    expect(record.fencing_token).toBe(lease.fencing_token);
    expect('permit' in record).toBe(false);
    expect('execute' in record).toBe(false);
    expect('effect_receipt' in record).toBe(false);
  });

  test('identical content is artifact-idempotent and exact contribution retry returns the existing record', () => {
    const { leaseStore, contributionStore, g, lease } = setup();
    let prepared = contributionStore.prepareContribution();
    const input = {
      graph: g,
      work_node_id: 'node-001',
      session: session(),
      lease_store: leaseStore,
      generation: lease.generation,
      fencing_token: lease.fencing_token,
      now_ms: 2_000,
      expected_store_root: prepared.store_root,
      media_type: 'text/plain' as const,
      text: 'same bytes',
    };
    const first = contributionStore.recordTextContribution(input);
    prepared = contributionStore.prepareContribution();
    const second = contributionStore.recordTextContribution({ ...input, expected_store_root: prepared.store_root });

    expect(second).toEqual(first);
    expect(contributionStore.getArtifact(first.artifact_sha256)).toEqual(
      contributionStore.getArtifact(second.artifact_sha256),
    );
  });

  test('rejects stale contribution-store prestate', () => {
    const { leaseStore, contributionStore, g, lease } = setup();
    const stale = contributionStore.prepareContribution();
    contributionStore.recordTextContribution({
      graph: g,
      work_node_id: 'node-001',
      session: session(),
      lease_store: leaseStore,
      generation: lease.generation,
      fencing_token: lease.fencing_token,
      now_ms: 2_000,
      expected_store_root: stale.store_root,
      media_type: 'text/plain',
      text: 'first',
    });

    expect(() => contributionStore.recordTextContribution({
      graph: g,
      work_node_id: 'node-001',
      session: session(),
      lease_store: leaseStore,
      generation: lease.generation,
      fencing_token: lease.fencing_token,
      now_ms: 2_001,
      expected_store_root: stale.store_root,
      media_type: 'text/plain',
      text: 'second',
    })).toThrowError('PROVIDER_CONTRIBUTION_PRESTATE_STALE');
  });

  test('rejects stale/replaced lease before touching evidence state', () => {
    const { leaseStore, contributionStore, g, lease } = setup();
    const before = contributionStore.stateRoot();
    const preparedLease = leaseStore.prepareClaim(g, 'node-001');
    leaseStore.claimWork({
      graph: g,
      work_node_id: 'node-001',
      owner_identity: 'provider:google:session:s2',
      expected_store_root: preparedLease.store_root,
      lease_ms: 10_000,
      now_ms: 20_001,
    });

    expect(() => contributionStore.recordTextContribution({
      graph: g,
      work_node_id: 'node-001',
      session: session(),
      lease_store: leaseStore,
      generation: lease.generation,
      fencing_token: lease.fencing_token,
      now_ms: 20_002,
      expected_store_root: before,
      media_type: 'text/plain',
      text: 'stale writer',
    })).toThrowError(/PROVIDER_CLAIM_(OWNER|GENERATION|FENCE)_MISMATCH/);
    expect(contributionStore.stateRoot()).toBe(before);
  });

  test('rejects provider/session mismatch and provider not admitted by the work node', () => {
    const { leaseStore, contributionStore, g, lease } = setup();
    const prepared = contributionStore.prepareContribution();
    expect(() => contributionStore.recordTextContribution({
      graph: g,
      work_node_id: 'node-001',
      session: session({ session_id: 'session:other' }),
      lease_store: leaseStore,
      generation: lease.generation,
      fencing_token: lease.fencing_token,
      now_ms: 2_000,
      expected_store_root: prepared.store_root,
      media_type: 'text/plain',
      text: 'wrong session',
    })).toThrowError(/PROVIDER_CLAIM_OWNER_MISMATCH/);
  });

  test('rejects empty, oversized, and unsupported evidence before persistence', () => {
    const { leaseStore, contributionStore, g, lease } = setup();
    const root = contributionStore.stateRoot();
    const base = {
      graph: g,
      work_node_id: 'node-001',
      session: session(),
      lease_store: leaseStore,
      generation: lease.generation,
      fencing_token: lease.fencing_token,
      now_ms: 2_000,
      expected_store_root: root,
    };

    expect(() => contributionStore.recordTextContribution({ ...base, media_type: 'text/plain', text: '' }))
      .toThrowError('PROVIDER_CONTRIBUTION_TEXT_EMPTY');
    expect(() => contributionStore.recordTextContribution({
      ...base,
      media_type: 'text/plain',
      text: 'x'.repeat(MAX_PROVIDER_CONTRIBUTION_BYTES + 1),
    })).toThrowError('PROVIDER_CONTRIBUTION_TEXT_TOO_LARGE');
    expect(() => contributionStore.recordTextContribution({
      ...base,
      media_type: 'text/html' as never,
      text: '<b>no</b>',
    })).toThrowError('PROVIDER_CONTRIBUTION_MEDIA_TYPE_INVALID');
    expect(contributionStore.stateRoot()).toBe(root);
  });

  test('detects persisted artifact tamper on restart', () => {
    const { leaseStore, contributionStore, contributionPath, g, lease } = setup();
    const prepared = contributionStore.prepareContribution();
    const record = contributionStore.recordTextContribution({
      graph: g,
      work_node_id: 'node-001',
      session: session(),
      lease_store: leaseStore,
      generation: lease.generation,
      fencing_token: lease.fencing_token,
      now_ms: 2_000,
      expected_store_root: prepared.store_root,
      media_type: 'application/json',
      text: '{"claim":"evidence"}',
    });

    const raw = JSON.parse(readFileSync(contributionPath, 'utf8')) as Record<string, any>;
    raw.artifacts[record.artifact_sha256].text = '{"claim":"tampered"}';
    writeFileSync(contributionPath, JSON.stringify(raw, null, 2), 'utf8');
    expect(() => new FileProviderContributionStoreV1(contributionPath))
      .toThrowError('PROVIDER_CONTRIBUTION_ARTIFACT_DIGEST_MISMATCH');
  });

  test('exact graph target/prestate changes cannot reuse the contribution lease binding', () => {
    const { leaseStore, contributionStore, g, lease } = setup();
    const changed = { ...g, nodes: [node({ target_commitment: B })] };
    expect(() => contributionStore.recordTextContribution({
      graph: changed,
      work_node_id: 'node-001',
      session: session(),
      lease_store: leaseStore,
      generation: lease.generation,
      fencing_token: lease.fencing_token,
      now_ms: 2_000,
      expected_store_root: contributionStore.stateRoot(),
      media_type: 'text/plain',
      text: 'wrong target',
    })).toThrowError('PROVIDER_CLAIM_BINDING_MISMATCH');
  });
});
