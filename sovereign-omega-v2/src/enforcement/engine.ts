// ============================================================
// SOVEREIGN OMEGA — Enforcement Engine
// EPISTEMIC TIER: T0 · Gate 14
//
// Phase 4 of the 7-phase frame execution contract.
// Deterministically evaluates ContainmentDirective[] against the
// current active agent and workflow sets; produces EnforcementResult
// as an E5-appendable audit record. Does NOT directly mutate
// agent or workflow state — all effects are downstream of E5 events.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import type { ContainmentDirective } from '../sitr/types.js'
import type { EnforcementDecision, EnforcementOutcome, EnforcementResult } from './types.js'
import { ENFORCEMENT_SCHEMA_VERSION } from './types.js'

function evaluateDirective(
  d: ContainmentDirective,
  activeAgentIds: readonly string[],
  activeWorkflowIds: readonly string[],
): EnforcementOutcome {
  if (d.action === 'quarantine_agent') {
    return activeAgentIds.includes(d.target_id) ? 'APPLIED' : 'SKIPPED'
  }
  if (d.action === 'freeze_workflow') {
    return activeWorkflowIds.includes(d.target_id) ? 'APPLIED' : 'SKIPPED'
  }
  // block_frame, invalidate_replay_chain, elevate_state are unconditional
  return 'APPLIED'
}

/**
 * Apply ContainmentDirective[] deterministically.
 * Same inputs always produce the same EnforcementResult.
 * Throws nothing — unknown targets produce SKIPPED, not errors.
 */
export function applyDirectives(
  directives: readonly ContainmentDirective[],
  activeAgentIds: readonly string[],
  activeWorkflowIds: readonly string[],
  sequence: number,
): EnforcementResult {
  const decisions: EnforcementDecision[] = []
  let applied = 0
  let skipped = 0

  for (const d of directives) {
    const outcome = evaluateDirective(d, activeAgentIds, activeWorkflowIds)
    decisions.push(deepFreeze<EnforcementDecision>({
      directive_id: d.directive_id,
      action: d.action,
      outcome,
      target_id: d.target_id,
      applied_at_sequence: sequence,
      is_replay_reconstructable: true,
    }))
    if (outcome === 'APPLIED') applied++
    else skipped++
  }

  return deepFreeze<EnforcementResult>({
    decisions: Object.freeze(decisions),
    directives_applied: applied,
    directives_skipped: skipped,
    sequence,
    is_replay_reconstructable: true,
    schema_version: ENFORCEMENT_SCHEMA_VERSION,
  })
}
