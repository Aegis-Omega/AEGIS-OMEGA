// AEGIS Ω · reversible local motor: creates inspectable proposals, never modifies production.
// Independent verification re-reads file bytes, not a claimed success flag.
import { mkdirSync, readFileSync, writeFileSync, lstatSync, realpathSync, existsSync } from 'node:fs'
import { resolve, join, sep } from 'node:path'
import { tmpdir } from 'node:os'
import { createHash } from 'node:crypto'
import { digest } from './organism-core.mjs'
const assert=(x,m)=>{if(!x)throw new Error(m)}
const HASH=/^[0-9a-f]{64}$/
const fileDigest=x=>createHash('sha256').update(x).digest('hex')
function confined(path,root){
  const base=realpathSync(root)
  const osTemp=realpathSync(tmpdir())
  assert(base.startsWith(osTemp+sep),'MOTOR_OUTSIDE_TEMP')
  assert(base===resolve(root),'MOTOR_SYMLINK_ROOT')
  const full=resolve(path)
  assert(full.startsWith(base+sep),'MOTOR_OUTSIDE_SANDBOX')
  assert(!existsSync(full),'MOTOR_NO_OVERWRITE')
  assert(!lstatSync(base).isSymbolicLink(),'MOTOR_SYMLINK_ROOT')
  return full
}
export function prepareProposal(decision,{sandbox}){
  assert(decision?.kind==='PROPOSE' && decision.choice!==null && HASH.test(decision.decision_hash),'MOTOR_ACTION_NOT_PROPOSAL')
  assert(decision.authority_effect==='NONE','MOTOR_AUTHORITY_INVALID')
  assert(sandbox && typeof sandbox==='string','MOTOR_SANDBOX_REQUIRED')
  mkdirSync(sandbox,{recursive:true})
  const path=confined(join(realpathSync(sandbox),`proposal-${decision.decision_hash}.json`),sandbox)
  const proposal={schema:'aegis.organism-proposal.v1',decision_hash:decision.decision_hash,
    action_id:decision.choice,evidence_receipt:decision.evidence_receipt,
    status:'CANDIDATE_ONLY',operator_approval:false,authority_effect:'NONE'}
  const bytes=Buffer.from(JSON.stringify(proposal,null,2)+'\n','utf8')
  assert(bytes.length<10000,'MOTOR_PROPOSAL_TOO_LARGE')
  writeFileSync(path,bytes,{flag:'wx',mode:0o600})
  return {path,content_sha256:fileDigest(bytes),decision_hash:decision.decision_hash,outcome:true,
    authority_effect:'NONE',receipt_sha256:digest({path,content_sha256:fileDigest(bytes),decision_hash:decision.decision_hash,outcome:true,authority_effect:'NONE'})}
}
export function verifyProposal(receipt,{sandbox}){
  if(!receipt||receipt.authority_effect!=='NONE'||receipt.outcome!==true||!HASH.test(receipt.decision_hash)||!HASH.test(receipt.receipt_sha256))return false
  const {receipt_sha256,...body}=receipt
  if(digest(body)!==receipt_sha256)return false
  try{
    const base=realpathSync(sandbox), full=resolve(receipt.path)
    if(!base.startsWith(realpathSync(tmpdir())+sep)||base!==resolve(sandbox))return false
    if(!full.startsWith(base+sep)||lstatSync(full).isSymbolicLink())return false
    const bytes=readFileSync(full)
    if(fileDigest(bytes)!==receipt.content_sha256)return false
    const proposal=JSON.parse(bytes.toString('utf8'))
    return proposal.schema==='aegis.organism-proposal.v1' && proposal.decision_hash===receipt.decision_hash &&
      proposal.authority_effect==='NONE' && proposal.operator_approval===false && proposal.status==='CANDIDATE_ONLY' &&
      proposal.evidence_receipt && HASH.test(proposal.evidence_receipt)
  }catch{return false}
}

// Crash-safe motor retry for a single hash-bound, previously recorded PROPOSE action.
// Never overwrites an existing artifact and never treats a corrupt artifact as a success.
export function resumeOrPrepareProposal(pending, {sandbox}) {
  assert(pending && pending.schema==='aegis.organism.v1' && pending.last_action_kind==='PROPOSE'
    && HASH.test(pending.last_action) && HASH.test(pending.last_evidence), 'MOTOR_NO_PROPOSE_PENDING')
  assert(typeof pending.last_action_id==='string' && /^[a-zA-Z0-9_.:-]{1,80}$/.test(pending.last_action_id), 'MOTOR_ACTION_ID_INVALID')
  const decision={kind:'PROPOSE',choice:pending.last_action_id,decision_hash:pending.last_action,
    evidence_receipt:pending.last_evidence,authority_effect:'NONE'}
  const full=resolve(sandbox,`proposal-${pending.last_action}.json`)
  if(!existsSync(full)) return {...prepareProposal(decision,{sandbox}),recovered:false}
  assert(lstatSync(full).isFile() && !lstatSync(full).isSymbolicLink(),'MOTOR_RECOVERY_INVALID_FILE')
  const bytes=readFileSync(full) // safe after regular-file check; subsequent readback validates bytes again.
  const receipt={path:full,content_sha256:fileDigest(bytes),decision_hash:pending.last_action,
    outcome:true,authority_effect:'NONE'}
  receipt.receipt_sha256=digest(receipt)
  assert(verifyProposal(receipt,{sandbox}),'MOTOR_RECOVERY_INVALID_ARTIFACT')
  // Bind the artifact to THIS pending action, not merely another hash-shaped receipt.
  const parsed=JSON.parse(bytes.toString('utf8'))
  assert(parsed.action_id===pending.last_action_id && parsed.evidence_receipt===pending.last_evidence,
    'MOTOR_RECOVERY_ACTION_OR_EVIDENCE_MISMATCH')
  return {...receipt,recovered:true}
}
