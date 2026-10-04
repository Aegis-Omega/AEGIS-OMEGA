import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, test } from 'vitest';

import type { CollectiveWorkGraphV1, CollectiveWorkNodeV1 } from '../../src/collective/contracts';
import { FileProviderClaimLeaseStoreV1 } from '../../src/collective/provider-claim-lease';
import {
  FileProviderContributionStoreV1,
  type ProviderSessionIdentityV1,
  validateProviderSessionIdentity,
} from '../../src/collective/provider-contribution';

const H = 'a'.repeat(64);
const B = 'b'.repeat(64);
const HEAD = 'c'.repeat(40);
const roots: string[] = [];

interface MutationCase {
  id: string;
  mutation: string;
  expected_error: string;
}

interface SessionCase {
  id: string;
  patch: Record<string, unknown>;
  expected_error: string;
}

interface Corpus {
  schema_version: '1.0.0';
  corpus_kind: 'UCI3_PROVIDER_CONTRIBUTION_VECTORS_V1';
  invalid_sessions: SessionCase[];
  invalid_contribution_inputs: MutationCase[];
  persisted_tamper: MutationCase[];
}

const corpusPath = path.resolve(
  process.cwd(),
  '..',
  'test-vectors',
  'collective-intelligence',
  'uci-3-provider-contribution-v1.json',
);

const corpus = (): Corpus => JSON.parse(readFileSync(corpusPath, 'utf8')) as Corpus;

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

const session = (overrides: Record<string, unknown> = {}): ProviderSessionIdentityV1 => ({
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
} as ProviderSessionIdentityV1);

const setup = () => {
  const root = mkdtempSync(path.join(tmpdir(), 'aegis-uci3-vector-'));
  roots.push(root);
  const leaseStore = new FileProviderClaimLeaseStoreV1(path.join(root, 'leases.json'));
  const contributionPath = path.join(root, 'contributions.json');
  const contributionStore = new FileProviderContributionStoreV1(contributionPath);
  const g = graph();
  const preparedLease = leaseStore.prepareClaim(g, 'node-001');
  const lease = leaseStore.claimWork({
    graph: g,
    work_node_id: 'node-001',
    owner_identity: 'provider:openai:session:s1',
    expected_store_root: preparedLease.store_root,
    lease_ms: 10_000,
    now_ms: 1_000,
  });
  return { root, leaseStore, contributionPath, contributionStore, g, lease };
};

afterEach(() => {
  while (roots.length > 0) rmSync(roots.pop()!, { recursive: true, force: true });
});

describe('UCI-3 canonical falsification vectors', () => {
  test('corpus is versioned and non-empty', () => {
    const vectors = corpus();
    expect(vectors.schema_version).toBe('1.0.0');
    expect(vectors.corpus_kind).toBe('UCI3_PROVIDER_CONTRIBUTION_VECTORS_V1');
    expect(vectors.invalid_sessions.length).toBeGreaterThan(0);
    expect(vectors.invalid_contribution_inputs.length).toBeGreaterThan(0);
    expect(vectors.persisted_tamper.length).toBeGreaterThan(0);
  });

  test('session falsifiers never gain provider authority', () => {
    const vectors = corpus();
    for (const vector of vectors.invalid_sessions) {
      expect(
        () => validateProviderSessionIdentity(session(vector.patch), graph(), 'node-001'),
        vector.id,
      ).toThrowError(vector.expected_error);
    }
  });

  test('lease/prestate/work/session falsifiers fail before contribution authority can emerge', () => {
    for (const vector of corpus().invalid_contribution_inputs) {
      const fixture = setup();
      let workNodeId = 'node-001';
      let providerSession = session();
      let generation = fixture.lease.generation;
      let fence = fixture.lease.fencing_token;
      let expectedRoot = fixture.contributionStore.stateRoot();
      let currentGraph = fixture.g;

      if (vector.mutation === 'stale_generation') generation += 1;
      else if (vector.mutation === 'wrong_fence') fence = B;
      else if (vector.mutation === 'wrong_work_node') workNodeId = 'missing-node';
      else if (vector.mutation === 'wrong_session') providerSession = session({ session_id: 'session:other' });
      else if (vector.mutation === 'wrong_target') currentGraph = { ...fixture.g, nodes: [node({ target_commitment: B })] };
      else if (vector.mutation === 'stale_store_root') {
        const stale = expectedRoot;
        fixture.contributionStore.recordTextContribution({
          graph: fixture.g,
          work_node_id: 'node-001',
          session: session(),
          lease_store: fixture.leaseStore,
          generation: fixture.lease.generation,
          fencing_token: fixture.lease.fencing_token,
          now_ms: 2_000,
          expected_store_root: stale,
          media_type: 'text/plain',
          text: 'baseline',
        });
        expectedRoot = stale;
      } else {
        throw new Error(`unknown contribution mutation: ${vector.mutation}`);
      }

      expect(() => fixture.contributionStore.recordTextContribution({
        graph: currentGraph,
        work_node_id: workNodeId,
        session: providerSession,
        lease_store: fixture.leaseStore,
        generation,
        fencing_token: fence,
        now_ms: 2_100,
        expected_store_root: expectedRoot,
        media_type: 'text/plain',
        text: 'candidate evidence',
      }), vector.id).toThrowError(new RegExp(vector.expected_error));
    }
  });

  test('persisted evidence tamper is detected on restart', () => {
    for (const vector of corpus().persisted_tamper) {
      const fixture = setup();
      const prepared = fixture.contributionStore.prepareContribution();
      const record = fixture.contributionStore.recordTextContribution({
        graph: fixture.g,
        work_node_id: 'node-001',
        session: session(),
        lease_store: fixture.leaseStore,
        generation: fixture.lease.generation,
        fencing_token: fixture.lease.fencing_token,
        now_ms: 2_000,
        expected_store_root: prepared.store_root,
        media_type: 'application/json',
        text: '{"claim":"evidence"}',
      });
      const state = JSON.parse(readFileSync(fixture.contributionPath, 'utf8')) as Record<string, any>;

      if (vector.mutation === 'artifact_text') {
        state.artifacts[record.artifact_sha256].text = '{"claim":"tampered"}';
      } else if (vector.mutation === 'artifact_authority') {
        state.artifacts[record.artifact_sha256].authority = 'PERMIT';
      } else if (vector.mutation === 'record_authority') {
        state.records[record.record_hash].authority = 'PERMIT';
      } else if (vector.mutation === 'record_effect_receipt') {
        state.records[record.record_hash].effect_receipt = { outcome: 'VERIFIED' };
      } else if (vector.mutation === 'record_policy') {
        state.records[record.record_hash].policy_commitment = B;
      } else {
        throw new Error(`unknown persisted mutation: ${vector.mutation}`);
      }

      writeFileSync(fixture.contributionPath, JSON.stringify(state, null, 2), 'utf8');
      expect(() => new FileProviderContributionStoreV1(fixture.contributionPath), vector.id)
        .toThrowError(new RegExp(vector.expected_error));
    }
  });
});
