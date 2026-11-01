// Reproducible offline experiment: evidence -> decision -> REAL sandbox file -> byte verification -> learned memory.
// Uses a synthetic sensor only in this demo; NOT native AEGIS source admission or evidence of consciousness.
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { genesis, assess, transition, settleFeedback, certifyHistory, predictedSuccess } from '../.claude/metacog/organism-core.mjs'
import { prepareProposal, verifyProposal } from '../.claude/metacog/organism-motor.mjs'
const sandbox=mkdtempSync(join(tmpdir(),'aegis-real-causal-'))
const evidence={receipt_sha256:'1'.repeat(64),authority_effect:'NONE',epistemic_state:'CURRENT_REINSPECTABLE'}
const options=[{id:'patch-candidate',kind:'PROPOSE',cost:2,benefit:9,risk:.05}]
const states=[genesis({energy:8,energy_ceiling:8})]
const decision=assess(states.at(-1),{evidence,candidates:options,verify:e=>e===evidence,operator_budget:2})
const after=transition(states.at(-1),decision,{outcome:null});states.push(after)
const feedback=prepareProposal(decision,{sandbox})
if(!verifyProposal(feedback,{sandbox}))throw new Error('PROPOSAL_BYTE_VERIFICATION_FAILED')
const settled=settleFeedback(after,feedback,r=>verifyProposal(r,{sandbox}));states.push(settled)
const receipt={mode:'LOCAL_CAUSAL_EXPERIMENT_SYNTHETIC_SENSOR',
  before:{sequence:0,energy:states[0].energy,model:predictedSuccess(states[0],decision.choice)},
  action:{kind:decision.kind,decision_hash:decision.decision_hash,proposal_path:feedback.path,
    actual_bytes:readFileSync(feedback.path).length,byte_verified:true,authority_effect:'NONE'},
  after:{sequence:settled.sequence,energy:settled.energy,verified_outcomes:settled.knowledge.n,
    model:predictedSuccess(settled,decision.choice)},history:certifyHistory(states)}
console.log(JSON.stringify(receipt,null,2))
