import assert from 'node:assert/strict'
import { hashValue } from '../../src/core/hashing.js'
import { buildProviderMeshSnapshotV1 } from '../../src/sovereignty/provider-mesh.js'
import { buildProviderNativeAgentRegistryV1, selectProviderNativeAgentV1 } from '../../src/sovereignty/provider-native-agents.js'
import { createProviderNativeFanoutV1, certifyProviderNativeFanoutV1 } from '../../src/sovereignty/provider-native-fanout.js'
import type { FanoutInputV1, FanoutAdapterV1, FanoutVerifierV1 } from '../../src/sovereignty/provider-native-fanout.js'
import type { ProviderDescriptorV1, ProviderObservationV1 } from '../../src/sovereignty/provider-mesh.js'
import type { SHA256Hex } from '../../src/core/types.js'

const ids = ['anthropic', 'google-cloud', 'openai'] as const
const h = (c: string) => c.repeat(64) as SHA256Hex
const delay = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))
const prefix = { anthropic: 'AEGIS_ANTHROPIC_NATIVE_AGENT', 'google-cloud': 'AEGIS_GOOGLE_ADK_NATIVE_AGENT', openai: 'AEGIS_OPENAI_NATIVE_AGENT' }

async function fixture(): Promise<FanoutInputV1> {
  const descriptors: ProviderDescriptorV1[] = ids.map(provider_id => ({ schema_version: '1.0.0', provider_id, planes: ['INTELLIGENCE'], declared_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'], authority_effect: 'NONE' }))
  const observations: ProviderObservationV1[] = ids.map((provider_id, i) => ({ schema_version: '1.0.0', provider_id, state: 'OBSERVED_AVAILABLE', observed_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'], observation_generation: '10', evidence_hash: h(String(i+1)), authority_effect: 'NONE' }))
  return { snapshot: await buildProviderMeshSnapshotV1(descriptors, observations), registry: await buildProviderNativeAgentRegistryV1(descriptors), batch_id: 'batch-test-1', task: 'Inspect only the supplied synthetic evidence.', providers: [...ids], max_parallel: 3, min_verified: 2, timeout_ms: 1000, current_generation: '10', max_observation_age_generations: '1' }
}

// Synthetic native execution, using the existing #589/#591/#592 receipt formats.
// This is deliberately NOT evidence that any provider SDK or API ran.
function adapter(provider_id: typeof ids[number], edit?: (result: any, input: any) => Promise<void> | void): FanoutAdapterV1 {
  return { provider_id, async execute(input) {
    const selection = await selectProviderNativeAgentV1(input.snapshot, input.registry, { required_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'], allowed_providers: [provider_id], preferred_provider_order: [provider_id], current_generation: input.current_generation, max_observation_age_generations: input.max_observation_age_generations })
    const model = 'synthetic-test-model'; const final_output = `evidence from ${provider_id}`; const id = `synthetic-${provider_id}`
    const output = provider_id === 'openai' ? { final_output, model, run_id: id } : { final_output, model, session_id: id }
    const body = { schema_version: '1.0.0', provider_id, agent_id: `provider-agent:${provider_id}`, provider_selection_receipt_root: selection.receipt_root, ...(provider_id === 'openai' ? { native_run_id: id } : { native_session_id: id }), model,
      task_hash: await hashValue({ domain: `${prefix[provider_id]}_TASK_V1`, task: input.task }),
      output_hash: await hashValue({ domain: `${prefix[provider_id]}_OUTPUT_V1`, ...(provider_id === 'openai' ? { native_run_id: id } : { session_id: id }), model, final_output }),
      write_authority: 'NOT_GRANTED', merge_authority: 'NOT_GRANTED', deploy_authority: 'NOT_GRANTED', financial_authority: 'NOT_GRANTED', authority_effect: 'NONE' }
    const result = { selection, output, receipt: { ...body, receipt_root: await hashValue({ domain: `${prefix[provider_id]}_EXECUTION_RECEIPT_V1`, receipt: body }) } }
    await edit?.(result, input)
    return result
  } }
}
const verifier: FanoutVerifierV1 = { verifier_id: 'synthetic-evidence-check-v1', policy_hash: h('f'), async verify() { return { passed: true, evidence_hash: h('e') } } }
function create(adapters = ids.map(id => adapter(id)), v = verifier) { return createProviderNativeFanoutV1({ adapters, verifier: v }) }

export function registerFanoutCases(test: (name: string, fn: () => Promise<void>) => unknown): void {
  test('executes all three eligible provider lanes concurrently and certifies the evidence bundle', async () => {
    let active = 0; let peak = 0
    const service = create(ids.map(id => adapter(id, async () => { active++; peak = Math.max(peak, active); await delay(10); active-- })))
    const input = await fixture(); const result = await service.execute(input)
    assert.equal(peak, 3); assert.equal(result.receipt.outcome, 'SYNTHESIZED'); assert.equal(result.receipt.dispatched_count, 3)
    assert.equal(result.receipt.verified_count, 3); assert.equal(await certifyProviderNativeFanoutV1(input, result), true)
    assert.equal(result.receipt.authority_effect, 'NONE'); assert.equal(result.receipt.durable_apply_performed, false)
    assert.equal(result.receipt.consensus_claim, 'NONE'); assert.equal(result.receipt.synthesis_policy, 'PROVENANCE_BUNDLE_V1')
  })
  test('respects max_parallel=1 without dropping any selected lane', async () => {
    let active = 0; let peak = 0
    const input = { ...await fixture(), max_parallel: 1 }
    const result = await create(ids.map(id => adapter(id, async () => { active++; peak=Math.max(active,peak); await delay(3); active-- }))).execute(input)
    assert.equal(peak,1); assert.equal(result.receipt.verified_count,3)
  })
  test('stale observations make zero native calls', async () => {
    let calls=0; const input = { ...await fixture(), current_generation:'50' }
    const result = await create(ids.map(id => adapter(id, () => { calls++ }))).execute(input)
    assert.equal(calls,0); assert.equal(result.receipt.outcome,'DENIED'); assert.equal(result.synthesis,null)
    assert.equal(await certifyProviderNativeFanoutV1(input,result),true)
  })
  test('insufficient preflight quorum makes zero calls instead of lowering quorum', async () => {
    let calls=0; const input=await fixture()
    input.snapshot=await buildProviderMeshSnapshotV1(input.snapshot.descriptors,input.snapshot.observations.map(o=>({...o,state:o.provider_id==='openai'?'OBSERVED_AVAILABLE':'OBSERVED_UNAVAILABLE'})))
    const result=await create(ids.map(id=>adapter(id,()=>{calls++}))).execute(input)
    assert.equal(calls,0); assert.equal(result.receipt.outcome,'DENIED'); assert.equal(result.receipt.request.min_verified,2)
  })
  test('future observations cannot authorize a call', async () => {
    const result=await create().execute({...await fixture(),current_generation:'9'})
    assert.equal(result.receipt.dispatched_count,0)
  })
  test('does not count verifier rejection toward the fixed quorum', async () => {
    const result=await create(undefined,{...verifier, async verify({provider_id}) {return {passed:provider_id==='openai',evidence_hash:h('a')}}}).execute(await fixture())
    assert.equal(result.receipt.outcome,'INSUFFICIENT_VERIFIED_RESULTS'); assert.equal(result.receipt.verified_count,1); assert.equal(result.synthesis,null)
  })
  test('isolates one native exception while retaining two independently verified results', async () => {
    const result=await create([adapter('anthropic',()=>{throw new Error('private detail')}),adapter('google-cloud'),adapter('openai')]).execute(await fixture())
    assert.equal(result.receipt.outcome,'SYNTHESIZED'); assert.equal(result.receipt.verified_count,2)
    assert.equal(JSON.stringify(result).includes('private detail'),false)
  })
  test('receipt bytes do not depend on provider completion order', async () => {
    const input=await fixture(); const roots:string[]=[]
    for (const delays of [[12,3,1],[1,12,3],[3,1,12]]) {
      const result=await create(ids.map((id,i)=>adapter(id,()=>delay(delays[i]!)))).execute(input)
      roots.push(result.receipt.receipt_root)
    }
    assert.equal(new Set(roots).size,1)
  })
  test('verified outputs are not promoted to a scientific consensus claim', async () => {
    const result=await create().execute(await fixture())
    assert.equal(result.receipt.consensus_claim,'NONE')
    assert.match(result.synthesis!,/anthropic/); assert.match(result.synthesis!,/openai/)
  })
  test('rejects registry-body tampering before invoking adapters', async () => {
    const input=await fixture(); input.registry.agents[0]!.agent_id='forged-agent'
    await assert.rejects(create().execute(input),/registry/)
  })
  test('rejects registry authority tampering even if the old root is retained', async () => {
    const input=await fixture(); (input.registry.agents[0] as any).write_authority='GRANTED'
    await assert.rejects(create().execute(input),/registry/)
  })
  for (const field of ['provider_id','agent_id','task_hash','output_hash','provider_selection_receipt_root','receipt_root','authority_effect','write_authority']) {
    test(`rejects a native receipt with tampered ${field}`, async () => {
      const result=await create(ids.map(id=>adapter(id,r=>{r.receipt[field]=field.endsWith('hash')||field.endsWith('root')?h('b'):'forged'}))).execute(await fixture())
      assert.equal(result.receipt.verified_count,0); assert.equal(result.synthesis,null)
    })
  }
  test('rejects mismatched selection bodies and edited final output', async () => {
    const result=await create([adapter('anthropic',r=>{r.selection.agent_id='fake'}),adapter('google-cloud',r=>{r.output.final_output='edited'}),adapter('openai')]).execute(await fixture())
    assert.equal(result.receipt.verified_count,1); assert.equal(result.synthesis,null)
  })
  test('records verifier exceptions as failure without accepting the candidate', async () => {
    const result=await create(undefined,{...verifier,async verify(){throw new Error('secret')}}).execute(await fixture())
    assert.equal(result.receipt.verified_count,0); assert.equal(JSON.stringify(result).includes('secret'),false)
  })
  test('times out, requests abort, but does not claim that native cancellation completed', async () => {
    let release!:()=>void; const stalled=new Promise<void>(resolve=>{release=resolve}); let signal:AbortSignal|undefined
    const input={...await fixture(), timeout_ms:20}
    const service=create([adapter('anthropic',async(_r,i)=>{signal=i.signal;await stalled}),adapter('google-cloud'),adapter('openai')])
    const result=await service.execute(input)
    const leaf=result.receipt.leaves.find(x=>x.provider_id==='anthropic')!
    assert.equal(leaf.status,'TIMED_OUT'); assert.equal(leaf.cancellation_requested,true); assert.equal(leaf.cancellation_confirmed,false); assert.equal(signal?.aborted,true)
    await assert.rejects(service.execute({...input,batch_id:'second'}),/in.flight|busy/)
    const root=result.receipt.receipt_root; release(); await delay(5); assert.equal(result.receipt.receipt_root,root)
  })
  test('a timed-out physical slot is not reused for a queued provider', async () => {
    let release!:()=>void; const stalled=new Promise<void>(resolve=>{release=resolve}); const calls:string[]=[]
    const service=create(ids.map(id=>adapter(id,async()=>{calls.push(id);if(id==='anthropic')await stalled})))
    const result=await service.execute({...await fixture(),max_parallel:1,timeout_ms:15})
    assert.deepEqual(calls,['anthropic']); assert.equal(result.receipt.dispatched_count,1); assert.equal(result.receipt.verified_count,0)
    release(); await delay(5)
  })
  test('refuses reuse of a batch ID in the same instance', async () => {
    const service=create();const input=await fixture();await service.execute(input)
    await assert.rejects(service.execute(input),/batch.*used/)
  })
  test('binds the batch ID into the native task so old native receipts cannot be replayed', async () => {
    let old:any; const first=create([adapter('openai',r=>{old=structuredClone(r)})]);const input={...await fixture(),providers:['openai'],min_verified:1}
    await first.execute(input)
    const replay=create([{provider_id:'openai',async execute(){return old}}])
    const result=await replay.execute({...input,batch_id:'different-batch'})
    assert.equal(result.receipt.verified_count,0)
  })
  test('invalid fan-out bounds are rejected before dispatch', async () => {
    const input=await fixture()
    for(const change of [{max_parallel:0},{max_parallel:4},{min_verified:0},{min_verified:4},{timeout_ms:0},{timeout_ms:30001},{task:' '},{providers:['openai','openai']},{providers:['unknown']},{providers:[]}]) {
      await assert.rejects(create().execute({...input,...change} as FanoutInputV1))
    }
    assert.throws(()=>create([adapter('openai'),adapter('openai')]),/duplicate/)
  })
  test('clones caller input before asynchronous selection starts', async () => {
    const input=await fixture(); const pending=create().execute(input); input.task='MUTATED'
    const result=await pending; assert.equal(result.receipt.request.task,'Inspect only the supplied synthetic evidence.')
  })
  test('independent certificate rejects leaf, synthesis and quorum tampering', async () => {
    const input=await fixture();const good=await create().execute(input)
    for(const edit of [(r:any)=>{r.synthesis='forged'},(r:any)=>{r.receipt.verified_count=100},(r:any)=>{r.receipt.leaves.reverse()},(r:any)=>{r.receipt.authority_effect='GRANTED'},(r:any)=>{r.receipt.leaves[0].output='changed'}]) {
      const bad=structuredClone(good);edit(bad); assert.equal(await certifyProviderNativeFanoutV1(input,bad),false)
    }
  })
  test('rejects unexpected native fields instead of retaining leaked private data', async () => {
    const result=await create(ids.map(id=>adapter(id,r=>{r.output.private_key='DO_NOT_RETAIN_THIS'}))).execute(await fixture())
    assert.equal(result.receipt.verified_count,0); assert.equal(JSON.stringify(result).includes('DO_NOT_RETAIN_THIS'),false)
  })
  test('rejects unexpected top-level native fields', async () => {
    const result=await create(ids.map(id=>adapter(id,r=>{r.extra_secret='DO_NOT_RETAIN_THIS'}))).execute(await fixture())
    assert.equal(result.receipt.verified_count,0); assert.equal(JSON.stringify(result).includes('DO_NOT_RETAIN_THIS'),false)
  })
  test('rehashed leaf tampering still fails native task verification', async () => {
    const input=await fixture(); const result=structuredClone(await create().execute(input)) as any
    const leaf=result.receipt.leaves[0]; leaf.native_result.receipt.task_hash=h('d')
    const {receipt_root: ignoredNative,...nativeBody}=leaf.native_result.receipt
    leaf.native_result.receipt.receipt_root=await hashValue({domain:'AEGIS_ANTHROPIC_NATIVE_AGENT_EXECUTION_RECEIPT_V1',receipt:nativeBody})
    const {leaf_root: ignoredLeaf,...leafBody}=leaf
    leaf.leaf_root=await hashValue({domain:'AEGIS_PROVIDER_FANOUT_LEAF_V1',body:leafBody})
    const {receipt_root: ignoredBatch,...batchBody}=result.receipt
    result.receipt.receipt_root=await hashValue({domain:'AEGIS_PROVIDER_FANOUT_RECEIPT_V1',body:batchBody})
    assert.equal(await certifyProviderNativeFanoutV1(input,result),false)
  })

}
