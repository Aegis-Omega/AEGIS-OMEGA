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
import { FileProviderClaimLeaseStoreV1 } from './provider-claim-lease';
import { validateCollectiveWorkGraph } from './validate';

export const PROVIDER_SESSION_KIND = 'PROVIDER_SESSION_IDENTITY_V1' as const;
export const PROVIDER_SESSION_AUTHORITY = 'IDENTITY_ONLY_NOT_AUTHORIZATION' as const;
export const PROVIDER_CONTRIBUTION_AUTHORITY = 'NON_AUTHORITATIVE_EVIDENCE' as const;
export const PROVIDER_CONTRIBUTION_ARTIFACT_KIND = 'PROVIDER_CONTRIBUTION_ARTIFACT_V1' as const;
export const PROVIDER_CONTRIBUTION_RECORD_KIND = 'PROVIDER_CONTRIBUTION_RECORD_V1' as const;
export const PROVIDER_CONTRIBUTION_STORE_KIND = 'UCI_PROVIDER_CONTRIBUTION_STORE_V1' as const;
export const PROVIDER_CONTRIBUTION_STORE_DOMAIN = 'AEGIS_UCI_PROVIDER_CONTRIBUTION_STORE_V1' as const;
export const PROVIDER_CONTRIBUTION_RECORD_DOMAIN = 'AEGIS_UCI_PROVIDER_CONTRIBUTION_RECORD_V1' as const;
export const MAX_PROVIDER_CONTRIBUTION_BYTES = 262_144;

export type ProviderContributionMediaType = 'text/plain' | 'text/markdown' | 'application/json';

const HASH_RE = /^[0-9a-f]{64}$/;
const GIT_OBJECT_RE = /^[0-9a-f]{40,64}$/;
const IDENTITY_RE = /^[A-Za-z0-9._:/@+\-]{1,128}$/;
const REPOSITORY_RE = /^[A-Za-z0-9._-]{1,100}\/[A-Za-z0-9._-]{1,100}$/;
const ALLOWED_MEDIA_TYPES = new Set<ProviderContributionMediaType>([
  'text/plain',
  'text/markdown',
  'application/json',
]);

const SESSION_KEYS = new Set([
  'schema_version',
  'session_kind',
  'provider',
  'model',
  'session_id',
  'repository',
  'head_sha',
  'capability_ids',
  'policy_commitment',
  'authority_epoch',
  'skill_catalog_root',
  'organism_state_root',
  'authority',
]);
const ARTIFACT_KEYS = new Set([
  'schema_version',
  'artifact_kind',
  'sha256',
  'media_type',
  'byte_length',
  'text',
  'authority',
]);
const RECORD_KEYS = new Set([
  'schema_version',
  'record_kind',
  'record_hash',
  'graph_id',
  'work_node_id',
  'provider',
  'model',
  'session_id',
  'session_head_sha',
  'lease_owner_identity',
  'lease_generation',
  'fencing_token',
  'artifact_sha256',
  'contribution_store_prestate_root',
  'intent_digest',
  'policy_commitment',
  'authority_epoch',
  'target_commitment',
  'pre_state_commitment',
  'authority',
]);
const STORE_KEYS = new Set(['schema_version', 'store_kind', 'artifacts', 'records']);

export class ProviderContributionError extends Error {
  constructor(code: string) {
    super(code);
    this.name = 'ProviderContributionError';
  }
}

export interface ProviderSessionIdentityV1 {
  schema_version: '1.0.0';
  session_kind: typeof PROVIDER_SESSION_KIND;
  provider: string;
  model: string;
  session_id: string;
  repository: string;
  head_sha: string;
  capability_ids: string[];
  policy_commitment: string;
  authority_epoch: number;
  skill_catalog_root: string;
  organism_state_root: string;
  authority: typeof PROVIDER_SESSION_AUTHORITY;
}

export interface ProviderContributionArtifactV1 {
  schema_version: '1.0.0';
  artifact_kind: typeof PROVIDER_CONTRIBUTION_ARTIFACT_KIND;
  sha256: string;
  media_type: ProviderContributionMediaType;
  byte_length: number;
  text: string;
  authority: typeof PROVIDER_CONTRIBUTION_AUTHORITY;
}

export interface ProviderContributionRecordV1 {
  schema_version: '1.0.0';
  record_kind: typeof PROVIDER_CONTRIBUTION_RECORD_KIND;
  record_hash: string;
  graph_id: string;
  work_node_id: string;
  provider: string;
  model: string;
  session_id: string;
  session_head_sha: string;
  lease_owner_identity: string;
  lease_generation: number;
  fencing_token: string;
  artifact_sha256: string;
  contribution_store_prestate_root: string;
  intent_digest: string;
  policy_commitment: string;
  authority_epoch: number;
  target_commitment: string;
  pre_state_commitment: string;
  authority: typeof PROVIDER_CONTRIBUTION_AUTHORITY;
}

interface ProviderContributionStoreStateV1 {
  schema_version: '1.0.0';
  store_kind: typeof PROVIDER_CONTRIBUTION_STORE_KIND;
  artifacts: Record<string, ProviderContributionArtifactV1>;
  records: Record<string, ProviderContributionRecordV1>;
}

export interface PreparedProviderContributionV1 {
  store_root: string;
}

export interface RecordTextContributionInputV1 {
  graph: CollectiveWorkGraphV1;
  work_node_id: string;
  session: ProviderSessionIdentityV1;
  lease_store: FileProviderClaimLeaseStoreV1;
  generation: number;
  fencing_token: string;
  now_ms: number;
  expected_store_root: string;
  media_type: ProviderContributionMediaType;
  text: string;
}

type UnsignedContributionRecordV1 = Omit<ProviderContributionRecordV1, 'record_hash'>;

function fail(code: string): never {
  throw new ProviderContributionError(code);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function exactKeys(value: Record<string, unknown>, allowed: ReadonlySet<string>, code: string): void {
  const keys = Object.keys(value);
  if (keys.length !== allowed.size || keys.some((key) => !allowed.has(key))) fail(code);
}

function validIdentity(value: unknown): value is string {
  return typeof value === 'string' && IDENTITY_RE.test(value);
}

function validHash(value: unknown): value is string {
  return typeof value === 'string' && HASH_RE.test(value);
}

function nonnegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

function positiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0;
}

function validateCapabilities(value: unknown): string[] {
  if (!Array.isArray(value) || value.some((item) => !validIdentity(item))) {
    fail('PROVIDER_SESSION_CAPABILITIES_INVALID');
  }
  const capabilities = value as string[];
  if (new Set(capabilities).size !== capabilities.length) {
    fail('PROVIDER_SESSION_CAPABILITIES_NOT_UNIQUE');
  }
  const sorted = [...capabilities].sort();
  if (capabilities.some((item, index) => item !== sorted[index])) {
    fail('PROVIDER_SESSION_CAPABILITIES_NOT_SORTED');
  }
  return [...capabilities];
}

function graphAndNode(graph: CollectiveWorkGraphV1, workNodeId: string): {
  graph: CollectiveWorkGraphV1;
  node: CollectiveWorkNodeV1;
} {
  const result = validateCollectiveWorkGraph(graph);
  if (!result.ok) fail(`PROVIDER_SESSION_GRAPH_INVALID:${result.errors.join('|')}`);
  const node = result.value.nodes.find((candidate) => candidate.work_node_id === workNodeId);
  if (!node) fail('PROVIDER_SESSION_WORK_NODE_MISSING');
  return { graph: result.value, node };
}

export function validateProviderSessionIdentity(
  value: unknown,
  graph: CollectiveWorkGraphV1,
  workNodeId: string,
): ProviderSessionIdentityV1 {
  const admitted = graphAndNode(graph, workNodeId);
  if (!isRecord(value)) fail('PROVIDER_SESSION_INVALID');
  exactKeys(value, SESSION_KEYS, 'PROVIDER_SESSION_UNKNOWN_FIELD');

  if (value.schema_version !== '1.0.0' || value.session_kind !== PROVIDER_SESSION_KIND) {
    fail('PROVIDER_SESSION_KIND_INVALID');
  }
  if (!validIdentity(value.provider)) fail('PROVIDER_SESSION_PROVIDER_INVALID');
  if (!validIdentity(value.model)) fail('PROVIDER_SESSION_MODEL_INVALID');
  if (!validIdentity(value.session_id)) fail('PROVIDER_SESSION_ID_INVALID');
  if (typeof value.repository !== 'string' || !REPOSITORY_RE.test(value.repository)) {
    fail('PROVIDER_SESSION_REPOSITORY_INVALID');
  }
  if (typeof value.head_sha !== 'string' || !GIT_OBJECT_RE.test(value.head_sha)) {
    fail('PROVIDER_SESSION_HEAD_INVALID');
  }
  const capabilityIds = validateCapabilities(value.capability_ids);
  if (!validHash(value.policy_commitment)) fail('PROVIDER_SESSION_POLICY_INVALID');
  if (!nonnegativeInteger(value.authority_epoch)) fail('PROVIDER_SESSION_AUTHORITY_EPOCH_INVALID');
  if (!validHash(value.skill_catalog_root)) fail('PROVIDER_SESSION_SKILL_ROOT_INVALID');
  if (!validHash(value.organism_state_root)) fail('PROVIDER_SESSION_ORGANISM_ROOT_INVALID');
  if (value.authority !== PROVIDER_SESSION_AUTHORITY) fail('PROVIDER_SESSION_AUTHORITY_INVALID');

  if (!admitted.node.allowed_providers.includes(value.provider)) fail('PROVIDER_SESSION_PROVIDER_NOT_ALLOWED');
  if (value.policy_commitment !== admitted.graph.policy_commitment || value.policy_commitment !== admitted.node.policy_commitment) {
    fail('PROVIDER_SESSION_POLICY_MISMATCH');
  }
  if (value.authority_epoch !== admitted.graph.authority_epoch || value.authority_epoch !== admitted.node.authority_epoch) {
    fail('PROVIDER_SESSION_AUTHORITY_EPOCH_MISMATCH');
  }

  return {
    schema_version: '1.0.0',
    session_kind: PROVIDER_SESSION_KIND,
    provider: value.provider,
    model: value.model,
    session_id: value.session_id,
    repository: value.repository,
    head_sha: value.head_sha,
    capability_ids: capabilityIds,
    policy_commitment: value.policy_commitment,
    authority_epoch: value.authority_epoch,
    skill_catalog_root: value.skill_catalog_root,
    organism_state_root: value.organism_state_root,
    authority: PROVIDER_SESSION_AUTHORITY,
  };
}

function artifactDigest(text: string): string {
  return createHash('sha256').update(Buffer.from(text, 'utf8')).digest('hex');
}

function buildArtifact(text: string, mediaType: ProviderContributionMediaType): ProviderContributionArtifactV1 {
  const bytes = Buffer.byteLength(text, 'utf8');
  if (bytes === 0) fail('PROVIDER_CONTRIBUTION_TEXT_EMPTY');
  if (bytes > MAX_PROVIDER_CONTRIBUTION_BYTES) fail('PROVIDER_CONTRIBUTION_TEXT_TOO_LARGE');
  if (!ALLOWED_MEDIA_TYPES.has(mediaType)) fail('PROVIDER_CONTRIBUTION_MEDIA_TYPE_INVALID');
  return {
    schema_version: '1.0.0',
    artifact_kind: PROVIDER_CONTRIBUTION_ARTIFACT_KIND,
    sha256: artifactDigest(text),
    media_type: mediaType,
    byte_length: bytes,
    text,
    authority: PROVIDER_CONTRIBUTION_AUTHORITY,
  };
}

function validateArtifact(value: unknown, expectedDigest?: string): ProviderContributionArtifactV1 {
  if (!isRecord(value)) fail('PROVIDER_CONTRIBUTION_ARTIFACT_INVALID');
  exactKeys(value, ARTIFACT_KEYS, 'PROVIDER_CONTRIBUTION_ARTIFACT_UNKNOWN_FIELD');
  if (value.schema_version !== '1.0.0' || value.artifact_kind !== PROVIDER_CONTRIBUTION_ARTIFACT_KIND) {
    fail('PROVIDER_CONTRIBUTION_ARTIFACT_KIND_INVALID');
  }
  if (!validHash(value.sha256)) fail('PROVIDER_CONTRIBUTION_ARTIFACT_HASH_INVALID');
  if (expectedDigest !== undefined && value.sha256 !== expectedDigest) fail('PROVIDER_CONTRIBUTION_ARTIFACT_KEY_MISMATCH');
  if (typeof value.media_type !== 'string' || !ALLOWED_MEDIA_TYPES.has(value.media_type as ProviderContributionMediaType)) {
    fail('PROVIDER_CONTRIBUTION_MEDIA_TYPE_INVALID');
  }
  if (!nonnegativeInteger(value.byte_length)) fail('PROVIDER_CONTRIBUTION_ARTIFACT_LENGTH_INVALID');
  if (typeof value.text !== 'string') fail('PROVIDER_CONTRIBUTION_ARTIFACT_TEXT_INVALID');
  const bytes = Buffer.byteLength(value.text, 'utf8');
  if (bytes === 0 || bytes > MAX_PROVIDER_CONTRIBUTION_BYTES || bytes !== value.byte_length) {
    fail('PROVIDER_CONTRIBUTION_ARTIFACT_LENGTH_INVALID');
  }
  if (artifactDigest(value.text) !== value.sha256) fail('PROVIDER_CONTRIBUTION_ARTIFACT_DIGEST_MISMATCH');
  if (value.authority !== PROVIDER_CONTRIBUTION_AUTHORITY) fail('PROVIDER_CONTRIBUTION_ARTIFACT_AUTHORITY_INVALID');
  return value as unknown as ProviderContributionArtifactV1;
}

function hashContributionRecord(unsigned: UnsignedContributionRecordV1): string {
  return createHash('sha256')
    .update(canonicalizeJCS({ domain: PROVIDER_CONTRIBUTION_RECORD_DOMAIN, record: unsigned }))
    .digest('hex');
}

function unsignedRecord(record: ProviderContributionRecordV1): UnsignedContributionRecordV1 {
  const { record_hash: _recordHash, ...unsigned } = record;
  return unsigned;
}

function validateContributionRecord(
  value: unknown,
  expectedHash?: string,
  artifacts?: Record<string, ProviderContributionArtifactV1>,
): ProviderContributionRecordV1 {
  if (!isRecord(value)) fail('PROVIDER_CONTRIBUTION_RECORD_INVALID');
  exactKeys(value, RECORD_KEYS, 'PROVIDER_CONTRIBUTION_RECORD_UNKNOWN_FIELD');
  if (value.schema_version !== '1.0.0' || value.record_kind !== PROVIDER_CONTRIBUTION_RECORD_KIND) {
    fail('PROVIDER_CONTRIBUTION_RECORD_KIND_INVALID');
  }
  for (const [field, entry] of [
    ['record_hash', value.record_hash],
    ['fencing_token', value.fencing_token],
    ['artifact_sha256', value.artifact_sha256],
    ['contribution_store_prestate_root', value.contribution_store_prestate_root],
    ['intent_digest', value.intent_digest],
    ['policy_commitment', value.policy_commitment],
    ['target_commitment', value.target_commitment],
    ['pre_state_commitment', value.pre_state_commitment],
  ] as const) {
    if (!validHash(entry)) fail(`PROVIDER_CONTRIBUTION_RECORD_${field.toUpperCase()}_INVALID`);
  }
  if (expectedHash !== undefined && value.record_hash !== expectedHash) fail('PROVIDER_CONTRIBUTION_RECORD_KEY_MISMATCH');
  for (const [field, entry] of [
    ['graph_id', value.graph_id],
    ['work_node_id', value.work_node_id],
    ['provider', value.provider],
    ['model', value.model],
    ['session_id', value.session_id],
    ['lease_owner_identity', value.lease_owner_identity],
  ] as const) {
    if (!validIdentity(entry)) fail(`PROVIDER_CONTRIBUTION_RECORD_${field.toUpperCase()}_INVALID`);
  }
  if (typeof value.session_head_sha !== 'string' || !GIT_OBJECT_RE.test(value.session_head_sha)) {
    fail('PROVIDER_CONTRIBUTION_RECORD_SESSION_HEAD_INVALID');
  }
  if (!positiveInteger(value.lease_generation)) fail('PROVIDER_CONTRIBUTION_RECORD_GENERATION_INVALID');
  if (!nonnegativeInteger(value.authority_epoch)) fail('PROVIDER_CONTRIBUTION_RECORD_AUTHORITY_EPOCH_INVALID');
  if (value.authority !== PROVIDER_CONTRIBUTION_AUTHORITY) fail('PROVIDER_CONTRIBUTION_RECORD_AUTHORITY_INVALID');

  const record = value as unknown as ProviderContributionRecordV1;
  if (hashContributionRecord(unsignedRecord(record)) !== record.record_hash) {
    fail('PROVIDER_CONTRIBUTION_RECORD_HASH_MISMATCH');
  }
  if (artifacts !== undefined && artifacts[record.artifact_sha256] === undefined) {
    fail('PROVIDER_CONTRIBUTION_RECORD_ARTIFACT_MISSING');
  }
  return record;
}

function initialContributionState(): ProviderContributionStoreStateV1 {
  return {
    schema_version: '1.0.0',
    store_kind: PROVIDER_CONTRIBUTION_STORE_KIND,
    artifacts: {},
    records: {},
  };
}

function validateContributionState(value: unknown): ProviderContributionStoreStateV1 {
  if (!isRecord(value)) fail('PROVIDER_CONTRIBUTION_STORE_INVALID');
  exactKeys(value, STORE_KEYS, 'PROVIDER_CONTRIBUTION_STORE_UNKNOWN_FIELD');
  if (value.schema_version !== '1.0.0' || value.store_kind !== PROVIDER_CONTRIBUTION_STORE_KIND) {
    fail('PROVIDER_CONTRIBUTION_STORE_KIND_INVALID');
  }
  if (!isRecord(value.artifacts) || !isRecord(value.records)) fail('PROVIDER_CONTRIBUTION_STORE_MAPS_INVALID');

  const artifacts: Record<string, ProviderContributionArtifactV1> = {};
  for (const [digest, raw] of Object.entries(value.artifacts)) {
    artifacts[digest] = validateArtifact(raw, digest);
  }
  const records: Record<string, ProviderContributionRecordV1> = {};
  for (const [hash, raw] of Object.entries(value.records)) {
    records[hash] = validateContributionRecord(raw, hash, artifacts);
  }
  return {
    schema_version: '1.0.0',
    store_kind: PROVIDER_CONTRIBUTION_STORE_KIND,
    artifacts,
    records,
  };
}

function contributionStateRoot(state: ProviderContributionStoreStateV1): string {
  return createHash('sha256')
    .update(canonicalizeJCS({ domain: PROVIDER_CONTRIBUTION_STORE_DOMAIN, state }))
    .digest('hex');
}

function sameContribution(
  record: ProviderContributionRecordV1,
  graph: CollectiveWorkGraphV1,
  node: CollectiveWorkNodeV1,
  session: ProviderSessionIdentityV1,
  ownerIdentity: string,
  generation: number,
  fencingToken: string,
  artifactDigestValue: string,
): boolean {
  return record.graph_id === graph.graph_id &&
    record.work_node_id === node.work_node_id &&
    record.provider === session.provider &&
    record.model === session.model &&
    record.session_id === session.session_id &&
    record.session_head_sha === session.head_sha &&
    record.lease_owner_identity === ownerIdentity &&
    record.lease_generation === generation &&
    record.fencing_token === fencingToken &&
    record.artifact_sha256 === artifactDigestValue &&
    record.intent_digest === graph.intent_digest &&
    record.policy_commitment === graph.policy_commitment &&
    record.authority_epoch === graph.authority_epoch &&
    record.target_commitment === node.target_commitment &&
    record.pre_state_commitment === node.pre_state_commitment;
}

export class FileProviderContributionStoreV1 {
  readonly path: string;
  readonly lockPath: string;

  constructor(path: string) {
    if (!path) fail('PROVIDER_CONTRIBUTION_STORE_PATH_REQUIRED');
    this.path = path;
    this.lockPath = `${path}.lock`;
    mkdirSync(dirname(path), { recursive: true });
    try {
      writeFileSync(path, JSON.stringify(initialContributionState(), null, 2), { encoding: 'utf8', flag: 'wx' });
    } catch (error) {
      if (!isRecord(error) || error.code !== 'EEXIST') throw error;
    }
    this.load();
  }

  private load(): ProviderContributionStoreStateV1 {
    try {
      return validateContributionState(JSON.parse(readFileSync(this.path, 'utf8')));
    } catch (error) {
      if (error instanceof ProviderContributionError) throw error;
      throw new ProviderContributionError('PROVIDER_CONTRIBUTION_STORE_INVALID');
    }
  }

  private persist(state: ProviderContributionStoreStateV1): void {
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
      if (isRecord(error) && error.code === 'EEXIST') fail('PROVIDER_CONTRIBUTION_STORE_LOCKED');
      throw error;
    }
    try {
      return operation();
    } finally {
      try { rmdirSync(this.lockPath); } catch { /* fail-closed state remains inspectable */ }
    }
  }

  stateRoot(): string {
    return contributionStateRoot(this.load());
  }

  prepareContribution(): PreparedProviderContributionV1 {
    return { store_root: this.stateRoot() };
  }

  getArtifact(digest: string): ProviderContributionArtifactV1 {
    if (!validHash(digest)) fail('PROVIDER_CONTRIBUTION_ARTIFACT_HASH_INVALID');
    const artifact = this.load().artifacts[digest];
    if (!artifact) fail('PROVIDER_CONTRIBUTION_ARTIFACT_MISSING');
    return artifact;
  }

  getRecord(recordHash: string): ProviderContributionRecordV1 {
    if (!validHash(recordHash)) fail('PROVIDER_CONTRIBUTION_RECORD_HASH_INVALID');
    const record = this.load().records[recordHash];
    if (!record) fail('PROVIDER_CONTRIBUTION_RECORD_MISSING');
    return record;
  }

  recordTextContribution(input: RecordTextContributionInputV1): ProviderContributionRecordV1 {
    const admitted = graphAndNode(input.graph, input.work_node_id);
    const session = validateProviderSessionIdentity(input.session, admitted.graph, input.work_node_id);
    if (!validHash(input.expected_store_root)) fail('PROVIDER_CONTRIBUTION_PRESTATE_INVALID');
    const artifact = buildArtifact(input.text, input.media_type);
    const ownerIdentity = `provider:${session.provider}:${session.session_id}`;

    return input.lease_store.withCurrentLease({
      graph: admitted.graph,
      work_node_id: input.work_node_id,
      owner_identity: ownerIdentity,
      generation: input.generation,
      fencing_token: input.fencing_token,
      now_ms: input.now_ms,
    }, (lease) => this.exclusive(() => {
      const state = this.load();
      const prestateRoot = contributionStateRoot(state);
      if (prestateRoot !== input.expected_store_root) fail('PROVIDER_CONTRIBUTION_PRESTATE_STALE');

      const existingArtifact = state.artifacts[artifact.sha256];
      if (existingArtifact !== undefined) {
        const validated = validateArtifact(existingArtifact, artifact.sha256);
        if (validated.text !== artifact.text || validated.media_type !== artifact.media_type) {
          fail('PROVIDER_CONTRIBUTION_ARTIFACT_COLLISION');
        }
      }

      const duplicate = Object.values(state.records).find((record) => sameContribution(
        record,
        admitted.graph,
        admitted.node,
        session,
        ownerIdentity,
        lease.generation,
        lease.fencing_token,
        artifact.sha256,
      ));
      if (duplicate) return duplicate;

      const unsigned: UnsignedContributionRecordV1 = {
        schema_version: '1.0.0',
        record_kind: PROVIDER_CONTRIBUTION_RECORD_KIND,
        graph_id: admitted.graph.graph_id,
        work_node_id: admitted.node.work_node_id,
        provider: session.provider,
        model: session.model,
        session_id: session.session_id,
        session_head_sha: session.head_sha,
        lease_owner_identity: ownerIdentity,
        lease_generation: lease.generation,
        fencing_token: lease.fencing_token,
        artifact_sha256: artifact.sha256,
        contribution_store_prestate_root: prestateRoot,
        intent_digest: admitted.graph.intent_digest,
        policy_commitment: admitted.graph.policy_commitment,
        authority_epoch: admitted.graph.authority_epoch,
        target_commitment: admitted.node.target_commitment,
        pre_state_commitment: admitted.node.pre_state_commitment,
        authority: PROVIDER_CONTRIBUTION_AUTHORITY,
      };
      const record: ProviderContributionRecordV1 = {
        ...unsigned,
        record_hash: hashContributionRecord(unsigned),
      };
      state.artifacts[artifact.sha256] = artifact;
      state.records[record.record_hash] = record;
      this.persist(state);
      return record;
    }));
  }
}
