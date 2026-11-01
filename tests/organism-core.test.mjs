import { test } from 'node:test'
import assert from 'node:assert/strict'
import { genesis, assess, transition, certifyHistory, predictedSuccess, fitness, digest, settleFeedback } from '../.claude/metacog/organism-core.mjs'
const evidence = {receipt_sha256:'a'.repeat(64),authority_effect:'NONE',epistemic_state:'CURRENT_REINSPECTABLE'}
const verify = e => e===evidence
const candidates = [{id:'inspect',kind:'OBSERVE',benefit:9,risk:0.05,cost:2},{id:'rest',kind:'REST',benefit:0.5,risk:0,cost:0},{id:'propose',kind:'PROPOSE',benefit:8,risk:0.1,cost:3}]
const plan = (s=genesis(),opts={})=>assess(s,{evidence,candidates,verify,operator_budget:10,...opts})
const fb = (h,outcome=true)=>({receipt_sha256:'c'.repeat(64),decision_hash:h,outcome,authority_effect:'NONE'})
const feedback = e=>e.receipt_sha256==='c'.repeat(64)
test('genesis deterministic and valid',()=>{assert.deepEqual(genesis(),genesis());assert.equal(certifyHistory([genesis()]).valid,true)})
test('cannot mint energy beyond operator ceiling',()=>{assert.throws(()=>genesis({energy:200,energy_ceiling:20}),/GENESIS_ENERGY_INVALID/)})
test('cannot accept malformed state',()=>{const s={...genesis(),energy:23};assert.throws(()=>predictedSuccess(s),/STATE_INTEGRITY_FAILED/)})
test('cannot inject arbitrary hash-matched bogus memory statistics',()=>{const s=genesis(), body={...s,knowledge:{...s.knowledge,n:99}};delete body.state_hash; assert.throws(()=>predictedSuccess({...body,state_hash:digest(body)}),/STATE_MEMORY_UNBALANCED/)})
test('denies absent independent verifier',()=>assert.throws(()=>assess(genesis(),{evidence,candidates,operator_budget:10}),/VERIFIER_MISSING/))
test('denies forged or unverified evidence',()=>assert.throws(()=>plan(genesis(),{verify:()=>false}),/EVIDENCE_NOT_VERIFIED/))
test('denies historical evidence',()=>assert.throws(()=>plan(genesis(),{evidence:{...evidence,epistemic_state:'HISTORICAL_NOT_REINSPECTABLE'},verify:()=>true}),/EVIDENCE_STALE_OR_UNKNOWN/))
test('denies evidence claiming authority',()=>assert.throws(()=>plan(genesis(),{evidence:{...evidence,authority_effect:'MERGE'},verify:()=>true}),/EVIDENCE_MAY_NOT_GRANT_AUTHORITY/))
test('no budget gives no external execution',()=>{const d=plan(genesis(),{operator_budget:0});assert.equal(d.kind,'REST');assert.equal(d.authority_effect,'NONE')})
test('ranked action chosen from eligible finite budget',()=>{const d=plan();assert.equal(d.kind,'OBSERVE');assert.equal(d.cost,2)})
test('cannot smuggle approval in proposal candidate',()=>assert.throws(()=>plan(genesis(),{candidates:[{...candidates[2],operator_approval:true}]}),/PROPOSAL_CANNOT_CARRY_GRANT/))
test('duplicate actions rejected',()=>assert.throws(()=>plan(genesis(),{candidates:[candidates[0],candidates[0]]}),/DUPLICATE_ACTION/))
test('fresh cycle burns bounded energy and links state',()=>{const s=genesis();const d=plan(s);const next=transition(s,d,{outcome:null});assert.equal(next.energy,s.energy-d.cost);assert.equal(next.previous_hash,s.state_hash);assert.equal(certifyHistory([s,next]).valid,true)})
test('tampered decision blocked',()=>{const s=genesis(),d=plan(s);assert.throws(()=>transition(s,{...d,cost:0},{outcome:null}),/DECISION_TAMPER_OR_DRIFT/)})
test('stale decision cannot be replayed against new state',()=>{const s=genesis(),d=plan(s),n=transition(s,d,{});assert.throws(()=>transition(n,d,{}),/DECISION_TAMPER_OR_DRIFT/)})
test('no unverified outcome learning',()=>{const s=genesis(),d=plan(s);assert.throws(()=>transition(s,d,{outcome:true}),/FEEDBACK_VERIFIER_MISSING/)})
test('feedback exact decision binding mandatory',()=>{const s=genesis(),d=plan(s);assert.throws(()=>transition(s,d,{outcome:true,feedback_receipt:fb('f'.repeat(64)),verifyFeedback:feedback}),/FEEDBACK_UNVERIFIED_OR_UNBOUND/)})
test('verified outcomes calibrate rather than self-report',()=>{const s=genesis(),d=plan(s),n=transition(s,d,{outcome:true,feedback_receipt:fb(d.decision_hash),verifyFeedback:feedback});assert.equal(n.knowledge.n,1);assert.equal(n.knowledge.successes,1);assert.equal(n.knowledge.brier_sum,.25);assert.equal(predictedSuccess(n),2/3)})
test('negative independently verified feedback also learns',()=>{const s=genesis(),d=plan(s),n=transition(s,d,{outcome:false,feedback_receipt:fb(d.decision_hash,false),verifyFeedback:feedback});assert.equal(n.knowledge.failures,1);assert.equal(predictedSuccess(n),1/3)})
test('no mutation rights can be gained through feedback',()=>{const s=genesis(),d=plan(s);assert.throws(()=>transition(s,d,{outcome:true,feedback_receipt:{...fb(d.decision_hash),authority_effect:'DEPLOY'},verifyFeedback:()=>true}),/FEEDBACK_AUTHORITY_INVALID/)})
test('depleted integrity stops productive actions',()=>{const s=genesis({integrity:10});const d=plan(s);assert.equal(d.status,'HOLD_INTEGRITY');assert.equal(d.kind,'REST')})
test('history mutation breaks chain',()=>{const s=genesis(),d=plan(s),n=transition(s,d,{});assert.throws(()=>certifyHistory([s,{...n,energy:15}]),/STATE_INTEGRITY_FAILED/)})
test('history dropping transition fails linkage',()=>{const s=genesis(),d=plan(s),n=transition(s,d,{}),settled=settleFeedback(n,fb(d.decision_hash),feedback);assert.throws(()=>certifyHistory([s,settled]),/HISTORY_BROKEN/)})
test('no fabricated positive fitness from speed alone',()=>{assert.deepEqual(fitness({quality:.4,robustness:1,resource_cost:0,capacity:100,policy:{min_quality:.9,min_robustness:.8}}),{eligible:false,utility:null});assert.equal(fitness({quality:.95,robustness:.9,resource_cost:2,capacity:100,policy:{min_quality:.9,min_robustness:.8}}).eligible,true)})
test('no NaN or infinity permitted',()=>assert.throws(()=>plan(genesis(),{candidates:[{id:'bad',kind:'REST',cost:0,risk:NaN,benefit:1}]}),/ACTION_ESTIMATE_INVALID/))
test('deterministic identical inputs and history produce same hash',()=>{const a=genesis(),b=genesis();const da=plan(a),db=plan(b);assert.equal(da.decision_hash,db.decision_hash);assert.equal(transition(a,da,{}).state_hash,transition(b,db,{}).state_hash)})

test('cannot claim success with independently bound failure receipt',()=>{const s=genesis(),d=plan(s);assert.throws(()=>transition(s,d,{outcome:true,feedback_receipt:fb(d.decision_hash,false),verifyFeedback:feedback}),/FEEDBACK_UNVERIFIED_OR_UNBOUND/)})
test('causal memory: verified failure changes next action, unchanged evidence does not',()=>{
 const actions=[{id:'a',kind:'OBSERVE',benefit:8,risk:0,cost:1},{id:'b',kind:'OBSERVE',benefit:8,risk:0,cost:1}]
 const s=genesis(),p0=plan(s,{candidates:actions});assert.equal(p0.choice,'a')
 const noFeedback=transition(s,p0,{outcome:null})
 assert.throws(()=>plan(noFeedback,{candidates:actions}),/PENDING_OUTCOME_MUST_SETTLE/) // no new action without outcome
 const learned=transition(s,p0,{outcome:false,feedback_receipt:fb(p0.decision_hash,false),verifyFeedback:feedback})
 assert.equal(learned.knowledge.actions.a.failures,1)
 assert.equal(plan(learned,{candidates:actions}).choice,'b')
})
test('ablation: unverifiable feedback cannot reverse action preference',()=>{
 const actions=[{id:'a',kind:'OBSERVE',benefit:8,risk:0,cost:1},{id:'b',kind:'OBSERVE',benefit:8,risk:0,cost:1}]
 const s=genesis(),p0=plan(s,{candidates:actions})
 assert.throws(()=>transition(s,p0,{outcome:false,feedback_receipt:fb(p0.decision_hash,false),verifyFeedback:()=>false}),/FEEDBACK_UNVERIFIED_OR_UNBOUND/)
 assert.equal(plan(s,{candidates:actions}).choice,'a')
})

test('late source-verified feedback causally updates the policy without spending energy twice',()=>{
 const choices=[{id:'a',kind:'OBSERVE',benefit:8,risk:0,cost:1},{id:'b',kind:'OBSERVE',benefit:8,risk:0,cost:1}]
 const s=genesis(),decision=plan(s,{candidates:choices}),after=transition(s,decision,{outcome:null})
 assert.equal(after.knowledge.n,0)
 const settled=settleFeedback(after,fb(decision.decision_hash,false),feedback)
 assert.equal(settled.energy,after.energy)
 assert.equal(settled.knowledge.n,1)
 assert.equal(plan(settled,{candidates:choices}).choice,'b')
 assert.equal(certifyHistory([s,after,settled]).valid,true)
 assert.throws(()=>settleFeedback(settled,fb(decision.decision_hash,false),feedback),/NO_UNSETTLED_ACTION/)
})
test('late feedback refuses conflicting decision',()=>{
 const s=genesis(),d=plan(s),n=transition(s,d,{})
 assert.throws(()=>settleFeedback(n,fb('f'.repeat(64),true),feedback),/FEEDBACK_UNVERIFIED_OR_UNBOUND/)
})

test('cannot invent fitness thresholds without an operator policy',()=>assert.throws(()=>fitness({quality:1,robustness:1,resource_cost:0,capacity:1}),/FITNESS_POLICY_REQUIRED/))

test('integrity floor is policy-bound and changes eligible decisions',()=>{const s=genesis({integrity:30,integrity_floor:40});const d=plan(s);assert.equal(d.status,'HOLD_INTEGRITY');assert.equal(d.kind,'REST')})

test('pending action cannot be overwritten by a new plan before verified settlement',()=>{
 const s=genesis(),d=plan(s),pending=transition(s,d,{outcome:null})
 assert.throws(()=>plan(pending),/PENDING_OUTCOME_MUST_SETTLE/)
 const settled=settleFeedback(pending,fb(d.decision_hash),feedback)
 assert.equal(plan(settled).sequence,settled.sequence+1)
})

test('adaptive memory window stores bounded verifiable outcomes without losing totals',()=>{
 const s=genesis({adapt_window:3,probe_every:0})
 const first=plan(s,{candidates:[{id:'a',kind:'OBSERVE',cost:1,benefit:9,risk:0}]})
 const a=transition(s,first,{outcome:true,feedback_receipt:fb(first.decision_hash),verifyFeedback:feedback})
 assert.equal(a.adaptation.window,3)
 assert.deepEqual(a.knowledge.actions.a.recent,[1]);assert.equal(a.knowledge.n,1)
 assert.equal(certifyHistory([s,a]).valid,true)
})
test('adaptive exploration is source-bound, periodic and budget-constrained',()=>{
 const choices=[{id:'a',kind:'OBSERVE',benefit:8,risk:0,cost:1},{id:'b',kind:'OBSERVE',benefit:8,risk:0,cost:1}]
 const s=genesis({adapt_window:5,probe_every:2})
 const d=plan(s,{candidates:choices})
 const n=transition(s,d,{outcome:true,feedback_receipt:fb(d.decision_hash),verifyFeedback:feedback})
 const d2=plan(n,{candidates:choices})
 const n2=transition(n,d2,{outcome:true,feedback_receipt:fb(d2.decision_hash),verifyFeedback:feedback})
 const p=plan(n2,{candidates:choices})
 assert.equal(p.probe,true);assert.equal(p.choice,'b')
 assert.equal(p.cost,1);assert.equal(p.authority_effect,'NONE')
})
test('adaptation parameters cannot be changed by hash-matched state tampering',()=>{
 const s=genesis({adapt_window:5,probe_every:2}), body={...s,adaptation:{window:1000,probe_every:2}}
 delete body.state_hash
 assert.throws(()=>predictedSuccess({...body,state_hash:digest(body)}),/ADAPTATION_POLICY_INVALID/)
})
