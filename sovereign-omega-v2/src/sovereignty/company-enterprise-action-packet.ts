// AEGIS Enterprise Consequential Packet Binding V1
// Converts an admitted enterprise engagement action into the existing exact
// ConsequentialActionPacketV1. It grants no authority and performs no side effect.

import {
  createConsequentialActionPacketV1,
  type ConsequentialActionPacketV1,
  type ConsequentialActionClassV1,
} from './company-approval-packet.js'
import {
  evaluateEnterpriseEngagementV1,
  type EnterpriseEngagementContextV1,
} from './company-enterprise-engagement-gate.js'

export type EnterprisePacketActionV1 =
  | 'SEND_SCOPING_MESSAGE'
  | 'SEND_COMMERCIAL_TERMS'
  | 'REQUEST_PAYMENT'

export interface EnterpriseConsequentialPacketInputV1 {
  readonly packet_id: string
  readonly task_id: string
  readonly opportunity_id: string
  readonly action: EnterprisePacketActionV1
  readonly context: EnterpriseEngagementContextV1
  readonly exact_target: string
  readonly exact_action_summary: string
  readonly reason: string
  readonly evidence_refs: readonly string[]
  readonly commercial_terms_digest: string | null
  readonly requested_amount_minor_units: number | null
  readonly requested_currency: string | null
  readonly rollback: string
  readonly created_generation: string
  readonly expires_generation: string
}

function text(value: unknown, label: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${label} must be non-empty`)
  return value
}

function sha(value: unknown, label: string): string {
  if (typeof value !== 'string' || !/^[0-9a-f]{64}$/.test(value)) {
    throw new TypeError(`${label} must be lowercase SHA-256 hex`)
  }
  return value
}

function money(
  amount: number | null,
  currency: string | null,
  required: boolean,
): { amount: number | null; currency: string | null } {
  if (!required) {
    if (amount !== null || currency !== null) {
      throw new TypeError('requested amount is only valid for REQUEST_PAYMENT')
    }
    return { amount: null, currency: null }
  }
  if (
    typeof amount !== 'number' ||
    !Number.isSafeInteger(amount) ||
    amount <= 0
  ) throw new TypeError('REQUEST_PAYMENT requires positive safe integer amount')
  if (typeof currency !== 'string' || !/^[A-Z]{3}$/.test(currency)) {
    throw new TypeError('REQUEST_PAYMENT requires uppercase 3-letter currency')
  }
  return { amount, currency }
}

export async function createEnterpriseConsequentialPacketV1(
  input: EnterpriseConsequentialPacketInputV1,
  hash: (domain: string, value: unknown) => Promise<string>,
): Promise<{
  readonly packet: ConsequentialActionPacketV1
  readonly packet_digest: string
  readonly enterprise_binding: Readonly<{
    opportunity_id: string
    opportunity_stage: EnterpriseEngagementContextV1['opportunity_stage']
    enterprise_action: EnterprisePacketActionV1
    commercial_terms_digest: string | null
    requested_amount_minor_units: number | null
    requested_currency: string | null
    authority_effect: 'NONE'
  }>
}> {
  const opportunity_id = text(input?.opportunity_id, 'opportunity_id')
  const exactTarget = text(input?.exact_target, 'exact_target')
  const summary = text(input?.exact_action_summary, 'exact_action_summary')
  const reason = text(input?.reason, 'reason')
  const rollback = text(input?.rollback, 'rollback')
  if (!Array.isArray(input.evidence_refs) || input.evidence_refs.length === 0) {
    throw new TypeError('evidence_refs must be non-empty')
  }
  const evidence = input.evidence_refs.map((ref) => text(ref, 'evidence_ref'))
  if (new Set(evidence).size !== evidence.length) throw new TypeError('duplicate evidence_ref')

  if (!['SEND_SCOPING_MESSAGE','SEND_COMMERCIAL_TERMS','REQUEST_PAYMENT'].includes(input.action)) {
    throw new TypeError('invalid enterprise packet action')
  }

  const engagement = evaluateEnterpriseEngagementV1(input.action, input.context)
  if (
    engagement.status !== 'APPROVAL_PACKET_REQUIRED' ||
    !engagement.operator_grant_required
  ) {
    throw new Error(`ENTERPRISE_ACTION_NOT_PACKET_ELIGIBLE:${engagement.denial_code ?? engagement.status}`)
  }

  let consequentialClass: ConsequentialActionClassV1
  switch (engagement.action_class) {
    case 'EXTERNAL_MESSAGE':
      consequentialClass = 'EXTERNAL_MESSAGE'
      break
    case 'LEGAL_COMMITMENT':
      consequentialClass = 'LEGAL_COMMITMENT'
      break
    case 'FINANCIAL':
      consequentialClass = 'FINANCIAL'
      break
    default:
      throw new Error(`ENTERPRISE_ACTION_CLASS_NOT_CONSEQUENTIAL:${engagement.action_class}`)
  }

  const requiresTerms = input.action === 'SEND_COMMERCIAL_TERMS' || input.action === 'REQUEST_PAYMENT'
  const commercialTermsDigest = requiresTerms
    ? sha(input.commercial_terms_digest, 'commercial_terms_digest')
    : null
  if (!requiresTerms && input.commercial_terms_digest !== null) {
    throw new TypeError('commercial_terms_digest not valid for scoping message')
  }

  const requested = money(
    input.requested_amount_minor_units,
    input.requested_currency,
    input.action === 'REQUEST_PAYMENT',
  )

  const bindingRefs = [
    ...evidence,
    `opportunity:${opportunity_id}`,
    `opportunity_stage:${input.context.opportunity_stage}`,
    ...(commercialTermsDigest ? [`commercial_terms_sha256:${commercialTermsDigest}`] : []),
  ]

  const actionText = input.action === 'REQUEST_PAYMENT'
    ? `${summary}; requested_amount_minor_units=${requested.amount}; requested_currency=${requested.currency}`
    : summary

  const created = await createConsequentialActionPacketV1({
    packet_id: text(input.packet_id, 'packet_id'),
    task_id: text(input.task_id, 'task_id'),
    action_class: consequentialClass,
    target: exactTarget,
    action: actionText,
    reason,
    evidence_refs: bindingRefs,
    risk_class: input.action === 'SEND_SCOPING_MESSAGE' ? 'LOW' : 'MEDIUM',
    cost_class: 'NONE',
    max_cost_minor_units: null,
    currency: null,
    rollback,
    created_generation: text(input.created_generation, 'created_generation'),
    expires_generation: text(input.expires_generation, 'expires_generation'),
  }, hash)

  return Object.freeze({
    ...created,
    enterprise_binding: Object.freeze({
      opportunity_id,
      opportunity_stage: input.context.opportunity_stage,
      enterprise_action: input.action,
      commercial_terms_digest: commercialTermsDigest,
      requested_amount_minor_units: requested.amount,
      requested_currency: requested.currency,
      authority_effect: 'NONE' as const,
    }),
  })
}
