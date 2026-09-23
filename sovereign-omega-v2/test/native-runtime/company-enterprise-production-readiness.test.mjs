import test from 'node:test'
import assert from 'node:assert/strict'
import {loadRepositoryTypescript} from './load-repository-ts.mjs'

const loaded=await loadRepositoryTypescript(['sovereignty/company-enterprise-production-readiness.ts'])
test.after(()=>loaded.cleanup())
const {evaluateEnterpriseProductionReadinessV1:evaluate}=loaded.modules['sovereignty/company-enterprise-production-readiness.ts']

const ready=(overrides={})=>({
  exact_head_execution_receipt:'PASS',
  openai_live_canary:'PASS',
  scale_os_runtime_v2:'APPLIED',
  opportunity_persistence_v1:'APPLIED',
  resource_persistence_v1:'APPLIED',
  enterprise_event_immutability_guard_v1:'APPLIED',
  enterprise_event_insert_guard_v1:'APPLIED',
  commercial_capacity_state:'VERIFIED',
  crm_sync_required:false,
  crm_write_state:'NOT_AVAILABLE',
  default_external_message_authority:'NOT_GRANTED',
  default_financial_authority:'NOT_GRANTED',
  default_legal_authority:'NOT_GRANTED',
  ...overrides,
})

test('fully evidenced substrate may be classified production ready without widening authority',()=>{
  const r=evaluate(ready())
  assert.equal(r.status,'PRODUCTION_READY')
  assert.deepEqual(r.blockers,[])
  assert.equal(r.consequential_authority_defaults_preserved,true)
  assert.equal(r.authority_effect,'NONE')
})

test('runnerless or otherwise unobserved exact-head execution blocks readiness',()=>{
  const r=evaluate(ready({exact_head_execution_receipt:'NOT_OBSERVED'}))
  assert.equal(r.status,'PRODUCTION_NOT_READY')
  assert.ok(r.blockers.includes('EXACT_HEAD_EXECUTION_NOT_VERIFIED'))
})

test('unapplied source migrations cannot become production readiness',()=>{
  const r=evaluate(ready({
    scale_os_runtime_v2:'NOT_APPLIED',
    opportunity_persistence_v1:'NOT_APPLIED',
    resource_persistence_v1:'NOT_APPLIED',
    enterprise_event_immutability_guard_v1:'NOT_APPLIED',
    enterprise_event_insert_guard_v1:'NOT_APPLIED',
  }))
  assert.ok(r.blockers.includes('SCALE_OS_RUNTIME_V2_NOT_APPLIED'))
  assert.ok(r.blockers.includes('OPPORTUNITY_PERSISTENCE_NOT_APPLIED'))
  assert.ok(r.blockers.includes('RESOURCE_PERSISTENCE_NOT_APPLIED'))
  assert.ok(r.blockers.includes('ENTERPRISE_EVENT_IMMUTABILITY_GUARD_NOT_APPLIED'))
  assert.ok(r.blockers.includes('ENTERPRISE_EVENT_INSERT_GUARD_NOT_APPLIED'))
})

test('missing live OpenAI canary blocks live company production readiness',()=>{
  const r=evaluate(ready({openai_live_canary:'NOT_OBSERVED'}))
  assert.ok(r.blockers.includes('OPENAI_LIVE_CANARY_NOT_VERIFIED'))
})

test('commercial capacity cannot be inferred or bypassed',()=>{
  assert.ok(evaluate(ready({commercial_capacity_state:'NOT_VERIFIED'})).blockers.includes('COMMERCIAL_CAPACITY_NOT_VERIFIED'))
  assert.ok(evaluate(ready({commercial_capacity_state:'INELIGIBLE'})).blockers.includes('COMMERCIAL_CAPACITY_INELIGIBLE'))
})

test('CRM is only a blocker when CRM synchronization is declared required',()=>{
  assert.equal(evaluate(ready({crm_sync_required:false,crm_write_state:'REQUIRES_REAUTHORIZATION'})).status,'PRODUCTION_READY')
  const r=evaluate(ready({crm_sync_required:true,crm_write_state:'REQUIRES_REAUTHORIZATION'}))
  assert.ok(r.blockers.includes('CRM_WRITE_REAUTHORIZATION_REQUIRED'))
})

test('production readiness refuses widened default consequential authority',()=>{
  assert.throws(()=>evaluate(ready({default_financial_authority:'GRANTED'})),/CONSEQUENTIAL_DEFAULT_AUTHORITY_WIDENED/)
})
