import test from 'node:test'
import assert from 'node:assert/strict'
import {loadRepositoryTypescript} from './load-repository-ts.mjs'

const loaded=await loadRepositoryTypescript(['sovereignty/company-enterprise-followup-policy.ts'])
test.after(()=>loaded.cleanup())
const {evaluateEnterpriseFollowupV1:evaluate}=loaded.modules['sovereignty/company-enterprise-followup-policy.ts']

const base=(overrides={})=>({
  initial_sent_at:'2026-09-22T17:25:00.000Z',
  last_outbound_at:'2026-09-22T17:25:00.000Z',
  now:'2026-09-22T19:30:00.000Z',
  followups_sent:0,
  stop_signals:[],
  ...overrides,
})

test('fresh outreach is not follow-up eligible before 72 hours',()=>{
  const r=evaluate(base())
  assert.equal(r.status,'NOT_ELIGIBLE')
  assert.equal(r.reason,'WAIT_INTERVAL')
  assert.equal(r.next_eligible_at,'2026-09-25T17:25:00.000Z')
  assert.equal(r.send_authority,'NOT_GRANTED')
})

test('eligibility means draft only and never grants send authority',()=>{
  const r=evaluate(base({now:'2026-09-25T17:25:00.000Z'}))
  assert.equal(r.status,'DRAFT_ELIGIBLE')
  assert.equal(r.reason,'DRAFT_MAY_BE_PREPARED')
  assert.equal(r.send_authority,'NOT_GRANTED')
  assert.equal(r.authority_effect,'NONE')
})

test('any reply stops follow-ups including nonqualifying replies',()=>{
  for(const signal of ['QUALIFYING_REPLY','ANY_REPLY']){
    const r=evaluate(base({now:'2026-09-30T00:00:00.000Z',stop_signals:[signal]}))
    assert.equal(r.reason,'STOP_SIGNAL')
  }
})

test('bounce unsubscribe and closed-lost stop all follow-ups',()=>{
  for(const signal of ['BOUNCE','UNSUBSCRIBE','CLOSED_LOST']){
    const r=evaluate(base({now:'2026-09-30T00:00:00.000Z',stop_signals:[signal]}))
    assert.equal(r.status,'NOT_ELIGIBLE')
    assert.equal(r.next_eligible_at,null)
  }
})

test('maximum two follow-ups are allowed to become draft-eligible',()=>{
  assert.equal(evaluate(base({now:'2026-09-30T00:00:00.000Z',followups_sent:1})).status,'DRAFT_ELIGIBLE')
  assert.equal(evaluate(base({now:'2026-09-30T00:00:00.000Z',followups_sent:2})).reason,'FOLLOWUP_LIMIT')
})

test('interval is measured from last outbound, not initial contact',()=>{
  const r=evaluate(base({
    last_outbound_at:'2026-09-25T17:25:00.000Z',
    now:'2026-09-27T17:25:00.000Z',
    followups_sent:1,
  }))
  assert.equal(r.reason,'WAIT_INTERVAL')
  assert.equal(r.next_eligible_at,'2026-09-28T17:25:00.000Z')
})

test('invalid chronology fails closed',()=>{
  assert.throws(()=>evaluate(base({last_outbound_at:'2026-09-21T00:00:00.000Z'})),/precedes initial/)
  assert.throws(()=>evaluate(base({now:'2026-09-21T00:00:00.000Z'})),/precedes last/)
})
