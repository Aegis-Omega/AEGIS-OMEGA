// ============================================================
// Environment Snapshot — schema-versioned constitutional artifacts (RULE-06)
// EPISTEMIC TIER: T0 (version-blind deserialization is constitutional violation)
// ============================================================

import { deepFreeze } from '../../core/immutable'
import type { WorkspaceSnapshot, GovernedWorkspace, EnvironmentBinding } from '../types'
import { WORKSPACE_SNAPSHOT_SCHEMA_VERSION } from '../types'
import type { SHA256Hex } from '../../core/types'

const GENESIS_HASH = '0'.repeat(64) as SHA256Hex

export interface SnapshotExport {
  readonly schema_version: typeof WORKSPACE_SNAPSHOT_SCHEMA_VERSION
  readonly snapshot: WorkspaceSnapshot
  readonly binding_count: number
  readonly is_attested: boolean
}

// Canonicalize workspace state into a stable string for hashing.
// Pure function — no external state, no Date.now().
export function canonicalizeWorkspaceState(
  workspace: GovernedWorkspace,
  bindings: readonly EnvironmentBinding[],
  sequence: number
): string {
  const paths = [...workspace.governed_paths]
    .map(p => p.canonical_path)
    .sort()
    .join('|')
  const caps = [...workspace.active_capability_ids].sort().join(',')
  const bindingIds = [...bindings].map(b => b.binding_id).sort().join(',')
  return `${workspace.workspace_id}:${paths}:${caps}:${bindingIds}:seq=${sequence}`
}

export function buildSnapshot(params: {
  workspace: GovernedWorkspace
  bindings: readonly EnvironmentBinding[]
  sequence: number
  totalMutations: number
  environmentHash?: SHA256Hex
}): WorkspaceSnapshot {
  const canonical = canonicalizeWorkspaceState(
    params.workspace,
    params.bindings,
    params.sequence
  )
  // Snapshot ID: FNV-1a hash of the canonical string (deterministic, no crypto dep)
  let hash = 2166136261
  for (let i = 0; i < canonical.length; i++) {
    hash ^= canonical.charCodeAt(i)
    hash = (hash * 16777619) >>> 0
  }
  const snapshotId = `snap_${hash.toString(16).padStart(8, '0')}`

  return deepFreeze({
    schema_version: WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
    snapshot_id: snapshotId,
    captured_at_sequence: params.sequence,
    canonical_root: params.workspace.canonical_root,
    governed_paths: deepFreeze(params.workspace.governed_paths.map(p => p.canonical_path)),
    active_capability_ids: deepFreeze([...params.workspace.active_capability_ids]),
    environment_hash: params.environmentHash ?? GENESIS_HASH,
    total_mutations: params.totalMutations,
  })
}

export function exportSnapshot(
  snapshot: WorkspaceSnapshot,
  bindingCount: number
): SnapshotExport {
  const isAttested =
    snapshot.schema_version === WORKSPACE_SNAPSHOT_SCHEMA_VERSION &&
    snapshot.snapshot_id.startsWith('snap_') &&
    snapshot.captured_at_sequence >= 0

  return deepFreeze({
    schema_version: WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
    snapshot,
    binding_count: bindingCount,
    is_attested: isAttested,
  })
}

// Deserializer: must read schema version before any other field (LAW-02 analog for env layer).
export function deserializeSnapshot(raw: unknown): WorkspaceSnapshot {
  if (typeof raw !== 'object' || raw === null) {
    throw new Error('Snapshot deserialization failed: not an object')
  }
  const obj = raw as Record<string, unknown>
  if (obj['schema_version'] !== WORKSPACE_SNAPSHOT_SCHEMA_VERSION) {
    throw new Error(
      `Snapshot schema version mismatch: expected ${WORKSPACE_SNAPSHOT_SCHEMA_VERSION}, got ${String(obj['schema_version'])}`
    )
  }
  return deepFreeze(raw as WorkspaceSnapshot)
}
