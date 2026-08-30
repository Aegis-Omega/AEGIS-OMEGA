// ============================================================
// IDE Orchestrator — ties panel states to agent and environment state
// EPISTEMIC TIER: T1
// Immutable update pattern. Returns new orchestrator on update.
// No Date.now(). No side effects.
// ============================================================

import { deepFreeze } from '../../core/immutable'
import type { IDERuntimeState } from '../types'
import type { AgentType } from '../../agents/types'
import type { AgentTelemetrySnapshot } from '../../agents/telemetry/agent-telemetry'
import {
  buildReplayExplorerPanel,
  buildWorkspaceTopologyPanel,
  buildAgentHabitatPanel,
  buildConstitutionalInvariantDashboard,
  buildTelemetryCockpit,
  buildCapabilityGovernanceSurface,
  buildExtensionEcologyView,
  buildMutationTimelinePanel,
  buildReplayIntegrityPanel,
  buildEnvironmentalDriftMonitor,
  buildInitialIDERuntimeState,
} from '../panels/panel-state'

export interface OrchestratorUpdateParams {
  readonly agentTelemetry: AgentTelemetrySnapshot
  readonly envEntropy: number
  readonly mutationCount: number
  readonly recentMutationTypes: readonly string[]
  readonly driftRate: number
  readonly stabilityScore: number
  readonly pressureIndex: number
  readonly activeAgents: number
  readonly registeredAgents: number
  readonly activeAgentTypes: readonly AgentType[]
  readonly registeredCapabilities: number
  readonly activeGrants: number
  readonly admittedPlugins: number
  readonly evictedPlugins: number
  readonly replayFrameCount: number
  readonly replayIntegrityRatio: number
  readonly governedPathCount: number
  readonly checkedInvariants: number
  readonly t0Violations: number
  readonly t1Alerts: number
  readonly sequence: number
}

export class IDEOrchestrator {
  private readonly _state: IDERuntimeState

  private constructor(state: IDERuntimeState) {
    this._state = state
  }

  static create(sequence: number): IDEOrchestrator {
    return new IDEOrchestrator(deepFreeze(buildInitialIDERuntimeState(sequence)))
  }

  getState(): IDERuntimeState { return this._state }

  panelSequence(): number { return this._state.replayExplorer.last_updated_sequence }

  update(p: OrchestratorUpdateParams): IDEOrchestrator {
    const state: IDERuntimeState = deepFreeze({
      replayExplorer: buildReplayExplorerPanel(p.sequence, { frameCount: p.replayFrameCount, newestSeq: p.sequence }),
      workspaceTopology: buildWorkspaceTopologyPanel(p.sequence, { pathCount: p.governedPathCount }),
      agentHabitat: buildAgentHabitatPanel(p.sequence, { activeAgents: p.activeAgents, registeredAgents: p.registeredAgents, agentTypes: p.activeAgentTypes }),
      constitutionalInvariants: buildConstitutionalInvariantDashboard(p.sequence, { checked: p.checkedInvariants, t0: p.t0Violations, t1: p.t1Alerts }),
      telemetryCockpit: buildTelemetryCockpit(p.sequence, { telemetry: p.agentTelemetry, envEntropy: p.envEntropy }),
      capabilityGovernance: buildCapabilityGovernanceSurface(p.sequence, { capabilityCount: p.registeredCapabilities, grantCount: p.activeGrants }),
      extensionEcology: buildExtensionEcologyView(p.sequence, { admitted: p.admittedPlugins, evicted: p.evictedPlugins }),
      mutationTimeline: buildMutationTimelinePanel(p.sequence, { totalMutations: p.mutationCount, recentTypes: p.recentMutationTypes }),
      replayIntegrity: buildReplayIntegrityPanel(p.sequence, { ratio: p.replayIntegrityRatio, frameCount: p.replayFrameCount }),
      environmentalDrift: buildEnvironmentalDriftMonitor(p.sequence, { driftRate: p.driftRate, stabilityScore: p.stabilityScore, pressureIndex: p.pressureIndex }),
    })
    return new IDEOrchestrator(state)
  }
}
