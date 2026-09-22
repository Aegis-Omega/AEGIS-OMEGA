// AEGIS Enterprise Snapshot/Ledger Reconciliation V1
// Reconstructs current commercial state from ordered enterprise event evidence.
// Pure verification only: no database, mail, CRM, or authority side effects.

import type { EnterpriseOpportunityStageV1 } from './company-enterprise-opportunity.js'

export type EnterpriseResourceLedgerStateV1 =
  | 'OFFERED'
  | 'CLAIMED'
  | 'ACTIVE'
  | 'EXPIRED'
  | 'REJECTED'

export interface EnterpriseLedgerAuthorityV1 {
  readonly external_authority: 'NOT_GRANTED'
  readonly authority_effect: 'NONE'
}

export interface EnterpriseOpportunityLedgerEventV1 extends EnterpriseLedgerAuthorityV1 {
  readonly sequence: number
  readonly event_id: string
  readonly from_stage: EnterpriseOpportunityStageV1 | null
  readonly to_stage: EnterpriseOpportunityStageV1
  readonly evidence_refs: readonly string[]
}

export interface EnterpriseOpportunitySnapshotV1 extends EnterpriseLedgerAuthorityV1 {
  readonly opportunity_id: string
  readonly stage: EnterpriseOpportunityStageV1
  readonly last_event_id: string
}

export interface EnterpriseResourceLedgerEventV1 extends EnterpriseLedgerAuthorityV1 {
  readonly sequence: number
  readonly event_id: string
  readonly from_state: EnterpriseResourceLedgerStateV1 | null
  readonly to_state: EnterpriseResourceLedgerStateV1
  readonly evidence_refs: readonly string[]
}

export interface EnterpriseResourceSnapshotV1 extends EnterpriseLedgerAuthorityV1 {
  readonly resource_id: string
  readonly state: EnterpriseResourceLedgerStateV1
  readonly last_event_id: string
}

function text(value: unknown, label: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${label} must be non-empty`)
  return value
}

function validateEvidenceRefs(value: readonly string[], label: string): readonly string[] {
  if (!Array.isArray(value) || value.length === 0) throw new TypeError(`${label} must be non-empty array`)
  const refs=value.map((ref)=>text(ref,label))
  if(new Set(refs).size!==refs.length) throw new TypeError(`${label} contains duplicates`)
  return refs
}

function validateAuthority(value: EnterpriseLedgerAuthorityV1, label: string): void {
  if (value?.external_authority !== 'NOT_GRANTED' || value?.authority_effect !== 'NONE') {
    throw new Error(`${label}:AUTHORITY_INVARIANT_VIOLATED`)
  }
}

function validateSequence(events: readonly {sequence:number;event_id:string}[]): void {
  const ids=new Set<string>()
  events.forEach((event,index)=>{
    if(!Number.isSafeInteger(event.sequence)||event.sequence!==index) {
      throw new Error(`LEDGER_SEQUENCE_INVALID:${index}`)
    }
    const id=text(event.event_id,'event_id')
    if(ids.has(id)) throw new Error('LEDGER_DUPLICATE_EVENT_ID')
    ids.add(id)
  })
}

const OPPORTUNITY_ORDER: readonly EnterpriseOpportunityStageV1[] = [
  'DISCOVERED','CONTACTED','QUALIFIED_REPLY','SCOPING_CALL_HELD',
  'WRITTEN_SCOPE_AGREED','PAYMENT_RECEIVED','AUDIT_STARTED',
]

function validOpportunityTransition(
  from: EnterpriseOpportunityStageV1,
  to: EnterpriseOpportunityStageV1,
): boolean {
  if (from === 'AUDIT_STARTED' || from === 'CLOSED_LOST') return false
  if (to === 'CLOSED_LOST') return true
  const fromIndex=OPPORTUNITY_ORDER.indexOf(from)
  const toIndex=OPPORTUNITY_ORDER.indexOf(to)
  return fromIndex>=0 && toIndex===fromIndex+1
}

export function reconcileEnterpriseOpportunityLedgerV1(
  snapshot: EnterpriseOpportunitySnapshotV1,
  events: readonly EnterpriseOpportunityLedgerEventV1[],
) {
  text(snapshot?.opportunity_id,'opportunity_id')
  text(snapshot?.last_event_id,'last_event_id')
  validateAuthority(snapshot,'snapshot')
  if(!Array.isArray(events)||events.length===0) throw new Error('OPPORTUNITY_LEDGER_EMPTY')
  validateSequence(events)

  for(const event of events){
    validateAuthority(event,'event')
    validateEvidenceRefs(event.evidence_refs,'evidence_ref')
  }

  const first=events[0]
  if(first.from_stage!==null||first.to_stage!=='DISCOVERED') {
    throw new Error('OPPORTUNITY_LEDGER_BAD_GENESIS')
  }

  let current:EnterpriseOpportunityStageV1='DISCOVERED'
  for(let i=1;i<events.length;i++){
    const event=events[i]
    if(event.from_stage!==current) throw new Error(`OPPORTUNITY_LEDGER_CHAIN_BREAK:${i}`)
    if(!validOpportunityTransition(current,event.to_stage)) {
      throw new Error(`OPPORTUNITY_LEDGER_INVALID_TRANSITION:${current}->${event.to_stage}`)
    }
    current=event.to_stage
  }

  const last=events[events.length-1]
  if(snapshot.stage!==current) throw new Error('OPPORTUNITY_SNAPSHOT_STAGE_DRIFT')
  if(snapshot.last_event_id!==last.event_id) throw new Error('OPPORTUNITY_SNAPSHOT_EVENT_DRIFT')

  return Object.freeze({
    status:'CONSISTENT' as const,
    opportunity_id:snapshot.opportunity_id,
    reconstructed_stage:current,
    event_count:events.length,
    last_event_id:last.event_id,
    terminal:current==='AUDIT_STARTED'||current==='CLOSED_LOST',
    authority_effect:'NONE' as const,
  })
}

function validResourceTransition(
  from: EnterpriseResourceLedgerStateV1,
  to: EnterpriseResourceLedgerStateV1,
): boolean {
  if(from==='EXPIRED'||from==='REJECTED') return false
  if(to==='EXPIRED'||to==='REJECTED') return true
  if(from==='OFFERED'&&to==='CLAIMED') return true
  if(from==='CLAIMED'&&to==='ACTIVE') return true
  return false
}

export function reconcileEnterpriseResourceLedgerV1(
  snapshot: EnterpriseResourceSnapshotV1,
  events: readonly EnterpriseResourceLedgerEventV1[],
) {
  text(snapshot?.resource_id,'resource_id')
  text(snapshot?.last_event_id,'last_event_id')
  validateAuthority(snapshot,'snapshot')
  if(!Array.isArray(events)||events.length===0) throw new Error('RESOURCE_LEDGER_EMPTY')
  validateSequence(events)

  for(const event of events){
    validateAuthority(event,'event')
    validateEvidenceRefs(event.evidence_refs,'evidence_ref')
  }

  const first=events[0]
  if(first.from_state!==null||first.to_state!=='OFFERED') {
    throw new Error('RESOURCE_LEDGER_BAD_GENESIS')
  }

  let current:EnterpriseResourceLedgerStateV1='OFFERED'
  for(let i=1;i<events.length;i++){
    const event=events[i]
    if(event.from_state!==current) throw new Error(`RESOURCE_LEDGER_CHAIN_BREAK:${i}`)
    if(!validResourceTransition(current,event.to_state)) {
      throw new Error(`RESOURCE_LEDGER_INVALID_TRANSITION:${current}->${event.to_state}`)
    }
    current=event.to_state
  }

  const last=events[events.length-1]
  if(snapshot.state!==current) throw new Error('RESOURCE_SNAPSHOT_STATE_DRIFT')
  if(snapshot.last_event_id!==last.event_id) throw new Error('RESOURCE_SNAPSHOT_EVENT_DRIFT')

  return Object.freeze({
    status:'CONSISTENT' as const,
    resource_id:snapshot.resource_id,
    reconstructed_state:current,
    event_count:events.length,
    last_event_id:last.event_id,
    terminal:current==='EXPIRED'||current==='REJECTED',
    authority_effect:'NONE' as const,
  })
}
