// ============================================================
// SOVEREIGN OMEGA — Cognitive Workflow Event Payloads (E5)
// EPISTEMIC TIER: T1
// Schema definitions for AI-mediated development events.
// These types make the development process itself replayable.
// Recording infrastructure is handled at the operator layer;
// this module defines the canonical payload schema.
// ============================================================

import type { SHA256Hex, CapabilityClass, UUIDv7 } from '../core/types.js'

// ─── E5 Payload Types ─────────────────────────────────────

/** Emitted when an agent proposes a patch to the codebase. */
export interface AgentPatchProposedPayload {
  readonly agent_id: string
  readonly agent_class: CapabilityClass
  readonly files_modified: readonly string[]      // paths relative to sovereign-omega-v2/
  readonly gate_required: number | null           // gate that must pass after this patch
  readonly tier_ceiling_violated: boolean         // true if tier check flagged a violation
  readonly diff_hash: SHA256Hex                   // RFC 8785 canonical hash of the diff
}

/** Emitted after a build gate runs — captures result for replay. */
export interface GateResultRecordedPayload {
  readonly gate_number: number
  readonly command: string
  readonly passed: boolean
  readonly pass_count: number
  readonly failure_output: string | null
  readonly decision: 'PROCEED' | 'HALT'
  readonly halt_reason: string | null
}

/** Emitted when an agent accesses a Drive corpus document. */
export interface CorpusNodeAccessedPayload {
  readonly agent_id: string
  readonly drive_file_id: string
  readonly document_name: string
  readonly epistemic_tier: 0 | 1 | 2 | 3 | 4 | 5
  readonly purpose: string  // why this document was accessed
}

/** Emitted when an agent delegates a task to a subagent. */
export interface SubagentDelegatedPayload {
  readonly delegating_agent_id: string
  readonly subagent_id: string
  readonly subagent_type: string               // e.g. 'Explore', 'claude-code-guide'
  readonly semantic_scope: readonly string[]   // file paths in declared authority scope
  readonly authority_class: CapabilityClass
  readonly task_hash: SHA256Hex                // canonical hash of the task prompt
}

/** Emitted when a subagent returns its result. */
export interface SubagentResultReceivedPayload {
  readonly subagent_id: string
  readonly parent_delegation_id: UUIDv7        // event_id of the SUBAGENT_DELEGATED event
  readonly succeeded: boolean
  readonly result_hash: SHA256Hex              // canonical hash of the result
  readonly files_affected: readonly string[]
}

/** Emitted when the Guardian agent is invoked. */
export interface GuardianInvokedPayload {
  readonly invoked_by: string
  readonly check_reason: string
  readonly files_under_review: readonly string[]
}

/** Emitted when the Guardian issues a verdict. */
export interface GuardianVerdictPayload {
  readonly verdict: 'APPROVED' | 'VETOED'
  readonly check_performed:
    | 'FROZEN_FILE_CHECK'
    | 'TIER_VIOLATION_CHECK'
    | 'GUARANTEE_INFLATION_CHECK'
    | 'GATE_PROTOCOL_CHECK'
  readonly location: string
  readonly reason: string
  readonly invocation_event_id: UUIDv7
}

/** Emitted when the semantic registry is queried. */
export interface SemanticNodeQueriedPayload {
  readonly query_type: 'lookupNode' | 'queryByGate' | 'queryByTier' | 'queryByMutationAuthority'
  readonly query_parameter: string
  readonly result_count: number
}
