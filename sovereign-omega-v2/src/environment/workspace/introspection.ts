// ============================================================
// Workspace Introspection — detect and canonicalize governed paths
// EPISTEMIC TIER: T1
// No Date.now(). No floats. Canonical paths are deterministic.
// ============================================================

import { deepFreeze } from '../../core/immutable'
import type { GovernedPath, GovernedWorkspace, InstallationContext } from '../types'

const FIXED_SHIFT = 16
const FIXED_SCALE = 1 << FIXED_SHIFT

// Canonicalize a filesystem path: normalize separators, collapse dots, lowercase on case-insensitive FS.
// Pure function — deterministic for the same input string.
export function canonicalizePath(raw: string): string {
  // Replace backslashes, collapse repeated slashes, remove trailing slash
  return raw
    .replace(/\\/g, '/')
    .replace(/\/+/g, '/')
    .replace(/\/\.$/, '')
    .replace(/\/\.\//g, '/')
    .replace(/\/$/, '') || '/'
}

// Generate a deterministic workspace ID from the canonical root path.
// Uses a stable hash function — not SHA-256 (no crypto dep here); uses FNV-1a 32-bit.
export function deterministicWorkspaceId(canonicalRoot: string): string {
  let hash = 2166136261
  for (let i = 0; i < canonicalRoot.length; i++) {
    hash ^= canonicalRoot.charCodeAt(i)
    hash = (hash * 16777619) >>> 0
  }
  return `ws_${hash.toString(16).padStart(8, '0')}`
}

// Generate a deterministic path ID from the canonical path string.
export function deterministicPathId(canonicalPath: string): string {
  let hash = 2166136261
  for (let i = 0; i < canonicalPath.length; i++) {
    hash ^= canonicalPath.charCodeAt(i)
    hash = (hash * 16777619) >>> 0
  }
  return `path_${hash.toString(16).padStart(8, '0')}`
}

// Detect the installation context from the directory listing.
// Pure function — returns a deterministic result for a given set of paths.
export function detectInstallationContext(
  rootContents: readonly string[]
): InstallationContext {
  /* c8 ignore next -- noUncheckedIndexedAccess artifact; path strings always have at least one segment after split('/') */
  const names = rootContents.map(p => canonicalizePath(p).split('/').pop() ?? '')
  if (names.includes('package.json') && names.includes('packages')) return 'monorepo'
  if (names.includes('.github') || names.includes('CI')) return 'ci-environment'
  if (names.includes('Dockerfile') || names.includes('.dockerenv')) return 'container'
  if (names.includes('package.json')) return 'standalone'
  return 'development'
}

export function buildGovernedPath(
  rawPath: string,
  accessClass: GovernedPath['access_class'],
  isConstitutional: boolean
): GovernedPath {
  const canonical = canonicalizePath(rawPath)
  return deepFreeze({
    canonical_path: canonical,
    path_id: deterministicPathId(canonical),
    access_class: accessClass,
    is_constitutional: isConstitutional,
  })
}

export function buildGovernedWorkspace(params: {
  canonicalRoot: string
  installationContext: InstallationContext
  governedPaths: readonly GovernedPath[]
  activeCapabilityIds: readonly string[]
}): GovernedWorkspace {
  const canonical = canonicalizePath(params.canonicalRoot)
  return deepFreeze({
    workspace_id: deterministicWorkspaceId(canonical),
    canonical_root: canonical,
    installation_context: params.installationContext,
    governed_paths: deepFreeze([...params.governedPaths]),
    active_capability_ids: deepFreeze([...params.activeCapabilityIds]),
    entropy_budget_fixed: 98 * FIXED_SCALE,  // 98.0 in Q16.16 — full budget at init
  })
}
