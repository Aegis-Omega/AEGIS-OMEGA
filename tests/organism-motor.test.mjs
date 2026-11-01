import {test} from 'node:test'
import assert from 'node:assert/strict'
import {mkdtempSync,readFileSync,writeFileSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {genesis,assess,transition,settleFeedback,certifyHistory} from '../.claude/metacog/organism-core.mjs'
import {prepareProposal,verifyProposal} from '../.claude/metacog/organism-motor.mjs'
const evidence={receipt_sha256:'a'.repeat(64),authority_effect:'NONE',epistemic_state:'CURRENT_REINSPECTABLE'}
function decision(s=genesis()){return assess(s,{evidence,candidates:[{id:'candidate',kind:'PROPOSE',benefit:9,cost:2,risk:0}],verify:e=>e===evidence,operator_budget:4})}
test('motor: actual local proposal file is created, read back and independently byte-verified',()=>{
 const sandbox=mkdtempSync(join(tmpdir(),'aegis-motor-')),s=genesis(),d=decision(s),after=transition(s,d,{outcome:null})
 const receipt=prepareProposal(d,{sandbox})
 assert.equal(verifyProposal(receipt,{sandbox}),true)
 const settled=settleFeedback(after,receipt,r=>verifyProposal(r,{sandbox}))
 assert.equal(settled.knowledge.successes,1)
 assert.equal(certifyHistory([s,after,settled]).valid,true)
 assert.equal(JSON.parse(readFileSync(receipt.path)).operator_approval,false)
})
test('motor: cannot treat arbitrary observation as actuator command',()=>{
 const s=genesis(),obs=assess(s,{evidence,candidates:[{id:'inspect',kind:'OBSERVE',benefit:8,cost:1,risk:0}],verify:()=>true,operator_budget:3})
 assert.throws(()=>prepareProposal(obs,{sandbox:mkdtempSync(join(tmpdir(),'aegis-motor-'))}),/MOTOR_ACTION_NOT_PROPOSAL/)
})
test('motor: tampered file invalidates receipt',()=>{
 const sandbox=mkdtempSync(join(tmpdir(),'aegis-motor-')),r=prepareProposal(decision(),{sandbox})
 writeFileSync(r.path,readFileSync(r.path,'utf8').replace('CANDIDATE_ONLY','DEPLOYED'))
 assert.equal(verifyProposal(r,{sandbox}),false)
})
test('motor: no external workspace can validate receipt',()=>{
 const sandbox=mkdtempSync(join(tmpdir(),'aegis-motor-')),r=prepareProposal(decision(),{sandbox})
 assert.equal(verifyProposal(r,{sandbox:mkdtempSync(join(tmpdir(),'aegis-other-'))}),false)
})
test('motor: immutability - no silent overwrite or re-run',()=>{
 const sandbox=mkdtempSync(join(tmpdir(),'aegis-motor-')),d=decision()
 prepareProposal(d,{sandbox});assert.throws(()=>prepareProposal(d,{sandbox}),/MOTOR_NO_OVERWRITE/)
})
test('motor: cannot inflate decision authority',()=>{
 const sandbox=mkdtempSync(join(tmpdir(),'aegis-motor-')),d=decision()
 assert.throws(()=>prepareProposal({...d,authority_effect:'DEPLOY'},{sandbox}),/MOTOR_AUTHORITY_INVALID/)
})
test('motor cannot create a proposal in repository or production-style path',()=>{
 const d=decision();assert.throws(()=>prepareProposal(d,{sandbox:process.cwd()}),/MOTOR_OUTSIDE_TEMP/)
})
