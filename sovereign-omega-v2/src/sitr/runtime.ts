// ============================================================
// SITR Runtime — main entry point for constitutional defense
// EPISTEMIC TIER: T0 (immune system; monotonic state enforcement)
// Immutable functional update. No de-escalation via observe().
// Directives are E5 events; enforcement engine applies them.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import type { CoordinationFrame } from '../agents/types.js'
import type { WorkflowReplayFrame } from '../agents/workflows/types.js'
import type { AgentTelemetrySnapshot } from '../agents/telemetry/agent-telemetry.js'
import type {
  SITRState, ContainmentDirective, InterventionRecord,
  ReplayViolation, SITRTelemetrySnapshot,
} from './types.js'
import { InterventionLog } from './intervention.js'
import { ReplayViolationLog } from './replay.js'
import { escalate } from './lattice.js'
import { buildSITRTelemetry } from './telemetry.js'
import { detectOrchestrationAnomalies, anomalyToRequiredState } from './orchestration.js'

export class SITRRuntime {
  private readonly _state: SITRState
  private readonly _interventions: InterventionLog
  private readonly _violations: ReplayViolationLog
  private readonly _directives: readonly ContainmentDirective[]
  private readonly _sequenceCount: number

  private constructor(
    state: SITRState,
    interventions: InterventionLog,
    violations: ReplayViolationLog,
    directives: readonly ContainmentDirective[],
    sequenceCount: number,
  ) {
    this._state = state
    this._interventions = interventions
    this._violations = violations
    this._directives = directives
    this._sequenceCount = sequenceCount
  }

  static empty(): SITRRuntime {
    return new SITRRuntime('STABLE', InterventionLog.empty(), ReplayViolationLog.empty(), deepFreeze([]), 0)
  }

  currentState(): SITRState { return this._state }
  interventions(): readonly InterventionRecord[] { return this._interventions.getAll() }
  violations(): readonly ReplayViolation[] { return this._violations.getAll() }

  telemetry(): SITRTelemetrySnapshot {
    return buildSITRTelemetry({
      currentState: this._state,
      interventionCount: this._interventions.length,
      containmentActionsTaken: this._directives.length,
      replayViolationsDetected: this._violations.violationCount,
      orchestrationAnomaliesDetected: 0,
      totalSequences: this._sequenceCount,
    })
  }

  observe(params: {
    frames: readonly CoordinationFrame[]
    workflowFrames: readonly WorkflowReplayFrame[]
    telemetry: AgentTelemetrySnapshot
    sequence: number
  }): SITRRuntime {
    let nextState: SITRState = this._state
    let nextViolations = this._violations

    const anomalies = detectOrchestrationAnomalies(params.frames, params.sequence)
    for (const a of anomalies) {
      nextState = escalate(nextState, anomalyToRequiredState(a))
    }

    for (const wf of params.workflowFrames) {
      if (!wf.invariant_satisfied) {
        nextState = escalate(nextState, 'UNSTABLE')
        nextViolations = nextViolations.record(deepFreeze({
          violation_id: `viol-${wf.frame_id}`,
          sequence: params.sequence,
          violation_type: 'invariant_not_satisfied',
          affected_workflow_id: wf.workflow_id,
          affected_frame_id: wf.frame_id,
        }))
      }
    }

    if (params.telemetry.workflow_replay_integrity < 1) {
      nextState = escalate(nextState, 'DEGRADED')
    }
    if (params.telemetry.orchestration_pressure_index > 0.9) {
      nextState = escalate(nextState, 'DEGRADED')
    }

    return new SITRRuntime(
      nextState,
      this._interventions,
      nextViolations,
      this._directives,
      this._sequenceCount + 1,
    )
  }

  issueDirective(d: ContainmentDirective): SITRRuntime {
    return new SITRRuntime(
      this._state,
      this._interventions,
      this._violations,
      deepFreeze([...this._directives, deepFreeze(d)]),
      this._sequenceCount,
    )
  }
}
