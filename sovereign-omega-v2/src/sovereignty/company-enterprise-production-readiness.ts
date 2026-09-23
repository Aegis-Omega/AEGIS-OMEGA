// AEGIS Enterprise Production Readiness Gate V1
// Prevents source completeness from being promoted into production readiness.

export type ReadinessStateV1 = 'PASS' | 'FAIL' | 'NOT_OBSERVED'
export type AppliedStateV1 = 'APPLIED' | 'NOT_APPLIED' | 'UNKNOWN'
export type CommercialCapacityV1 = 'VERIFIED' | 'NOT_VERIFIED' | 'INELIGIBLE'
export type CrmWriteStateV1 = 'AVAILABLE' | 'REQUIRES_REAUTHORIZATION' | 'NOT_AVAILABLE'

export interface EnterpriseProductionReadinessInputV1 {
  readonly exact_head_execution_receipt: ReadinessStateV1
  readonly openai_live_canary: ReadinessStateV1
  readonly scale_os_runtime_v2: AppliedStateV1
  readonly opportunity_persistence_v1: AppliedStateV1
  readonly resource_persistence_v1: AppliedStateV1
  readonly enterprise_event_immutability_guard_v1: AppliedStateV1
  readonly enterprise_event_insert_guard_v1: AppliedStateV1
  readonly commercial_capacity_state: CommercialCapacityV1
  readonly crm_sync_required: boolean
  readonly crm_write_state: CrmWriteStateV1
  readonly default_external_message_authority: 'NOT_GRANTED'
  readonly default_financial_authority: 'NOT_GRANTED'
  readonly default_legal_authority: 'NOT_GRANTED'
}

export type EnterpriseProductionBlockerV1 =
  | 'EXACT_HEAD_EXECUTION_NOT_VERIFIED'
  | 'EXACT_HEAD_EXECUTION_FAILED'
  | 'OPENAI_LIVE_CANARY_NOT_VERIFIED'
  | 'OPENAI_LIVE_CANARY_FAILED'
  | 'SCALE_OS_RUNTIME_V2_NOT_APPLIED'
  | 'OPPORTUNITY_PERSISTENCE_NOT_APPLIED'
  | 'RESOURCE_PERSISTENCE_NOT_APPLIED'
  | 'ENTERPRISE_EVENT_IMMUTABILITY_GUARD_NOT_APPLIED'
  | 'ENTERPRISE_EVENT_INSERT_GUARD_NOT_APPLIED'
  | 'COMMERCIAL_CAPACITY_NOT_VERIFIED'
  | 'COMMERCIAL_CAPACITY_INELIGIBLE'
  | 'CRM_WRITE_REAUTHORIZATION_REQUIRED'
  | 'CRM_WRITE_NOT_AVAILABLE'

export interface EnterpriseProductionReadinessDecisionV1 {
  readonly status: 'PRODUCTION_READY' | 'PRODUCTION_NOT_READY'
  readonly blockers: readonly EnterpriseProductionBlockerV1[]
  readonly consequential_authority_defaults_preserved: true
  readonly authority_effect: 'NONE'
}

function assertEnum<T extends string>(value: unknown, allowed: readonly T[], label: string): asserts value is T {
  if (typeof value !== 'string' || !allowed.includes(value as T)) throw new TypeError(`invalid ${label}`)
}

export function evaluateEnterpriseProductionReadinessV1(
  input: EnterpriseProductionReadinessInputV1,
): EnterpriseProductionReadinessDecisionV1 {
  assertEnum(input.exact_head_execution_receipt,['PASS','FAIL','NOT_OBSERVED'],'exact_head_execution_receipt')
  assertEnum(input.openai_live_canary,['PASS','FAIL','NOT_OBSERVED'],'openai_live_canary')
  for (const [label,value] of [
    ['scale_os_runtime_v2',input.scale_os_runtime_v2],
    ['opportunity_persistence_v1',input.opportunity_persistence_v1],
    ['resource_persistence_v1',input.resource_persistence_v1],
    ['enterprise_event_immutability_guard_v1',input.enterprise_event_immutability_guard_v1],
    ['enterprise_event_insert_guard_v1',input.enterprise_event_insert_guard_v1],
  ] as const) assertEnum(value,['APPLIED','NOT_APPLIED','UNKNOWN'],label)
  assertEnum(input.commercial_capacity_state,['VERIFIED','NOT_VERIFIED','INELIGIBLE'],'commercial_capacity_state')
  assertEnum(input.crm_write_state,['AVAILABLE','REQUIRES_REAUTHORIZATION','NOT_AVAILABLE'],'crm_write_state')

  if (
    input.default_external_message_authority !== 'NOT_GRANTED' ||
    input.default_financial_authority !== 'NOT_GRANTED' ||
    input.default_legal_authority !== 'NOT_GRANTED'
  ) throw new Error('CONSEQUENTIAL_DEFAULT_AUTHORITY_WIDENED')

  const blockers: EnterpriseProductionBlockerV1[]=[]

  if(input.exact_head_execution_receipt==='FAIL') blockers.push('EXACT_HEAD_EXECUTION_FAILED')
  else if(input.exact_head_execution_receipt!=='PASS') blockers.push('EXACT_HEAD_EXECUTION_NOT_VERIFIED')

  if(input.openai_live_canary==='FAIL') blockers.push('OPENAI_LIVE_CANARY_FAILED')
  else if(input.openai_live_canary!=='PASS') blockers.push('OPENAI_LIVE_CANARY_NOT_VERIFIED')

  if(input.scale_os_runtime_v2!=='APPLIED') blockers.push('SCALE_OS_RUNTIME_V2_NOT_APPLIED')
  if(input.opportunity_persistence_v1!=='APPLIED') blockers.push('OPPORTUNITY_PERSISTENCE_NOT_APPLIED')
  if(input.resource_persistence_v1!=='APPLIED') blockers.push('RESOURCE_PERSISTENCE_NOT_APPLIED')
  if(input.enterprise_event_immutability_guard_v1!=='APPLIED') blockers.push('ENTERPRISE_EVENT_IMMUTABILITY_GUARD_NOT_APPLIED')
  if(input.enterprise_event_insert_guard_v1!=='APPLIED') blockers.push('ENTERPRISE_EVENT_INSERT_GUARD_NOT_APPLIED')

  if(input.commercial_capacity_state==='INELIGIBLE') blockers.push('COMMERCIAL_CAPACITY_INELIGIBLE')
  else if(input.commercial_capacity_state!=='VERIFIED') blockers.push('COMMERCIAL_CAPACITY_NOT_VERIFIED')

  if(input.crm_sync_required){
    if(input.crm_write_state==='REQUIRES_REAUTHORIZATION') blockers.push('CRM_WRITE_REAUTHORIZATION_REQUIRED')
    else if(input.crm_write_state!=='AVAILABLE') blockers.push('CRM_WRITE_NOT_AVAILABLE')
  }

  return Object.freeze({
    status:blockers.length===0?'PRODUCTION_READY':'PRODUCTION_NOT_READY',
    blockers:Object.freeze(blockers),
    consequential_authority_defaults_preserved:true,
    authority_effect:'NONE',
  })
}
