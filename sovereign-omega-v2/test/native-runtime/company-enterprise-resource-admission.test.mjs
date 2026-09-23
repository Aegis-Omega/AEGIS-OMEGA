import test from 'node:test'
import assert from 'node:assert/strict'
import {loadRepositoryTypescript} from './load-repository-ts.mjs'

const loaded=await loadRepositoryTypescript(['sovereignty/company-enterprise-resource-admission.ts'])
test.after(()=>loaded.cleanup())
const {
  admitEnterpriseResourceV1:admit,
  classifyEnterpriseResourceActionV1:classify,
}=loaded.modules['sovereignty/company-enterprise-resource-admission.ts']

const offer=(overrides={})=>({
  resource_id:'resource-1',
  provider:'Example Provider',
  resource_class:'API_CREDIT',
  state:'OFFERED',
  evidence_authority:'PROVIDER_ATTESTATION',
  known_value_minor_units:2500,
  currency:'USD',
  terms_state:'NOT_REVIEWED',
  activation_requires_payment_method:null,
  expires_generation:'100',
  ...overrides,
})

test('offered credit is not active budget capacity',()=>{
  const r=admit(offer(),'1')
  assert.equal(r.usable_for_budgeting,false)
  assert.equal(r.admitted_value_minor_units,null)
  assert.equal(r.claim_or_activation_authority,'NOT_GRANTED')
})

test('claimed credit is still not active capacity',()=>{
  assert.equal(admit(offer({state:'CLAIMED',terms_state:'REVIEWED'}),'1').usable_for_budgeting,false)
})

test('active evidenced reviewed credit becomes budget-visible without granting claim authority',()=>{
  const r=admit(offer({state:'ACTIVE',terms_state:'REVIEWED'}),'1')
  assert.equal(r.usable_for_budgeting,true)
  assert.equal(r.admitted_value_minor_units,2500)
  assert.equal(r.currency,'USD')
  assert.equal(r.claim_or_activation_authority,'NOT_GRANTED')
  assert.equal(r.authority_effect,'NONE')
})

test('unverified active claim fails closed',()=>{
  assert.equal(admit(offer({state:'ACTIVE',terms_state:'REVIEWED',evidence_authority:'UNVERIFIED'}),'1').usable_for_budgeting,false)
})

test('unreviewed terms block budgeting even when provider says active',()=>{
  assert.equal(admit(offer({state:'ACTIVE'}),'1').usable_for_budgeting,false)
})

test('expiry overrides active state',()=>{
  const r=admit(offer({state:'ACTIVE',terms_state:'REVIEWED',expires_generation:'2'}),'3')
  assert.equal(r.usable_for_budgeting,false)
  assert.match(r.reason,/expired/)
})

test('claim and payment-method actions remain consequential',()=>{
  assert.equal(classify('RESEARCH_TERMS').operator_grant_required,false)
  assert.equal(classify('RECORD_OFFER').operator_grant_required,false)
  assert.deepEqual(classify('CLAIM_RESOURCE'),{
    action:'CLAIM_RESOURCE',action_class:'LEGAL_COMMITMENT',operator_grant_required:true,authority_effect:'NONE',
  })
  assert.equal(classify('ADD_PAYMENT_METHOD').action_class,'FINANCIAL')
  assert.equal(classify('ADD_PAYMENT_METHOD').operator_grant_required,true)
  assert.equal(classify('ACTIVATE_PAID_PLAN').operator_grant_required,true)
})

test('monetary value must carry a valid currency and safe integer amount',()=>{
  assert.throws(()=>admit(offer({currency:null}),'1'),/currency/)
  assert.throws(()=>admit(offer({known_value_minor_units:1.5}),'1'),/known_value/)
})
