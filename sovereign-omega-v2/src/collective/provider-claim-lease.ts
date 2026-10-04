import { createHash } from 'node:crypto';
import {
  mkdirSync,
  readFileSync,
  renameSync,
  rmdirSync,
  unlinkSync,
  writeFileSync,
} from 'node:fs';
import { dirname } from 'node:path';

import { canonicalizeJCS } from '../core/canonicalize';
import type { CollectiveWorkGraphV1, CollectiveWorkNodeV1 } from './contracts';
import { validateCollectiveWorkGraph } from './validate';

export const PROVIDER_CLAIM_STORE_KIND = 'UCI_PROVIDER_CLAIM_STORE_V1' as const;
export const PROVIDER_CLAIM_KIND = 'DURABLE_PROVIDER_CLAIM_LEASE_V1' as const;
export const PROVIDER_CLAIM_AUTHORITY = 'SCHEDULING_LEASE_ONLY' as const;
export const PROVIDER_CLAIM_STORE_DOMAIN = 'AEGIS_UCI_PROVIDER_CLAIM_STORE_V1' as const;
export const MAX_PROVIDER_CLAIM_LEASE_MS = 900_000;

const HASH_RE = /^[0-9a-f]{64}$/;
const IDENTITY_RE = /^[A-Za-z0-9._:/@+\-]{1,128}$/;

export class ProviderClaimLeaseError extends Error {
  constructor(code: string) {
    super(code);
    this.name = 'ProviderClaimLeaseError';
  }
}

export interface DurableProviderClaimLeaseV1 {
  schema_version: '1.0.0';
  claim_kind: typeof PROVIDER_CLAIM_KIND;
  graph_id: string;
  work_node_id: string;
  owner_identity: string;
  generation: number;
  fencing_token: string;
  issued_ms: number;
  expires_ms: number;
  intent_digest: string;
  policy_commitment: string;
  authority_epoch: number;
  target_commitment: string;
  pre_state_commitment: string;
  authority: typeof PROVIDER_CLAIM_AUTHORITY;
}

interface ProviderClaimStoreStateV1 {
  schema_version: '1.0.0';
  store_kind: typeof PROVIDER_CLAIM_STORE_KIND;
  generations: Record<string, number>;
  claims: Record<string, DurableProviderClaimLeaseV1>;
}

export interface PreparedProviderClaimV1 {
  work_node_id: string;
  store_root: string;
  next_generation: number;
}

export interface ClaimWorkInputV1 {
  graph: CollectiveWorkGraphV1;
  work_node_id: string;
  owner_identity: string;
  expected_store_root: string;
  lease_ms: number;
  now_ms: number;
}

export interface CurrentLeaseInputV1 {
  graph: CollectiveWorkGraphV1;
  work_node_id: string;
  owner_identity: string;
  generation: number;
  fencing_token: string;
  now_ms: number;
}

const STORE_KEYS = new Set(['schema_version', 'store_kind', 'generations', 'claims']);
const LEASE_KEYS = new Set([
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
]);

function fail(code: string): never {
  throw new ProviderClaimLeaseError(code);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function exactKeys(value: Record<string, unknown>, allowed: ReadonlySet<string>, code: string): void {
  const keys = Object.keys(value);
  if (keys.length !== allowed.size || keys.some((key) => !allowed.has(key))) fail(code);
}

function nonnegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

function positiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0;
}

function validHash(value: unknown): value is string {
  return typeof value === 'string' && HASH_RE.test(value);
}

function validIdentity(value: unknown): value is string {
  return typeof value === 'string' && IDENTITY_RE.test(value);
}

function fenceToken(workNodeId: string, ownerIdentity: string, generation: number): string {
  if (!workNodeId || !validIdentity(ownerIdentity) || !positiveInteger(generation)) {
    fail('PROVIDER_CLAIM_FENCE_INPUT_INVALID');
  }
  return createHash('sha256')
    .update(`${workNodeId}\0${ownerIdentity}\0${generation}`, 'utf8')
    .digest('hex');
}

function stateRoot(state: ProviderClaimStoreStateV1): string {
  return createHash('sha256')
    .update(canonicalizeJCS({ domain: PROVIDER_CLAIM_STORE_DOMAIN, state }))
    .digest('hex');
}

function initialState(): ProviderClaimStoreStateV1 {
  return {
    schema_version: '1.0.0',
    store_kind: PROVIDER_CLAIM_STORE_KIND,
    generations: {},
    claims: {},
  };
}

function validateLease(value: unknown, expectedWorkNodeId?: string): DurableProviderClaimLeaseV1 {
  if (!isRecord(value)) fail('PROVIDER_CLAIM_STORE_INVALID_LEASE');
  exactKeys(value, LEASE_KEYS, 'PROVIDER_CLAIM_STORE_INVALID_LEASE_FIELDS');
  if (value.schema_version !== '1.0.0' || value.claim_kind !== PROVIDER_CLAIM_KIND) {
    fail('PROVIDER_CLAIM_STORE_INVALID_LEASE_KIND');
  }
  if (typeof value.graph_id !== 'string' || value.graph_id.length === 0) fail('PROVIDER_CLAIM_STORE_INVALID_GRAPH_ID');
  if (typeof value.work_node_id !== 'string' || value.work_node_id.length === 0) fail('PROVIDER_CLAIM_STORE_INVALID_WORK_NODE_ID');
  if (expectedWorkNodeId !== undefined && value.work_node_id !== expectedWorkNodeId) fail('PROVIDER_CLAIM_STORE_KEY_MISMATCH');
  if (!validIdentity(value.owner_identity)) fail('PROVIDER_CLAIM_STORE_INVALID_OWNER');
  if (!positiveInteger(value.generation)) fail('PROVIDER_CLAIM_STORE_INVALID_GENERATION');
  if (!validHash(value.fencing_token)) fail('PROVIDER_CLAIM_STORE_INVALID_FENCE');
  if (!nonnegativeInteger(value.issued_ms) || !nonnegativeInteger(value.expires_ms) || value.expires_ms < value.issued_ms) {
    fail('PROVIDER_CLAIM_STORE_INVALID_TIME');
  }
  if (!validHash(value.intent_digest) || !validHash(value.policy_commitment) ||
      !validHash(value.target_commitment) || !validHash(value.pre_state_commitment)) {
    fail('PROVIDER_CLAIM_STORE_INVALID_BINDING');
  }
  if (!nonnegativeInteger(value.authority_epoch)) fail('PROVIDER_CLAIM_STORE_INVALID_AUTHORITY_EPOCH');
  if (value.authority !== PROVIDER_CLAIM_AUTHORITY) fail('PROVIDER_CLAIM_STORE_INVALID_AUTHORITY_MARKER');

  const lease = value as unknown as DurableProviderClaimLeaseV1;
  if (lease.fencing_token !== fenceToken(lease.work_node_id, lease.owner_identity, lease.generation)) {
    fail('PROVIDER_CLAIM_STORE_FENCE_TAMPERED');
  }
  return lease;
}

function validateState(value: unknown): ProviderClaimStoreStateV1 {
  if (!isRecord(value)) fail('PROVIDER_CLAIM_STORE_INVALID');
  exactKeys(value, STORE_KEYS, 'PROVIDER_CLAIM_STORE_UNKNOWN_FIELD');
  if (value.schema_version !== '1.0.0' || value.store_kind !== PROVIDER_CLAIM_STORE_KIND) {
    fail('PROVIDER_CLAIM_STORE_KIND_MISMATCH');
  }
  if (!isRecord(value.generations) || !isRecord(value.claims)) fail('PROVIDER_CLAIM_STORE_INVALID_MAPS');

  const generations: Record<string, number> = {};
  for (const [workNodeId, generation] of Object.entries(value.generations)) {
    if (!workNodeId || !nonnegativeInteger(generation)) fail('PROVIDER_CLAIM_STORE_INVALID_GENERATION_HISTORY');
    generations[workNodeId] = generation;
  }

  const claims: Record<string, DurableProviderClaimLeaseV1> = {};
  for (const [workNodeId, rawLease] of Object.entries(value.claims)) {
    const lease = validateLease(rawLease, workNodeId);
    if ((generations[workNodeId] ?? 0) < lease.generation) fail('PROVIDER_CLAIM_STORE_GENERATION_REGRESSION');
    claims[workNodeId] = lease;
  }

  return {
    schema_version: '1.0.0',
    store_kind: PROVIDER_CLAIM_STORE_KIND,
    generations,
    claims,
  };
}

function validateNow(nowMs: number): void {
  if (!nonnegativeInteger(nowMs)) fail('PROVIDER_CLAIM_TIME_INVALID');
}

function graphAndNode(graph: CollectiveWorkGraphV1, workNodeId: string): {
  graph: CollectiveWorkGraphV1;
  node: CollectiveWorkNodeV1;
} {
  const result = validateCollectiveWorkGraph(graph);
  if (!result.ok) fail(`PROVIDER_CLAIM_GRAPH_INVALID:${result.errors.join('|')}`);
  const node = result.value.nodes.find((candidate) => candidate.work_node_id === workNodeId);
  if (!node) fail('PROVIDER_CLAIM_WORK_NODE_MISSING');
  return { graph: result.value, node };
}

function assertLeaseBinding(
  lease: DurableProviderClaimLeaseV1,
  graph: CollectiveWorkGraphV1,
  node: CollectiveWorkNodeV1,
): void {
  if (
    lease.graph_id !== graph.graph_id ||
    lease.work_node_id !== node.work_node_id ||
    lease.intent_digest !== graph.intent_digest ||
    lease.policy_commitment !== graph.policy_commitment ||
    lease.authority_epoch !== graph.authority_epoch ||
    lease.target_commitment !== node.target_commitment ||
    lease.pre_state_commitment !== node.pre_state_commitment
  ) {
    fail('PROVIDER_CLAIM_BINDING_MISMATCH');
  }
}

function active(lease: DurableProviderClaimLeaseV1, nowMs: number): boolean {
  return nowMs <= lease.expires_ms;
}

export class FileProviderClaimLeaseStoreV1 {
  readonly path: string;
  readonly lockPath: string;

  constructor(path: string) {
    if (!path) fail('PROVIDER_CLAIM_STORE_PATH_REQUIRED');
    this.path = path;
    this.lockPath = `${path}.lock`;
    mkdirSync(dirname(path), { recursive: true });
    try {
      writeFileSync(path, JSON.stringify(initialState(), null, 2), { encoding: 'utf8', flag: 'wx' });
    } catch (error) {
      if (!isRecord(error) || error.code !== 'EEXIST') throw error;
    }
    this.load();
  }

  private load(): ProviderClaimStoreStateV1 {
    try {
      return validateState(JSON.parse(readFileSync(this.path, 'utf8')));
    } catch (error) {
      if (error instanceof ProviderClaimLeaseError) throw error;
      throw new ProviderClaimLeaseError('PROVIDER_CLAIM_STORE_INVALID');
    }
  }

  private persist(state: ProviderClaimStoreStateV1): void {
    const temporary = `${this.path}.tmp`;
    try {
      writeFileSync(temporary, JSON.stringify(state, null, 2), 'utf8');
      renameSync(temporary, this.path);
    } finally {
      try { unlinkSync(temporary); } catch { /* already renamed or absent */ }
    }
  }

  private exclusive<T>(operation: () => T): T {
    try {
      mkdirSync(this.lockPath);
    } catch (error) {
      if (isRecord(error) && error.code === 'EEXIST') fail('PROVIDER_CLAIM_STORE_LOCKED');
      throw error;
    }
    try {
      return operation();
    } finally {
      try { rmdirSync(this.lockPath); } catch { /* fail-closed state remains inspectable */ }
    }
  }

  private currentLease(input: CurrentLeaseInputV1): DurableProviderClaimLeaseV1 {
    const { graph, node } = graphAndNode(input.graph, input.work_node_id);
    validateNow(input.now_ms);
    if (!positiveInteger(input.generation)) fail('PROVIDER_CLAIM_GENERATION_INVALID');
    if (!validHash(input.fencing_token)) fail('PROVIDER_CLAIM_FENCE_INVALID');
    const state = this.load();
    const current = state.claims[input.work_node_id];
    if (!current) fail('PROVIDER_CLAIM_MISSING');
    if (!active(current, input.now_ms)) fail('PROVIDER_CLAIM_EXPIRED');
    if (current.owner_identity !== input.owner_identity) fail('PROVIDER_CLAIM_OWNER_MISMATCH');
    if (current.generation !== input.generation) fail('PROVIDER_CLAIM_GENERATION_MISMATCH');
    if (current.fencing_token !== input.fencing_token) fail('PROVIDER_CLAIM_FENCE_MISMATCH');
    assertLeaseBinding(current, graph, node);
    return current;
  }

  prepareClaim(graph: CollectiveWorkGraphV1, workNodeId: string): PreparedProviderClaimV1 {
    graphAndNode(graph, workNodeId);
    const state = this.load();
    return {
      work_node_id: workNodeId,
      store_root: stateRoot(state),
      next_generation: (state.generations[workNodeId] ?? 0) + 1,
    };
  }

  claimWork(input: ClaimWorkInputV1): DurableProviderClaimLeaseV1 {
    const { graph, node } = graphAndNode(input.graph, input.work_node_id);
    if (!validIdentity(input.owner_identity)) fail('PROVIDER_CLAIM_OWNER_INVALID');
    if (!validHash(input.expected_store_root)) fail('PROVIDER_CLAIM_PRESTATE_INVALID');
    if (!positiveInteger(input.lease_ms) || input.lease_ms > MAX_PROVIDER_CLAIM_LEASE_MS) {
      fail('PROVIDER_CLAIM_LEASE_INVALID');
    }
    validateNow(input.now_ms);
    if (!['D0', 'D1', 'D2'].includes(node.consequence_class)) {
      fail('PROVIDER_CLAIM_CONSEQUENCE_NOT_CLAIMABLE');
    }

    return this.exclusive(() => {
      const state = this.load();
      if (stateRoot(state) !== input.expected_store_root) fail('PROVIDER_CLAIM_PRESTATE_STALE');
      const current = state.claims[input.work_node_id];
      if (current && active(current, input.now_ms)) {
        assertLeaseBinding(current, graph, node);
        if (current.owner_identity === input.owner_identity) return current;
        fail('PROVIDER_CLAIM_ACTIVE');
      }

      const generation = (state.generations[input.work_node_id] ?? 0) + 1;
      const lease: DurableProviderClaimLeaseV1 = {
        schema_version: '1.0.0',
        claim_kind: PROVIDER_CLAIM_KIND,
        graph_id: graph.graph_id,
        work_node_id: node.work_node_id,
        owner_identity: input.owner_identity,
        generation,
        fencing_token: fenceToken(node.work_node_id, input.owner_identity, generation),
        issued_ms: input.now_ms,
        expires_ms: input.now_ms + input.lease_ms,
        intent_digest: graph.intent_digest,
        policy_commitment: graph.policy_commitment,
        authority_epoch: graph.authority_epoch,
        target_commitment: node.target_commitment,
        pre_state_commitment: node.pre_state_commitment,
        authority: PROVIDER_CLAIM_AUTHORITY,
      };
      state.generations[input.work_node_id] = generation;
      state.claims[input.work_node_id] = lease;
      this.persist(state);
      return lease;
    });
  }

  assertCurrentLease(input: CurrentLeaseInputV1): DurableProviderClaimLeaseV1 {
    return this.currentLease(input);
  }

  withCurrentLease<T>(
    input: CurrentLeaseInputV1,
    operation: (lease: DurableProviderClaimLeaseV1) => T,
  ): T {
    return this.exclusive(() => operation(this.currentLease(input)));
  }

  releaseClaim(input: CurrentLeaseInputV1): true {
    return this.exclusive(() => {
      const { graph, node } = graphAndNode(input.graph, input.work_node_id);
      validateNow(input.now_ms);
      const state = this.load();
      const current = state.claims[input.work_node_id];
      if (!current) fail('PROVIDER_CLAIM_MISSING');
      if (!active(current, input.now_ms)) fail('PROVIDER_CLAIM_EXPIRED');
      if (current.owner_identity !== input.owner_identity) fail('PROVIDER_CLAIM_OWNER_MISMATCH');
      if (current.generation !== input.generation) fail('PROVIDER_CLAIM_GENERATION_MISMATCH');
      if (current.fencing_token !== input.fencing_token) fail('PROVIDER_CLAIM_FENCE_MISMATCH');
      assertLeaseBinding(current, graph, node);
      delete state.claims[input.work_node_id];
      this.persist(state);
      return true;
    });
  }
}
