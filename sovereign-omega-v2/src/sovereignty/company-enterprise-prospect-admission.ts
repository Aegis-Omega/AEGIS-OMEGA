// AEGIS Enterprise Prospect Admission V1
// Public fit evidence can admit a prospect for drafting only.
// It never authorizes or sends outreach.

export type EnterpriseProspectFitV1 =
  | 'RUNTIME_GOVERNANCE'
  | 'AGENTIC_AI_GOVERNANCE'
  | 'ACTION_AUTHORIZATION'
  | 'AUDITABILITY'
  | 'MCP_GOVERNANCE'
  | 'AI_SECURITY'
  | 'IMPLEMENTATION_PARTNER'

export interface EnterpriseProspectAdmissionInputV1 {
  readonly prospect_id: string
  readonly organization_name: string
  readonly official_contact_ref: string | null
  readonly public_fit_evidence_refs: readonly string[]
  readonly fit: readonly EnterpriseProspectFitV1[]
  readonly prior_contact_observed: boolean
  readonly bounce_observed: boolean
  readonly unsubscribe_or_dnc_observed: boolean
}

export interface EnterpriseProspectAdmissionDecisionV1 {
  readonly prospect_id: string
  readonly organization_name: string
  readonly status: 'DRAFT_ELIGIBLE' | 'DENIED'
  readonly denial_codes: readonly (
    | 'OFFICIAL_CONTACT_NOT_VERIFIED'
    | 'PUBLIC_FIT_EVIDENCE_MISSING'
    | 'NO_RELEVANT_ENTERPRISE_FIT'
    | 'PRIOR_CONTACT_REQUIRES_EXISTING_THREAD_POLICY'
    | 'BOUNCE_OBSERVED'
    | 'UNSUBSCRIBE_OR_DNC'
  )[]
  readonly send_authority: 'NOT_GRANTED'
  readonly authority_effect: 'NONE'
}

function text(value: unknown,label:string):string{
  if(typeof value!=='string'||!value.trim()) throw new TypeError(`${label} must be non-empty`)
  return value
}

export function evaluateEnterpriseProspectAdmissionV1(
  input: EnterpriseProspectAdmissionInputV1,
): EnterpriseProspectAdmissionDecisionV1 {
  const prospect_id=text(input?.prospect_id,'prospect_id')
  const organization_name=text(input?.organization_name,'organization_name')
  if(!Array.isArray(input.public_fit_evidence_refs)) throw new TypeError('public_fit_evidence_refs must be array')
  if(!Array.isArray(input.fit)) throw new TypeError('fit must be array')
  const allowed:readonly EnterpriseProspectFitV1[]=[
    'RUNTIME_GOVERNANCE','AGENTIC_AI_GOVERNANCE','ACTION_AUTHORIZATION',
    'AUDITABILITY','MCP_GOVERNANCE','AI_SECURITY','IMPLEMENTATION_PARTNER',
  ]
  const refs=input.public_fit_evidence_refs.map(x=>text(x,'public_fit_evidence_ref'))
  if(new Set(refs).size!==refs.length) throw new TypeError('duplicate public_fit_evidence_ref')
  for(const fit of input.fit){
    if(!allowed.includes(fit)) throw new TypeError('invalid enterprise prospect fit')
  }

  const denial_codes:EnterpriseProspectAdmissionDecisionV1['denial_codes'][number][]=[]
  if(input.official_contact_ref===null) denial_codes.push('OFFICIAL_CONTACT_NOT_VERIFIED')
  else text(input.official_contact_ref,'official_contact_ref')
  if(refs.length===0) denial_codes.push('PUBLIC_FIT_EVIDENCE_MISSING')
  if(input.fit.length===0) denial_codes.push('NO_RELEVANT_ENTERPRISE_FIT')
  if(input.prior_contact_observed) denial_codes.push('PRIOR_CONTACT_REQUIRES_EXISTING_THREAD_POLICY')
  if(input.bounce_observed) denial_codes.push('BOUNCE_OBSERVED')
  if(input.unsubscribe_or_dnc_observed) denial_codes.push('UNSUBSCRIBE_OR_DNC')

  return Object.freeze({
    prospect_id,
    organization_name,
    status:denial_codes.length===0?'DRAFT_ELIGIBLE':'DENIED',
    denial_codes:Object.freeze(denial_codes),
    send_authority:'NOT_GRANTED',
    authority_effect:'NONE',
  })
}
