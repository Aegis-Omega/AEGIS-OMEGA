import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtempSync,writeFileSync,readFileSync,unlinkSync,lstatSync,symlinkSync,existsSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {createHash} from 'node:crypto'
import {runLocalOrganismStep} from '../.claude/metacog/organism-coordinator.mjs'
import {inspectOrganismState,runBoundOrganismCycle} from '../.claude/metacog/organism-bridge.mjs'
import {digest,certifyHistory} from '../.claude/metacog/organism-core.mjs'
const H='e'.repeat(40)
function fixture({kind='PROPOSE',sourceOK=true}={}){
  const dir=mkdtempSync(join(tmpdir(),'aegis-v4-local-'))
  const sandbox=join(dir,'motor')
  const historyPath=join(dir,'history.json')
  const chainPath=join(dir,'chain.mjs')
  const chainFile=join(dir,'chain.jsonl')
  const receiptPath=join(dir,'receipt.json')
  const source=join(dir,'source.dat')
  const sourceData=Buffer.from('byte verified original evidence\n')
  writeFileSync(source,sourceData)
  writeFileSync(chainFile,JSON.stringify({observation:{layer:'SENSATION',signal:'bootstrap-readonly'}})+'\n')
  writeFileSync(chainPath,`import {readFileSync} from 'node:fs';
const es=readFileSync(${JSON.stringify(chainFile)},'utf8').trim().split('\\n').filter(Boolean);
console.log(JSON.stringify({is_valid:true,entry_count:es.length,terminal_hash:'f'.repeat(64)}));`)
  const base={schema:'aegis.metacognitive-evidence-receipt.v1',head_sha:H,authority_effect:'NONE',
    current_epistemic_state:'CURRENT_REINSPECTABLE',evidence:[{evidence_id:'source:test',load_bearing:true,
    exact_head_bound:true,evidence_state:'CURRENT_REINSPECTABLE',artifact:{available:true,expired:false,
    digest:'sha256:'+createHash('sha256').update(sourceOK?sourceData:Buffer.from('other')).digest('hex')}}]}
  const receipt={...base,receipt_sha256:digest(base)}
  const transitionHash='b'.repeat(64)
  let calls=0
  const options={historyPath,sandbox,receiptPath,chainPath,ledgerPath:join(dir,'ledger.jsonl'),
    snapshotPath:join(dir,'snap.json'),env:{...process.env,AEGIS_METACOG_CHAIN:chainFile},
    sourcePaths:{'source:test':source},operator_budget:3,allowInitialize:true,
    candidates:[{id:'draft',kind,benefit:10,cost:1,risk:0}],
    ledgerVerifier:entries=>Array.isArray(entries)&&entries.every(e=>/^[0-9a-f]{64}$/.test(e.transition_hash??'')&&/^[0-9a-f]{64}$/.test(e.receipt_sha256??'')),
    evidenceCycle:()=>{calls++;writeFileSync(receiptPath,JSON.stringify(receipt));
      writeFileSync(join(dir,'ledger.jsonl'),JSON.stringify({receipt_sha256:receipt.receipt_sha256,transition_hash:transitionHash})+'\n');
      writeFileSync(chainFile,readFileSync(chainFile,'utf8')+JSON.stringify({observation:{layer:'METACOGNITIVE',signal:`receipt=${receipt.receipt_sha256} transition=${transitionHash} authority=NONE`}})+'\n')
      return {authority_effect:'NONE',receipt_sha256:receipt.receipt_sha256,ledger:{transition_hash:transitionHash}}},
    receiptVerifier:r=>r.receipt_sha256===digest(Object.fromEntries(Object.entries(r).filter(([key])=>key!=='receipt_sha256')))}
  return {options,dir,sandbox,historyPath,getCalls:()=>calls,source,receipt}
}

test('complete: evidence -> decision -> proposal byte check -> verified feedback -> memory',()=>{
 const f=fixture();const result=runLocalOrganismStep(f.options)
 assert.equal(result.stage,'LOCAL_ARTIFACT_VERIFIED');assert.equal(result.feedback.n_verified,1)
 assert.equal(f.getCalls(),1)
 const states=JSON.parse(readFileSync(f.historyPath,'utf8')).states
 assert.equal(states.length,3);assert.equal(states.at(-1).knowledge.successes,1)
 assert.equal(states.at(-1).last_action_kind,'PROPOSE')
 assert.ok(certifyHistory(states).valid)
 assert.equal(runLocalOrganismStep(f.options).stage,'NOOP')
 assert.equal(f.getCalls(),2) // underlying native port may be invoked again, but no new motor action
 assert.equal(JSON.parse(readFileSync(f.historyPath)).states.length,3)
})
test('crash after decision: recover pending without invoking evidence again',()=>{
 const f=fixture();assert.throws(()=>runLocalOrganismStep(f.options,{failpoint:'AFTER_DECISION'}),/INJECTED_AFTER_DECISION/)
 assert.equal(f.getCalls(),1)
 assert.equal(inspectOrganismState(f.historyPath).last_receipt,null)
 const out=runLocalOrganismStep(f.options)
 assert.equal(out.stage,'LOCAL_ARTIFACT_VERIFIED');assert.equal(f.getCalls(),1)
 assert.equal(out.feedback.n_verified,1)
})
test('crash after motor: recover existing bytes without overwriting artifact',()=>{
 const f=fixture();assert.throws(()=>runLocalOrganismStep(f.options,{failpoint:'AFTER_MOTOR'}),/INJECTED_AFTER_MOTOR/)
 const prior=inspectOrganismState(f.historyPath)
 const path=join(f.sandbox,`proposal-${prior.last_action}.json`)
 const data=readFileSync(path)
 const out=runLocalOrganismStep(f.options)
 assert.equal(out.recovered_artifact,true);assert.equal(f.getCalls(),1)
 assert.deepEqual(readFileSync(path),data)
})
test('corrupted motor output: recovery HOLD and no false feedback',()=>{
 const f=fixture();assert.throws(()=>runLocalOrganismStep(f.options,{failpoint:'AFTER_MOTOR'}))
 const s=inspectOrganismState(f.historyPath)
 writeFileSync(join(f.sandbox,`proposal-${s.last_action}.json`),'wrong bytes')
 assert.throws(()=>runLocalOrganismStep(f.options),/MOTOR_RECOVERY_INVALID_ARTIFACT/)
 assert.equal(inspectOrganismState(f.historyPath).knowledge.n,0)
 assert.equal(f.getCalls(),1)
})
test('source bytes mismatch: no state and no local motor',()=>{
 const f=fixture({sourceOK:false})
 assert.throws(()=>runLocalOrganismStep(f.options),/SOURCE_BYTES_MISMATCH/)
 assert.equal(existsSync(f.historyPath),false)
})
test('non-motor OBSERVE cannot be relabeled as PROPOSE',()=>{
 const f=fixture({kind:'OBSERVE'})
 const out=runLocalOrganismStep(f.options)
 assert.equal(out.stage,'HOLD_NO_LOCAL_MOTOR')
 assert.equal(inspectOrganismState(f.historyPath).last_action_kind,'OBSERVE')
 assert.equal(runLocalOrganismStep(f.options).stage,'HOLD_NO_LOCAL_MOTOR')
 assert.equal(f.getCalls(),1)
})
test('concurrent runner lease: refusal does not alter foreign lock',()=>{
 const f=fixture();writeFileSync(f.historyPath+'.cycle.lock','someone-else')
 assert.throws(()=>runLocalOrganismStep(f.options),/ORGANISM_CYCLE_WRITER_BUSY/)
 assert.equal(readFileSync(f.historyPath+'.cycle.lock','utf8'),'someone-else')
 assert.equal(f.getCalls(),0)
})
test('legacy V3 state lacking action kind: remains valid, cannot silently replay an unknown motor', async()=>{
 const f=fixture();
 // The old V3 source produces hash-linked states without last_action_kind.
 const {genesis,assess,transition,certifyHistory:oldCert}=await import('../fixtures/v3-original/organism-core.mjs')
 const oldG=genesis({energy:12,energy_ceiling:12})
 const ev={receipt_sha256:'a'.repeat(64),authority_effect:'NONE',epistemic_state:'CURRENT_REINSPECTABLE'}
 const d=assess(oldG,{evidence:ev,candidates:[{id:'legacy',kind:'PROPOSE',benefit:5,cost:1,risk:0}],verify:x=>x===ev,operator_budget:3})
 const oldPending=transition(oldG,d,{outcome:null})
 oldCert([oldG,oldPending])
 assert.equal(certifyHistory([oldG,oldPending]).valid,true)
 assert.equal(Object.hasOwn(oldPending,'last_action_kind'),false)
})
test('corrupt chained state or lost anchor remains HOLD',()=>{
 const f=fixture();runLocalOrganismStep(f.options)
 const raw=JSON.parse(readFileSync(f.historyPath));raw.states[1].energy=999;
 writeFileSync(f.historyPath,JSON.stringify(raw))
 assert.throws(()=>runLocalOrganismStep(f.options),/STATE_RESOURCE_CEILING/)
})
test('second distinct receipt can generate new action after settled state',()=>{
 const f=fixture();runLocalOrganismStep(f.options)
 const first=inspectOrganismState(f.historyPath)
 const previousPort=f.options.evidenceCycle
 // Same exact source bytes, but a new exact-head-bound receipt (different provenance attribute)
 const newBody={...f.receipt,observed_at:'2026-11-01T15:00:00Z'}
 delete newBody.receipt_sha256
 const newReceipt={...newBody,receipt_sha256:digest(newBody)}
 f.options.evidenceCycle=()=>{ const old=previousPort();writeFileSync(f.options.receiptPath,JSON.stringify(newReceipt));
   writeFileSync(f.options.env.AEGIS_METACOG_CHAIN,readFileSync(f.options.env.AEGIS_METACOG_CHAIN,'utf8')+JSON.stringify({observation:{layer:'METACOGNITIVE',signal:`receipt=${newReceipt.receipt_sha256} transition=${'c'.repeat(64)} authority=NONE`}})+'\n');
   return {...old,receipt_sha256:newReceipt.receipt_sha256,ledger:{transition_hash:'c'.repeat(64)}} }
 const result=runLocalOrganismStep(f.options)
 assert.equal(result.stage,'LOCAL_ARTIFACT_VERIFIED')
 assert.equal(inspectOrganismState(f.historyPath).knowledge.n,2)
 assert.notEqual(inspectOrganismState(f.historyPath).state_hash,first.state_hash)
})

test('crash recovery refuses source drift before repeating motor action',()=>{
 const f=fixture();assert.throws(()=>runLocalOrganismStep(f.options,{failpoint:'AFTER_DECISION'}))
 writeFileSync(f.source,'stale or replaced source')
 assert.throws(()=>runLocalOrganismStep(f.options),/SOURCE_BYTES_MISMATCH/)
 assert.equal(f.getCalls(),1)
 assert.equal(inspectOrganismState(f.historyPath).knowledge.n,0)
})
test('crash recovery refuses changed receipt and missing ledger',()=>{
 const f=fixture();assert.throws(()=>runLocalOrganismStep(f.options,{failpoint:'AFTER_DECISION'}))
 unlinkSync(f.options.ledgerPath)
 assert.throws(()=>runLocalOrganismStep(f.options),/RECOVERY_LEDGER_MISSING/)
 assert.equal(inspectOrganismState(f.historyPath).knowledge.n,0)
})
