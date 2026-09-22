// AEGIS Enterprise Resource Admission V1
// Offers and credits are evidence-bearing resources, not authority.
// Offered or claimed resources cannot be budgeted until activation is evidenced.

export type EnterpriseResourceClassV1 =
  | 'API_CREDIT'
  | 'CLOUD_CREDIT'
  | 'PROGRAM_ACCESS'
  | 'TRIAL_EXTENSION'
  | 'CONDITIONAL_REWARD'

export type EnterpriseResourceStateV1 =
  | 'OFFERED'
  | 'CLAIMED'
  | 'ACTIVE'
  | 'EXPIRED'
  | 'REJECTED'

export type EnterpriseResourceEvidenceAuthorityV1 =
  | 'DIRECT_OBSERVATION'
  | 'PROVIDER_ATTESTATION'
  | 'DERIVED_FROM_VERIFIED'
  | 'UNVERIFIED'

export type EnterpriseResourceTermsStateV1 =
  | 'REVIEWED'
  | 'NOT_REVIEWED'
  | 'NOT_APPLICABLE'

export type EnterpriseResourceActionV1 =
  | 'RESEARCH_TERMS'
  | 'RECORD_OFFER'
  | 'CLAIM_RESOURCE'
  | 'ADD_PAYMENT_METHOD'
  | 'ACTIVATE_PAID_PLAN'

export interface EnterpriseResourceV1 {
  readonly resource_id: string
  readonly provider: string
  readonly resource_class: EnterpriseResourceClassV1
  readonly state: EnterpriseResourceStateV1
  readonly evidence_authority: EnterpriseResourceEvidenceAuthorityV1
  readonly known_value_minor_units: number | null
  readonly currency: string | null
  readonly terms_state: EnterpriseResourceTermsStateV1
  readonly activation_requires_payment_method: boolean | null
  readonly expires_generation: string | null
}

export interface EnterpriseResourceAdmissionV1 {
  readonly resource_id: string
  readonly provider: string
  readonly state: EnterpriseResourceStateV1
  readonly usable_for_budgeting: boolean
  readonly admitted_value_minor_units: number | null
  readonly currency: string | null
  readonly claim_or_activation_authority: 'NOT_GRANTED'
  readonly reason: string
  readonly authority_effect: 'NONE'
}

function text(value: unknown,label: string): string {
  if (typeof value!=='string'||!value.trim()) throw new TypeError(`${label} must be non-empty`)
  return value
}

function generation(value: unknown,label: string): bigint {
  const parsed=BigInt(text(value,label))
  if(parsed<0n) throw new TypeError(`${label} must be non-negative`)
  return parsed
}

export function admitEnterpriseResourceV1(
  input: EnterpriseResourceV1,
  currentGeneration: string,
): EnterpriseResourceAdmissionV1 {
  const resource_id=text(input?.resource_id,'resource_id')
  const provider=text(input?.provider,'provider')
  const current=generation(currentGeneration,'current_generation')
  if(!['API_CREDIT','CLOUD_CREDIT','PROGRAM_ACCESS','TRIAL_EXTENSION','CONDITIONAL_REWARD'].includes(input.resource_class)) {
    throw new TypeError('invalid resource_class')
  }
  if(!['OFFERED','CLAIMED','ACTIVE','EXPIRED','REJECTED'].includes(input.state)) throw new TypeError('invalid resource state')
  if(!['DIRECT_OBSERVATION','PROVIDER_ATTESTATION','DERIVED_FROM_VERIFIED','UNVERIFIED'].includes(input.evidence_authority)) {
    throw new TypeError('invalid evidence_authority')
  }
  if(!['REVIEWED','NOT_REVIEWED','NOT_APPLICABLE'].includes(input.terms_state)) throw new TypeError('invalid terms_state')
  if(input.activation_requires_payment_method!==null && typeof input.activation_requires_payment_method!=='boolean') {
    throw new TypeError('activation_requires_payment_method must be boolean or null')
  }
  if(input.known_value_minor_units===null) {
    if(input.currency!==null) throw new TypeError('currency requires known monetary value')
  } else {
    if(!Number.isSafeInteger(input.known_value_minor_units)||input.known_value_minor_units<0) throw new TypeError('invalid known_value_minor_units')
    if(typeof input.currency!=='string'||!/^[A-Z]{3}$/.test(input.currency)) throw new TypeError('currency must be ISO-like uppercase code')
  }

  let expired=false
  if(input.expires_generation!==null) expired=current>generation(input.expires_generation,'expires_generation')

  const base={
    resource_id,
    provider,
    state:input.state,
    currency:input.currency,
    claim_or_activation_authority:'NOT_GRANTED' as const,
    authority_effect:'NONE' as const,
  }

  if(expired||input.state==='EXPIRED') return Object.freeze({
    ...base,usable_for_budgeting:false,admitted_value_minor_units:null,
    reason:'resource expired; capacity is not admitted',
  })
  if(input.state==='REJECTED') return Object.freeze({
    ...base,usable_for_budgeting:false,admitted_value_minor_units:null,
    reason:'resource rejected; capacity is not admitted',
  })
  if(input.state!=='ACTIVE') return Object.freeze({
    ...base,usable_for_budgeting:false,admitted_value_minor_units:null,
    reason:'offer or claim is not evidence of activated capacity',
  })
  if(input.evidence_authority==='UNVERIFIED') return Object.freeze({
    ...base,usable_for_budgeting:false,admitted_value_minor_units:null,
    reason:'active state lacks admitted evidence authority',
  })
  if(input.terms_state==='NOT_REVIEWED') return Object.freeze({
    ...base,usable_for_budgeting:false,admitted_value_minor_units:null,
    reason:'resource terms are not reviewed',
  })

  return Object.freeze({
    ...base,
    usable_for_budgeting:true,
    admitted_value_minor_units:input.known_value_minor_units,
    reason:'active resource admitted within observed provider scope',
  })
}

export function classifyEnterpriseResourceActionV1(action: EnterpriseResourceActionV1) {
  const classes: Readonly<Record<EnterpriseResourceActionV1,{
    action_class:'RESEARCH_READ'|'ANALYZE'|'LEGAL_COMMITMENT'|'FINANCIAL'
    operator_grant_required:boolean
  }>>={
    RESEARCH_TERMS:{action_class:'RESEARCH_READ',operator_grant_required:false},
    RECORD_OFFER:{action_class:'ANALYZE',operator_grant_required:false},
    CLAIM_RESOURCE:{action_class:'LEGAL_COMMITMENT',operator_grant_required:true},
    ADD_PAYMENT_METHOD:{action_class:'FINANCIAL',operator_grant_required:true},
    ACTIVATE_PAID_PLAN:{action_class:'FINANCIAL',operator_grant_required:true},
  }
  if(!(action in classes)) throw new TypeError('invalid enterprise resource action')
  return Object.freeze({action,...classes[action],authority_effect:'NONE' as const})
}
