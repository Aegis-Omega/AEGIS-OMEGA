import {describe,expect,it} from 'vitest'
import {generateKeypair,signBytes} from '../../src/consensus/crypto.js'
import type {SHA256Hex} from '../../src/core/types.js'
import {
  buildProviderMeshSnapshotV1,
  DECLARED_PROVIDER_CATALOG_V1,
  PROVIDER_MESH_SCHEMA_VERSION,
  type ProviderObservationV1,
} from '../../src/sovereignty/provider-mesh.js'
import {
  freeResourceEvidenceRootV1,
  type FreeResourceEvidenceV1,
} from '../../src/sovereignty/free-resource-planning.js'
import {
  createTrustedFreeResourcePlannerV1,
  signedFreeResourceApprovalBytesV1,
  freeResourceRequestRootV1,
  type FreeResourceApprovalPayloadV1,
  type SignedFreeResourceApprovalV1,
  type TrustedFreeResourcePolicyV1,
} from '../../src/sovereignty/trusted-free-resource-planner.js'

const h=(digit:string)=>digit.repeat(64) as SHA256Hex
const observation:ProviderObservationV1={
  schema_version:PROVIDER_MESH_SCHEMA_VERSION,
  provider_id:'cloudflare-anthropic',
  state:'OBSERVED_AVAILABLE',
  observed_capabilities:['MODEL_INFERENCE'],
  evidence_hash:h('a'),
  observation_generation:'10',
  authority_effect:'NONE',
}
const request={
  required_capabilities:['MODEL_INFERENCE'] as const,
  current_generation:'10',
  max_observation_age_generations:'1',
  unit:'NEURON' as const,
  worst_case_units:'100',
}
async function context(){
  const snapshot=await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1,[observation])
  const body={
    provider_id:'cloudflare-anthropic',source_id:'SYNTHETIC_TEST_ONLY_NOT_PROVIDER_EVIDENCE',
    observation_generation:'10',snapshot_root:snapshot.snapshot_root,
    observation_evidence_hash:observation.evidence_hash,
    unit:'NEURON' as const,remaining_units:'200',
    billing_mode:'FREE_ONLY' as const,overage:'HARD_DENY' as const,
  }
  const evidence:FreeResourceEvidenceV1={...body,evidence_root:await freeResourceEvidenceRootV1(body)}
  const signer=await generateKeypair(new Uint8Array(32).fill(7))
  const other=await generateKeypair(new Uint8Array(32).fill(9))
  const trust:TrustedFreeResourcePolicyV1={
    schema:'AEGIS_TRUSTED_FREE_RESOURCE_POLICY_V1',
    policy_id:'offline-test-policy',
    signer_public_keys:[signer.publicKey],
    revoked_signer_keys:[],
    revoked_approval_ids:[],
    revocation_generation:'10',
    max_revocation_age_generations:'1',
    max_observation_age_generations:'1',
  }
  const payload:FreeResourceApprovalPayloadV1={
    schema:'AEGIS_FREE_RESOURCE_APPROVAL_V1',
    audience:'AEGIS_FREE_RESOURCE_PLANNING_V1',
    policy_id:'offline-test-policy',
    approval_id:h('b'),
    evidence_root:evidence.evidence_root,
    request_root:await freeResourceRequestRootV1(request),
    provider_id:evidence.provider_id,
    snapshot_root:snapshot.snapshot_root,
    observation_evidence_hash:observation.evidence_hash,
    issued_generation:'10',
    expires_generation:'11',
  }
  const sign=async(p:FreeResourceApprovalPayloadV1, privateKey=signer.privateKey, publicKey=signer.publicKey):Promise<SignedFreeResourceApprovalV1>=>({
    payload:p,
    signer_public_key:publicKey,
    signature_hex:await signBytes(privateKey,signedFreeResourceApprovalBytesV1(p)),
  })
  const signed=await sign(payload)
  return {snapshot,evidence,signer,other,trust,payload,signed,sign}
}
describe('trusted free-resource Ed25519 approval boundary (synthetic only)',()=>{
  it('accepts a domain-bound signed approval with a trusted startup signer and fresh revocations for planning only',async()=>{
    const c=await context()
    const x=await createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation).plan(c.snapshot,request,[c.evidence],[c.signed])
    expect(x.outcome).toBe('PLANNING_ELIGIBLE')
    expect(x.provider_id).toBe('cloudflare-anthropic')
    expect(x.authority_effect).toBe('NONE')
  })
  it('holds when the untrusted request submits its own signer and signature',async()=>{
    const c=await context()
    const forged=await c.sign(c.payload,c.other.privateKey,c.other.publicKey)
    expect((await createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation).plan(c.snapshot,request,[c.evidence],[forged])).outcome).toBe('HOLD')
  })
  it('holds when signed payload changes without a fresh signature',async()=>{
    const c=await context()
    const changed={...c.signed,payload:{...c.payload,approval_id:h('f')}}
    expect((await createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation).plan(c.snapshot,request,[c.evidence],[changed])).outcome).toBe('HOLD')
  })
  it('holds when signer is revoked by the trusted bootstrap',async()=>{
    const c=await context()
    const trust={...c.trust,revoked_signer_keys:[c.signer.publicKey]}
    expect((await createTrustedFreeResourcePlannerV1(trust,()=>request.current_generation).plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
  })
  it('holds when individual approval is revoked',async()=>{
    const c=await context()
    const trust={...c.trust,revoked_approval_ids:[c.payload.approval_id]}
    expect((await createTrustedFreeResourcePlannerV1(trust,()=>request.current_generation).plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
  })
  it('holds when revocation snapshot is stale or from the future',async()=>{
    const c=await context()
    for(const generation of ['8','11']){
      const trust={...c.trust,revocation_generation:generation}
      expect((await createTrustedFreeResourcePlannerV1(trust,()=>request.current_generation).plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    }
  })
  it('holds for an expired or not-yet-valid approval',async()=>{
    const c=await context()
    for(const patch of [{issued_generation:'11'},{expires_generation:'9'}]){
      const signed=await c.sign({...c.payload,...patch})
      expect((await createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation).plan(c.snapshot,request,[c.evidence],[signed])).outcome).toBe('HOLD')
    }
  })
  it('holds an approval signed for a different audience, policy or snapshot',async()=>{
    const c=await context()
    const otherPolicy=await c.sign({...c.payload,policy_id:'some-other-policy'})
    const wrongSnapshot=await c.sign({...c.payload,snapshot_root:h('c')})
    const wrongAudience=await c.sign({...c.payload,audience:'NOT_RESOURCE_PLANNING' as FreeResourceApprovalPayloadV1['audience']})
    for(const s of [otherPolicy,wrongSnapshot,wrongAudience]){
      expect((await createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation).plan(c.snapshot,request,[c.evidence],[s])).outcome).toBe('HOLD')
    }
  })
  it('holds when approval signature is missing or malformed',async()=>{
    const c=await context()
    for(const signature_hex of ['', '1'.repeat(128)]){
      const signed={...c.signed,signature_hex}
      expect((await createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation).plan(c.snapshot,request,[c.evidence],[signed])).outcome).toBe('HOLD')
    }
    expect((await createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation).plan(c.snapshot,request,[c.evidence],[])).outcome).toBe('HOLD')
  })
  it('does not trust mutations of the bootstrap arrays after construction',async()=>{
    const c=await context()
    const keys=[c.signer.publicKey]
    const trust={...c.trust,signer_public_keys:keys}
    const planner=createTrustedFreeResourcePlannerV1(trust,()=>request.current_generation)
    keys.splice(0,1)
    keys.push(c.other.publicKey)
    const forged=await c.sign(c.payload,c.other.privateKey,c.other.publicKey)
    expect((await planner.plan(c.snapshot,request,[c.evidence],[forged])).outcome).toBe('HOLD')
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('PLANNING_ELIGIBLE')
  })
  it('fails bootstrap for invalid keys, missing authenticated revocations or duplicate trust keys',async()=>{
    const c=await context()
    expect(()=>createTrustedFreeResourcePlannerV1({...c.trust,signer_public_keys:['not-a-key']},()=>request.current_generation)).toThrow('invalid signer keys')
    expect(()=>createTrustedFreeResourcePlannerV1({...c.trust,signer_public_keys:[c.signer.publicKey,c.signer.publicKey]},()=>request.current_generation)).toThrow('duplicate signer keys')
    expect(()=>createTrustedFreeResourcePlannerV1({...c.trust,revocation_generation:'bad'},()=>request.current_generation)).toThrow('trusted policy')
  })
  it('holds a replay when untrusted request rolls back generation after trusted clock advances',async()=>{
    const c=await context()
    let authenticatedGeneration='10'
    const planner=createTrustedFreeResourcePlannerV1(c.trust,()=>authenticatedGeneration)
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('PLANNING_ELIGIBLE')
    authenticatedGeneration='12'
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
  })
  it('holds when a request loosens the trusted observation age limit',async()=>{
    const c=await context()
    const lessStrict={...request,max_observation_age_generations:'10000000'}
    expect((await createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation)
      .plan(c.snapshot,lessStrict,[c.evidence],[c.signed])).outcome).toBe('HOLD')
  })
  it('holds if the trusted generation source is unavailable or malformed',async()=>{
    const c=await context()
    for(const source of [()=>{throw new Error('clock unavailable')},()=>'-1']){
      const planner=createTrustedFreeResourcePlannerV1(c.trust,source)
      expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    }
  })
  it('holds a valid signature reused for a larger task budget within remaining capacity',async()=>{
    const c=await context()
    const changedRequest={...request,worst_case_units:'150'}
    const decision=await createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation)
      .plan(c.snapshot,changedRequest,[c.evidence],[c.signed])
    expect(decision.outcome).toBe('HOLD')
  })
  it('holds valid signature reused with different allowed/preferred provider controls',async()=>{
    const c=await context()
    const planner=createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation)
    for(const changedRequest of [
      {...request,allowed_providers:['cloudflare-anthropic']},
      {...request,preferred_provider_order:['cloudflare-anthropic']},
      {...request,max_observation_age_generations:'0'},
    ]){
      expect((await planner.plan(c.snapshot,changedRequest,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    }
  })
  it('holds an approval signed for another exact request digest',async()=>{
    const c=await context()
    const signed=await c.sign({...c.payload,request_root:h('c')})
    expect((await createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation)
      .plan(c.snapshot,request,[c.evidence],[signed])).outcome).toBe('HOLD')
  })
  it('keeps unsigned quota evidence on HOLD even if every evidence hash is well-formed',async()=>{
    const c=await context()
    const x=await createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation).plan(c.snapshot,request,[c.evidence],[])
    expect(x.outcome).toBe('HOLD')
    expect(x.provider_id).toBeNull()
  })
})
