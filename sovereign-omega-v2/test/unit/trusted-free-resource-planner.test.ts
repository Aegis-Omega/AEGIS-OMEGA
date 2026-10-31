import {describe,expect,it} from 'vitest'
import {
  createIsolatedPostgresGenerationCheckpointV1,
  type AuthenticatedParameterizedPostgresV1,
} from '../../src/sovereignty/postgres-generation-checkpoint.js'
import {
  createDurableFreeResourcePlannerV1,
  type AuthenticatedAtomicGenerationCheckpointV1,
} from '../../src/sovereignty/durable-free-resource-planner.js'
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
  it('ignores an untrusted fake signed envelope with the same ID before a valid approval',async()=>{
    const c=await context()
    const forged=await c.sign(c.payload,c.other.privateKey,c.other.publicKey)
    const planner=createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation)
    const decision=await planner.plan(c.snapshot,request,[c.evidence],[forged,c.signed])
    expect(decision.outcome).toBe('PLANNING_ELIGIBLE')
    expect(decision.authority_effect).toBe('NONE')
  })
  it('does not reserve an ID after cryptographic signature tampering',async()=>{
    const c=await context()
    const tampered={...c.signed,signature_hex:'1'.repeat(128)}
    const decision=await createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation)
      .plan(c.snapshot,request,[c.evidence],[tampered,c.signed])
    expect(decision.outcome).toBe('PLANNING_ELIGIBLE')
  })
  it('still rejects an independently revoked approval even when a forged duplicate is prepended',async()=>{
    const c=await context()
    const trust={...c.trust,revoked_approval_ids:[c.payload.approval_id]}
    const forged=await c.sign(c.payload,c.other.privateKey,c.other.publicKey)
    const decision=await createTrustedFreeResourcePlannerV1(trust,()=>request.current_generation)
      .plan(c.snapshot,request,[c.evidence],[forged,c.signed])
    expect(decision.outcome).toBe('HOLD')
  })
  it('latches HOLD when trusted generation rolls backwards even after valid earlier planning',async()=>{
    const c=await context()
    let actual='10'
    const planner=createTrustedFreeResourcePlannerV1(c.trust,()=>actual)
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('PLANNING_ELIGIBLE')
    actual='12'
    expect((await planner.plan(c.snapshot,{...request,current_generation:'12'},[c.evidence],[c.signed])).outcome).toBe('HOLD')
    actual='10'
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    // Reaching the former maximum must not clear the rollback alarm.
    actual='12'
    expect((await planner.plan(c.snapshot,{...request,current_generation:'12'},[c.evidence],[c.signed])).outcome).toBe('HOLD')
  })
  it('records trusted generation advance despite stale caller request, then blocks rollback',async()=>{
    const c=await context()
    let actual='10'
    const planner=createTrustedFreeResourcePlannerV1(c.trust,()=>actual)
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('PLANNING_ELIGIBLE')
    actual='12'
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    actual='10'
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
  })
  it('still allows monotonic fresh signed requests within trusted limits',async()=>{
    const c=await context()
    let actual='10'
    const planner=createTrustedFreeResourcePlannerV1(c.trust,()=>actual)
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('PLANNING_ELIGIBLE')
    actual='11'
    const nextRequest={...request,current_generation:'11'}
    const next=await c.sign({...c.payload,request_root:await freeResourceRequestRootV1(nextRequest)})
    const decision=await planner.plan(c.snapshot,nextRequest,[c.evidence],[next])
    expect(decision.outcome).toBe('PLANNING_ELIGIBLE')
    expect(decision.authority_effect).toBe('NONE')
  })
  it('holds when the trusted generation advances during asynchronous signature verification',async()=>{
    const c=await context()
    let calls=0
    const clock=()=>++calls===1?'10':'11'
    const planner=createTrustedFreeResourcePlannerV1(c.trust,clock)
    const result=await planner.plan(c.snapshot,request,[c.evidence],[c.signed])
    expect(result.outcome).toBe('HOLD')
    expect(result.provider_id).toBeNull()
    expect(calls).toBeGreaterThanOrEqual(2)
  })
  it('holds and latches a clock rollback observed only after asynchronous verification',async()=>{
    const c=await context()
    let actual='9'
    let calls=0
    const clock=()=>++calls===1?'10':actual
    const planner=createTrustedFreeResourcePlannerV1(c.trust,clock)
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    actual='10'
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
  })
  it('allows a stable authenticated clock with no signing or request changes',async()=>{
    const c=await context()
    let reads=0
    const clock=()=>{reads++;return '10'}
    const result=await createTrustedFreeResourcePlannerV1(c.trust,clock)
      .plan(c.snapshot,request,[c.evidence],[c.signed])
    expect(result.outcome).toBe('PLANNING_ELIGIBLE')
    expect(reads).toBeGreaterThanOrEqual(2)
    expect(result.authority_effect).toBe('NONE')
  })
  it('holds conflicting valid Ed25519 approvals that reuse one ID regardless of order',async()=>{
    const c=await context()
    const alternate=await c.sign({...c.payload,expires_generation:'12'})
    const planner=createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation)
    for(const signed of [[c.signed,alternate],[alternate,c.signed]]){
      const decision=await planner.plan(c.snapshot,request,[c.evidence],signed)
      expect(decision.outcome).toBe('HOLD')
      expect(decision.capacity_root).toBeNull()
      expect(decision.authority_effect).toBe('NONE')
    }
  })
  it('permits an exact duplicate of one valid signed payload for planning only',async()=>{
    const c=await context()
    const planner=createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation)
    const result=await planner.plan(c.snapshot,request,[c.evidence],[c.signed,c.signed])
    expect(result.outcome).toBe('PLANNING_ELIGIBLE')
    expect(result.capacity_root).toBe(c.evidence.evidence_root)
    expect(result.authority_effect).toBe('NONE')
  })
  it('fails closed on a second valid same-ID signature bound to a different request',async()=>{
    const c=await context()
    const otherRequest={...request,worst_case_units:'150'}
    const alternate=await c.sign({...c.payload,request_root:await freeResourceRequestRootV1(otherRequest)})
    const planner=createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation)
    const result=await planner.plan(c.snapshot,request,[c.evidence],[c.signed,alternate])
    expect(result.outcome).toBe('HOLD')
  })
  it('keeps unsigned quota evidence on HOLD even if every evidence hash is well-formed',async()=>{
    const c=await context()
    const x=await createTrustedFreeResourcePlannerV1(c.trust,()=>request.current_generation).plan(c.snapshot,request,[c.evidence],[])
    expect(x.outcome).toBe('HOLD')
    expect(x.provider_id).toBeNull()
  })
})

describe('shared durable high-water checkpoint contract (isolated synthetic store)',()=>{
  function seededStore(initial:string|null='10'){
    let floor=initial
    const seen:string[]=[]
    const store:AuthenticatedAtomicGenerationCheckpointV1={
      async observe_and_advance(policy_id,generation){
        seen.push(policy_id+':'+generation)
        if(floor===null) return {outcome:'UNAVAILABLE'}
        if(BigInt(generation)<BigInt(floor)) return {outcome:'ROLLBACK'}
        floor=generation
        return {outcome:'ACCEPTED',persisted_generation:floor}
      },
    }
    return {store,seen,getFloor:()=>floor}
  }
  it('accepts signed evidence only when a preseeded durable floor is atomically checked twice',async()=>{
    const c=await context()
    const durable=seededStore()
    const planner=createDurableFreeResourcePlannerV1(c.trust,()=>request.current_generation,durable.store)
    const result=await planner.plan(c.snapshot,request,[c.evidence],[c.signed])
    expect(result.outcome).toBe('PLANNING_ELIGIBLE')
    expect(result.authority_effect).toBe('NONE')
    expect(planner.authority_effect).toBe('NONE')
    expect(durable.seen).toEqual(['offline-test-policy:10','offline-test-policy:10'])
  })
  it('holds on an absent durable row rather than silently seeding a reset high water mark',async()=>{
    const c=await context()
    const durable=seededStore(null)
    const planner=createDurableFreeResourcePlannerV1(c.trust,()=>request.current_generation,durable.store)
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    expect(durable.getFloor()).toBeNull()
  })
  it('holds the older planner after a second process advances a shared durable floor',async()=>{
    const c=await context()
    const shared=seededStore('10')
    const old=createDurableFreeResourcePlannerV1(c.trust,()=>request.current_generation,shared.store)
    const nextRequest={...request,current_generation:'11'}
    const nextSigned=await c.sign({...c.payload,request_root:await freeResourceRequestRootV1(nextRequest)})
    const newer=createDurableFreeResourcePlannerV1(c.trust,()=>nextRequest.current_generation,shared.store)
    expect((await old.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('PLANNING_ELIGIBLE')
    expect((await newer.plan(c.snapshot,nextRequest,[c.evidence],[nextSigned])).outcome).toBe('PLANNING_ELIGIBLE')
    expect(shared.getFloor()).toBe('11')
    // Recreating the old planner (simulating process restart) cannot reset the shared floor.
    const restarted=createDurableFreeResourcePlannerV1(c.trust,()=>request.current_generation,shared.store)
    expect((await restarted.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    expect(shared.getFloor()).toBe('11')
  })
  it('holds when the durable adapter fails or fabricates a mismatched committed floor',async()=>{
    const c=await context()
    const broken:AuthenticatedAtomicGenerationCheckpointV1={
      async observe_and_advance(){throw new Error('storage unavailable')},
    }
    const mismatched:AuthenticatedAtomicGenerationCheckpointV1={
      async observe_and_advance(){return {outcome:'ACCEPTED',persisted_generation:'9'}},
    }
    for(const store of [broken,mismatched]){
      const planner=createDurableFreeResourcePlannerV1(c.trust,()=>request.current_generation,store)
      expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    }
  })
  it('holds when the final transaction loses a race to a newer persisted floor',async()=>{
    const c=await context()
    let reads=0
    const race:AuthenticatedAtomicGenerationCheckpointV1={
      async observe_and_advance(_policy,generation){
        reads++
        if(reads===1) return {outcome:'ACCEPTED',persisted_generation:generation}
        return {outcome:'ROLLBACK'}
      },
    }
    const planner=createDurableFreeResourcePlannerV1(c.trust,()=>request.current_generation,race)
    const decision=await planner.plan(c.snapshot,request,[c.evidence],[c.signed])
    expect(reads).toBe(2)
    expect(decision.outcome).toBe('HOLD')
    expect(decision.capacity_root).toBeNull()
  })
  it('refuses untrusted request time and missing transactional checkpoint',async()=>{
    const c=await context()
    const durable=seededStore('10')
    const planner=createDurableFreeResourcePlannerV1(c.trust,()=>request.current_generation,durable.store)
    const stale={...request,current_generation:'9'}
    expect((await planner.plan(c.snapshot,stale,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    expect(durable.seen).toEqual([])
    expect(()=>createDurableFreeResourcePlannerV1(c.trust,()=>request.current_generation,null as unknown as AuthenticatedAtomicGenerationCheckpointV1))
      .toThrow('trusted durable checkpoint')
  })
  it('latches HOLD across transient checkpoint failure even after the backend recovers',async()=>{
    const c=await context()
    let calls=0
    let online=false
    const store:AuthenticatedAtomicGenerationCheckpointV1={
      async observe_and_advance(_policy,generation){
        calls++
        if(!online) throw new Error('checkpoint temporarily unavailable')
        return {outcome:'ACCEPTED',persisted_generation:generation}
      },
    }
    const planner=createDurableFreeResourcePlannerV1(c.trust,()=>request.current_generation,store)
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    online=true
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    expect(calls).toBe(1)
    // Only a newly and independently authenticated host bootstrap can retry.
    const restarted=createDurableFreeResourcePlannerV1(c.trust,()=>request.current_generation,store)
    expect((await restarted.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('PLANNING_ELIGIBLE')
    expect(calls).toBe(3)
  })
  it('latches HOLD after final-checkpoint rollback even if future reads claim recovery',async()=>{
    const c=await context()
    let calls=0
    const store:AuthenticatedAtomicGenerationCheckpointV1={
      async observe_and_advance(_policy,generation){
        calls++
        return calls===2
          ? {outcome:'ROLLBACK'}
          : {outcome:'ACCEPTED',persisted_generation:generation}
      },
    }
    const planner=createDurableFreeResourcePlannerV1(c.trust,()=>request.current_generation,store)
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    expect(calls).toBe(2)
  })
  it('latches HOLD after a forged committed-generation acknowledgement',async()=>{
    const c=await context()
    let calls=0
    const store:AuthenticatedAtomicGenerationCheckpointV1={
      async observe_and_advance(_policy,generation){
        calls++
        if(calls===1) return {outcome:'ACCEPTED',persisted_generation:'9'}
        return {outcome:'ACCEPTED',persisted_generation:generation}
      },
    }
    const planner=createDurableFreeResourcePlannerV1(c.trust,()=>request.current_generation,store)
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    expect(calls).toBe(1)
  })

})

describe('SQL-to-Ed25519 planner integration contract (synthetic parameterized client)',()=>{
  it('composes a parameterized PostgreSQL RPC with complete signed planning and two floor checks',async()=>{
    const c=await context()
    const sqlCalls:{sql:string;args:readonly string[]}[]=[]
    let highWater=10n
    const client:AuthenticatedParameterizedPostgresV1={
      async query(sql,parameters){
        sqlCalls.push({sql,args:parameters})
        const generation=BigInt(parameters[1])
        if(generation<highWater) return {rows:[{outcome:'ROLLBACK',persisted_generation:null}]}
        highWater=generation
        return {rows:[{outcome:'ACCEPTED',persisted_generation:generation.toString()}]}
      },
    }
    const adapter=createIsolatedPostgresGenerationCheckpointV1(client)
    const planner=createDurableFreeResourcePlannerV1(c.trust,()=>request.current_generation,adapter)
    const result=await planner.plan(c.snapshot,request,[c.evidence],[c.signed])
    expect(result.outcome).toBe('PLANNING_ELIGIBLE')
    expect(result.authority_effect).toBe('NONE')
    expect(sqlCalls).toHaveLength(2)
    expect(sqlCalls[0].sql).toBe(
      'SELECT outcome, persisted_generation FROM public.aegis_test_observe_advance_v1($1::text,$2::text)',
    )
    expect(sqlCalls.map(x=>x.args)).toEqual([
      ['offline-test-policy','10'],['offline-test-policy','10'],
    ])
  })
  it('detects another worker advancing the SQL floor before signed planning finishes',async()=>{
    const c=await context()
    let calls=0
    const client:AuthenticatedParameterizedPostgresV1={
      async query(_sql,params){
        calls++
        return calls===1
          ? {rows:[{outcome:'ACCEPTED',persisted_generation:params[1]}]}
          : {rows:[{outcome:'ROLLBACK',persisted_generation:null}]}
      },
    }
    const planner=createDurableFreeResourcePlannerV1(
      c.trust,()=>request.current_generation,
      createIsolatedPostgresGenerationCheckpointV1(client),
    )
    const result=await planner.plan(c.snapshot,request,[c.evidence],[c.signed])
    expect(result.outcome).toBe('HOLD')
    expect(result.capacity_root).toBeNull()
    expect(calls).toBe(2)
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    expect(calls).toBe(2)
  })
  it('rejects malformed SQL acknowledgements without permitting retry on the same planner',async()=>{
    const c=await context()
    for(const rows of [
      [],[{},{}],[{outcome:'ACCEPTED',persisted_generation:'9'}],
      [{outcome:'ACCEPTED',persisted_generation:'010'}],
      [{outcome:'ACCEPTED',persisted_generation:10}],
      [{outcome:'ROLLBACK',persisted_generation:'10'}],
      [{outcome:'SURPRISE',persisted_generation:null}],
      [null],
    ]){
      let queries=0
      const client:AuthenticatedParameterizedPostgresV1={
        async query(_sql,params){
          queries++
          return {rows:queries===1?rows:[{
            outcome:'ACCEPTED',persisted_generation:params[1],
          }]}
        },
      }
      const planner=createDurableFreeResourcePlannerV1(
        c.trust,()=>request.current_generation,
        createIsolatedPostgresGenerationCheckpointV1(client),
      )
      expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
      expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
      expect(queries).toBe(1)
    }
  })
  it('denies malformed policy/generation before SQL calls and missing client at bootstrap',async()=>{
    let queries=0
    const client:AuthenticatedParameterizedPostgresV1={
      async query(){queries++;return {rows:[{outcome:'ACCEPTED',persisted_generation:'10'}]}}
    }
    const adapter=createIsolatedPostgresGenerationCheckpointV1(client)
    expect(await adapter.observe_and_advance('bad; DROP TABLE x','10')).toEqual({outcome:'UNAVAILABLE'})
    expect(await adapter.observe_and_advance('offline-test-policy','01')).toEqual({outcome:'UNAVAILABLE'})
    expect(queries).toBe(0)
    expect(()=>createIsolatedPostgresGenerationCheckpointV1(
      null as unknown as AuthenticatedParameterizedPostgresV1,
    )).toThrow('trusted parameterized PostgreSQL client required')
  })
  it('converts SQL connection failure to HOLD, never treating errors as valid receipts',async()=>{
    const c=await context()
    const client:AuthenticatedParameterizedPostgresV1={
      async query(){throw new Error('offline SQL connection')}
    }
    const planner=createDurableFreeResourcePlannerV1(
      c.trust,()=>request.current_generation,
      createIsolatedPostgresGenerationCheckpointV1(client),
    )
    expect((await planner.plan(c.snapshot,request,[c.evidence],[c.signed])).outcome).toBe('HOLD')
    expect(planner.authority_effect).toBe('NONE')
  })
  it('still holds unsigned provider quota even with a good SQL checkpoint',async()=>{
    const c=await context()
    const client:AuthenticatedParameterizedPostgresV1={
      async query(_sql,parameters){
        return {rows:[{outcome:'ACCEPTED',persisted_generation:parameters[1]}]}
      },
    }
    const planner=createDurableFreeResourcePlannerV1(
      c.trust,()=>request.current_generation,
      createIsolatedPostgresGenerationCheckpointV1(client),
    )
    const result=await planner.plan(c.snapshot,request,[c.evidence],[])
    expect(result.outcome).toBe('HOLD')
    expect(result.authority_effect).toBe('NONE')
  })
})
