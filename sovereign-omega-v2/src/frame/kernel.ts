// ============================================================
// SOVEREIGN OMEGA — Frame Execution Kernel
// EPISTEMIC TIER: T0 · Gate 14
//
// The canonical 7-phase deterministic frame execution kernel.
// runFrame() is the T0 expression of the holonic RALPH loop:
//
//   R (Read)      — phase 1: intake CoordinationFrame[] + telemetry
//   A (Assess)    — phase 3: SITR observe → detect violations, compute ΔS
//   L (Lock)      — phase 4: enforce directives, freeze enforcement result
//   P (Propagate) — phase 5: AOIE classify post-enforcement snapshot
//   H (Harmonize) — phase 6: Constitutional verdict → Guardian E5 events
//
// Same FrameInput always produces the same FrameExecutionResult.
// All separation boundaries (SITR|AOIE|CGS) are preserved — the
// kernel is composition, not collapse.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { classifyRuntime } from '../aoie/runtime.js'
import { applyDirectives } from '../enforcement/engine.js'
import { capturePostEnforcementSnapshot } from './snapshot.js'
import { computeAutoDirectives } from './directives.js'
import type { FrameInput, FrameExecutionResult, FramePhaseTrace } from './types.js'
import { FRAME_SCHEMA_VERSION } from './types.js'

/**
 * Execute one complete governance frame through all 7 phases.
 * Deterministic pure function: identical FrameInput → identical result.
 * Class instances (SITRRuntime, ConstitutionalRuntime) are returned
 * as updated immutable values — source instances are unchanged.
 */
export function runFrame(input: FrameInput): FrameExecutionResult {
  // Phase 3 — SITR constitutional evaluation
  const newSitr = input.sitr.observe({
    frames: input.frames,
    workflowFrames: input.workflowFrames,
    telemetry: input.telemetry,
    sequence: input.sequence,
  })

  // Phase 3→4 — auto-generate directives from frame violations
  const directives = computeAutoDirectives(
    input.frames,
    input.workflowFrames,
    input.sequence,
  )

  // Record directives in SITR runtime (E5 event tracking)
  let sitrWithDirectives = newSitr
  for (const d of directives) {
    sitrWithDirectives = sitrWithDirectives.issueDirective(d)
  }

  // Phase 4 — enforcement engine (deterministic directive application)
  const enforcement = applyDirectives(
    directives,
    input.activeAgentIds,
    input.activeWorkflowIds,
    input.sequence,
  )

  // Phase 5 — capture post-enforcement snapshot, then AOIE classify
  const postEnforcementSnapshot = capturePostEnforcementSnapshot({
    enforcement_result: enforcement,
    sitr_state: sitrWithDirectives.currentState(),
    panel_sequence_numbers: input.panelSequenceNumbers,
    sequence: input.sequence,
  })

  const aoie = classifyRuntime({
    snapshots: [postEnforcementSnapshot],
    mutations: input.mutations,
    assertions: input.assertions,
    sequence: input.sequence,
  })

  // Phase 6 — Constitutional Governance Surface
  const newConstitutional = input.constitutional.evaluate({
    sitr: sitrWithDirectives,
    aoie,
    invariantSnapshot: input.invariantSnapshot,
    sequence: input.sequence,
    decision_id: input.decision_id,
  })

  const phaseTrace = deepFreeze<FramePhaseTrace>({
    phase_1_frame_count: input.frames.length,
    phase_3_directives_emitted: directives.length,
    phase_4_directives_applied: enforcement.directives_applied,
    phase_5_aoie_global_state: aoie.global_state,
    phase_6_verdict: newConstitutional.currentVerdict(),
    sequence: input.sequence,
    is_replay_reconstructable: true,
  })

  // Shallow freeze: result contains class instances (SITRRuntime,
  // ConstitutionalRuntime) that manage their own immutability invariants.
  return Object.freeze<FrameExecutionResult>({
    sitr: sitrWithDirectives,
    constitutional: newConstitutional,
    aoie,
    enforcement,
    phase_trace: phaseTrace,
    sequence: input.sequence,
    is_replay_reconstructable: true,
    schema_version: FRAME_SCHEMA_VERSION,
  })
}
