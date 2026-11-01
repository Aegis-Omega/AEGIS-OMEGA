import {test} from 'node:test'
import assert from 'node:assert/strict'
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,unlinkSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {runBoundOrganismCycle,settleBoundFeedback} from '../.claude/metacog/organism-bridge.mjs'
import {digest} from '../.claude/metacog/organism-core.mjs'
import {createHash} from 'node:crypto'
// PORT-CONTRACT tests only. The native evidence-cycle/chain modules are exercised on actual AEGIS source AFTER integration.
const candidates=[{id:'observe',kind:'OBSERVE',benefit:9,risk:0,cost:2},{id:'rest',kind:'REST',benefit:0,risk:0,cost:0}]
function fixtures(mode='current'){
 const dir=mkdtempSync(join(tmpdir(),'aegis-organism-contract-'))
 const paths={snapshotPath:join(dir,'snapshot.json'),receiptPath:join(dir,'receipt.json'),ledgerPath:join(dir,'ledger.jsonl'),chainPath:join(dir,'chain.mjs'),historyPath:join(dir,'history.json')}
 const meta=join(dir,'chain-state.json')
 // Contract is intentionally minimal and is NOT a substitute for actual chain.mjs.
 writeFileSync(paths.chainPath,`import {readFileSync} from 'node:fs'; const x=JSON.parse(readFileSync('${meta}','utf8')); console.log(JSON.stringify(x));`)
 writeFileSync(meta,JSON.stringify({is_valid:true,entry_count:1,terminal_hash:'f'.repeat(64)}))
 const sourceFile=join(dir,'source-bytes.bin'), sourceBytes=Buffer.from('real source bytes\n')
 writeFileSync(sourceFile,sourceBytes)
 const evidenceId='github-actions:example:one'
 const evidenceState=mode==='current'?'CURRENT_REINSPECTABLE':'HISTORICAL_NOT_REINSPECTABLE'
 const sourcePaths={[evidenceId]:sourceFile}
 const body={schema:'aegis.metacognitive-evidence-receipt.v1',current_epistemic_state:evidenceState,authority_effect:'NONE',
   evidence:[{evidence_id:evidenceId,load_bearing:true,exact_head_bound:true,evidence_state:evidenceState,
     artifact:{available:true,expired:false,digest:'sha256:'+createHash('sha256').update(sourceBytes).digest('hex')}}]}
 const receipt={...body,receipt_sha256:digest(body)}
 const transitionHash='b'.repeat(64)
 const evidenceCycle=()=>{
   writeFileSync(paths.receiptPath,JSON.stringify(receipt))
   writeFileSync(join(dir,'chain.jsonl'),JSON.stringify({observation:{layer:'METACOGNITIVE',
     signal:`evidence-transition receipt=${receipt.receipt_sha256} transition=${transitionHash} authority=NONE`}})+'\n')
   return {authority_effect:'NONE',receipt_sha256:receipt.receipt_sha256,ledger:{transition_hash:transitionHash}}
 }
 return {...paths,candidates,operator_budget:10,sourcePaths,allowInitialize:true,evidenceCycle,receiptVerifier:r=>r.receipt_sha256===digest(Object.fromEntries(Object.entries(r).filter(([k])=>k!=='receipt_sha256'))),env:process.env}
}
test('contract: source-bound observation produces hash-linked state',()=>{const p=fixtures();const r=runBoundOrganismCycle(p);assert.equal(r.sequence,1);assert.equal(r.authority_effect,'NONE');assert.equal(r.outcome,'UNKNOWN');assert.equal(JSON.parse(readFileSync(p.historyPath,'utf8')).states.length,2)})
test('contract: identical source receipt is idempotent',()=>{const p=fixtures();runBoundOrganismCycle(p);assert.equal(runBoundOrganismCycle(p).status,'DUPLICATE_NOOP')})
test('contract: unavailable real verifier fails closed',()=>{const p=fixtures();p.receiptVerifier=()=>false;assert.throws(()=>runBoundOrganismCycle(p),/RECEIPT_SIGNATURE_INVALID/)})
test('contract: historical artifact blocked, no state file',()=>{const p=fixtures('historical');assert.throws(()=>runBoundOrganismCycle(p),/SOURCE_STATUS_INVALID/);assert.throws(()=>readFileSync(p.historyPath))})
test('contract: chain failure blocks state update',()=>{const p=fixtures();p.chainPath=join(p.historyPath,'missing');assert.throws(()=>runBoundOrganismCycle(p))})
test('contract: modified state cannot be loaded',()=>{const p=fixtures();runBoundOrganismCycle(p);const raw=JSON.parse(readFileSync(p.historyPath));raw.states[1].energy=999;writeFileSync(p.historyPath,JSON.stringify(raw));assert.throws(()=>runBoundOrganismCycle(p),/STATE_RESOURCE_CEILING/)})

test('contract: externally verified feedback persists across sessions and adapts',()=>{
 const p=fixtures();const r=runBoundOrganismCycle(p)
 const receipt={receipt_sha256:'e'.repeat(64),decision_hash:r.decision_hash,outcome:false,authority_effect:'NONE'}
 const out=settleBoundFeedback({historyPath:p.historyPath,receipt,verifyFeedback:x=>x===receipt})
 assert.equal(out.n_verified,1)
 assert.equal(JSON.parse(readFileSync(p.historyPath,'utf8')).states.length,3)
 assert.throws(()=>settleBoundFeedback({historyPath:p.historyPath,receipt,verifyFeedback:()=>true}),/NO_UNSETTLED_ACTION/)
})

test('contract: missing history never silently resets unless bootstrap is explicit',()=>{
 const p=fixtures();p.allowInitialize=false
 assert.throws(()=>runBoundOrganismCycle(p),/HISTORY_BOOTSTRAP_REQUIRED/)
 assert.throws(()=>readFileSync(p.historyPath))
 p.allowInitialize=true
 const r=runBoundOrganismCycle(p)
 assert.equal(r.sequence,1)
})
test('contract: deleted established history never silently resets',()=>{
 const p=fixtures();runBoundOrganismCycle(p)
 unlinkSync(p.historyPath)
 p.allowInitialize=false
 assert.throws(()=>runBoundOrganismCycle(p),/HISTORY_MISSING_ANCHORED/)
})
test('contract: source bytes must match load-bearing digest',()=>{
 const p=fixtures();writeFileSync(Object.values(p.sourcePaths)[0],'tampered content')
 assert.throws(()=>runBoundOrganismCycle(p),/SOURCE_BYTES_MISMATCH/)
 assert.throws(()=>readFileSync(p.historyPath))
})
test('contract: missing source bytes cannot be accepted on claimed availability',()=>{
 const p=fixtures();unlinkSync(Object.values(p.sourcePaths)[0])
 assert.throws(()=>runBoundOrganismCycle(p),/SOURCE_FILE_INVALID/)
})
test('contract: source evidence cannot be empty and still be called current',()=>{
 const p=fixtures();p.sourcePaths={}
 assert.throws(()=>runBoundOrganismCycle(p),/SOURCE_MAP_MISSING/)
})

test('contract: origin remains protected even with bootstrap flag if history was deleted',()=>{
 const p=fixtures();runBoundOrganismCycle(p)
 unlinkSync(p.historyPath)
 p.allowInitialize=true
 assert.throws(()=>runBoundOrganismCycle(p),/HISTORY_MISSING_ANCHORED/)
})
test('contract: exact state anchor detects internally rehashed state truncation',()=>{
 const p=fixtures();runBoundOrganismCycle(p)
 const raw=JSON.parse(readFileSync(p.historyPath))
 raw.states=raw.states.slice(0,1)
 writeFileSync(p.historyPath,JSON.stringify(raw))
 assert.throws(()=>runBoundOrganismCycle(p),/HISTORY_ANCHOR_MISMATCH/)
})
test('contract: missing anchor prevents history reuse without explicit migration',()=>{
 const p=fixtures();runBoundOrganismCycle(p)
 unlinkSync(p.historyPath+'.anchor.json')
 assert.throws(()=>runBoundOrganismCycle(p),/HISTORY_ANCHOR_MISSING/)
})
test('contract: foreign lock prohibits new writer and remains untouched',()=>{
 const p=fixtures();writeFileSync(p.historyPath+'.lock','foreign-writer')
 assert.throws(()=>runBoundOrganismCycle(p),/HISTORY_WRITER_BUSY_OR_PATH_INVALID/)
 assert.equal(readFileSync(p.historyPath+'.lock','utf8'),'foreign-writer')
})

test('contract: a torn evidence ledger without a mirrored metacognitive observation is HOLD',()=>{
 const p=fixtures();const original=p.evidenceCycle
 p.evidenceCycle=(x)=>{const out=original(x);writeFileSync(join(p.chainPath,'../chain.jsonl'),'') ;return out}
 assert.throws(()=>runBoundOrganismCycle(p),/EVIDENCE_TRANSITION_NOT_MIRRORED/)
 assert.throws(()=>readFileSync(p.historyPath))
})

test('contract: foreign metacognitive receipt cannot satisfy another transition',()=>{
 const p=fixtures();const original=p.evidenceCycle
 p.evidenceCycle=(x)=>{const out=original(x);const path=join(p.chainPath,'../chain.jsonl');
   const a=JSON.parse(readFileSync(path,'utf8'));a.observation.signal=a.observation.signal.replace(out.ledger.transition_hash,'c'.repeat(64));
   writeFileSync(path,JSON.stringify(a)+'\n');return out}
 assert.throws(()=>runBoundOrganismCycle(p),/EVIDENCE_TRANSITION_NOT_MIRRORED/)
})

test('contract: configured exploration policy survives bounded genesis and state hash',()=>{
 const p=fixtures();p.initialState={energy:30,energy_ceiling:30,adapt_window:12,probe_every:6}
 runBoundOrganismCycle(p)
 const raw=JSON.parse(readFileSync(p.historyPath,'utf8'))
 assert.equal(raw.states[0].adaptation.window,12)
 assert.equal(raw.states[1].adaptation.probe_every,6)
})
