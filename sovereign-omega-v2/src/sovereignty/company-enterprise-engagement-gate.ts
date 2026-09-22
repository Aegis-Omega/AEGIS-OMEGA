// AEGIS Enterprise Engagement Gate V1
// Pipeline progress is evidence, not commercial/legal authority.
// This gate can admit preparation or request an approval packet, never execute the action.

import type { EnterpriseOpportunityStageV1 } from './company-enterprise-opportunity.js'

export type EnterpriseEngagementActionV1 =
  | 'PREPARE_SCOPING_DRAFT'
  | 'SEND_SCOPING_MESSAGE'
  | 'PREPARE_SCOPE_DRAFT'
  | 'SEND_COMMERCIAL_TERMS'
  | 'REQUEST_PAYMENT'
  | 'START_AUDIT'

export type CommercialCapacityStateV1 =
  | 'VERIFIED'
  | 'NOT_VERIFIED'
  | 'INELIGIBLE'

export type CommercialTermsStateV1 =
  | 'NOT_DRAFTED'
  | 'DRAFTED'
  | 'REVIEWED'
  | 'AGREED'

export type DeliveryReadinessStateV1 =
  | 'NOT_READY'
  | 'READY'

export interface EnterpriseEngagementContextV1 {
  readonly opportunity_stage: EnterpriseOpportunityStageV1
  readonly commercial_capacity_state: CommercialCapacityStateV1
  readonly commercial_terms_state: CommercialTermsStateV1
  readonly delivery_readiness_state: DeliveryReadinessStateV1
}

export interface EnterpriseEngagementDecisionV1 {
  readonly action: EnterpriseEngagementActionV1
  readonly status:
    | 'PREPARATION_ADMITTED'
    | 'APPROVAL_PACKET_REQUIRED'
    | 'ACTION_ADMITTED_INTERNAL'
    | 'DENIED'
  readonly action_class:
    | 'DRAFT'
    | 'EXTERNAL_MESSAGE'
    | 'LEGAL_COMMITMENT'
    | 'FINANCIAL'
    | 'PROPOSE'
  readonly operator_grant_required: boolean
  readonly denial_code:
    | 'STAGE_NOT_READY'
    | 'COMMERCIAL_CAPACITY_NOT_VERIFIED'
    | 'COMMERCIAL_CAPACITY_INELIGIBLE'
    | 'TERMS_NOT_REVIEWED'
    | 'TERMS_NOT_AGREED'
    | 'DELIVERY_NOT_READY'
    | null
  readonly authority_effect: 'NONE'
}

const STAGE_RANK: Readonly<Record<EnterpriseOpportunityStageV1, number>> = {
  DISCOVERED: 0,
  CONTACTED: 1,
  QUALIFIED_REPLY: 2,
  SCOPING_CALL_HELD: 3,
  WRITTEN_SCOPE_AGREED: 4,
  PAYMENT_RECEIVED: 5,
  AUDIT_STARTED: 6,
  CLOSED_LOST: -1,
}

function decision(
  action: EnterpriseEngagementActionV1,
  status: EnterpriseEngagementDecisionV1['status'],
  action_class: EnterpriseEngagementDecisionV1['action_class'],
  operator_grant_required: boolean,
  denial_code: EnterpriseEngagementDecisionV1['denial_code'],
): EnterpriseEngagementDecisionV1 {
  return Object.freeze({
    action,
    status,
    action_class,
    operator_grant_required,
    denial_code,
    authority_effect: 'NONE',
  })
}

function stageAtLeast(
  actual: EnterpriseOpportunityStageV1,
  required: EnterpriseOpportunityStageV1,
): boolean {
  if (actual === 'CLOSED_LOST') return false
  return STAGE_RANK[actual] >= STAGE_RANK[required]
}

function capacityDenial(
  action: EnterpriseEngagementActionV1,
  actionClass: EnterpriseEngagementDecisionV1['action_class'],
  state: CommercialCapacityStateV1,
): EnterpriseEngagementDecisionV1 | null {
  if (state === 'INELIGIBLE') {
    return decision(action, 'DENIED', actionClass, false, 'COMMERCIAL_CAPACITY_INELIGIBLE')
  }
  if (state !== 'VERIFIED') {
    return decision(action, 'DENIED', actionClass, false, 'COMMERCIAL_CAPACITY_NOT_VERIFIED')
  }
  return null
}

export function evaluateEnterpriseEngagementV1(
  action: EnterpriseEngagementActionV1,
  ctx: EnterpriseEngagementContextV1,
): EnterpriseEngagementDecisionV1 {
  if (!(ctx.opportunity_stage in STAGE_RANK)) throw new TypeError('invalid opportunity_stage')
  if (!['VERIFIED','NOT_VERIFIED','INELIGIBLE'].includes(ctx.commercial_capacity_state)) {
    throw new TypeError('invalid commercial_capacity_state')
  }
  if (!['NOT_DRAFTED','DRAFTED','REVIEWED','AGREED'].includes(ctx.commercial_terms_state)) {
    throw new TypeError('invalid commercial_terms_state')
  }
  if (!['NOT_READY','READY'].includes(ctx.delivery_readiness_state)) {
    throw new TypeError('invalid delivery_readiness_state')
  }

  switch (action) {
    case 'PREPARE_SCOPING_DRAFT':
      if (!stageAtLeast(ctx.opportunity_stage, 'QUALIFIED_REPLY')) {
        return decision(action, 'DENIED', 'DRAFT', false, 'STAGE_NOT_READY')
      }
      return decision(action, 'PREPARATION_ADMITTED', 'DRAFT', false, null)

    case 'SEND_SCOPING_MESSAGE':
      if (!stageAtLeast(ctx.opportunity_stage, 'QUALIFIED_REPLY')) {
        return decision(action, 'DENIED', 'EXTERNAL_MESSAGE', false, 'STAGE_NOT_READY')
      }
      return decision(action, 'APPROVAL_PACKET_REQUIRED', 'EXTERNAL_MESSAGE', true, null)

    case 'PREPARE_SCOPE_DRAFT':
      if (!stageAtLeast(ctx.opportunity_stage, 'SCOPING_CALL_HELD')) {
        return decision(action, 'DENIED', 'DRAFT', false, 'STAGE_NOT_READY')
      }
      return decision(action, 'PREPARATION_ADMITTED', 'DRAFT', false, null)

    case 'SEND_COMMERCIAL_TERMS': {
      if (!stageAtLeast(ctx.opportunity_stage, 'SCOPING_CALL_HELD')) {
        return decision(action, 'DENIED', 'LEGAL_COMMITMENT', false, 'STAGE_NOT_READY')
      }
      const cap = capacityDenial(action, 'LEGAL_COMMITMENT', ctx.commercial_capacity_state)
      if (cap) return cap
      if (!['REVIEWED','AGREED'].includes(ctx.commercial_terms_state)) {
        return decision(action, 'DENIED', 'LEGAL_COMMITMENT', false, 'TERMS_NOT_REVIEWED')
      }
      return decision(action, 'APPROVAL_PACKET_REQUIRED', 'LEGAL_COMMITMENT', true, null)
    }

    case 'REQUEST_PAYMENT': {
      if (!stageAtLeast(ctx.opportunity_stage, 'WRITTEN_SCOPE_AGREED')) {
        return decision(action, 'DENIED', 'FINANCIAL', false, 'STAGE_NOT_READY')
      }
      const cap = capacityDenial(action, 'FINANCIAL', ctx.commercial_capacity_state)
      if (cap) return cap
      if (ctx.commercial_terms_state !== 'AGREED') {
        return decision(action, 'DENIED', 'FINANCIAL', false, 'TERMS_NOT_AGREED')
      }
      return decision(action, 'APPROVAL_PACKET_REQUIRED', 'FINANCIAL', true, null)
    }

    case 'START_AUDIT':
      if (!stageAtLeast(ctx.opportunity_stage, 'PAYMENT_RECEIVED')) {
        return decision(action, 'DENIED', 'PROPOSE', false, 'STAGE_NOT_READY')
      }
      if (ctx.commercial_terms_state !== 'AGREED') {
        return decision(action, 'DENIED', 'PROPOSE', false, 'TERMS_NOT_AGREED')
      }
      if (ctx.delivery_readiness_state !== 'READY') {
        return decision(action, 'DENIED', 'PROPOSE', false, 'DELIVERY_NOT_READY')
      }
      return decision(action, 'ACTION_ADMITTED_INTERNAL', 'PROPOSE', false, null)

    default:
      throw new TypeError('invalid enterprise engagement action')
  }
}
