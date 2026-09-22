import assert from 'node:assert/strict'
import {hashValue} from '../../src/core/hashing.js'
import type {SHA256Hex} from '../../src/core/types.js'
import {buildProviderMeshSnapshotV1, type ProviderDescriptorV1, type ProviderObservationV1} from '../../src/sovereignty/provider-mesh.js'
import {buildProviderNativeAgentRegistryV1} from '../../src/sovereignty/provider-native-agents.js'
import {certifyProviderNativeFanoutV1, type FanoutInputV1, type FanoutVerifierV1} from '../../src/sovereignty/provider-native-fanout.js'
import {createProviderNativeFanoutTeamV1, certifyProviderNativeFanoutTeamV1} from '../../src/sovereignty/provider-native-fanout-team.js'
import type {NativeProviderIdV1, NativeSdkPackageV1, ProviderNativeSdkRuntimeOptionsV1} from '../../src/sovereignty/provider-adapters/provider-native-sdk-runtime.js'

const ids = ['anthropic', 'google-cloud', 'openai'] as const
const digest = (c: string) => c.repeat(64) as SHA256Hex
const delay = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(r => {resolve = r}); return {promise, resolve} }
async function fixture(): Promise<FanoutInputV1> {
  const descriptors: ProviderDescriptorV1[] = ids.map(provider_id => ({schema_version:'1.0.0', provider_id, planes:['INTELLIGENCE'], declared_capabilities:['AGENT_EXECUTION','MODEL_INFERENCE'], authority_effect:'NONE'}))
  const observations: ProviderObservationV1[] = ids.map((provider_id,i) => ({schema_version:'1.0.0',provider_id,state:'OBSERVED_AVAILABLE',observed_capabilities:['AGENT_EXECUTION','MODEL_INFERENCE'],evidence_hash:digest(String(i+1)),observation_generation:'10',authority_effect:'NONE'}))
  return {snapshot:await buildProviderMeshSnapshotV1(descriptors,observations),registry:await buildProviderNativeAgentRegistryV1(descriptors),batch_id:'integration-1',task:'Inspect this synthetic test evidence.',providers:[...ids],max_parallel:3,min_verified:3,timeout_ms:1000,current_generation:'10',max_observation_age_generations:'1'}
}

// Only SDK modules are doubled. Selection, adapters, SDK-runner code, fanout,
// receipt creation/validation and independent certification are the actual imports.
function harness(control: {
  authorize?: (provider: NativeProviderIdV1) => boolean | Promise<boolean>
  beforeRun?: (provider: NativeProviderIdV1) => Promise<void>
  beforeLoad?: () => Promise<void>
  loadFailure?: NativeSdkPackageV1
  malformed?: NativeProviderIdV1
  rejectVerification?: NativeProviderIdV1
} = {}) {
  const loads: string[] = [], calls: string[] = [], authorizations: string[] = []
  const tasks: string[] = [], configurations: Record<string, any> = {}
  let active = 0, peak = 0
  async function invoke(provider: NativeProviderIdV1, task: string): Promise<string> {
    calls.push(provider); tasks.push(task); active++; peak=Math.max(peak,active)
    try { await control.beforeRun?.(provider); await delay(3); return `fixture-evidence:${provider}` }
    finally {active--}
  }
  const sdkModules: Record<NativeSdkPackageV1, unknown> = {
    '@openai/agents': {
      Agent: class {constructor(config: unknown) {configurations.openai=config}},
      Runner: class {
        constructor(config: unknown) {configurations.openaiRunner=config}
        async run(_agent: unknown, task: string, options: unknown) {
          configurations.openaiRun=options
          return {finalOutput:await invoke('openai',task),lastResponseId:control.malformed==='openai'?'':'fixture-openai-response'}
        }
      },
    },
    '@anthropic-ai/claude-agent-sdk': {
      async *query(config: any) {
        configurations.anthropic=config.options
        const result=await invoke('anthropic',config.prompt)
        yield {type:'result',subtype:control.malformed==='anthropic'?'error_during_execution':'success',is_error:control.malformed==='anthropic',result,session_id:'fixture-anthropic-session'}
      },
    },
    '@google/adk': {
      LlmAgent: class {constructor(config: unknown) {configurations.google=config}},
      InMemoryRunner: class {
        constructor(config: unknown) {configurations.googleRunner=config}
        sessionService={async createSession() {return {id:'fixture-google-session'}}}
        async *runAsync(config: any) {
          configurations.googleRun=config
          const text=await invoke('google-cloud',config.newMessage.parts[0].text)
          yield {final:true,author:'aegis_google_provider_agent',content:{parts:control.malformed==='google-cloud'?[{functionCall:{name:'forbidden'}}]:[{text}]}}
        }
      },
      isFinalResponse(event: any) {return event.final===true},
    },
  }
  const runtime: ProviderNativeSdkRuntimeOptionsV1 = {
    models:{openai:'fixture-openai-model',anthropic:'fixture-anthropic-model',google_cloud:'fixture-google-model'},
    maxTurns:2,maxOutputTokens:128,maxEvents:8,maxTaskChars:64000,
    async authorize(request) {authorizations.push(request.provider_id); return control.authorize ? await control.authorize(request.provider_id) : true},
    async loadSdk(specifier) {
      loads.push(specifier); await control.beforeLoad?.()
      if (specifier===control.loadFailure) throw new Error('SENSITIVE_SDK_FAILURE_DETAIL')
      return sdkModules[specifier]
    },
  }
  const verifier: FanoutVerifierV1 = {
    verifier_id:'fixture-output-policy',policy_hash:digest('f'),
    async verify(input) {
      const passed=input.output===`fixture-evidence:${input.provider_id}` && input.provider_id!==control.rejectVerification
      return {passed,evidence_hash:await hashValue({domain:'TEST_ONLY_VERIFIER',subject_root:input.subject_root,passed})}
    },
  }
  const options={runtime,verifier,authorization_policy_hash:digest('a')}
  return {options,loads,calls,authorizations,tasks,configurations,get active(){return active},get peak(){return peak}}
}
const leaf = (result: any, id: string) => result.receipt.leaves.find((item: any) => item.provider_id===id)

export function registerNativeFanoutTeamCases(test: (name: string, fn: () => Promise<void>) => unknown): void {
  test('team construction imports no SDK and performs no authorization or execution', async () => {
    const h=harness(); const team=createProviderNativeFanoutTeamV1(h.options)
    assert.deepEqual([...team.agent_ids].sort(),ids.map(id=>`provider-agent:${id}`)); assert.equal(h.loads.length,0); assert.equal(h.authorizations.length,0)
  })
  test('real mesh, real three adapters and real SDK-runner source compose into a certified fanout result', async () => {
    const h=harness(); const team=createProviderNativeFanoutTeamV1(h.options); const input=await fixture(); const result=await team.execute(input)
    assert.deepEqual([...h.calls].sort(),ids); assert.equal(h.peak,3); assert.equal(result.receipt.verified_count,3)
    assert.equal(result.receipt.outcome,'SYNTHESIZED'); assert.equal(result.receipt.authority_effect,'NONE'); assert.equal(result.receipt.durable_apply_performed,false)
    assert.equal(await certifyProviderNativeFanoutTeamV1(input,result,team.configuration),true)
    assert.equal(await certifyProviderNativeFanoutV1(result.receipt.request,result),true)
    for(const task of h.tasks) {const outer=JSON.parse(task);const inner=JSON.parse(outer.task);assert.equal(inner.task,input.task);assert.deepEqual(inner.runtime_configuration,team.configuration)}
    assert.equal(h.configurations.openai.model,'fixture-openai-model'); assert.equal(h.configurations.google.model,'fixture-google-model')
  })
  test('SDK tool denial and tracing configuration survive the complete integration', async () => {
    const h=harness(); await createProviderNativeFanoutTeamV1(h.options).execute(await fixture())
    assert.deepEqual(h.configurations.openai.tools,[]);assert.deepEqual(h.configurations.openai.handoffs,[]);assert.equal(h.configurations.openaiRunner.tracingDisabled,true)
    assert.deepEqual(h.configurations.anthropic.tools,[]);assert.deepEqual(h.configurations.anthropic.mcpServers,{});assert.equal(h.configurations.anthropic.persistSession,false)
    assert.equal((await h.configurations.anthropic.canUseTool()).behavior,'deny')
    assert.deepEqual(h.configurations.google.tools,[]);assert.deepEqual(h.configurations.google.subAgents,[])
  })
  for(const max_parallel of [1,2]) test(`physical SDK calls respect max_parallel=${max_parallel}`, async () => {
    const h=harness(); const result=await createProviderNativeFanoutTeamV1(h.options).execute({...await fixture(),max_parallel})
    assert.equal(h.peak,max_parallel);assert.equal(h.calls.length,3);assert.equal(result.receipt.verified_count,3)
  })
  for(const current_generation of ['9','50']) test(`future/stale evidence at generation ${current_generation} makes zero authorizer and SDK calls`, async () => {
    const h=harness();const result=await createProviderNativeFanoutTeamV1(h.options).execute({...await fixture(),current_generation})
    assert.equal(result.receipt.outcome,'DENIED');assert.equal(h.authorizations.length,0);assert.equal(h.loads.length,0);assert.equal(h.calls.length,0)
  })
  test('insufficient preflight quorum never loads an SDK', async () => {
    const h=harness();const input=await fixture()
    input.snapshot=await buildProviderMeshSnapshotV1(input.snapshot.descriptors,input.snapshot.observations.map(o=>({...o,state:o.provider_id==='openai'?'OBSERVED_AVAILABLE':'OBSERVED_UNAVAILABLE'})))
    const result=await createProviderNativeFanoutTeamV1(h.options).execute(input)
    assert.equal(result.receipt.outcome,'DENIED');assert.equal(h.loads.length,0);assert.equal(h.authorizations.length,0)
  })
  test('host denial suppresses that SDK and does not reduce the required verification quorum', async () => {
    const h=harness({authorize:id=>id!=='anthropic'});const result=await createProviderNativeFanoutTeamV1(h.options).execute(await fixture())
    assert.equal(h.loads.includes('@anthropic-ai/claude-agent-sdk'),false);assert.equal(h.calls.length,2)
    assert.equal(result.receipt.outcome,'INSUFFICIENT_VERIFIED_RESULTS');assert.equal(result.receipt.request.min_verified,3)
  })
  test('truthy nonboolean host approval is denied before import', async () => {
    const h=harness({authorize:()=> 'true' as unknown as boolean});const result=await createProviderNativeFanoutTeamV1(h.options).execute(await fixture())
    assert.equal(h.loads.length,0);assert.equal(result.receipt.verified_count,0)
  })
  test('package load failure is isolated and does not expose private error details', async () => {
    const h=harness({loadFailure:'@openai/agents'});const result=await createProviderNativeFanoutTeamV1(h.options).execute({...await fixture(),min_verified:2})
    assert.equal(result.receipt.verified_count,2);assert.equal(result.receipt.outcome,'SYNTHESIZED');assert.equal(JSON.stringify(result).includes('SENSITIVE_SDK_FAILURE_DETAIL'),false)
  })
  for(const malformed of ids) test(`malformed ${malformed} native terminal result is rejected through the real runner`, async () => {
    const h=harness({malformed});const result=await createProviderNativeFanoutTeamV1(h.options).execute(await fixture())
    assert.equal(leaf(result,malformed).status,'FAILED');assert.equal(result.receipt.verified_count,2);assert.equal(result.receipt.outcome,'INSUFFICIENT_VERIFIED_RESULTS')
  })
  test('external verifier rejection cannot be replaced by cross-provider agreement', async () => {
    const h=harness({rejectVerification:'openai'});const result=await createProviderNativeFanoutTeamV1(h.options).execute(await fixture())
    assert.equal(leaf(result,'openai').status,'VERIFIER_REJECTED');assert.equal(result.synthesis,null);assert.equal(result.receipt.consensus_claim,'NONE')
  })
  test('input and host models are captured before asynchronous authorization', async () => {
    const entered=deferred<void>(),release=deferred<boolean>();const h=harness({authorize:async()=>{entered.resolve();return release.promise}})
    const team=createProviderNativeFanoutTeamV1(h.options);const input={...await fixture(),providers:['openai'],min_verified:1}
    const pending=team.execute(input);await entered.promise
    input.task='MUTATED_TASK';(h.options.runtime.models as {openai:string}).openai='MUTATED_MODEL';release.resolve(true)
    const result=await pending;assert.equal(h.configurations.openai.model,'fixture-openai-model');assert.equal(JSON.stringify(result).includes('MUTATED_TASK'),false);assert.equal(JSON.stringify(result).includes('MUTATED_MODEL'),false)
  })
  test('model and policy configuration changes alter the native task and request commitment', async () => {
    const input=await fixture();const a=harness(),b=harness();(b.options.runtime.models as {openai:string}).openai='fixture-alternative-model';b.options.authorization_policy_hash=digest('b')
    const first=await createProviderNativeFanoutTeamV1(a.options).execute(input);const second=await createProviderNativeFanoutTeamV1(b.options).execute(input)
    assert.notEqual(first.receipt.request_root,second.receipt.request_root);assert.notEqual(a.tasks[0],b.tasks[0])
  })
  test('one persistent team retains batch replay protection across calls', async () => {
    const h=harness();const team=createProviderNativeFanoutTeamV1(h.options);const input=await fixture();await team.execute(input)
    await assert.rejects(()=>team.execute(input),/batch_id already used/);assert.equal(h.calls.length,3)
  })
  test('timed-out native work retains its slot and cannot rewrite a receipt after late completion', async () => {
    const release=deferred<void>(),entered=deferred<void>();let held=false
    const h=harness({beforeRun:async()=>{if(!held){held=true;entered.resolve();await release.promise}}})
    const team=createProviderNativeFanoutTeamV1(h.options);const input={...await fixture(),providers:['openai'],min_verified:1,max_parallel:1,timeout_ms:20}
    const pending=team.execute(input);await entered.promise;const result=await pending;const bytes=JSON.stringify(result)
    assert.equal(leaf(result,'openai').status,'TIMED_OUT');assert.equal(leaf(result,'openai').cancellation_confirmed,false)
    await assert.rejects(()=>team.execute({...input,batch_id:'overlap'}),/busy/);release.resolve();await delay(30)
    assert.equal(JSON.stringify(result),bytes);assert.equal(h.peak,1)
    const next=await team.execute({...input,batch_id:'after-settlement',timeout_ms:1000});assert.equal(next.receipt.verified_count,1)
  })
  test('late authorization after timeout cannot start an SDK import or provider call', async () => {
    const entered=deferred<void>(),release=deferred<boolean>();const h=harness({authorize:async()=>{entered.resolve();return release.promise}})
    const team=createProviderNativeFanoutTeamV1(h.options);const pending=team.execute({...await fixture(),providers:['openai'],min_verified:1,timeout_ms:20})
    await entered.promise;const result=await pending;assert.equal(leaf(result,'openai').status,'TIMED_OUT');release.resolve(true);await delay(30)
    assert.equal(h.loads.length,0);assert.equal(h.calls.length,0)
  })
  test('late module loading after timeout cannot start a provider call', async () => {
    const entered=deferred<void>(),release=deferred<void>();const h=harness({beforeLoad:async()=>{entered.resolve();await release.promise}})
    const pending=createProviderNativeFanoutTeamV1(h.options).execute({...await fixture(),providers:['openai'],min_verified:1,timeout_ms:20})
    await entered.promise;const result=await pending;release.resolve();await delay(30)
    assert.equal(leaf(result,'openai').status,'TIMED_OUT');assert.equal(h.calls.length,0)
  })
  test('forged registry body is rejected before host authorization', async () => {
    const h=harness();const input=await fixture();input.registry.agents[0]!.agent_id='forged-agent'
    await assert.rejects(()=>createProviderNativeFanoutTeamV1(h.options).execute(input),/registry/);assert.equal(h.authorizations.length,0)
  })
  test('independent team certification rejects altered output and wrong runtime configuration', async () => {
    const h=harness();const team=createProviderNativeFanoutTeamV1(h.options);const input=await fixture();const result=await team.execute(input)
    const corrupt=structuredClone(result);(corrupt.receipt.leaves[0]!.native_result!.output as {final_output:string}).final_output='forged'
    assert.equal(await certifyProviderNativeFanoutTeamV1(input,corrupt,team.configuration),false)
    const wrong=structuredClone(team.configuration);(wrong.models as {openai:string}).openai='another-model'
    assert.equal(await certifyProviderNativeFanoutTeamV1(input,result,wrong),false)
  })
  test('three equivalent complete runs produce byte-identical receipts with deterministic SDK fixtures', async () => {
    const input=await fixture();const encoded:string[]=[]
    for(let i=0;i<3;i++)encoded.push(JSON.stringify(await createProviderNativeFanoutTeamV1(harness().options).execute(input)))
    assert.equal(encoded[0],encoded[1]);assert.equal(encoded[1],encoded[2])
  })
  for(const task of ['   ','x'.repeat(20000)]) test(`invalid source task (${task.length} characters) fails before any SDK import`, async () => {
    const h=harness();const input={...await fixture(),task};await assert.rejects(async()=>createProviderNativeFanoutTeamV1(h.options).execute(input));assert.equal(h.loads.length,0)
  })
  test('missing host authorization, verifier or configuration policy cannot create an executable team', async () => {
    const h=harness()
    assert.throws(()=>createProviderNativeFanoutTeamV1({...h.options,runtime:{...h.options.runtime,authorize:undefined as any}}))
    assert.throws(()=>createProviderNativeFanoutTeamV1({...h.options,verifier:undefined as any}))
    assert.throws(()=>createProviderNativeFanoutTeamV1({...h.options,authorization_policy_hash:'invalid' as SHA256Hex}))
    assert.equal(h.loads.length,0)
  })
}
