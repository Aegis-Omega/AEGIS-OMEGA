// ============================================================
// AEGIS IDE Runtime — Constitutional Panel State Types
// EPISTEMIC TIER: T1
// The IDE is the constitutional operational nervous system.
// All panel states derive from replay state. No UI components.
// Each panel: is_replay_reconstructable=true, schema_version present.
// ============================================================

import type { AgentType } from '../agents/types'
import type { AgentTelemetrySnapshot } from '../agents/telemetry/agent-telemetry'
import type { InstallationContext } from '../environment/types'

export const IDE_PANEL_SCHEMA_VERSION = '1.0.0' as const

interface BasePanelState {
  readonly panel_id: string
  readonly last_updated_sequence: number
  readonly is_replay_reconstructable: true
  readonly schema_version: typeof IDE_PANEL_SCHEMA_VERSION
}

export interface ReplayExplorerPanelState extends BasePanelState {
  readonly replay_frame_count: number
  readonly oldest_sequence: number
  readonly newest_sequence: number
}

export interface WorkspaceTopologyPanelState extends BasePanelState {
  readonly governed_path_count: number
  readonly installation_context: InstallationContext
}

export interface AgentHabitatPanelState extends BasePanelState {
  readonly active_agent_count: number
  readonly registered_agent_count: number
  readonly agent_types: readonly AgentType[]
}

export interface ConstitutionalInvariantDashboardState extends BasePanelState {
  readonly checked_invariant_count: number
  readonly t0_violations: number
  readonly t1_alerts: number
}

export interface TelemetryCockpitState extends BasePanelState {
  readonly agent_telemetry: AgentTelemetrySnapshot
  readonly env_entropy: number
}

export interface CapabilityGovernanceSurfaceState extends BasePanelState {
  readonly registered_capability_count: number
  readonly active_grant_count: number
}

export interface ExtensionEcologyViewState extends BasePanelState {
  readonly admitted_plugin_count: number
  readonly evicted_plugin_count: number
}

export interface MutationTimelinePanelState extends BasePanelState {
  readonly total_mutations: number
  readonly recent_mutation_types: readonly string[]
}

export interface ReplayIntegrityPanelState extends BasePanelState {
  readonly reconstruction_ratio: number
  readonly frame_count: number
}

export interface EnvironmentalDriftMonitorState extends BasePanelState {
  readonly drift_rate: number
  readonly stability_score: number
  readonly pressure_index: number
}

export interface IDERuntimeState {
  readonly replayExplorer: ReplayExplorerPanelState
  readonly workspaceTopology: WorkspaceTopologyPanelState
  readonly agentHabitat: AgentHabitatPanelState
  readonly constitutionalInvariants: ConstitutionalInvariantDashboardState
  readonly telemetryCockpit: TelemetryCockpitState
  readonly capabilityGovernance: CapabilityGovernanceSurfaceState
  readonly extensionEcology: ExtensionEcologyViewState
  readonly mutationTimeline: MutationTimelinePanelState
  readonly replayIntegrity: ReplayIntegrityPanelState
  readonly environmentalDrift: EnvironmentalDriftMonitorState
}
