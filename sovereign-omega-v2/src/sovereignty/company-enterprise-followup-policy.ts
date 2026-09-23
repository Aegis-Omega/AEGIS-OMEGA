// AEGIS Enterprise Follow-up Policy V1
// Determines only whether a follow-up draft may be prepared.
// It never authorizes or sends an external message.

export type EnterpriseFollowupStopSignalV1 =
  | 'QUALIFYING_REPLY'
  | 'ANY_REPLY'
  | 'BOUNCE'
  | 'UNSUBSCRIBE'
  | 'CLOSED_LOST'

export interface EnterpriseFollowupInputV1 {
  readonly initial_sent_at: string
  readonly last_outbound_at: string
  readonly now: string
  readonly followups_sent: number
  readonly stop_signals: readonly EnterpriseFollowupStopSignalV1[]
}

export interface EnterpriseFollowupDecisionV1 {
  readonly status: 'DRAFT_ELIGIBLE' | 'NOT_ELIGIBLE'
  readonly reason:
    | 'WAIT_INTERVAL'
    | 'STOP_SIGNAL'
    | 'FOLLOWUP_LIMIT'
    | 'DRAFT_MAY_BE_PREPARED'
  readonly next_eligible_at: string | null
  readonly send_authority: 'NOT_GRANTED'
  readonly authority_effect: 'NONE'
}

const MIN_INTERVAL_MS = 72 * 60 * 60 * 1000
const MAX_FOLLOWUPS = 2

function timestamp(value: unknown, label: string): number {
  if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${label} must be non-empty`)
  const parsed = Date.parse(value)
  if (!Number.isFinite(parsed)) throw new TypeError(`${label} must be ISO-like timestamp`)
  return parsed
}

export function evaluateEnterpriseFollowupV1(
  input: EnterpriseFollowupInputV1,
): EnterpriseFollowupDecisionV1 {
  const initial = timestamp(input?.initial_sent_at, 'initial_sent_at')
  const last = timestamp(input?.last_outbound_at, 'last_outbound_at')
  const now = timestamp(input?.now, 'now')
  if (last < initial) throw new TypeError('last_outbound_at precedes initial_sent_at')
  if (now < last) throw new TypeError('now precedes last_outbound_at')
  if (!Number.isSafeInteger(input.followups_sent) || input.followups_sent < 0) {
    throw new TypeError('followups_sent must be a non-negative safe integer')
  }
  if (!Array.isArray(input.stop_signals)) throw new TypeError('stop_signals must be an array')
  const allowed: readonly EnterpriseFollowupStopSignalV1[] = [
    'QUALIFYING_REPLY','ANY_REPLY','BOUNCE','UNSUBSCRIBE','CLOSED_LOST',
  ]
  for (const signal of input.stop_signals) {
    if (!allowed.includes(signal)) throw new TypeError('invalid follow-up stop signal')
  }

  const base = {
    send_authority: 'NOT_GRANTED' as const,
    authority_effect: 'NONE' as const,
  }

  if (input.stop_signals.length > 0) {
    return Object.freeze({
      status:'NOT_ELIGIBLE' as const,
      reason:'STOP_SIGNAL' as const,
      next_eligible_at:null,
      ...base,
    })
  }

  if (input.followups_sent >= MAX_FOLLOWUPS) {
    return Object.freeze({
      status:'NOT_ELIGIBLE' as const,
      reason:'FOLLOWUP_LIMIT' as const,
      next_eligible_at:null,
      ...base,
    })
  }

  const next = last + MIN_INTERVAL_MS
  if (now < next) {
    return Object.freeze({
      status:'NOT_ELIGIBLE' as const,
      reason:'WAIT_INTERVAL' as const,
      next_eligible_at:new Date(next).toISOString(),
      ...base,
    })
  }

  return Object.freeze({
    status:'DRAFT_ELIGIBLE' as const,
    reason:'DRAFT_MAY_BE_PREPARED' as const,
    next_eligible_at:null,
    ...base,
  })
}
