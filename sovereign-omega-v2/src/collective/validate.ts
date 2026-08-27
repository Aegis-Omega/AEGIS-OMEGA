import {
  CAPABILITY_STATUSES,
  CONSEQUENCE_CLASSES,
  type CapabilityRefV1,
  type CollectiveWorkGraphV1,
  type CollectiveWorkNodeV1,
  type IntentEnvelopeV1,
} from './contracts';

export type ValidationResult<T> =
  | { ok: true; value: T }
  | { ok: false; errors: readonly string[] };

const HASH_RE = /^[0-9a-f]{64}$/;
const CONSEQUENCE_SET = new Set<string>(CONSEQUENCE_CLASSES);
const CAPABILITY_STATUS_SET = new Set<string>(CAPABILITY_STATUSES);

const INTENT_KEYS = new Set([
  'schema_version',
  'intent_kind',
  'intent_id',
  'intent_digest',
  'actor_identity',
  'session_identity',
  'policy_commitment',
  'authority_epoch',
  'input_artifact_digests',
  'requested_capability_ids',
  'max_cost_microunits',
  'max_tokens',
  'max_duration_seconds',
  'consequence_ceiling',
  'deterministic_nonce',
]);

const GRAPH_KEYS = new Set([
  'schema_version',
  'graph_kind',
  'graph_id',
  'intent_digest',
  'nodes',
  'policy_commitment',
  'authority_epoch',
  'graph_nonce',
]);

const NODE_KEYS = new Set([
  'schema_version',
  'work_node_kind',
  'work_node_id',
  'objective_digest',
  'intent_digest',
  'required_capabilities',
  'allowed_providers',
  'allowed_tools',
  'dependency_ids',
  'input_artifact_digests',
  'max_cost_microunits',
  'max_tokens',
  'max_duration_seconds',
  'consequence_class',
  'authority_epoch',
  'policy_commitment',
  'target_commitment',
  'pre_state_commitment',
  'nonce',
]);

const CAPABILITY_KEYS = new Set([
  'capability_kind',
  'capability_id',
  'status',
  'profile',
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function addUnknownFields(
  value: Record<string, unknown>,
  allowed: ReadonlySet<string>,
  path: string,
  errors: string[],
): void {
  for (const key of Object.keys(value).sort()) {
    if (!allowed.has(key)) errors.push(`UNKNOWN_FIELD:${path}.${key}`);
  }
}

function requireConst(
  value: unknown,
  expected: string,
  path: string,
  errors: string[],
): void {
  if (value !== expected) errors.push(`INVALID_CONST:${path}`);
}

function requireNonempty(value: unknown, path: string, errors: string[]): value is string {
  if (typeof value !== 'string' || value.length === 0) {
    errors.push(`INVALID_NONEMPTY:${path}`);
    return false;
  }
  return true;
}

function requireHash(value: unknown, path: string, errors: string[]): value is string {
  if (typeof value !== 'string' || !HASH_RE.test(value)) {
    errors.push(`INVALID_HASH:${path}`);
    return false;
  }
  return true;
}

function requireNonnegativeInteger(
  value: unknown,
  path: string,
  errors: string[],
): value is number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < 0) {
    errors.push(`INVALID_NONNEGATIVE_INTEGER:${path}`);
    return false;
  }
  return true;
}

function validateStringArray(
  value: unknown,
  path: string,
  errors: string[],
  options: { hashes?: boolean; rejectDuplicates?: boolean } = {},
): value is string[] {
  if (!Array.isArray(value)) {
    errors.push(`INVALID_ARRAY:${path}`);
    return false;
  }

  const seen = new Set<string>();
  value.forEach((item, index) => {
    if (options.hashes) {
      requireHash(item, `${path}[${index}]`, errors);
    } else {
      requireNonempty(item, `${path}[${index}]`, errors);
    }
    if (options.rejectDuplicates && typeof item === 'string') {
      if (seen.has(item)) errors.push(`DUPLICATE_VALUE:${path}:${item}`);
      seen.add(item);
    }
  });
  return true;
}

function validateCapability(
  value: unknown,
  path: string,
  errors: string[],
): value is CapabilityRefV1 {
  if (!isRecord(value)) {
    errors.push(`INVALID_OBJECT:${path}`);
    return false;
  }
  addUnknownFields(value, CAPABILITY_KEYS, path, errors);
  requireConst(value.capability_kind, 'CAPABILITY_REF_V1', `${path}.capability_kind`, errors);
  requireNonempty(value.capability_id, `${path}.capability_id`, errors);
  if (typeof value.status !== 'string' || !CAPABILITY_STATUS_SET.has(value.status)) {
    errors.push(`INVALID_CAPABILITY_STATUS:${path}.status`);
  }
  if ('profile' in value && value.profile !== undefined) {
    requireNonempty(value.profile, `${path}.profile`, errors);
  }
  return true;
}

function validateNode(value: unknown, path: string, errors: string[]): value is CollectiveWorkNodeV1 {
  if (!isRecord(value)) {
    errors.push(`INVALID_OBJECT:${path}`);
    return false;
  }

  addUnknownFields(value, NODE_KEYS, path, errors);
  requireConst(value.schema_version, '1.0.0', `${path}.schema_version`, errors);
  requireConst(value.work_node_kind, 'COLLECTIVE_WORK_NODE_V1', `${path}.work_node_kind`, errors);
  requireNonempty(value.work_node_id, `${path}.work_node_id`, errors);
  requireHash(value.objective_digest, `${path}.objective_digest`, errors);
  requireHash(value.intent_digest, `${path}.intent_digest`, errors);

  if (!Array.isArray(value.required_capabilities)) {
    errors.push(`INVALID_ARRAY:${path}.required_capabilities`);
  } else {
    const capabilityIds = new Set<string>();
    value.required_capabilities.forEach((capability, index) => {
      const capabilityPath = `${path}.required_capabilities[${index}]`;
      validateCapability(capability, capabilityPath, errors);
      if (isRecord(capability) && typeof capability.capability_id === 'string') {
        if (capabilityIds.has(capability.capability_id)) {
          errors.push(
            `DUPLICATE_CAPABILITY:${path}.required_capabilities:${capability.capability_id}`,
          );
        }
        capabilityIds.add(capability.capability_id);
      }
    });
  }

  validateStringArray(value.allowed_providers, `${path}.allowed_providers`, errors, {
    rejectDuplicates: true,
  });
  validateStringArray(value.allowed_tools, `${path}.allowed_tools`, errors, {
    rejectDuplicates: true,
  });
  validateStringArray(value.dependency_ids, `${path}.dependency_ids`, errors, {
    rejectDuplicates: true,
  });
  validateStringArray(value.input_artifact_digests, `${path}.input_artifact_digests`, errors, {
    hashes: true,
    rejectDuplicates: true,
  });

  requireNonnegativeInteger(value.max_cost_microunits, `${path}.max_cost_microunits`, errors);
  requireNonnegativeInteger(value.max_tokens, `${path}.max_tokens`, errors);
  requireNonnegativeInteger(value.max_duration_seconds, `${path}.max_duration_seconds`, errors);
  requireNonnegativeInteger(value.authority_epoch, `${path}.authority_epoch`, errors);

  if (typeof value.consequence_class !== 'string' || !CONSEQUENCE_SET.has(value.consequence_class)) {
    errors.push(`INVALID_CONSEQUENCE_CLASS:${path}.consequence_class`);
  }

  requireHash(value.policy_commitment, `${path}.policy_commitment`, errors);
  requireHash(value.target_commitment, `${path}.target_commitment`, errors);
  requireHash(value.pre_state_commitment, `${path}.pre_state_commitment`, errors);
  requireNonempty(value.nonce, `${path}.nonce`, errors);
  return true;
}

function result<T>(value: unknown, errors: string[]): ValidationResult<T> {
  if (errors.length > 0) {
    return { ok: false, errors: [...new Set(errors)].sort() };
  }
  return { ok: true, value: value as T };
}

export function validateIntentEnvelope(value: unknown): ValidationResult<IntentEnvelopeV1> {
  const errors: string[] = [];
  if (!isRecord(value)) {
    return { ok: false, errors: ['INVALID_OBJECT:intent'] };
  }

  addUnknownFields(value, INTENT_KEYS, 'intent', errors);
  requireConst(value.schema_version, '1.0.0', 'intent.schema_version', errors);
  requireConst(value.intent_kind, 'INTENT_ENVELOPE_V1', 'intent.intent_kind', errors);
  requireNonempty(value.intent_id, 'intent.intent_id', errors);
  requireHash(value.intent_digest, 'intent.intent_digest', errors);
  requireNonempty(value.actor_identity, 'intent.actor_identity', errors);
  requireNonempty(value.session_identity, 'intent.session_identity', errors);
  requireHash(value.policy_commitment, 'intent.policy_commitment', errors);
  requireNonnegativeInteger(value.authority_epoch, 'intent.authority_epoch', errors);
  validateStringArray(value.input_artifact_digests, 'intent.input_artifact_digests', errors, {
    hashes: true,
    rejectDuplicates: true,
  });
  validateStringArray(value.requested_capability_ids, 'intent.requested_capability_ids', errors, {
    rejectDuplicates: true,
  });
  requireNonnegativeInteger(value.max_cost_microunits, 'intent.max_cost_microunits', errors);
  requireNonnegativeInteger(value.max_tokens, 'intent.max_tokens', errors);
  requireNonnegativeInteger(value.max_duration_seconds, 'intent.max_duration_seconds', errors);
  if (typeof value.consequence_ceiling !== 'string' || !CONSEQUENCE_SET.has(value.consequence_ceiling)) {
    errors.push('INVALID_CONSEQUENCE_CLASS:intent.consequence_ceiling');
  }
  requireNonempty(value.deterministic_nonce, 'intent.deterministic_nonce', errors);
  return result<IntentEnvelopeV1>(value, errors);
}

export function validateCollectiveWorkGraph(value: unknown): ValidationResult<CollectiveWorkGraphV1> {
  const errors: string[] = [];
  if (!isRecord(value)) {
    return { ok: false, errors: ['INVALID_OBJECT:graph'] };
  }

  addUnknownFields(value, GRAPH_KEYS, 'graph', errors);
  requireConst(value.schema_version, '1.0.0', 'graph.schema_version', errors);
  requireConst(value.graph_kind, 'COLLECTIVE_WORK_GRAPH_V1', 'graph.graph_kind', errors);
  requireNonempty(value.graph_id, 'graph.graph_id', errors);
  const graphIntentValid = requireHash(value.intent_digest, 'graph.intent_digest', errors);
  const graphPolicyValid = requireHash(value.policy_commitment, 'graph.policy_commitment', errors);
  const graphEpochValid = requireNonnegativeInteger(value.authority_epoch, 'graph.authority_epoch', errors);
  requireNonempty(value.graph_nonce, 'graph.graph_nonce', errors);

  if (!Array.isArray(value.nodes)) {
    errors.push('INVALID_ARRAY:graph.nodes');
    return result<CollectiveWorkGraphV1>(value, errors);
  }

  const nodeIds: string[] = [];
  value.nodes.forEach((node, index) => {
    const path = `graph.nodes[${index}]`;
    validateNode(node, path, errors);
    if (!isRecord(node)) return;

    if (typeof node.work_node_id === 'string') nodeIds.push(node.work_node_id);
    if (graphIntentValid && node.intent_digest !== value.intent_digest && typeof node.work_node_id === 'string') {
      errors.push(`INTENT_BINDING_MISMATCH:${node.work_node_id}`);
    }
    if (graphPolicyValid && node.policy_commitment !== value.policy_commitment && typeof node.work_node_id === 'string') {
      errors.push(`POLICY_BINDING_MISMATCH:${node.work_node_id}`);
    }
    if (graphEpochValid && node.authority_epoch !== value.authority_epoch && typeof node.work_node_id === 'string') {
      errors.push(`AUTHORITY_EPOCH_MISMATCH:${node.work_node_id}`);
    }
  });

  const idCounts = new Map<string, number>();
  for (const id of nodeIds) idCounts.set(id, (idCounts.get(id) ?? 0) + 1);
  for (const [id, count] of [...idCounts.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    if (count > 1) errors.push(`DUPLICATE_NODE_ID:${id}`);
  }

  const uniqueIds = new Set(nodeIds);
  for (const node of value.nodes) {
    if (!isRecord(node) || typeof node.work_node_id !== 'string' || !Array.isArray(node.dependency_ids)) {
      continue;
    }
    const dependencies = node.dependency_ids.filter((dep): dep is string => typeof dep === 'string').sort();
    for (const dependency of dependencies) {
      if (dependency === node.work_node_id) {
        errors.push(`SELF_DEPENDENCY:${node.work_node_id}`);
      } else if (!uniqueIds.has(dependency)) {
        errors.push(`MISSING_DEPENDENCY:${node.work_node_id}->${dependency}`);
      }
    }
  }

  if (![...idCounts.values()].some((count) => count > 1)) {
    const adjacency = new Map<string, string[]>();
    const indegree = new Map<string, number>();
    for (const id of [...uniqueIds].sort()) {
      adjacency.set(id, []);
      indegree.set(id, 0);
    }

    for (const node of value.nodes) {
      if (!isRecord(node) || typeof node.work_node_id !== 'string' || !Array.isArray(node.dependency_ids)) {
        continue;
      }
      const deps = [...new Set(node.dependency_ids.filter((dep): dep is string => typeof dep === 'string'))]
        .filter((dep) => dep !== node.work_node_id && uniqueIds.has(dep))
        .sort();
      indegree.set(node.work_node_id, deps.length);
      for (const dep of deps) adjacency.get(dep)?.push(node.work_node_id);
    }

    for (const dependents of adjacency.values()) dependents.sort();
    const queue = [...indegree.entries()]
      .filter(([, degree]) => degree === 0)
      .map(([id]) => id)
      .sort();
    const visited = new Set<string>();

    while (queue.length > 0) {
      const id = queue.shift()!;
      if (visited.has(id)) continue;
      visited.add(id);
      for (const dependent of adjacency.get(id) ?? []) {
        const next = (indegree.get(dependent) ?? 0) - 1;
        indegree.set(dependent, next);
        if (next === 0) {
          queue.push(dependent);
          queue.sort();
        }
      }
    }

    if (visited.size !== uniqueIds.size) {
      const remaining = [...uniqueIds].filter((id) => !visited.has(id)).sort();
      errors.push(`GRAPH_CYCLE:${remaining.join(',')}`);
    }
  }

  return result<CollectiveWorkGraphV1>(value, errors);
}
