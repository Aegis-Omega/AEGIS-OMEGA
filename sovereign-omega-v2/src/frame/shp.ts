// ============================================================
// SOVEREIGN OMEGA — Subatomic Holon Particle (SHP) Identity
// EPISTEMIC TIER: T0 · Gate 14 Lock
//
// Formal code expression of the SHP execution model.
// runFrame() IS the SHP: one loop, five phases, one commitment boundary.
//
// SITR = pre-commit constraint evaluator (ASSESS phase)
// AOIE = post-commit structural observer (PROPAGATE phase)
// Both are temporal projections of the same loop — separated by LOCK.
//
// Collapsing SITR+AOIE destroys the proof invariant:
//   pre-commit safety ≠ post-commit observation
// The boundary is not architectural preference; it is the causal boundary.
// ============================================================

import type { SITRState } from '../sitr/types.js'
import type { GlobalState } from '../aoie/types.js'
import type { ConstitutionalVerdict } from '../constitutional/types.js'
import type { FrameExecutionResult } from './types.js'

export const SHP_LOOP = 'R→A→L→P→H' as const
export const SHP_COMMITMENT_BOUNDARY = 'LOCK' as const

// Formal phase descriptor table — the SHP identity at T0
export const SHP_PHASES = Object.freeze({
  READ: Object.freeze({
    phase_number: 1,
    label: 'READ',
    domain: 'intake',
    pre_commit: true,
    post_commit: false,
    system: 'agents+ide',
  }),
  ASSESS: Object.freeze({
    phase_number: 3,
    label: 'ASSESS',
    domain: 'sitr',
    pre_commit: true,
    post_commit: false,
    system: 'sitr',
  }),
  LOCK: Object.freeze({
    phase_number: 4,
    label: 'LOCK',
    domain: 'enforcement',
    pre_commit: false,
    post_commit: false,
    system: 'enforcement',
  }),
  PROPAGATE: Object.freeze({
    phase_number: 5,
    label: 'PROPAGATE',
    domain: 'aoie',
    pre_commit: false,
    post_commit: true,
    system: 'aoie',
  }),
  HARMONIZE: Object.freeze({
    phase_number: 6,
    label: 'HARMONIZE',
    domain: 'constitutional',
    pre_commit: false,
    post_commit: true,
    system: 'constitutional+guardian',
  }),
} as const)

// ─── Ralph Loop Trace ─────────────────────────────────────

export interface RalphLoopTrace {
  readonly READ: { readonly frame_count: number }
  readonly ASSESS: { readonly sitr_state: SITRState; readonly directives_emitted: number }
  readonly LOCK: { readonly directives_applied: number; readonly directives_skipped: number }
  readonly PROPAGATE: { readonly aoie_global_state: GlobalState }
  readonly HARMONIZE: { readonly verdict: ConstitutionalVerdict }
  readonly loop: typeof SHP_LOOP
  readonly sequence: number
  readonly is_replay_reconstructable: true
}

/**
 * Map a FrameExecutionResult to its RALPH loop trace.
 * Expresses the SHP execution identity in observable form.
 */
export function toRalphTrace(result: FrameExecutionResult): Readonly<RalphLoopTrace> {
  const t = result.phase_trace
  return Object.freeze<RalphLoopTrace>({
    READ: Object.freeze({ frame_count: t.phase_1_frame_count }),
    ASSESS: Object.freeze({
      sitr_state: result.sitr.currentState(),
      directives_emitted: t.phase_3_directives_emitted,
    }),
    LOCK: Object.freeze({
      directives_applied: t.phase_4_directives_applied,
      directives_skipped: result.enforcement.directives_skipped,
    }),
    PROPAGATE: Object.freeze({ aoie_global_state: t.phase_5_aoie_global_state }),
    HARMONIZE: Object.freeze({ verdict: t.phase_6_verdict }),
    loop: SHP_LOOP,
    sequence: result.sequence,
    is_replay_reconstructable: true,
  })
}
