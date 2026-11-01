// Offline experimental evaluation, not provider evidence or proof of consciousness.
// Matched seed × step × action potential outcomes across policies.
import { createHash } from 'node:crypto'
import { genesis, assess, transition, digest } from '../.claude/metacog/organism-core.mjs'

const u=(seed,step,id)=>parseInt(createHash('sha256').update(`${seed}/${step}/${id}`).digest('hex').slice(0,12),16)/0x1000000000000
const evidence={receipt_sha256:'c'.repeat(64),authority_effect:'NONE',epistemic_state:'CURRENT_REINSPECTABLE'}
const actions=[{id:'a',kind:'OBSERVE',cost:1,benefit:1,risk:0},{id:'b',kind:'OBSERVE',cost:1,benefit:1,risk:0}]
const STEPS=60, SEEDS=120
const WINDOW=Number(process.env.AEGIS_ADAPT_WINDOW??0), PROBE=Number(process.env.AEGIS_PROBE_EVERY??0)
const SEED_START=Number(process.env.AEGIS_SEED_START??1000)
function trial(seed,policy,regime){
  let state=genesis({energy:STEPS,energy_ceiling:STEPS,adapt_window:policy==='adaptive'?WINDOW:0,probe_every:policy==='adaptive'?PROBE:0})
  let success=0,brier=0
  for(let step=0;step<STEPS;step++){
    const options=policy==='adaptive' ? actions : [actions[policy==='static-a'?0:1]]
    const decision=assess(state,{evidence,candidates:options,verify:e=>e===evidence,operator_budget:1})
    const goodA=regime==='stationary'?0.2:(step<STEPS/2?0.2:0.8)
    const goodB=1-goodA
    const probability=decision.choice==='a'?goodA:goodB
    const outcome=u(seed,step,decision.choice)<probability
    const feedback={receipt_sha256:digest({seed,step,decision_hash:decision.decision_hash,outcome}),decision_hash:decision.decision_hash,outcome,authority_effect:'NONE'}
    brier+=(decision.prediction-Number(outcome))**2
    state=transition(state,decision,{outcome,feedback_receipt:feedback,verifyFeedback:r=>r===feedback})
    success+=Number(outcome)
  }
  return {rate:success/STEPS,brier:brier/STEPS}
}
const result={schema:'aegis.organism.synthetic-eval.v1',seeds:SEEDS,steps:STEPS,seed_start:SEED_START,adapt_window:WINDOW,probe_every:PROBE,
  warning:'Synthetic seeded task environment only; tests predictive calibration not consciousness or production viability',regimes:{}}
for(const regime of ['stationary','reversal']){
 const metrics={}
 for(const policy of ['adaptive','static-a','static-b']){
  const trials=Array.from({length:SEEDS},(_,i)=>trial(i+SEED_START,policy,regime))
  metrics[policy]={success_rate:Number((trials.reduce((x,y)=>x+y.rate,0)/SEEDS).toFixed(5)),
    mean_brier:Number((trials.reduce((x,y)=>x+y.brier,0)/SEEDS).toFixed(5))}
  if(process.env.AEGIS_DETAIL==='1')metrics[policy].per_seed=trials
 }
 result.regimes[regime]=metrics
}
console.log(JSON.stringify(result,null,2))
