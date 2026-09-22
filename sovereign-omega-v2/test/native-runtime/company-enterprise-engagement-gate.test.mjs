import test from 'node:test'
import assert from 'node:assert/strict'
import {loadRepositoryTypescript} from './load-repository-ts.mjs'

const loaded=await loadRepositoryTypescript(['sovereignty/company-enterprise-engagement-gate.ts'])
test.after(()=>loaded.cleanup())
const {evaluateEnterpriseEngagementV1:evaluate}=loaded.modules['sovereignty/company-enterprise-engagement-gate.ts']

const ctx=(overrides={})=>({
  opportunity_stage:'QUALIFIED_REPLY',
  commercial_capacity_state:'NOT_VERIFIED',
  commercial_terms_state:'NOT_DRAFTED',
  delivery_readiness_state:'NOT_READY',
  ...overrides,
})

test('qualified reply admits scoping draft but not send authority',()=>{
  const draft=evaluate('PREPARE_SCOPING_DRAFT',ctx())
  assert.equal(draft.status,'PREPARATION_ADMITTED')
  assert.equal(draft.action_class,'DRAFT')
  assert.equal(draft.operator_grant_required,false)

  const send=evaluate('SEND_SCOPING_MESSAGE',ctx())
  assert.equal(send.status,'APPROVAL_PACKET_REQUIRED')
  assert.equal(send.action_class,'EXTERNAL_MESSAGE')
  assert.equal(send.operator_grant_required,true)
  assert.equal(send.authority_effect,'NONE')
})

test('scope draft requires held scoping call',()=>{
  assert.equal(evaluate('PREPARE_SCOPE_DRAFT',ctx()).denial_code,'STAGE_NOT_READY')
  assert.equal(evaluate('PREPARE_SCOPE_DRAFT',ctx({opportunity_stage:'SCOPING_CALL_HELD'})).status,'PREPARATION_ADMITTED')
})

test('legal terms require held call verified commercial capacity and reviewed terms',()=>{
  let r=evaluate('SEND_COMMERCIAL_TERMS',ctx({opportunity_stage:'SCOPING_CALL_HELD'}))
  assert.equal(r.denial_code,'COMMERCIAL_CAPACITY_NOT_VERIFIED')

  r=evaluate('SEND_COMMERCIAL_TERMS',ctx({
    opportunity_stage:'SCOPING_CALL_HELD',
    commercial_capacity_state:'VERIFIED',
    commercial_terms_state:'DRAFTED',
  }))
  assert.equal(r.denial_code,'TERMS_NOT_REVIEWED')

  r=evaluate('SEND_COMMERCIAL_TERMS',ctx({
    opportunity_stage:'SCOPING_CALL_HELD',
    commercial_capacity_state:'VERIFIED',
    commercial_terms_state:'REVIEWED',
  }))
  assert.equal(r.status,'APPROVAL_PACKET_REQUIRED')
  assert.equal(r.action_class,'LEGAL_COMMITMENT')
  assert.equal(r.operator_grant_required,true)
})

test('ineligible commercial capacity hard-denies legal and financial actions',()=>{
  for(const action of ['SEND_COMMERCIAL_TERMS','REQUEST_PAYMENT']){
    const r=evaluate(action,ctx({
      opportunity_stage:'WRITTEN_SCOPE_AGREED',
      commercial_capacity_state:'INELIGIBLE',
      commercial_terms_state:'AGREED',
    }))
    assert.equal(r.status,'DENIED')
    assert.equal(r.denial_code,'COMMERCIAL_CAPACITY_INELIGIBLE')
    assert.equal(r.operator_grant_required,false)
  }
})

test('payment request requires written agreement and agreed terms',()=>{
  let r=evaluate('REQUEST_PAYMENT',ctx({
    opportunity_stage:'SCOPING_CALL_HELD',
    commercial_capacity_state:'VERIFIED',
    commercial_terms_state:'AGREED',
  }))
  assert.equal(r.denial_code,'STAGE_NOT_READY')

  r=evaluate('REQUEST_PAYMENT',ctx({
    opportunity_stage:'WRITTEN_SCOPE_AGREED',
    commercial_capacity_state:'VERIFIED',
    commercial_terms_state:'REVIEWED',
  }))
  assert.equal(r.denial_code,'TERMS_NOT_AGREED')

  r=evaluate('REQUEST_PAYMENT',ctx({
    opportunity_stage:'WRITTEN_SCOPE_AGREED',
    commercial_capacity_state:'VERIFIED',
    commercial_terms_state:'AGREED',
  }))
  assert.equal(r.status,'APPROVAL_PACKET_REQUIRED')
  assert.equal(r.action_class,'FINANCIAL')
  assert.equal(r.operator_grant_required,true)
})

test('audit cannot start from payment alone without agreed terms and delivery readiness',()=>{
  let r=evaluate('START_AUDIT',ctx({
    opportunity_stage:'PAYMENT_RECEIVED',
    commercial_terms_state:'AGREED',
  }))
  assert.equal(r.denial_code,'DELIVERY_NOT_READY')

  r=evaluate('START_AUDIT',ctx({
    opportunity_stage:'PAYMENT_RECEIVED',
    commercial_terms_state:'AGREED',
    delivery_readiness_state:'READY',
  }))
  assert.equal(r.status,'ACTION_ADMITTED_INTERNAL')
  assert.equal(r.action_class,'PROPOSE')
  assert.equal(r.operator_grant_required,false)
})

test('closed-lost opportunity cannot prepare or execute engagement work',()=>{
  for(const action of [
    'PREPARE_SCOPING_DRAFT','SEND_SCOPING_MESSAGE','PREPARE_SCOPE_DRAFT',
    'SEND_COMMERCIAL_TERMS','REQUEST_PAYMENT','START_AUDIT',
  ]){
    const r=evaluate(action,ctx({
      opportunity_stage:'CLOSED_LOST',
      commercial_capacity_state:'VERIFIED',
      commercial_terms_state:'AGREED',
      delivery_readiness_state:'READY',
    }))
    assert.equal(r.status,'DENIED')
    assert.equal(r.denial_code,'STAGE_NOT_READY')
  }
})
