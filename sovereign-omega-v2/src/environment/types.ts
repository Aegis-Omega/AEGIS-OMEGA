// ============================================================
// AEGIS Environment Adaptation Layer — Core Types
// EPISTEMIC TIER: T1 (empirically validated against host environments)
// HOLONIC SCALE: MOLECULAR (environment bindings) → CELLULAR (adaptation layer)
// CONSTITUTIONAL LAW: "The runtime may adapt to its host environment, but no
//   adaptation may violate replay determinism, ontology integrity, provenance
//   continuity, or constitutional invariants."
// ============================================================

import type { SHA256Hex, EpistemicTier } from '../core/types'

export type HostCapabilityClass = 'filesystem' | 'process' | 'network' | 'telemetry'

export type InstallationContext =
  | 'monorepo'
  | 'standalone'
  | 'container'
  | 'ci-environment'
  | 'development'

export type MutationType =
  | 'path_registered'
  | 'capability_granted'
  | 'capability_revoked'
  | 'workspace_added'
  | 'workspace_removed'
  | 'tool_registered'
  | 'plugin_admitted'
  | 'plugin_evicted'

export type PathAccessClass = 'read-only' | 'append-only' | 'governed-write'

export const WORKSPACE_SNAPSHOT_SCHEMA_VERSION = '1.0.0' as const

export interface HostCapability {
  readonly capability_id: string
  readonly class: HostCapabilityClass
  readonly name: string
  readonly provenance_tier: EpistemicTier
  readonly ontology_term: string
  readonly admissibility_reason: string
  readonly entropy_impact_bounded: boolean
}

export interface CapabilityGrant {
  readonly grant_id: string
  readonly capability_id: string
  readonly granted_to: string
  readonly scope: readonly string[]
  readonly sequence_granted: number
  readonly sequence_revoked?: number
  readonly least_privilege: boolean
}

export interface EnvironmentBinding {
  readonly binding_id: string
  readonly capability_class: HostCapabilityClass
  readonly canonical_path: string
  readonly provenance_source: string
  readonly admitted_at_sequence: number
  readonly grants: readonly CapabilityGrant[]
}

export interface GovernedPath {
  readonly canonical_path: string
  readonly path_id: string
  readonly access_class: PathAccessClass
  readonly is_constitutional: boolean
}

export interface GovernedWorkspace {
  readonly workspace_id: string
  readonly canonical_root: string
  readonly installation_context: InstallationContext
  readonly governed_paths: readonly GovernedPath[]
  readonly active_capability_ids: readonly string[]
  readonly entropy_budget_fixed: number  // Q16.16
}

export interface WorkspaceSnapshot {
  readonly schema_version: typeof WORKSPACE_SNAPSHOT_SCHEMA_VERSION
  readonly snapshot_id: string
  readonly captured_at_sequence: number
  readonly canonical_root: string
  readonly governed_paths: readonly string[]
  readonly active_capability_ids: readonly string[]
  readonly environment_hash: SHA256Hex
  readonly total_mutations: number
}

export interface ReplayFrame {
  readonly frame_sequence: number
  readonly environment_state_hash: SHA256Hex
  readonly mutation_hash: SHA256Hex
  readonly capability_grants_hash: SHA256Hex
  readonly invariant_outcomes_hash: SHA256Hex
}

export interface EnvironmentMutation {
  readonly mutation_id: string
  readonly sequence: number
  readonly mutation_type: MutationType
  readonly target_path: string
  readonly prev_state_hash: SHA256Hex
  readonly next_state_hash: SHA256Hex
  readonly provenance_source: string
  readonly admitted_by: string
  readonly is_replay_reconstructable: boolean
}

export interface ToolInvocationRecord {
  readonly invocation_id: string
  readonly tool_id: string
  readonly sequence: number
  readonly canonical_input_hash: SHA256Hex
  readonly canonical_output_hash: SHA256Hex
  readonly capability_used: string
  readonly duration_sequence_units: number
  readonly replay_reconstructable: boolean
}

export interface EnvironmentState {
  readonly state_id: string
  readonly sequence: number
  readonly workspace: GovernedWorkspace
  readonly active_bindings: readonly EnvironmentBinding[]
  readonly mutation_count: number
  readonly entropy_fixed: number  // Q16.16
  readonly adaptation_pressure_index_fixed: number  // Q16.16
}

export class CapabilityAdmissionError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'CapabilityAdmissionError'
  }
}

export class MutationRejectedError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'MutationRejectedError'
  }
}
