// AEGIS Ω: run the *real* PR #560 evidence-cycle, ledger and chain modules,
// not mocked providers. Synthetic source bytes only, no cloud or model calls.
import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {resolve,join} from 'node:path'
import {spawnSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import {runLocalOrganismStep} from '../.claude/metacog/organism-coordinator.mjs'
import {inspectOrganismState} from '../.claude/metacog/organism-bridge.mjs'
import {runEvidenceCycle} from '../.claude/metacog/evidence-cycle.mjs'
import {verifyReceipt,certifyLedger} from '../.claude/metacog/evidence-ledger.mjs'

const HEAD='a'.repeat(40)
const sha256=x=>createHash('sha256').update(x).digest('hex')
function fixture(){
 const dir=mkdtempSync(join(tmpdir(),'aegis-native-organism-'))
 const meta=join(dir,'.claude/metacog');mkdirSync(meta,{recursive:true})
 const chainPath=resolve('.claude/metacog/chain.mjs')
 const chainFile=join(meta,'chain.jsonl')
 const env={...process.env,CLAUDE_PROJECT_DIR:dir,AEGIS_METACOG_CHAIN:chainFile}
 const seed=spawnSync(process.execPath,[chainPath,'observe','SENSATION','T1','organism-native-test-bootstrap'],{env,encoding:'utf8'})
 assert.equal(seed.status,0,`native chain bootstrap: ${seed.stderr}`)
 const source=join(dir,'source.bin'),bytes=Buffer.from('AEGIS native evidence integration fixture\n')
 writeFileSync(source,bytes)
 const evidenceId='local:source:sha256'
 const snapshot={schema:'aegis.metacognitive-evidence-snapshot.v1',
  subject:{repository:'Aegis-Omega/AEGIS-OMEGA',kind:'local_test',id:560},
  observed_at:'2026-11-01T15:30:00Z',head_sha:HEAD,
  evidence:[{evidence_id:evidenceId,kind:'SOURCE_BYTES',load_bearing:true,
    conclusion:'SUCCESS',bound_head_sha:HEAD,artifact:{id:'bytes',digest:`sha256:${sha256(bytes)}`,
      available:true,expired:false,http_status:200}}]}
 const snapshotPath=join(dir,'snapshot.json');writeFileSync(snapshotPath,JSON.stringify(snapshot))
 const options={snapshotPath,receiptPath:join(meta,'evidence-receipt.tmp'),
  ledgerPath:join(meta,'evidence-transitions.log'),chainPath,historyPath:join(meta,'organism-history.json'),
  sandbox:join(dir,'sandbox'),sourcePaths:{[evidenceId]:source},env,
  candidates:[{id:'local-propose',kind:'PROPOSE',benefit:10,cost:1,risk:0}],
  operator_budget:2,allowInitialize:true,
  evidenceCycle:runEvidenceCycle,receiptVerifier:verifyReceipt,
  ledgerVerifier:entries=>certifyLedger(entries).is_valid===true}
 return {dir,options,source,chainFile}
}

test('native: actual evidence-cycle -> chain mirror -> local motor -> feedback -> certified memory',()=>{
 const f=fixture()
 const r=runLocalOrganismStep(f.options)
 assert.equal(r.stage,'LOCAL_ARTIFACT_VERIFIED')
 assert.equal(r.feedback.n_verified,1)
 assert.equal(inspectOrganismState(f.options.historyPath).knowledge.successes,1)
 const entries=readFileSync(f.options.ledgerPath,'utf8').trim().split('\n').map(JSON.parse)
 assert.equal(certifyLedger(entries).is_valid,true)
 const chain=spawnSync(process.execPath,[f.options.chainPath,'certify'],{env:f.options.env,encoding:'utf8'})
 assert.equal(chain.status,0)
 assert.equal(JSON.parse(chain.stdout).is_valid,true)
 const second=runLocalOrganismStep(f.options)
 assert.equal(second.stage,'NOOP')
 assert.equal(JSON.parse(readFileSync(f.options.historyPath,'utf8')).states.length,3)
})
test('native: crash after actuator write recovers same file and leaves only one ledger receipt',()=>{
 const f=fixture()
 assert.throws(()=>runLocalOrganismStep(f.options,{failpoint:'AFTER_MOTOR'}),/INJECTED_AFTER_MOTOR/)
 const prior=inspectOrganismState(f.options.historyPath)
 assert.equal(prior.knowledge.n,0)
 const rec=runLocalOrganismStep(f.options)
 assert.equal(rec.stage,'LOCAL_ARTIFACT_VERIFIED')
 assert.equal(rec.recovered_artifact,true)
 assert.equal(rec.feedback.n_verified,1)
 const entries=readFileSync(f.options.ledgerPath,'utf8').trim().split('\n').map(JSON.parse)
 assert.equal(entries.length,1)
 assert.equal(certifyLedger(entries).is_valid,true)
})
test('native: altered source after crash refuses to turn stale information into action',()=>{
 const f=fixture()
 assert.throws(()=>runLocalOrganismStep(f.options,{failpoint:'AFTER_DECISION'}),/INJECTED_AFTER_DECISION/)
 writeFileSync(f.source,'source was changed after the receipt')
 assert.throws(()=>runLocalOrganismStep(f.options),/SOURCE_BYTES_MISMATCH/)
 assert.equal(inspectOrganismState(f.options.historyPath).knowledge.n,0)
})