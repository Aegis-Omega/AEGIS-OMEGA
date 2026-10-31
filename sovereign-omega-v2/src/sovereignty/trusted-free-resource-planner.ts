/**
 * Trusted-runtime entrypoint for free-only planning with Ed25519 approval receipts.
 *
 * DO NOT expose createTrustedFreeResourcePlannerV1 to untrusted HTTP callers.
 * The trust policy must come from operator-controlled, separately authenticated
 * bootstrap configuration (not from the request or model/provider output).
 * Still only creates a planning receipt. Never reserves quota or grants spending.
 */
import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'
import { verifyBytes } from '../consensus/crypto.js'
import type { SHA256Hex } from '../core/types.js'
import {
  planFreeResourceV1,
  type FreeResourceEvidenceV1,
  type FreeResourceRequestV1,
  type FreeResourceDecisionV1,
} from './free-resource-planning.js'
import type { ProviderMeshSnapshotV1 } from './provider-mesh.js'

const HEX32=/^[0-9a-f]{64}$/
const HEX64=/^[0-9a-f]{128}$/
const DEC=/^(0|[1-9][0-9]*)$/
const POLICY_ID=/^[a-zA-Z0-9._:-]{1,128}$/
const AUDIENCE='AEGIS_FREE_RESOURCE_PLANNING_V1' as const
const DOMAIN='AEGIS_FREE_RESOURCE_ED25519_APPROVAL_V1' as const

export interface TrustedFreeResourcePolicyV1 {
  schema:'AEGIS_TRUSTED_FREE_RESOURCE_POLICY_V1'
  policy_id:string
  /** Trusted bootstrap signer keys. Never accept these from the request. */
  signer_public_keys:readonly string[]
  /** A genuine authenticated revocation read must be injected by the host. */
  revoked_signer_keys:readonly string[]
  revoked_approval_ids:readonly string[]
  revocation_generation:string
  max_revocation_age_generations:string
  /** Trusted upper bound on an untrusted request's provider observation age. */
  max_observation_age_generations:string
}
export interface FreeResourceApprovalPayloadV1 {
  schema:'AEGIS_FREE_RESOURCE_APPROVAL_V1'
  audience:typeof AUDIENCE
  policy_id:string
  approval_id:SHA256Hex
  evidence_root:SHA256Hex
  /** Prevent reuse of one approved quota for a different task or budget. */
  request_root:SHA256Hex
  provider_id:string
  snapshot_root:SHA256Hex
  observation_evidence_hash:SHA256Hex
  issued_generation:string
  expires_generation:string
}
export interface SignedFreeResourceApprovalV1 {
  payload:FreeResourceApprovalPayloadV1
  signer_public_key:string
  signature_hex:string
}
export interface TrustedFreeResourcePlannerV1 {
  plan:(
    snapshot:ProviderMeshSnapshotV1,
    request:FreeResourceRequestV1,
    evidence:readonly FreeResourceEvidenceV1[],
    untrusted_approvals:readonly SignedFreeResourceApprovalV1[],
  )=>Promise<FreeResourceDecisionV1>
}

/** Source-bound, task-specific SHA256 root for the full planning request. */
export async function freeResourceRequestRootV1(request:FreeResourceRequestV1):Promise<SHA256Hex> {
  return sha256Hex(canonicalizeJCS({domain:'AEGIS_FREE_RESOURCE_REQUEST_V1',request}))
}
export function signedFreeResourceApprovalBytesV1(payload:FreeResourceApprovalPayloadV1):Uint8Array {
  return canonicalizeJCS({domain:DOMAIN,approval:payload})
}
function decimal(value:unknown):value is string {
  return typeof value==='string' && DEC.test(value)
}
function assertHexSet(name:string, values:readonly string[], regex:RegExp):Set<string> {
  if(!Array.isArray(values) || values.some(v=>typeof v!=='string'||!regex.test(v))) {
    throw new TypeError('invalid '+name)
  }
  const result=new Set(values)
  if(result.size!==values.length) throw new TypeError('duplicate '+name)
  return result
}
function trustedPolicy(policy:TrustedFreeResourcePolicyV1) {
  if(!policy||policy.schema!=='AEGIS_TRUSTED_FREE_RESOURCE_POLICY_V1'
    ||typeof policy.policy_id!=='string'||!POLICY_ID.test(policy.policy_id)
    ||!decimal(policy.revocation_generation)||!decimal(policy.max_revocation_age_generations)
    ||!decimal(policy.max_observation_age_generations)){
    throw new TypeError('invalid trusted policy bootstrap')
  }
  const signers=assertHexSet('signer keys',policy.signer_public_keys,HEX32)
  const revokedSigners=assertHexSet('revoked signer keys',policy.revoked_signer_keys,HEX32)
  const revokedApprovals=assertHexSet('revoked approval ids',policy.revoked_approval_ids,HEX32)
  return {
    policy_id:policy.policy_id,
    signers,
    revokedSigners,
    revokedApprovals,
    revocationGeneration:BigInt(policy.revocation_generation),
    maxAge:BigInt(policy.max_revocation_age_generations),
    maxObservationAge:BigInt(policy.max_observation_age_generations),
  }
}
function approvalMatches(
  approval:SignedFreeResourceApprovalV1,
  snapshot:ProviderMeshSnapshotV1,
  request:FreeResourceRequestV1,
  requestRoot:SHA256Hex,
  evidence:ReadonlyMap<string,FreeResourceEvidenceV1>,
  policyId:string,
):boolean {
  const a=approval?.payload
  if(!a||a.schema!=='AEGIS_FREE_RESOURCE_APPROVAL_V1'||a.audience!==AUDIENCE
    ||a.policy_id!==policyId||typeof a.provider_id!=='string'
    ||!HEX32.test(a.approval_id)||!HEX32.test(a.evidence_root)
    ||!HEX32.test(a.request_root)
    ||!HEX32.test(a.snapshot_root)||!HEX32.test(a.observation_evidence_hash)
    ||!decimal(a.issued_generation)||!decimal(a.expires_generation)) return false
  if(a.snapshot_root!==snapshot.snapshot_root||a.request_root!==requestRoot) return false
  const witness=evidence.get(a.evidence_root)
  if(!witness||witness.provider_id!==a.provider_id
    ||witness.snapshot_root!==a.snapshot_root
    ||witness.observation_evidence_hash!==a.observation_evidence_hash) return false
  const observation=snapshot.observations.find(o=>o.provider_id===a.provider_id)
  if(!observation||observation.evidence_hash!==a.observation_evidence_hash) return false
  if(!decimal(request.current_generation)) return false
  const now=BigInt(request.current_generation)
  return BigInt(a.issued_generation)<=now && now<=BigInt(a.expires_generation)
}

/**
 * Construct this only at a trusted application bootstrap boundary. Trust keys
 * and revocations are copied into private Sets, preventing a request from
 * changing them after construction. No trust store is bundled in this repo.
 */
export function createTrustedFreeResourcePlannerV1(
  authenticated_bootstrap_policy:TrustedFreeResourcePolicyV1,
  /** Injected by trusted host, never by the untrusted request. */
  read_authenticated_generation:()=>string,
):TrustedFreeResourcePlannerV1 {
  const trusted=trustedPolicy(authenticated_bootstrap_policy)
  if(typeof read_authenticated_generation!=='function') throw new TypeError('missing trusted generation reader')
  // Generation is monotonic within this trusted planner instance. On rollback,
  // fail closed permanently; only an authenticated fresh bootstrap may reset it.
  let highestAuthenticatedGeneration:bigint|null=null
  let generationRegressed=false
  return Object.freeze({
    async plan(
      snapshot:ProviderMeshSnapshotV1,
      request:FreeResourceRequestV1,
      evidence:readonly FreeResourceEvidenceV1[],
      untrusted_approvals:readonly SignedFreeResourceApprovalV1[],
    ) {
      if(!Array.isArray(evidence)||!Array.isArray(untrusted_approvals)){
        throw new TypeError('invalid resource evidence or approvals')
      }
      if(!decimal(request.current_generation)||!decimal(request.max_observation_age_generations)){
        throw new TypeError('invalid request generation')
      }
      let authenticatedNow:unknown
      try {authenticatedNow=read_authenticated_generation()} catch {authenticatedNow=null}
      // A caller cannot roll time back, refresh revocations, or loosen
      // the observation freshness bound using request-controlled fields.
      if(!decimal(authenticatedNow)) {
        return planFreeResourceV1(snapshot,request,evidence,[])
      }
      const now=BigInt(authenticatedNow)
      if(highestAuthenticatedGeneration!==null && now<highestAuthenticatedGeneration) {
        generationRegressed=true
      }
      if(highestAuthenticatedGeneration===null||now>highestAuthenticatedGeneration) {
        highestAuthenticatedGeneration=now
      }
      if(generationRegressed
        ||request.current_generation!==authenticatedNow
        ||BigInt(request.max_observation_age_generations)>trusted.maxObservationAge) {
        return planFreeResourceV1(snapshot,request,evidence,[])
      }
      // Missing, future or stale revocation view: fail closed even if signatures
      // and evidence hashes are valid. Caller cannot refresh this trusted view.
      if(trusted.revocationGeneration>now
        ||now-trusted.revocationGeneration>trusted.maxAge){
        return planFreeResourceV1(snapshot,request,evidence,[])
      }
      const byRoot=new Map<string,FreeResourceEvidenceV1>()
      for(const item of evidence){
        if(item&&typeof item.evidence_root==='string') byRoot.set(item.evidence_root,item)
      }
      const requestRoot=await freeResourceRequestRootV1(request)
      const approved=new Set<SHA256Hex>()
      const seenApprovalIds=new Set<string>()
      for(const signed of untrusted_approvals){
        if(!signed||!signed.payload) continue
        const key=signed.signer_public_key
        const sig=signed.signature_hex
        const id=signed.payload.approval_id
        if(typeof key!=='string'||!HEX32.test(key)
          ||typeof sig!=='string'||!HEX64.test(sig)
          ||typeof id!=='string'||!HEX32.test(id)
          ||seenApprovalIds.has(id)) continue
        // Untrusted malformed or forged envelopes must never reserve a
        // legitimate approval ID before cryptographic verification.
        if(!trusted.signers.has(key)||trusted.revokedSigners.has(key)
          ||trusted.revokedApprovals.has(id)) continue
        if(!approvalMatches(signed,snapshot,request,requestRoot,byRoot,trusted.policy_id)) continue
        let valid=false
        try {
          valid=await verifyBytes(key,signedFreeResourceApprovalBytesV1(signed.payload),sig)
        } catch {
          valid=false
        }
        if(valid) {
          seenApprovalIds.add(id)
          approved.add(signed.payload.evidence_root)
        }
      }
      return planFreeResourceV1(snapshot,request,evidence,[...approved])
    },
  })
}
