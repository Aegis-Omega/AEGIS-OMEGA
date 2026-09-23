import test from 'node:test'
import assert from 'node:assert/strict'
import {loadRepositoryTypescript} from './load-repository-ts.mjs'

const loaded=await loadRepositoryTypescript(['sovereignty/company-enterprise-prospect-admission.ts'])
test.after(()=>loaded.cleanup())
const {evaluateEnterpriseProspectAdmissionV1:evaluate}=loaded.modules['sovereignty/company-enterprise-prospect-admission.ts']

const candidate=(overrides={})=>({
  prospect_id:'p1',
  organization_name:'Example Governance Co',
  official_contact_ref:'official-site:contact',
  public_fit_evidence_refs:['public-site:runtime-governance'],
  fit:['RUNTIME_GOVERNANCE'],
  prior_contact_observed:false,
  bounce_observed:false,
  unsubscribe_or_dnc_observed:false,
  ...overrides,
})

test('well-evidenced public-fit candidate is draft eligible only',()=>{
  const r=evaluate(candidate())
  assert.equal(r.status,'DRAFT_ELIGIBLE')
  assert.deepEqual(r.denial_codes,[])
  assert.equal(r.send_authority,'NOT_GRANTED')
  assert.equal(r.authority_effect,'NONE')
})

test('unverified contact or missing fit evidence denies candidate',()=>{
  let r=evaluate(candidate({official_contact_ref:null}))
  assert.ok(r.denial_codes.includes('OFFICIAL_CONTACT_NOT_VERIFIED'))
  r=evaluate(candidate({public_fit_evidence_refs:[]}))
  assert.ok(r.denial_codes.includes('PUBLIC_FIT_EVIDENCE_MISSING'))
  r=evaluate(candidate({fit:[]}))
  assert.ok(r.denial_codes.includes('NO_RELEVANT_ENTERPRISE_FIT'))
})

test('prior contact must route through existing-thread follow-up policy',()=>{
  const r=evaluate(candidate({prior_contact_observed:true}))
  assert.equal(r.status,'DENIED')
  assert.ok(r.denial_codes.includes('PRIOR_CONTACT_REQUIRES_EXISTING_THREAD_POLICY'))
})

test('bounce unsubscribe or do-not-contact signals hard-deny new outreach drafting',()=>{
  assert.ok(evaluate(candidate({bounce_observed:true})).denial_codes.includes('BOUNCE_OBSERVED'))
  assert.ok(evaluate(candidate({unsubscribe_or_dnc_observed:true})).denial_codes.includes('UNSUBSCRIBE_OR_DNC'))
})

test('duplicate evidence refs fail closed instead of inflating fit evidence',()=>{
  assert.throws(()=>evaluate(candidate({
    public_fit_evidence_refs:['public:a','public:a'],
  })),/duplicate public_fit_evidence_ref/)
})
