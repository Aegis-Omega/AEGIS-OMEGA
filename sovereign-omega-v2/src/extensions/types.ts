// ============================================================
// AEGIS Extension / Plugin Habitat — Core Types
// EPISTEMIC TIER: T1
// HOLONIC SCALE: MOLECULAR (plugin) → CELLULAR (extension ecosystem)
// RULE: Plugins are environment inhabitants, not constitutional authorities.
// RULE: Plugins may evolve operational behavior but may not redefine ontology primitives.
// ============================================================

import type { EpistemicTier } from '../core/types'
import type { HostCapabilityClass } from '../environment/types'

export const PLUGIN_MANIFEST_SCHEMA_VERSION = '1.0.0' as const

export type PluginStatus = 'admitted' | 'suspended' | 'evicted'

export type PluginCapabilityRequest = {
  readonly capability_class: HostCapabilityClass
  readonly scope: readonly string[]
  readonly justification: string
}

export interface PluginManifest {
  readonly schema_version: typeof PLUGIN_MANIFEST_SCHEMA_VERSION
  readonly plugin_id: string
  readonly name: string
  readonly version: string
  readonly epistemic_tier: EpistemicTier
  readonly capability_requests: readonly PluginCapabilityRequest[]
  readonly ontology_terms_used: readonly string[]
  readonly is_replay_safe: boolean
  readonly entropy_budget_fixed: number  // Q16.16 — max entropy contribution allowed
  readonly admitted_at_sequence?: number
  readonly status: PluginStatus
}

export interface CapabilityContract {
  readonly contract_id: string
  readonly plugin_id: string
  readonly capability_id: string
  readonly granted_scope: readonly string[]
  readonly sequence_granted: number
  readonly sequence_expires?: number
  readonly is_least_privilege: boolean
  readonly admissibility_reason: string
}

export interface SandboxBoundary {
  readonly sandbox_id: string
  readonly plugin_id: string
  readonly allowed_capability_ids: readonly string[]
  readonly allowed_paths: readonly string[]
  readonly max_mutation_count: number
  readonly current_mutation_count: number
  readonly entropy_used_fixed: number  // Q16.16
  readonly entropy_budget_fixed: number  // Q16.16
  readonly is_isolated: boolean
}

export interface MutationReceipt {
  readonly receipt_id: string
  readonly plugin_id: string
  readonly mutation_type: string
  readonly target_path: string
  readonly sequence: number
  readonly authorized_by_contract: string
  readonly is_replay_reconstructable: boolean
  readonly entropy_contribution_fixed: number  // Q16.16
}

export interface ExtensionTelemetry {
  readonly plugin_id: string
  readonly mutation_count: number
  readonly entropy_used_fixed: number  // Q16.16
  readonly replay_safe_ratio: number  // [0,1] fraction of mutations that are replay-safe
  readonly capability_grants_active: number
  readonly sandbox_isolation_intact: boolean
}

export class PluginAdmissionError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'PluginAdmissionError'
  }
}

export class SandboxViolationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SandboxViolationError'
  }
}
