// AEGIS Ω: bounded, local organ integration. No cloud/network, no grants.
// Integrates evidence-cycle ports -> organism self-model -> pending decision ->
// sandbox motor -> independent byte readback -> feedback -> hash-linked memory.
// A deterministic retry resumes a pending action without rerunning evidence-cycle.
import {existsSync, openSync, closeSync, unlinkSync, lstatSync, fstatSync, readFileSync} from 'node:fs'
import {spawnSync} from 'node:child_process'
import {inspectOrganismState,runBoundOrganismCycle,settleBoundFeedback,verifySourceBytes,verifyEvidenceMirrored} from './organism-bridge.mjs'
import {resumeOrPrepareProposal,verifyProposal} from './organism-motor.mjs'

function assert(x,m){if(!x)throw new Error(m)}
function withLease(path,fn){
  let fd
  try {fd=openSync(path,'wx',0o600)}
  catch{throw new Error('ORGANISM_CYCLE_WRITER_BUSY')}
  const own=fstatSync(fd)
  try{return fn()}
  finally {
    closeSync(fd)
    try{const current=lstatSync(path);if(current.dev===own.dev && current.ino===own.ino)unlinkSync(path)}
    catch(e){if(e.code!=='ENOENT')throw e}
  }
}

// Crash recovery must recheck the original bytes, receipt, ledger and chain;
// the stored state hash alone cannot authorize a new motor side effect.
function certifyPendingRecovery(options,state){
  assert(typeof options.receiptVerifier==='function' && typeof options.ledgerVerifier==='function',
    'RECOVERY_VERIFIERS_REQUIRED')
  assert(existsSync(options.receiptPath) && lstatSync(options.receiptPath).isFile() &&
    !lstatSync(options.receiptPath).isSymbolicLink(), 'RECOVERY_RECEIPT_MISSING')
  const receipt=JSON.parse(readFileSync(options.receiptPath,'utf8'))
  assert(receipt.receipt_sha256===state.last_evidence,'RECOVERY_EVIDENCE_CHANGED')
  assert(options.receiptVerifier(receipt)===true,'RECOVERY_RECEIPT_INVALID')
  verifySourceBytes(receipt,options.sourcePaths)
  assert(existsSync(options.ledgerPath) && lstatSync(options.ledgerPath).isFile() &&
    !lstatSync(options.ledgerPath).isSymbolicLink(),'RECOVERY_LEDGER_MISSING')
  const entries=readFileSync(options.ledgerPath,'utf8').split('\n').filter(Boolean).map(s=>JSON.parse(s))
  assert(options.ledgerVerifier(entries)===true,'RECOVERY_LEDGER_INVALID')
  const relevant=entries.filter(e=>e.receipt_sha256===receipt.receipt_sha256 &&
    /^[0-9a-f]{64}$/.test(e.transition_hash??''))
  assert(relevant.length===1,'RECOVERY_LEDGER_BINDING_MISSING_OR_AMBIGUOUS')
  const cert=spawnSync(process.execPath,[options.chainPath,'certify'],
    {encoding:'utf8',env:options.env??process.env,timeout:15000})
  assert(cert.status===0,'RECOVERY_CHAIN_CERTIFY_FAILED')
  const chain=JSON.parse(cert.stdout)
  assert(chain.is_valid===true && chain.entry_count>0,'RECOVERY_CHAIN_INVALID')
  verifyEvidenceMirrored(receipt,{ledger:{transition_hash:relevant[0].transition_hash}},
    options.chainPath,options.env??process.env)
  return receipt
}

// failpoint is for offline fault-injection tests only; never used by the CLI.
export function runLocalOrganismStep(options,{failpoint=null}={}){
  assert(options?.historyPath && options?.sandbox,'ORGANISM_HISTORY_AND_SANDBOX_REQUIRED')
  return withLease(options.historyPath+'.cycle.lock',()=>{
    let state,record,initial=false
    if(existsSync(options.historyPath)){
      state=inspectOrganismState(options.historyPath) // validates history+anchor
    }
    if(state?.last_action !== null && state?.last_receipt === null){
      // Recover a prior outcome before requesting any new agent/provider call.
      certifyPendingRecovery(options,state)
      record={status:'RECOVER_PENDING',decision_hash:state.last_action,kind:state.last_action_kind}
    }else{
      record=runBoundOrganismCycle(options)
      if(record.status==='DUPLICATE_NOOP') return {...record,stage:'NOOP'}
      state=inspectOrganismState(options.historyPath)
      initial=true
    }
    if(state.last_action===null || state.last_receipt!==null)
      return {...record,stage:'HOLD_NO_PENDING_ACTION'}
    if(state.last_action_kind!=='PROPOSE')
      return {...record,stage:'HOLD_NO_LOCAL_MOTOR',pending:state.last_action}
    if(failpoint==='AFTER_DECISION' && initial)throw new Error('INJECTED_AFTER_DECISION')
    const {recovered,...receipt}=resumeOrPrepareProposal(state,{sandbox:options.sandbox})
    if(failpoint==='AFTER_MOTOR' && initial)throw new Error('INJECTED_AFTER_MOTOR')
    // Byte readback is logically independent of proposed success flag. The caller's
    // safety contract is local sandbox verification; NOT third-party attestations.
    assert(verifyProposal(receipt,{sandbox:options.sandbox}),'MOTOR_READBACK_FAILED')
    const outcome=settleBoundFeedback({historyPath:options.historyPath,receipt,
      verifyFeedback:r=>verifyProposal(r,{sandbox:options.sandbox})})
    return {...record,stage:'LOCAL_ARTIFACT_VERIFIED',feedback:outcome,
      recovered_artifact:recovered,outcome:'LOCAL_BYTES_VERIFIED',authority_effect:'NONE'}
  })
}
