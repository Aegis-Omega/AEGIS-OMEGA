import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import {loadRepositoryTypescript} from './load-repository-ts.mjs'

const loaded=await loadRepositoryTypescript(['sovereignty/company-enterprise-action-packet.ts'])
test.after(()=>loaded.cleanup())
const {createEnterpriseConsequentialPacketV1:create}=loaded.modules['sovereignty/company-enterprise-action-packet.ts']

const stable=(value)=>{
  if(Array.isArray(value)) return '['+value.map(stable).join(',')+']'
  if(value&&typeof value==='object') return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+stable(value[k])).join(',')+'}'
  return JSON.stringify(value)
}
const hash=async(domain,value)=>createHash('sha256').update(domain+'\n'+stable(value)).digest('hex')
const digest='a'.repeat(64)

const base=(overrides={})=>({
  packet_id:'packet-1',
  task_id:'task-1',
  opportunity_id:'opp-1',
  action:'SEND_SCOPING_MESSAGE',
  context:{
    opportunity_stage:'QUALIFIED_REPLY',
    commercial_capacity_state:'NOT_VERIFIED',
    commercial_terms_state:'NOT_DRAFTED',
    delivery_readiness_state:'NOT_READY',
  },
  exact_target:'prospect@example.test',
  exact_action_summary:'Send the reviewed 20-minute scoping-call invitation',
  reason:'Observed qualifying reply requires a bounded next-step proposal',
  evidence_refs:['gmail:reply-1'],
  commercial_terms_digest:null,
  requested_amount_minor_units:null,
  requested_currency:null,
  rollback:'Do not send if packet/grant verification fails; sent mail cannot be unsent.',
  created_generation:'10',
  expires_generation:'12',
  ...overrides,
})

test('scoping send packet is exact-target external-message authority request',async()=>{
  const r=await create(base(),hash)
  assert.equal(r.packet.action_class,'EXTERNAL_MESSAGE')
  assert.equal(r.packet.target,'prospect@example.test')
  assert.ok(r.packet.evidence_refs.includes('opportunity:opp-1'))
  assert.ok(r.packet.evidence_refs.includes('opportunity_stage:QUALIFIED_REPLY'))
  assert.equal(r.enterprise_binding.authority_effect,'NONE')
  assert.match(r.packet_digest,/^[0-9a-f]{64}$/)
})

test('legal terms packet requires verified capacity reviewed terms and exact terms digest',async()=>{
  await assert.rejects(()=>create(base({
    action:'SEND_COMMERCIAL_TERMS',
    context:{
      opportunity_stage:'SCOPING_CALL_HELD',
      commercial_capacity_state:'NOT_VERIFIED',
      commercial_terms_state:'REVIEWED',
      delivery_readiness_state:'NOT_READY',
    },
    commercial_terms_digest:digest,
  }),hash),/COMMERCIAL_CAPACITY_NOT_VERIFIED/)

  const r=await create(base({
    action:'SEND_COMMERCIAL_TERMS',
    context:{
      opportunity_stage:'SCOPING_CALL_HELD',
      commercial_capacity_state:'VERIFIED',
      commercial_terms_state:'REVIEWED',
      delivery_readiness_state:'NOT_READY',
    },
    commercial_terms_digest:digest,
  }),hash)
  assert.equal(r.packet.action_class,'LEGAL_COMMITMENT')
  assert.ok(r.packet.evidence_refs.includes('commercial_terms_sha256:'+digest))
})

test('payment request requires agreed scope terms verified capacity and exact amount',async()=>{
  const r=await create(base({
    action:'REQUEST_PAYMENT',
    context:{
      opportunity_stage:'WRITTEN_SCOPE_AGREED',
      commercial_capacity_state:'VERIFIED',
      commercial_terms_state:'AGREED',
      delivery_readiness_state:'NOT_READY',
    },
    commercial_terms_digest:digest,
    requested_amount_minor_units:300000,
    requested_currency:'USD',
  }),hash)
  assert.equal(r.packet.action_class,'FINANCIAL')
  assert.match(r.packet.action,/requested_amount_minor_units=300000/)
  assert.match(r.packet.action,/requested_currency=USD/)
  assert.equal(r.enterprise_binding.requested_amount_minor_units,300000)
})

test('payment amount cannot be silently omitted or malformed',async()=>{
  await assert.rejects(()=>create(base({
    action:'REQUEST_PAYMENT',
    context:{
      opportunity_stage:'WRITTEN_SCOPE_AGREED',
      commercial_capacity_state:'VERIFIED',
      commercial_terms_state:'AGREED',
      delivery_readiness_state:'NOT_READY',
    },
    commercial_terms_digest:digest,
    requested_amount_minor_units:null,
    requested_currency:null,
  }),hash),/requires positive safe integer amount/)
})

test('terms digest is mandatory for legal and financial packets',async()=>{
  await assert.rejects(()=>create(base({
    action:'SEND_COMMERCIAL_TERMS',
    context:{
      opportunity_stage:'SCOPING_CALL_HELD',
      commercial_capacity_state:'VERIFIED',
      commercial_terms_state:'REVIEWED',
      delivery_readiness_state:'NOT_READY',
    },
  }),hash),/commercial_terms_digest/)
})

test('stage-ineligible action cannot mint an approval packet',async()=>{
  await assert.rejects(()=>create(base({
    action:'REQUEST_PAYMENT',
    context:{
      opportunity_stage:'QUALIFIED_REPLY',
      commercial_capacity_state:'VERIFIED',
      commercial_terms_state:'AGREED',
      delivery_readiness_state:'NOT_READY',
    },
    commercial_terms_digest:digest,
    requested_amount_minor_units:300000,
    requested_currency:'USD',
  }),hash),/STAGE_NOT_READY/)
})

test('scoping packet cannot smuggle commercial terms or payment amount',async()=>{
  await assert.rejects(()=>create(base({commercial_terms_digest:digest}),hash),/not valid for scoping/)
  await assert.rejects(()=>create(base({requested_amount_minor_units:1,requested_currency:'USD'}),hash),/only valid for REQUEST_PAYMENT/)
})
