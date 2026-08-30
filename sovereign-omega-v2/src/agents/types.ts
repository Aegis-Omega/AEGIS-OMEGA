// ============================================================
// AEGIS Agent Habitat — Core Types
// EPISTEMIC TIER: T1
// HOLONIC SCALE: MOLECULAR (agent) → CELLULAR (agent ecosystem)
// RULE: Agents are operational inhabitants, not constitutional authorities.
// RULE: All agent mutations require replay persistence.
// ============================================================

import type { SHA256Hex, EpistemicTier } from '../core/types'

export const AGENT_MANIFEST_SCHEMA_VERSION = '1.0.0' as const

export type AgentType =
  | 'WorkspaceMappingAgent'
  | 'ResearchAgent'
  | 'ReplayAuditAgent'
  | 'TelemetryAnalysisAgent'
  | 'ExtensionGovernanceAgent'
  | 'InvariantEnforcementAgent'
  | 'DocumentationAgent'
  | 'EnvironmentAdaptationAgent'
  // CRGM §8 — 7 new agent types (Gate 143, T2 engineering hypothesis)
  | 'SentinelAgent'                // Threat detection — ASSESS phase
  | 'ArbitrationAgent'             // Governance validation — LOCK phase
  | 'MemoryAgent'                  // Lineage preservation — HARMONIZE phase
  | 'SimulationAgent'              // Future-state projection — bounded T2
  | 'EntropySuppressionAgent'      // Drift containment — all phases
  | 'ConstitutionalGuardianAgent'  // Invariant enforcement — LOCK phase
  | 'FederationRelayAgent'         // Cross-node synchronization — PROPAGATE phase

export const ALL_AGENT_TYPES: readonly AgentType[] = [
  'WorkspaceMappingAgent',
  'ResearchAgent',
  'ReplayAuditAgent',
  'TelemetryAnalysisAgent',
  'ExtensionGovernanceAgent',
  'InvariantEnforcementAgent',
  'DocumentationAgent',
  'EnvironmentAdaptationAgent',
  'SentinelAgent',
  'ArbitrationAgent',
  'MemoryAgent',
  'SimulationAgent',
  'EntropySuppressionAgent',
  'ConstitutionalGuardianAgent',
  'FederationRelayAgent',
] as const

export type AgentStatus = 'registered' | 'active' | 'suspended' | 'retired'

export interface AgentCapabilityManifest {
  readonly capability_ids: readonly string[]
  readonly invariant_bindings: readonly string[]
  readonly telemetry_schema_version: string
}

export interface AgentManifest {
  readonly schema_version: typeof AGENT_MANIFEST_SCHEMA_VERSION
  readonly agent_id: string
  readonly name: string
  readonly agent_type: AgentType
  readonly epistemic_tier: EpistemicTier
  readonly capability_manifest: AgentCapabilityManifest
  readonly is_replay_safe: boolean
  readonly entropy_budget_fixed: number  // Q16.16
  readonly workspace_boundary: readonly string[]  // canonical paths
  readonly status: AgentStatus
  readonly registered_at_sequence?: number
}

export interface AgentMemoryEntry {
  readonly entry_id: string
  readonly agent_id: string
  readonly sequence: number
  readonly content_hash: SHA256Hex
  readonly memory_type: string
  readonly is_replay_reconstructable: boolean
}

export interface CoordinationFrame {
  readonly frame_id: string
  readonly sequence: number
  readonly agent_id: string
  readonly action_type: string
  readonly mutation_ids: readonly string[]
  readonly replay_safe: boolean
}

export type WorkflowType =
  | 'research'
  | 'refactor'
  | 'replay-audit'
  | 'ontology-review'
  | 'environment-scan'
  | 'extension-review'
  | 'telemetry-analysis'

export type WorkflowStatus = 'pending' | 'active' | 'completed' | 'aborted'

export interface WorkflowExecution {
  readonly workflow_id: string
  readonly workflow_type: WorkflowType
  readonly agent_id: string
  readonly started_at_sequence: number
  readonly completed_at_sequence?: number
  readonly replay_frame_count: number
  readonly status: WorkflowStatus
}

export class AgentRegistrationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'AgentRegistrationError'
  }
}

export class AgentCoordinationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'AgentCoordinationError'
  }
}
