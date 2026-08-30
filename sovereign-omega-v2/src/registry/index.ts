// ============================================================
// SOVEREIGN OMEGA — Semantic Particle Registry
// EPISTEMIC TIER: T0
// Frozen, deterministic registry of all classified artifacts.
// Query interface: lookupNode, queryByGate, queryByTier,
//                 queryByMutationAuthority, registrySize.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { REGISTRY_ENTRIES } from './entries.js'
import { MutationAuthority } from './types.js'
import type { SemanticNode } from './types.js'

export type { SemanticNode, AncestryEdge, AncestryRelationship } from './types.js'
export { HolonicScale, MutationAuthority, ProofCoverage, EpistemicTier } from './types.js'

/**
 * The canonical frozen registry.
 * Access is deterministic: same index → same node across all calls.
 * noUncheckedIndexedAccess: direct indexing returns SemanticNode | undefined.
 * Use lookupNode() for safe access.
 */
export const SEMANTIC_REGISTRY: readonly SemanticNode[] =
  deepFreeze([...REGISTRY_ENTRIES]) as readonly SemanticNode[]

/**
 * Return the node for a given path, or undefined if not registered.
 * Path is relative to sovereign-omega-v2/.
 */
export function lookupNode(path: string): SemanticNode | undefined {
  return SEMANTIC_REGISTRY.find(n => n.path === path)
}

/**
 * Return all nodes validated by a specific build gate.
 * gate(1) → canonicalize.ts, types.ts, hashing.ts
 * gate(null) → nodes with no designated gate.
 */
export function queryByGate(gate: number | null): readonly SemanticNode[] {
  return SEMANTIC_REGISTRY.filter(n => n.gate === gate)
}

/**
 * Return all nodes at a specific epistemic tier (0–5).
 */
export function queryByTier(tier: 0 | 1 | 2 | 3 | 4 | 5): readonly SemanticNode[] {
  return SEMANTIC_REGISTRY.filter(n => n.tier === tier)
}

/**
 * Return all nodes with a specific mutation authority classification.
 */
export function queryByMutationAuthority(authority: MutationAuthority): readonly SemanticNode[] {
  return SEMANTIC_REGISTRY.filter(n => n.mutation_authority === authority)
}

/**
 * Return all constitutional (frozen) nodes.
 * These require GUARDIAN_ONLY authority to modify.
 */
export function queryConstitutional(): readonly SemanticNode[] {
  return SEMANTIC_REGISTRY.filter(n => n.is_constitutional)
}

/** Total number of registered semantic nodes. */
export function registrySize(): number {
  return SEMANTIC_REGISTRY.length
}
