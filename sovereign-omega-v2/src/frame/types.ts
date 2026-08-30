// ============================================================
// SOVEREIGN OMEGA — Frame Execution Types
// EPISTEMIC TIER: T0 · Gate 14
//
// Types for the canonical 7-phase frame execution kernel.
// FrameExecutionResult is the replay unit: same FrameInput
// always produces the same FrameExecutionResult.
// ============================================================

import type { SITRRuntime } from '../sitr/runtime.js'
import type { AOIEClassification, GlobalState, PolicyMutation, EpistemicAssertion } from '../aoie/types.js'
import type { ConstitutionalRuntime } from '../constitutional/runtime.js'
import type { ConstitutionalVerdict } from '../constitutional/types.js'
import type { CoordinationFrame } from '../agents/types.js'
import type { WorkflowReplayFrame } from '../agents/workflows/types.js'
import type { AgentTelemetrySnapshot } from '../agents/telemetry/agent-telemetry.js'
import type { RuntimeSnapshot as InvariantRuntimeSnapshot } from '../core/invariant-checker.js'
import type { EnforcementResult } from '../enforcement/types.js'

export const FRAME_SCHEMA_VERSION = '1.0.0' as const

// ─── Frame Input ───────────────────────────────────────────
// All state needed to execute one governance frame.
// Both sitr and constitutional are immutable runtimes — each
// runFrame() call returns updated instances without mutating inputs.

export interface FrameInput {
  readonly sitr: SITRRuntime
  readonly constitutional: ConstitutionalRuntime
  readonly frames: readonly CoordinationFrame[]
  readonly workflowFrames: readonly WorkflowReplayFrame[]
  readonly telemetry: AgentTelemetrySnapshot
  readonly mutations: readonly PolicyMutation[]
  readonly assertions: readonly EpistemicAssertion[]
  readonly invariantSnapshot: InvariantRuntimeSnapshot
  readonly activeAgentIds: readonly string[]
  readonly activeWorkflowIds: readonly string[]
  readonly panelSequenceNumbers: readonly number[]
  readonly sequence: number
  readonly decision_id: string
}

// ─── Phase Trace ───────────────────────────────────────────
// Observability record for each frame's 7-phase execution.

export interface FramePhaseTrace {
  readonly phase_1_frame_count: number
  readonly phase_3_directives_emitted: number
  readonly phase_4_directives_applied: number
  readonly phase_5_aoie_global_state: GlobalState
  readonly phase_6_verdict: ConstitutionalVerdict
  readonly sequence: number
  readonly is_replay_reconstructable: true
}

// ─── Frame Execution Result ────────────────────────────────

export interface FrameExecutionResult {
  readonly sitr: SITRRuntime
  readonly constitutional: ConstitutionalRuntime
  readonly aoie: AOIEClassification
  readonly enforcement: EnforcementResult
  readonly phase_trace: FramePhaseTrace
  readonly sequence: number
  readonly is_replay_reconstructable: true
  readonly schema_version: typeof FRAME_SCHEMA_VERSION
}
