// ============================================================
// SOVEREIGN OMEGA — Guardian Event Payload Builder
// EPISTEMIC TIER: T0 · Gate 13
//
// Pure factory functions. Produce E5-appendable Guardian event
// payloads from constitutional verdict decisions.
// These payloads are downstream of SITRRuntime (phase 3) and
// AOIE classification (phase 5); they flow into E5 as phase-6 events.
// ============================================================

import type { GuardianInvokedPayload, GuardianVerdictPayload } from '../event/workflow.js'
import type { UUIDv7 } from '../core/types.js'
import type { ConstitutionalVerdict } from './types.js'

/**
 * PERMIT and DEFER both allow the system to continue operating.
 * REJECT and ESCALATE produce a VETOED verdict in E5.
 */
export function verdictToGuardianOutcome(v: ConstitutionalVerdict): 'APPROVED' | 'VETOED' {
  return v === 'PERMIT' || v === 'DEFER' ? 'APPROVED' : 'VETOED'
}

/**
 * Build a GuardianInvokedPayload for E5 append (phase 6).
 * Represents the constitutional assembly requesting a governance check.
 */
export function buildGuardianInvokedPayload(params: {
  readonly invoked_by: string
  readonly check_reason: string
  readonly files_under_review: readonly string[]
}): GuardianInvokedPayload {
  return Object.freeze({
    invoked_by: params.invoked_by,
    check_reason: params.check_reason,
    files_under_review: Object.freeze([...params.files_under_review]),
  })
}

/**
 * Build a GuardianVerdictPayload for E5 append (phase 6).
 * Maps a ConstitutionalVerdict to the canonical Guardian verdict schema.
 */
export function buildGuardianVerdictPayload(params: {
  readonly verdict: ConstitutionalVerdict
  readonly location: string
  readonly reason: string
  readonly invocation_event_id: UUIDv7
}): GuardianVerdictPayload {
  return Object.freeze({
    verdict: verdictToGuardianOutcome(params.verdict),
    check_performed: 'GATE_PROTOCOL_CHECK' as const,
    location: params.location,
    reason: params.reason,
    invocation_event_id: params.invocation_event_id,
  })
}
