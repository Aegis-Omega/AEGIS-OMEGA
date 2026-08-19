import type { CollectiveWorkGraphV1, CollectiveWorkNodeV1 } from './contracts';
import { validateCollectiveWorkGraph } from './validate';

export const PROVIDER_SESSION_KIND = 'PROVIDER_SESSION_IDENTITY_V1' as const;
export const PROVIDER_SESSION_AUTHORITY = 'IDENTITY_ONLY_NOT_AUTHORIZATION' as const;

const HASH_RE = /^[0-9a-f]{64}$/;
const GIT_OBJECT_RE = /^[0-9a-f]{40,64}$/;
const IDENTITY_RE = /^[A-Za-z0-9._:/@+\-]{1,128}$/;
const REPOSITORY_RE = /^[A-Za-z0-9._-]{1,100}\/[A-Za-z0-9._-]{1,100}$/;
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

function fail(code: string): never {
  throw new ProviderContributionError(code);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function exactKeys(value: Record<string, unknown>): void {
  const keys = Object.keys(value);
  if (keys.length !== SESSION_KEYS.size || keys.some((key) => !SESSION_KEYS.has(key))) {
    fail('PROVIDER_SESSION_UNKNOWN_FIELD');
  }
}

function validIdentity(value: unknown): value is string {
  return typeof value === 'string' && IDENTITY_RE.test(value);
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
  exactKeys(value);

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
  if (typeof value.policy_commitment !== 'string' || !HASH_RE.test(value.policy_commitment)) {
    fail('PROVIDER_SESSION_POLICY_INVALID');
  }
  if (!Number.isInteger(value.authority_epoch) || (value.authority_epoch as number) < 0) {
    fail('PROVIDER_SESSION_AUTHORITY_EPOCH_INVALID');
  }
  if (typeof value.skill_catalog_root !== 'string' || !HASH_RE.test(value.skill_catalog_root)) {
    fail('PROVIDER_SESSION_SKILL_ROOT_INVALID');
  }
  if (typeof value.organism_state_root !== 'string' || !HASH_RE.test(value.organism_state_root)) {
    fail('PROVIDER_SESSION_ORGANISM_ROOT_INVALID');
  }
  if (value.authority !== PROVIDER_SESSION_AUTHORITY) fail('PROVIDER_SESSION_AUTHORITY_INVALID');

  if (!admitted.node.allowed_providers.includes(value.provider)) {
    fail('PROVIDER_SESSION_PROVIDER_NOT_ALLOWED');
  }
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
    authority_epoch: value.authority_epoch as number,
    skill_catalog_root: value.skill_catalog_root,
    organism_state_root: value.organism_state_root,
    authority: PROVIDER_SESSION_AUTHORITY,
  };
}
