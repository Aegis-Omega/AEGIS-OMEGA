// AEGIS Ω · evidence → self-model → bounded action proposal → linked memory
// Reuses existing evidence-cycle.mjs / evidence-ledger.mjs when installed in AEGIS repo.
// No network, deployment, protected writes, or model inference. Does not execute proposals.
import { existsSync, readFileSync, writeFileSync, mkdirSync, renameSync, lstatSync, openSync, closeSync, unlinkSync, fstatSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { join, dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import { genesis, assess, transition, settleFeedback, certifyHistory, digest } from './organism-core.mjs'
const HERE=dirname(fileURLToPath(import.meta.url))
const ROOT=resolve(HERE,'../..')
const assert=(x,m)=>{if(!x)throw new Error(m)}

// One writer only; never release a lock we did not acquire.
function withHistoryLease(path, fn) {
  let fd
  const lockPath=path+'.lock'
  try { fd=openSync(lockPath,'wx',0o600) }
  catch { throw new Error('HISTORY_WRITER_BUSY_OR_PATH_INVALID') }
  const owner=fstatSync(fd)
  try { return fn() }
  finally {
    closeSync(fd)
    // Never unlink a different writer's lock after a concurrent replacement.
    try {const current=lstatSync(lockPath);if(current.ino===owner.ino && current.dev===owner.dev)unlinkSync(lockPath)}
    catch(e){if(e.code!=='ENOENT')throw e}
  }
}
function certifyAnchor(path,states){
  const anchorPath=path+'.anchor.json'
  assert(existsSync(anchorPath),'HISTORY_ANCHOR_MISSING')
  assert(lstatSync(anchorPath).isFile() && !lstatSync(anchorPath).isSymbolicLink(),'HISTORY_ANCHOR_NOT_REGULAR')
  const anchor=JSON.parse(readFileSync(anchorPath,'utf8'))
  assert(anchor?.schema==='aegis.organism-anchor.v1','HISTORY_ANCHOR_SCHEMA')
  const {anchor_hash,...body}=anchor
  assert(digest(body)===anchor_hash,'HISTORY_ANCHOR_TAMPER')
  assert(anchor.length===states.length && anchor.genesis_hash===states[0].state_hash &&
    anchor.terminal_hash===states.at(-1).state_hash,'HISTORY_ANCHOR_MISMATCH')
  return true
}
function persistHistory(path,states,extra={}){
  certifyHistory(states)
  const body={schema:'aegis.organism-anchor.v1',length:states.length,
    genesis_hash:states[0].state_hash,terminal_hash:states.at(-1).state_hash}
  // Ordering is intentional: a crash between writes yields HOLD until reviewed.
  // No silent rollback, no claims of transactional two-file commit.
  atomic(path,{schema:'aegis.organism-history.v1',states,authority_effect:'NONE',...extra})
  atomic(path+'.anchor.json',{...body,anchor_hash:digest(body)})
}

function readHistory(path, allowInitialize=false, initialState={}){
  if(!existsSync(path)){
    assert(!existsSync(path+'.anchor.json'),'HISTORY_MISSING_ANCHORED')
    assert(allowInitialize===true,'HISTORY_BOOTSTRAP_REQUIRED')
    return [genesis(initialState)]
  }
  assert(lstatSync(path).isFile() && !lstatSync(path).isSymbolicLink(),'HISTORY_NOT_REGULAR_FILE')
  const data=JSON.parse(readFileSync(path,'utf8'))
  assert(data?.schema==='aegis.organism-history.v1' && Array.isArray(data.states),'ORGANISM_HISTORY_INVALID')
  assert(data.states.length<=2048,'ORGANISM_HISTORY_CAPACITY')
  certifyHistory(data.states)
  certifyAnchor(path,data.states)
  return data.states
}

export function inspectOrganismState(historyPath) {
  return readHistory(historyPath).at(-1)
}

// Evidence admission requires actual source bytes, not self-reported `available:true` metadata.
// `sourcePaths` binds exact evidence_id to previously acquired, local immutable data.
// Detect torn native evidence-cycle transactions: a ledger receipt without its
// mirrored, certified metacognitive observation MUST NOT advance the organism.
export function verifyEvidenceMirrored(receipt,cycle,chainPath,env={}){
  assert(/^[0-9a-f]{64}$/.test(cycle?.ledger?.transition_hash??''),'EVIDENCE_TRANSITION_UNBOUND')
  const path=env.AEGIS_METACOG_CHAIN || join(dirname(chainPath),'chain.jsonl')
  assert(existsSync(path) && lstatSync(path).isFile(),'EVIDENCE_CHAIN_DATA_MISSING')
  const entries=readFileSync(path,'utf8').split('\n').filter(Boolean).map(x=>JSON.parse(x))
  const bound=entries.some(x=>{
    if(x.observation?.layer!=='METACOGNITIVE' || typeof x.observation.signal!=='string')return false
    const tokens=new Set(x.observation.signal.split(/\s+/))
    return tokens.has(`receipt=${receipt.receipt_sha256}`) &&
      tokens.has(`transition=${cycle.ledger.transition_hash}`) && tokens.has('authority=NONE')
  })
  assert(bound,'EVIDENCE_TRANSITION_NOT_MIRRORED')
  return true
}

export function verifySourceBytes(receipt, sourcePaths){
  assert(receipt && receipt.current_epistemic_state==='CURRENT_REINSPECTABLE','SOURCE_STATUS_INVALID')
  assert(receipt.authority_effect==='NONE','SOURCE_AUTHORITY_INVALID')
  assert(typeof sourcePaths==='object' && sourcePaths!==null && !Array.isArray(sourcePaths),'SOURCE_PATHS_REQUIRED')
  const required=(receipt.evidence??[]).filter(e=>e.load_bearing===true)
  assert(required.length>0,'SOURCE_EVIDENCE_EMPTY')
  for(const e of required){
    assert(e.evidence_state==='CURRENT_REINSPECTABLE' && e.exact_head_bound===true,'SOURCE_EVIDENCE_NOT_CURRENT')
    assert(typeof e.evidence_id==='string' && Object.hasOwn(sourcePaths,e.evidence_id),'SOURCE_MAP_MISSING')
    const item=e.artifact
    assert(item && item.available===true && item.expired!==true && /^sha256:[0-9a-f]{64}$/i.test(item.digest??''),'SOURCE_DIGEST_INVALID')
    const path=sourcePaths[e.evidence_id]
    assert(typeof path==='string' && existsSync(path) && lstatSync(path).isFile() && !lstatSync(path).isSymbolicLink(),'SOURCE_FILE_INVALID')
    const actual=createHash('sha256').update(readFileSync(path)).digest('hex')
    assert(actual===item.digest.slice(7).toLowerCase(),'SOURCE_BYTES_MISMATCH')
  }
  return true
}

function atomic(path,value){
  mkdirSync(dirname(path),{recursive:true})
  const temp=`${path}.${process.pid}.tmp`
  writeFileSync(temp,JSON.stringify(value,null,2)+'\n','utf8')
  renameSync(temp,path)
}
function requireChain(chainPath,env){
  assert(existsSync(chainPath),'CHAIN_MISSING')
  const r=spawnSync(process.execPath,[chainPath,'certify'],{encoding:'utf8',env,timeout:15000})
  assert(r.status===0,'CHAIN_CERTIFY_FAILED')
  const c=JSON.parse(r.stdout)
  assert(c.is_valid===true && Number.isSafeInteger(c.entry_count) && c.entry_count>0, 'CHAIN_NOT_VALID')
  return c
}
function runBoundOrganismCycleUnsafe({snapshotPath, receiptPath, ledgerPath, chainPath, historyPath,
  candidates, operator_budget=0, env=process.env, evidenceCycle, receiptVerifier,
  sourcePaths, allowInitialize=false, initialState={}}) {
  assert(typeof evidenceCycle==='function' && typeof receiptVerifier==='function','REAL_EVIDENCE_PORTS_REQUIRED')
  const chainBefore=existsSync(chainPath)?requireChain(chainPath,env):null
  const states=readHistory(historyPath,allowInitialize,initialState)
  const state=states.at(-1)
  const cycle=evidenceCycle({snapshotPath,receiptPath,ledgerPath,chainPath,env})
  assert(cycle?.authority_effect==='NONE','EVIDENCE_CYCLE_AUTHORITY_INVALID')
  const chain=requireChain(chainPath,env)
  assert(chain.entry_count>= (chainBefore?.entry_count??0),'CHAIN_REGRESSION')
  const receipt=JSON.parse(readFileSync(receiptPath,'utf8'))
  assert(receiptVerifier(receipt)===true,'RECEIPT_SIGNATURE_INVALID')
  assert(receipt.receipt_sha256===cycle.receipt_sha256,'RECEIPT_CYCLE_MISMATCH')
  verifySourceBytes(receipt,sourcePaths)
  verifyEvidenceMirrored(receipt,cycle,chainPath,env)
  if(state.last_evidence===receipt.receipt_sha256){
    return {status:'DUPLICATE_NOOP',sequence:state.sequence,terminal_hash:state.state_hash,chain_terminal:chain.terminal_hash}
  }
  assert(states.length<2048,'ORGANISM_HISTORY_CAPACITY')
  const ev={receipt_sha256:receipt.receipt_sha256,authority_effect:receipt.authority_effect,epistemic_state:receipt.current_epistemic_state}
  const verify=e=>e===ev && receiptVerifier(receipt)===true
  const decision=assess(state,{evidence:ev,candidates,verify,operator_budget})
  const next=transition(state,decision,{outcome:null}) // unknown is not a victory
  const updated=[...states,next]
  certifyHistory(updated)
  persistHistory(historyPath,updated,{evidence_chain_terminal:chain.terminal_hash})
  return {status:decision.status,kind:decision.kind,decision_hash:decision.decision_hash,decision,
    sequence:next.sequence,energy:next.energy,integrity:next.integrity,
    prediction:decision.prediction,terminal_hash:next.state_hash,chain_terminal:chain.terminal_hash,
    outcome:'UNKNOWN',authority_effect:'NONE'}
}
// In the actual runtime, only a separately trusted source may provide verifyFeedback.
// No CLI accepting user-supplied "verified":true, and no automatic self-certification.
function settleBoundFeedbackUnsafe({historyPath,receipt,verifyFeedback}) {
  const states=readHistory(historyPath)
  assert(states.length<2048,'ORGANISM_HISTORY_CAPACITY')
  const next=settleFeedback(states.at(-1),receipt,verifyFeedback)
  const updated=[...states,next]
  certifyHistory(updated)
  persistHistory(historyPath,updated)
  return {status:'FEEDBACK_ADMITTED',sequence:next.sequence,terminal_hash:next.state_hash,
    n_verified:next.knowledge.n,mean_brier:next.knowledge.brier_sum/next.knowledge.n,
    authority_effect:'NONE'}
}

export function runBoundOrganismCycle(options){
  assert(options?.historyPath && typeof options.historyPath==='string','HISTORY_PATH_REQUIRED')
  return withHistoryLease(options.historyPath,()=>runBoundOrganismCycleUnsafe(options))
}
export function settleBoundFeedback(options){
  assert(options?.historyPath && typeof options.historyPath==='string','HISTORY_PATH_REQUIRED')
  return withHistoryLease(options.historyPath,()=>settleBoundFeedbackUnsafe(options))
}

if(process.argv[1] && fileURLToPath(import.meta.url)===resolve(process.argv[1])){
  try{
    const [snapshotPath,candidatesPath]=process.argv.slice(2)
    assert(snapshotPath&&candidatesPath,'usage: node organism-bridge.mjs <snapshot.json> <candidates.json>')
    const {runEvidenceCycle}=await import('./evidence-cycle.mjs')
    const {verifyReceipt}=await import('./evidence-ledger.mjs')
    const options=JSON.parse(readFileSync(candidatesPath,'utf8'))
    const env={...process.env}
    const paths={snapshotPath:resolve(snapshotPath),
      receiptPath:env.AEGIS_EVIDENCE_RECEIPT || join(ROOT,'.claude/metacog/evidence-receipt.tmp'),
      ledgerPath:env.AEGIS_EVIDENCE_LEDGER || join(ROOT,'.claude/metacog/evidence-transitions.log'),
      chainPath:join(ROOT,'.claude/metacog/chain.mjs'),
      historyPath:env.AEGIS_ORGANISM_HISTORY || join(ROOT,'.claude/metacog/organism-history.json'),
      env,candidates:options.candidates,operator_budget:options.operator_budget??0,
      sourcePaths:options.sourcePaths,allowInitialize:env.AEGIS_ORGANISM_INIT==='1',
      initialState:options.initial_state??{},
      evidenceCycle:runEvidenceCycle,receiptVerifier:verifyReceipt}
    console.log(JSON.stringify(runBoundOrganismCycle(paths),null,2))
  }catch(e){console.error('AEGIS_ORGANISM_HOLD '+(e?.message??e));process.exitCode=2}
}
