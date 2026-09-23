import test from 'node:test'
import assert from 'node:assert/strict'
import {loadRepositoryTypescript} from './load-repository-ts.mjs'

const loaded=await loadRepositoryTypescript(['sovereignty/company-enterprise-ledger-reconcile.ts'])
test.after(()=>loaded.cleanup())
const {
  reconcileEnterpriseOpportunityLedgerV1:reconcileOpportunity,
  reconcileEnterpriseResourceLedgerV1:reconcileResource,
}=loaded.modules['sovereignty/company-enterprise-ledger-reconcile.ts']

const auth={external_authority:'NOT_GRANTED',authority_effect:'NONE'}
const oe=(sequence,event_id,from_stage,to_stage)=>({
  sequence,event_id,from_stage,to_stage,evidence_refs:[`e:${event_id}`],...auth,
})
const re=(sequence,event_id,from_state,to_state)=>({
  sequence,event_id,from_state,to_state,evidence_refs:[`e:${event_id}`],...auth,
})

test('opportunity snapshot reconciles from exact genesis through payment',()=>{
  const events=[
    oe(0,'o0',null,'DISCOVERED'),
    oe(1,'o1','DISCOVERED','CONTACTED'),
    oe(2,'o2','CONTACTED','QUALIFIED_REPLY'),
    oe(3,'o3','QUALIFIED_REPLY','SCOPING_CALL_HELD'),
    oe(4,'o4','SCOPING_CALL_HELD','WRITTEN_SCOPE_AGREED'),
    oe(5,'o5','WRITTEN_SCOPE_AGREED','PAYMENT_RECEIVED'),
  ]
  const r=reconcileOpportunity({opportunity_id:'opp',stage:'PAYMENT_RECEIVED',last_event_id:'o5',...auth},events)
  assert.equal(r.status,'CONSISTENT')
  assert.equal(r.reconstructed_stage,'PAYMENT_RECEIVED')
  assert.equal(r.event_count,6)
})

test('opportunity chain break and stage skip fail closed',()=>{
  assert.throws(()=>reconcileOpportunity(
    {opportunity_id:'opp',stage:'QUALIFIED_REPLY',last_event_id:'o1',...auth},
    [oe(0,'o0',null,'DISCOVERED'),oe(1,'o1','CONTACTED','QUALIFIED_REPLY')],
  ),/CHAIN_BREAK/)

  assert.throws(()=>reconcileOpportunity(
    {opportunity_id:'opp',stage:'SCOPING_CALL_HELD',last_event_id:'o1',...auth},
    [oe(0,'o0',null,'DISCOVERED'),oe(1,'o1','DISCOVERED','SCOPING_CALL_HELD')],
  ),/INVALID_TRANSITION/)
})

test('opportunity snapshot drift is detected',()=>{
  const events=[oe(0,'o0',null,'DISCOVERED'),oe(1,'o1','DISCOVERED','CONTACTED')]
  assert.throws(()=>reconcileOpportunity(
    {opportunity_id:'opp',stage:'QUALIFIED_REPLY',last_event_id:'o1',...auth},events
  ),/SNAPSHOT_STAGE_DRIFT/)
  assert.throws(()=>reconcileOpportunity(
    {opportunity_id:'opp',stage:'CONTACTED',last_event_id:'wrong',...auth},events
  ),/SNAPSHOT_EVENT_DRIFT/)
})

test('closed-lost is terminal and cannot be revived',()=>{
  const events=[oe(0,'o0',null,'DISCOVERED'),oe(1,'o1','DISCOVERED','CLOSED_LOST')]
  const r=reconcileOpportunity({opportunity_id:'opp',stage:'CLOSED_LOST',last_event_id:'o1',...auth},events)
  assert.equal(r.terminal,true)
  assert.throws(()=>reconcileOpportunity(
    {opportunity_id:'opp',stage:'CONTACTED',last_event_id:'o2',...auth},
    [...events,oe(2,'o2','CLOSED_LOST','CONTACTED')],
  ),/INVALID_TRANSITION/)
})

test('resource ledger requires OFFERED then CLAIMED then ACTIVE',()=>{
  const events=[
    re(0,'r0',null,'OFFERED'),
    re(1,'r1','OFFERED','CLAIMED'),
    re(2,'r2','CLAIMED','ACTIVE'),
  ]
  const r=reconcileResource({resource_id:'res',state:'ACTIVE',last_event_id:'r2',...auth},events)
  assert.equal(r.status,'CONSISTENT')
  assert.equal(r.reconstructed_state,'ACTIVE')
})

test('resource cannot skip directly from offered to active',()=>{
  assert.throws(()=>reconcileResource(
    {resource_id:'res',state:'ACTIVE',last_event_id:'r1',...auth},
    [re(0,'r0',null,'OFFERED'),re(1,'r1','OFFERED','ACTIVE')],
  ),/INVALID_TRANSITION/)
})

test('resource expiration and rejection are terminal',()=>{
  for(const terminal of ['EXPIRED','REJECTED']){
    const events=[re(0,'r0',null,'OFFERED'),re(1,'r1','OFFERED',terminal)]
    const r=reconcileResource({resource_id:'res',state:terminal,last_event_id:'r1',...auth},events)
    assert.equal(r.terminal,true)
    assert.throws(()=>reconcileResource(
      {resource_id:'res',state:'CLAIMED',last_event_id:'r2',...auth},
      [...events,re(2,'r2',terminal,'CLAIMED')],
    ),/INVALID_TRANSITION/)
  }
})

test('duplicate or out-of-order event sequence fails closed',()=>{
  assert.throws(()=>reconcileResource(
    {resource_id:'res',state:'CLAIMED',last_event_id:'r1',...auth},
    [re(0,'same',null,'OFFERED'),re(1,'same','OFFERED','CLAIMED')],
  ),/DUPLICATE_EVENT_ID/)
  assert.throws(()=>reconcileResource(
    {resource_id:'res',state:'CLAIMED',last_event_id:'r1',...auth},
    [re(0,'r0',null,'OFFERED'),re(2,'r1','OFFERED','CLAIMED')],
  ),/SEQUENCE_INVALID/)
})

test('authority-neutral event invariant is mandatory during reconciliation',()=>{
  const bad=oe(0,'o0',null,'DISCOVERED')
  assert.throws(()=>reconcileOpportunity(
    {opportunity_id:'opp',stage:'DISCOVERED',last_event_id:'o0',...auth},
    [{...bad,external_authority:'GRANTED'}],
  ),/AUTHORITY_INVARIANT/)
})
