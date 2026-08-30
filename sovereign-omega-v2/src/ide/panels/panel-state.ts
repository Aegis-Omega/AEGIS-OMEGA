// ============================================================
// Panel State Factories — pure functions deriving panel state
// EPISTEMIC TIER: T1
// All panel states are derived from replay state (pure functions).
// No side effects. No Date.now(). No external state.
// ============================================================

import type {
  IDERuntimeState,
  ReplayExplorerPanelState,
  WorkspaceTopologyPanelState,
  AgentHabitatPanelState,
  ConstitutionalInvariantDashboardState,
  TelemetryCockpitState,
  CapabilityGovernanceSurfaceState,
  ExtensionEcologyViewState,
  MutationTimelinePanelState,
  ReplayIntegrityPanelState,
  EnvironmentalDriftMonitorState,
} from '../types'
import { IDE_PANEL_SCHEMA_VERSION } from '../types'
import type { AgentTelemetrySnapshot } from '../../agents/telemetry/agent-telemetry'

const BASE = (panel_id: string, seq: number) => ({
  panel_id,
  last_updated_sequence: seq,
  is_replay_reconstructable: true as const,
  schema_version: IDE_PANEL_SCHEMA_VERSION,
})

export function buildReplayExplorerPanel(seq: number, p?: { frameCount?: number; oldestSeq?: number; newestSeq?: number }): ReplayExplorerPanelState {
  return Object.freeze({ ...BASE('replay-explorer', seq), replay_frame_count: p?.frameCount ?? 0, oldest_sequence: p?.oldestSeq ?? seq, newest_sequence: p?.newestSeq ?? seq })
}

export function buildWorkspaceTopologyPanel(seq: number, p?: { pathCount?: number; context?: string }): WorkspaceTopologyPanelState {
  return Object.freeze({ ...BASE('workspace-topology', seq), governed_path_count: p?.pathCount ?? 0, installation_context: (p?.context ?? 'development') as WorkspaceTopologyPanelState['installation_context'] })
}

export function buildAgentHabitatPanel(seq: number, p?: { activeAgents?: number; registeredAgents?: number; agentTypes?: readonly string[] }): AgentHabitatPanelState {
  return Object.freeze({ ...BASE('agent-habitat', seq), active_agent_count: p?.activeAgents ?? 0, registered_agent_count: p?.registeredAgents ?? 0, agent_types: Object.freeze(p?.agentTypes ?? []) as AgentHabitatPanelState['agent_types'] })
}

export function buildConstitutionalInvariantDashboard(seq: number, p?: { checked?: number; t0?: number; t1?: number }): ConstitutionalInvariantDashboardState {
  return Object.freeze({ ...BASE('constitutional-invariants', seq), checked_invariant_count: p?.checked ?? 0, t0_violations: p?.t0 ?? 0, t1_alerts: p?.t1 ?? 0 })
}

const EMPTY_TELEMETRY: AgentTelemetrySnapshot = Object.freeze({
  agent_coordination_stability: 1,
  workflow_replay_integrity: 1,
  workspace_memory_density: 0,
  extension_ecology_entropy: 0,
  mutation_chain_depth: 0,
  orchestration_pressure_index: 0,
})

export function buildTelemetryCockpit(seq: number, p?: { telemetry?: AgentTelemetrySnapshot; envEntropy?: number }): TelemetryCockpitState {
  return Object.freeze({ ...BASE('telemetry-cockpit', seq), agent_telemetry: p?.telemetry ?? EMPTY_TELEMETRY, env_entropy: p?.envEntropy ?? 0 })
}

export function buildCapabilityGovernanceSurface(seq: number, p?: { capabilityCount?: number; grantCount?: number }): CapabilityGovernanceSurfaceState {
  return Object.freeze({ ...BASE('capability-governance', seq), registered_capability_count: p?.capabilityCount ?? 0, active_grant_count: p?.grantCount ?? 0 })
}

export function buildExtensionEcologyView(seq: number, p?: { admitted?: number; evicted?: number }): ExtensionEcologyViewState {
  return Object.freeze({ ...BASE('extension-ecology', seq), admitted_plugin_count: p?.admitted ?? 0, evicted_plugin_count: p?.evicted ?? 0 })
}

export function buildMutationTimelinePanel(seq: number, p?: { totalMutations?: number; recentTypes?: readonly string[] }): MutationTimelinePanelState {
  return Object.freeze({ ...BASE('mutation-timeline', seq), total_mutations: p?.totalMutations ?? 0, recent_mutation_types: Object.freeze(p?.recentTypes ?? []) })
}

export function buildReplayIntegrityPanel(seq: number, p?: { ratio?: number; frameCount?: number }): ReplayIntegrityPanelState {
  return Object.freeze({ ...BASE('replay-integrity', seq), reconstruction_ratio: p?.ratio ?? 1, frame_count: p?.frameCount ?? 0 })
}

export function buildEnvironmentalDriftMonitor(seq: number, p?: { driftRate?: number; stabilityScore?: number; pressureIndex?: number }): EnvironmentalDriftMonitorState {
  return Object.freeze({ ...BASE('environmental-drift', seq), drift_rate: p?.driftRate ?? 0, stability_score: p?.stabilityScore ?? 1, pressure_index: p?.pressureIndex ?? 0 })
}

export function buildInitialIDERuntimeState(sequence: number): IDERuntimeState {
  return Object.freeze({
    replayExplorer: buildReplayExplorerPanel(sequence),
    workspaceTopology: buildWorkspaceTopologyPanel(sequence),
    agentHabitat: buildAgentHabitatPanel(sequence),
    constitutionalInvariants: buildConstitutionalInvariantDashboard(sequence),
    telemetryCockpit: buildTelemetryCockpit(sequence),
    capabilityGovernance: buildCapabilityGovernanceSurface(sequence),
    extensionEcology: buildExtensionEcologyView(sequence),
    mutationTimeline: buildMutationTimelinePanel(sequence),
    replayIntegrity: buildReplayIntegrityPanel(sequence),
    environmentalDrift: buildEnvironmentalDriftMonitor(sequence),
  })
}
