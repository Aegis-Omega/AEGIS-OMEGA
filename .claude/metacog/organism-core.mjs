// AEGIS Ω · Causal Organism Core v1
// Authority-neutral, deterministic, finite-energy, evidence-bound controller.
// Does not confer agency rights, consciousness, protected-main access, or self-preservation rights.
import { createHash } from 'node:crypto'

export const SCHEMA = 'aegis.organism.v1'
const Z = '0'.repeat(64)
const HASH = /^[0-9a-f]{64}$/
const ACTIONS = new Set(['OBSERVE', 'PROPOSE', 'REST'])
const freeze = x => Object.freeze(x)
export function canonical(x) {
  if (x === null || typeof x !== 'object') {
    if (typeof x === 'number' && !Number.isFinite(x)) throw new Error('non-finite value')
    return JSON.stringify(x)
  }
  if (Array.isArray(x)) return '[' + x.map(canonical).join(',') + ']'
  return '{' + Object.keys(x).sort().map(k => JSON.stringify(k) + ':' + canonical(x[k])).join(',') + '}'
}
export const digest = value => createHash('sha256').update(canonical(value), 'utf8').digest('hex')
const integer = (x,min=0,max=Number.MAX_SAFE_INTEGER) => Number.isSafeInteger(x) && x>=min && x<=max
const assert = (x,m) => {if (!x) throw new Error(m)}
const finite = (x,min=0,max=1) => typeof x==='number' && Number.isFinite(x) && x>=min && x<=max
const reduced = (p,o,action,sequence,window) => {
  const previous=p.actions[action] ?? {n:0,successes:0,failures:0,brier_sum:0}
  const recent=window>0?[...(previous.recent??[]),o].slice(-window):[]
  const next=freeze({n:previous.n+1,successes:previous.successes+(o?1:0),
    failures:previous.failures+(o?0:1),brier_sum:previous.brier_sum+(p.last_prediction-o)**2,
    recent:freeze(recent),last_seen_sequence:sequence})
  return freeze({successes:p.successes+(o?1:0), failures:p.failures+(o?0:1),
    n:p.n+1,brier_sum:p.brier_sum+(p.last_prediction-o)**2,
    last_prediction:p.last_prediction,actions:freeze({...p.actions,[action]:next})})
}
function checkState(s) {
  assert(s && s.schema===SCHEMA, 'STATE_SCHEMA_INVALID')
  assert(integer(s.sequence), 'STATE_SEQUENCE_INVALID')
  assert(integer(s.energy,0,10000) && integer(s.integrity,0,100), 'STATE_HOMEOSTASIS_INVALID')
  assert(integer(s.energy_ceiling,1,10000) && s.energy<=s.energy_ceiling, 'STATE_RESOURCE_CEILING')
  assert(integer(s.integrity_floor,1,100), 'STATE_INTEGRITY_POLICY_INVALID')
  assert(s.adaptation && integer(s.adaptation.window,0,256) && integer(s.adaptation.probe_every,0,256),'ADAPTATION_POLICY_INVALID')
  assert(HASH.test(s.previous_hash) && HASH.test(s.state_hash), 'STATE_HASH_FORMAT')
  assert(s.last_action===null || HASH.test(s.last_action), 'STATE_ACTION_INVALID')
  assert(s.last_action_id===null || /^[a-zA-Z0-9_.:-]{1,80}$/.test(s.last_action_id), 'STATE_ACTION_ID_INVALID')
  // v1 checkpoints predate the optional action-kind witness: accept their exact bytes.
  // A legacy pending action with unknown kind must never be motor-replayed.
  if(Object.hasOwn(s,'last_action_kind')) {
    assert(s.last_action_kind===null || ACTIONS.has(s.last_action_kind), 'STATE_ACTION_KIND_INVALID')
    assert((s.last_action_kind===null)===(s.last_action_id===null),'STATE_ACTION_KIND_PAIR_INVALID')
  }
  assert((s.last_action===null)===(s.last_action_id===null), 'STATE_ACTION_PAIR_INVALID')
  assert(s.last_receipt===null || HASH.test(s.last_receipt), 'STATE_RECEIPT_INVALID')
  assert(s.last_evidence===null || HASH.test(s.last_evidence), 'STATE_EVIDENCE_INVALID')
  assert(s.knowledge && integer(s.knowledge.n) && integer(s.knowledge.successes) && integer(s.knowledge.failures), 'STATE_MEMORY_INVALID')
  assert(s.knowledge.n===s.knowledge.successes+s.knowledge.failures, 'STATE_MEMORY_UNBALANCED')
  assert(Number.isFinite(s.knowledge.brier_sum) && s.knowledge.brier_sum>=0 && finite(s.knowledge.last_prediction), 'STATE_CALIBRATION_INVALID')
  assert(s.knowledge.actions && typeof s.knowledge.actions==='object' && !Array.isArray(s.knowledge.actions),'STATE_ACTION_MEMORY_INVALID')
  let actionCount=0
  for(const [id,p] of Object.entries(s.knowledge.actions)) {
    assert(/^[a-zA-Z0-9_.:-]{1,80}$/.test(id) && integer(p.n) && integer(p.successes) && integer(p.failures)
      && p.n===p.successes+p.failures && Number.isFinite(p.brier_sum) && p.brier_sum>=0,'STATE_ACTION_MEMORY_INVALID')
    assert(Array.isArray(p.recent)&&p.recent.length<=s.adaptation.window&&p.recent.every(x=>x===0||x===1),'STATE_RECENCY_INVALID')
    assert(integer(p.last_seen_sequence,1,s.sequence),'STATE_LAST_SEEN_INVALID')
    actionCount+=p.n
  }
  assert(actionCount===s.knowledge.n,'STATE_ACTION_MEMORY_UNBALANCED')
  const {state_hash,...body}=s
  assert(digest(body)===state_hash,'STATE_INTEGRITY_FAILED')
  return true
}
export function genesis({energy=24,energy_ceiling=24,integrity=100,integrity_floor=20,
  adapt_window=0,probe_every=0}={}) {
  assert(integer(energy,0,10000) && integer(energy_ceiling,1,10000) && energy<=energy_ceiling, 'GENESIS_ENERGY_INVALID')
  assert(integer(integrity,0,100),'GENESIS_INTEGRITY_INVALID')
  assert(integer(integrity_floor,1,100),'GENESIS_INTEGRITY_POLICY_INVALID')
  assert(integer(adapt_window,0,256)&&integer(probe_every,0,256),'GENESIS_ADAPTATION_POLICY_INVALID')
  const body={schema:SCHEMA,sequence:0,previous_hash:Z,energy,energy_ceiling,integrity,integrity_floor,last_action:null,last_action_id:null,last_action_kind:null,
    knowledge:freeze({n:0,successes:0,failures:0,brier_sum:0,last_prediction:0.5,actions:freeze({})}),last_receipt:null,
    last_evidence:null,mode:'ACTIVE',adaptation:freeze({window:adapt_window,probe_every})}
  return freeze({...body,state_hash:digest(body)})
}
// Evidence must be independently checked outside this module. A mere `verified:true` string is NOT evidence.
// The verifier is a required dependency; callers cannot bypass its verdict.
function validateEvidence(e,verify) {
  assert(typeof verify==='function','VERIFIER_MISSING')
  assert(e && typeof e==='object' && HASH.test(e.receipt_sha256), 'EVIDENCE_FORMAT_INVALID')
  assert(verify(e)===true,'EVIDENCE_NOT_VERIFIED')
  assert(e.authority_effect==='NONE','EVIDENCE_MAY_NOT_GRANT_AUTHORITY')
  assert(e.epistemic_state==='CURRENT_REINSPECTABLE','EVIDENCE_STALE_OR_UNKNOWN')
}
function validateCandidates(candidates) {
  assert(Array.isArray(candidates) && candidates.length>0 && candidates.length<=32,'CANDIDATES_INVALID')
  const ids=new Set()
  for(const a of candidates){
    assert(a && typeof a.id==='string' && /^[a-zA-Z0-9_.:-]{1,80}$/.test(a.id),'ACTION_ID_INVALID')
    assert(!ids.has(a.id),'DUPLICATE_ACTION');ids.add(a.id)
    assert(ACTIONS.has(a.kind),'ACTION_KIND_FORBIDDEN')
    assert(integer(a.cost,0,10000) && finite(a.benefit,0,100) && finite(a.risk), 'ACTION_ESTIMATE_INVALID')
    assert(a.kind!=='PROPOSE'||a.operator_approval!==true,'PROPOSAL_CANNOT_CARRY_GRANT')
  }
}
const clamp=(x,lo,hi)=>Math.max(lo,Math.min(hi,x))
export function predictedSuccess(state,action=null) {
  checkState(state)
  const k=action ? (state.knowledge.actions[action] ?? {n:0,successes:0}) : state.knowledge
  // A bounded recent window lets the self-model recover when the world changes.
  // Window=0 retains the V2 all-history posterior.
  if(action && state.adaptation.window>0 && Array.isArray(k.recent) && k.recent.length>0)
    return (1+k.recent.reduce((sum,v)=>sum+v,0))/(k.recent.length+2)
  return (k.successes+1)/(k.n+2) // Beta(1,1), verified feedback only
}
export function assess(state,{evidence,candidates,verify,operator_budget=0}) {
  checkState(state);validateEvidence(evidence,verify);validateCandidates(candidates)
  assert(state.last_action===null || state.last_receipt!==null,'PENDING_OUTCOME_MUST_SETTLE')
  assert(integer(operator_budget,0,10000),'OPERATOR_BUDGET_INVALID')
  // No automatic budget increase. An operator budget is a per-cycle cap, not a credit or stored energy.
  const eligible=candidates.filter(a=>a.cost<=state.energy && a.cost<=operator_budget &&
    (a.kind==='REST'||state.integrity>=state.integrity_floor))
  const ranked=eligible.map(a=>({action:a,score:(a.benefit*predictedSuccess(state,a.id)*(1-a.risk)-a.cost/state.energy_ceiling)/(1+a.cost/Math.max(1,operator_budget))}))
    .sort((a,b)=>b.score-a.score || a.action.id.localeCompare(b.action.id))
  // Controlled counterfactual probe: occasionally measure the stalest eligible
  // action rather than permanently exploiting an obsolete posterior.
  const explore=state.adaptation.probe_every>0 && state.sequence>0 &&
    state.sequence%state.adaptation.probe_every===0
  const probes=eligible.filter(a=>a.kind!=='REST').sort((a,b)=>{
    const aLast=state.knowledge.actions[a.id]?.last_seen_sequence ?? -1
    const bLast=state.knowledge.actions[b.id]?.last_seen_sequence ?? -1
    return aLast-bLast || a.id.localeCompare(b.id)
  })
  const chosen=explore && probes.length>1 ? probes[0] : ranked[0]?.action ?? null
  const chosenScore=ranked.find(x=>x.action.id===chosen?.id)?.score ?? null
  const prediction=chosen ? predictedSuccess(state,chosen.id) : predictedSuccess(state)
  const status= state.integrity<state.integrity_floor?'HOLD_INTEGRITY':state.energy===0?'HOLD_ENERGY':chosen?'ADVISORY':'HOLD_BUDGET'
  const decision={schema:'aegis.organism-decision.v1',state_hash:state.state_hash,sequence:state.sequence+1,
    evidence_receipt:evidence.receipt_sha256,choice:chosen?.id??null,kind:chosen?.kind??'HOLD',
    cost:chosen?.cost??0,prediction,score:chosenScore,status,probe:Boolean(explore&&probes.length>1),authority_effect:'NONE'}
  return freeze({...decision,decision_hash:digest(decision)})
}
// Feedback is supplied by an INDEPENDENT verifier and must bind the exact preregistered decision.
// Unknown outcomes are not silently learned as successes or failures.
export function transition(state,decision,{outcome,feedback_receipt,verifyFeedback,integrity_delta=0}={}) {
  checkState(state)
  assert(decision?.schema==='aegis.organism-decision.v1','DECISION_SCHEMA_INVALID')
  const {decision_hash,...d}=decision
  assert(digest(d)===decision_hash && decision.state_hash===state.state_hash,'DECISION_TAMPER_OR_DRIFT')
  assert(decision.sequence===state.sequence+1,'DECISION_SEQUENCE_MISMATCH')
  assert(integer(decision.cost) && decision.cost<=state.energy,'ENERGY_BUDGET_EXCEEDED')
  assert(decision.choice!==null || (decision.cost===0 && decision.kind==='HOLD'),'INVALID_HOLD_COST')
  assert(integer(integrity_delta,-100,100),'INTEGRITY_DELTA_INVALID')
  assert(outcome===true||outcome===false||outcome===null||outcome===undefined,'OUTCOME_INVALID')
  assert(decision.authority_effect==='NONE','AUTHORITY_ESCALATION')
  let knowledge=state.knowledge
  let receipt=null
  if(outcome===true||outcome===false){
    assert(typeof verifyFeedback==='function','FEEDBACK_VERIFIER_MISSING')
    assert(feedback_receipt && HASH.test(feedback_receipt.receipt_sha256), 'FEEDBACK_RECEIPT_INVALID')
    assert(feedback_receipt.decision_hash===decision_hash && feedback_receipt.outcome===outcome && verifyFeedback(feedback_receipt)===true,'FEEDBACK_UNVERIFIED_OR_UNBOUND')
    assert(feedback_receipt.authority_effect==='NONE','FEEDBACK_AUTHORITY_INVALID')
    knowledge=reduced({...state.knowledge,last_prediction:decision.prediction},outcome?1:0,decision.choice,decision.sequence,state.adaptation.window)
    receipt=feedback_receipt.receipt_sha256
  }
  const energy=state.energy-decision.cost
  const integrity=clamp(state.integrity+integrity_delta,0,100)
  const mode=integrity===0||energy===0?'DORMANT':integrity<state.integrity_floor?'REPAIR_ONLY':'ACTIVE'
  const body={schema:SCHEMA,sequence:decision.sequence,previous_hash:state.state_hash,
    energy,energy_ceiling:state.energy_ceiling,integrity,integrity_floor:state.integrity_floor,last_action:decision.choice===null?null:decision_hash,last_action_id:decision.choice,
    last_action_kind:decision.choice===null?null:decision.kind,
    knowledge:outcome===null||outcome===undefined?freeze({...knowledge,last_prediction:decision.prediction}):knowledge,last_receipt:receipt,last_evidence:decision.evidence_receipt,mode,adaptation:state.adaptation}
  return freeze({...body,state_hash:digest(body)})
}
// Actuator feedback can arrive after the advisory action was recorded.
// Do not mutate confidence until an independent provider binds the exact decision and outcome.
export function settleFeedback(state, receipt, verifyFeedback) {
  checkState(state)
  assert(state.last_action!==null && state.last_receipt===null,'NO_UNSETTLED_ACTION')
  assert(typeof verifyFeedback==='function','FEEDBACK_VERIFIER_MISSING')
  assert(receipt && HASH.test(receipt.receipt_sha256) && receipt.decision_hash===state.last_action
    && (receipt.outcome===true||receipt.outcome===false) && receipt.authority_effect==='NONE'
    && verifyFeedback(receipt)===true,'FEEDBACK_UNVERIFIED_OR_UNBOUND')
  const knowledge=reduced(state.knowledge,receipt.outcome?1:0,state.last_action_id,state.sequence+1,state.adaptation.window)
  const body={schema:SCHEMA,sequence:state.sequence+1,previous_hash:state.state_hash,
    energy:state.energy,energy_ceiling:state.energy_ceiling,integrity:state.integrity,integrity_floor:state.integrity_floor,
    last_action:state.last_action,last_action_id:state.last_action_id,
    ...(Object.hasOwn(state,'last_action_kind') ? {last_action_kind:state.last_action_kind} : {}),
    knowledge,last_receipt:receipt.receipt_sha256,last_evidence:state.last_evidence,mode:state.mode,adaptation:state.adaptation}
  return freeze({...body,state_hash:digest(body)})
}
export function certifyHistory(states) {
  assert(Array.isArray(states)&&states.length>0,'HISTORY_EMPTY')
  for(let i=0;i<states.length;i++){
    checkState(states[i])
    if(i===0){assert(states[i].sequence===0 && states[i].previous_hash===Z,'HISTORY_GENESIS_INVALID')}
    else assert(states[i].previous_hash===states[i-1].state_hash && states[i].sequence===states[i-1].sequence+1,'HISTORY_BROKEN')
  }
  return freeze({valid:true,length:states.length,terminal_hash:states.at(-1).state_hash})
}
export function fitness({quality,robustness,resource_cost,capacity,policy}) {
  assert(finite(quality)&&finite(robustness)&&finite(resource_cost,0,10000)&&finite(capacity,1,10000),'FITNESS_INPUT_INVALID')
  assert(policy && finite(policy.min_quality) && finite(policy.min_robustness),'FITNESS_POLICY_REQUIRED')
  // Benefit-density only AFTER viability gates. Efficiency must never substitute correctness.
  return freeze({eligible:quality>=policy.min_quality && robustness>=policy.min_robustness,
    utility:quality>=policy.min_quality&&robustness>=policy.min_robustness ? (quality*robustness)/(1+resource_cost/capacity):null})
}
