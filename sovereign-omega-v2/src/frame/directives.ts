// ============================================================
// SOVEREIGN OMEGA — Auto-Directive Generator (Phase 3→4 Bridge)
// EPISTEMIC TIER: T0 · Gate 14
//
// Pure function. Inspects CoordinationFrame[] and WorkflowReplayFrame[]
// for constitutional violations detected in phase 3 (SITR), then
// generates the minimal ContainmentDirective[] to feed phase 4
// (enforcement engine). Directive IDs are deterministic — FNV-1a
// of (sequence:action:target_id). No UUIDv7, no Date.now().
// ============================================================

import type { ContainmentDirective } from '../sitr/types.js'
import type { CoordinationFrame } from '../agents/types.js'
import type { WorkflowReplayFrame } from '../agents/workflows/types.js'

function fnv1a32(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619) >>> 0
  }
  return h >>> 0
}

function directiveId(seq: number, action: string, targetId: string): string {
  return `dir-${fnv1a32(`${seq}:${action}:${targetId}`).toString(16).padStart(8, '0')}`
}

/**
 * Compute ContainmentDirective[] from phase-1 frame data.
 * Non-replay-safe coordination frames → quarantine the issuing agent.
 * Workflow frames with invariant_satisfied=false → invalidate replay chain.
 * Pure function — same inputs always produce identical directives.
 */
export function computeAutoDirectives(
  frames: readonly CoordinationFrame[],
  workflowFrames: readonly WorkflowReplayFrame[],
  sequence: number,
): readonly ContainmentDirective[] {
  const directives: ContainmentDirective[] = []

  for (const f of frames) {
    if (!f.replay_safe) {
      directives.push(Object.freeze<ContainmentDirective>({
        directive_id: directiveId(sequence, 'quarantine_agent', f.agent_id),
        sequence,
        action: 'quarantine_agent',
        target_id: f.agent_id,
        reason: `Frame ${f.frame_id} is not replay-safe`,
        is_replay_reconstructable: true,
      }))
    }
  }

  for (const wf of workflowFrames) {
    if (!wf.invariant_satisfied) {
      directives.push(Object.freeze<ContainmentDirective>({
        directive_id: directiveId(sequence, 'invalidate_replay_chain', wf.workflow_id),
        sequence,
        action: 'invalidate_replay_chain',
        target_id: wf.workflow_id,
        reason: `Workflow frame ${wf.frame_id} invariant not satisfied`,
        is_replay_reconstructable: true,
      }))
    }
  }

  return Object.freeze(directives)
}
