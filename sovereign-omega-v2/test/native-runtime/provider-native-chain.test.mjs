// Real AEGIS control plane. Only the external provider SDKs are doubled.
import test, {after} from 'node:test';
import assert from 'node:assert/strict';
import {loadRepositoryTypescript} from './load-repository-ts.mjs';
const loaded = await loadRepositoryTypescript([
  'sovereignty/provider-native-agent-team.ts', 'sovereignty/provider-mesh.ts',
  'sovereignty/provider-native-agents.ts', 'core/hashing.ts',
]);
after(loaded.cleanup);
const {createProviderNativeAgentTeamV1: createTeam} = loaded.modules['sovereignty/provider-native-agent-team.ts'];
const {buildProviderMeshSnapshotV1: buildSnapshot, DECLARED_PROVIDER_CATALOG_V1: catalog} = loaded.modules['sovereignty/provider-mesh.ts'];
const {buildProviderNativeAgentRegistryV1: buildRegistry, selectProviderNativeAgentV1: selectAgent} = loaded.modules['sovereignty/provider-native-agents.ts'];
const {hashValue} = loaded.modules['core/hashing.ts'];
const providers = ['openai', 'anthropic', 'google-cloud'];
const models = {openai:'fixture-openai', anthropic:'fixture-claude', google_cloud:'fixture-google'};
const descriptors = catalog.filter(d => providers.includes(d.provider_id));
const caps = ['AGENT_EXECUTION', 'MODEL_INFERENCE'];
const packageName = {openai:'@openai/agents', anthropic:'@anthropic-ai/claude-agent-sdk', 'google-cloud':'@google/adk'};

async function evidence({state='OBSERVED_AVAILABLE', generation='10', capabilities=caps, only=null}={}) {
  const selected = only ? descriptors.filter(d => d.provider_id === only) : descriptors;
  return {
    snapshot: await buildSnapshot(selected, selected.map((d,i) => ({
      schema_version:'1.0.0', provider_id:d.provider_id, state,
      observed_capabilities:capabilities, observation_generation:generation,
      evidence_hash:String(i + 1).repeat(64), authority_effect:'NONE',
    }))),
    registry: await buildRegistry(selected),
  };
}
function fixture({authorize=async()=>true, beforeReturn=async()=>{}, fail=null, incomplete=false}={}) {
  const calls=[], loads=[], authorized=[], configs={};
  async function output(provider, task) {
    calls.push({provider,task});
    await beforeReturn(provider,task);
    if (fail === provider) throw new Error('FIXTURE_SDK_FAILURE');
    return `${provider}:${task}`;
  }
  const modules = {
    '@openai/agents': {
      Agent: class { constructor(c) { configs.openai=c; } },
      Runner: class { async run(_agent, task) {
        const finalOutput = await output('openai', task);
        return {finalOutput, lastResponseId:incomplete?undefined:`fixture-response:${task}`};
      }},
    },
    '@anthropic-ai/claude-agent-sdk': {query({prompt,options}) {
      configs.anthropic=options;
      return (async function*(){
        const result = await output('anthropic',prompt);
        yield {type:'result', subtype:'success', is_error:false, result,
          session_id:incomplete?undefined:`fixture-session:${prompt}`};
      })();
    }},
    '@google/adk': {
      LlmAgent: class { constructor(c){configs.google=c;} },
      InMemoryRunner: class {
        constructor(){this.sessionService={createSession:async()=>({id:'fixture-google-session'})};}
        async *runAsync({newMessage}) {
          const task = newMessage.parts[0].text;
          const result = await output('google-cloud',task);
          yield {author:incomplete?'other':'aegis_google_provider_agent', final:true, content:{parts:[{text:result}]}};
        }
      },
      isFinalResponse(event){return event.final===true;},
    },
  };
  const team = createTeam({models, authorize:async req=>{authorized.push(req);return authorize(req);},
    loadSdk:async spec=>{loads.push(spec);return modules[spec];}});
  return {team,calls,loads,authorized,configs};
}
function task(f, provider='openai', text='inspect') {
  return {...f, task:text, current_generation:'10', max_observation_age_generations:'1', preferred_provider_order:[provider]};
}
async function verifyReceipt(input, result, provider) {
  const selection = await selectAgent(input.snapshot, input.registry, {
    required_capabilities:caps, allowed_providers:providers, preferred_provider_order:input.preferred_provider_order,
    current_generation:input.current_generation, max_observation_age_generations:input.max_observation_age_generations,
  });
  const nativeSelection = await selectAgent(input.snapshot, input.registry, {
    required_capabilities:caps, allowed_providers:[provider], preferred_provider_order:[provider],
    current_generation:input.current_generation, max_observation_age_generations:input.max_observation_age_generations,
  });
  const prefix = {openai:'AEGIS_OPENAI_NATIVE_AGENT',anthropic:'AEGIS_ANTHROPIC_NATIVE_AGENT','google-cloud':'AEGIS_GOOGLE_ADK_NATIVE_AGENT'}[provider];
  const model = models[provider==='google-cloud'?'google_cloud':provider];
  const id = provider==='openai'?`fixture-response:${input.task}`:provider==='anthropic'?`fixture-session:${input.task}`:'fixture-google-session';
  const outputPayload = {domain:`${prefix}_OUTPUT_V1`, model, final_output:result.output,
    [provider==='openai'?'native_run_id':'session_id']:id};
  const nativeBody = {
    schema_version:'1.0.0',provider_id:provider,agent_id:`provider-agent:${provider}`,
    provider_selection_receipt_root:nativeSelection.receipt_root,
    [provider==='openai'?'native_run_id':'native_session_id']:id,model,
    task_hash:await hashValue({domain:`${prefix}_TASK_V1`,task:input.task}),
    output_hash:await hashValue(outputPayload),write_authority:'NOT_GRANTED',merge_authority:'NOT_GRANTED',
    deploy_authority:'NOT_GRANTED',financial_authority:'NOT_GRANTED',authority_effect:'NONE',
  };
  assert.equal(result.receipt.native_receipt_root, await hashValue({domain:`${prefix}_EXECUTION_RECEIPT_V1`,receipt:nativeBody}));
  assert.equal(result.receipt.provider_selection_receipt_root,selection.receipt_root);
  assert.equal(result.receipt.agent_id,`provider-agent:${provider}`);
  assert.equal(result.receipt.task_hash, await hashValue({domain:'AEGIS_PROVIDER_NATIVE_CONDUCTOR_TASK_V1',task:input.task}));
  assert.equal(result.receipt.output_hash, await hashValue({domain:'AEGIS_PROVIDER_NATIVE_CONDUCTOR_OUTPUT_V1',provider_id:provider,output:result.output}));
  const {receipt_root,...body}=result.receipt;
  assert.equal(receipt_root,await hashValue({domain:'AEGIS_PROVIDER_NATIVE_CONDUCTOR_RECEIPT_V1',receipt:body}));
  assert.equal(result.receipt.authority_effect,'NONE');
}

test('integration loads all ten real AEGIS modules with no boundary substitution',()=>{
  assert.deepEqual([...loaded.sources.keys()].sort(),[
    'core/canonicalize.ts','core/hashing.ts','sovereignty/provider-mesh.ts',
    'sovereignty/provider-native-agents.ts','sovereignty/provider-native-conductor.ts','sovereignty/provider-native-agent-team.ts',
    'sovereignty/provider-adapters/openai-native-agent.ts','sovereignty/provider-adapters/anthropic-native-agent.ts',
    'sovereignty/provider-adapters/google-adk-native-agent.ts','sovereignty/provider-adapters/provider-native-sdk-runtime.ts',
  ].sort());
});
for(const provider of providers) {
  test(`real ${provider} chain binds native and conductor receipt roots`,async()=>{
    const f=fixture();const input=task(await evidence(),provider);const result=await f.team.execute(input);
    assert.equal(result.output,`${provider}:inspect`);assert.equal(result.receipt.outcome,'EXECUTED');
    assert.deepEqual(f.loads,[packageName[provider]]);assert.deepEqual(f.calls,[{provider,task:'inspect'}]);
    assert.equal(f.authorized.length,1);assert.equal(f.authorized[0].provider_id,provider);
    await verifyReceipt(input,result,provider);
  });
}
for(const [name,opts] of [
  ['stale',{generation:'1'}],['future',{generation:'11'}],['configured',{state:'CONFIGURED'}],
  ['billing blocked',{state:'BILLING_BLOCKED'}],['missing agent capability',{capabilities:['MODEL_INFERENCE']}],
  ['missing model capability',{capabilities:['AGENT_EXECUTION']}],
]) test(`actual chain denies ${name} before authorization and SDK loading`,async()=>{
  const f=fixture();const result=await f.team.execute(task(await evidence(opts)));
  assert.equal(result.receipt.outcome,'DENIED');assert.equal(result.output,null);
  assert.deepEqual(f.authorized,[]);assert.deepEqual(f.loads,[]);assert.deepEqual(f.calls,[]);
});
for(const field of ['agent_id','write_authority'])test(`real chain rejects forged registry ${field} before SDK boundary`,async()=>{
  const f=fixture();const input=task(await evidence());input.registry.agents[0][field]='FORGED';
  await assert.rejects(f.team.execute(input),/registry.*verification failed/);
  assert.deepEqual(f.authorized,[]);assert.deepEqual(f.loads,[]);assert.deepEqual(f.calls,[]);
});
test('actual chain rejects a tampered observation with unchanged snapshot root',async()=>{
  const f=fixture();const input=task(await evidence());input.snapshot.observations[0].evidence_hash='f'.repeat(64);
  await assert.rejects(f.team.execute(input),/snapshot_root/);assert.deepEqual(f.authorized,[]);assert.deepEqual(f.calls,[]);
});
test('real selection respects a valid subset registry',async()=>{
  const f=fixture();const e=await evidence();e.registry=await buildRegistry(descriptors.filter(d=>d.provider_id==='anthropic'));
  const result=await f.team.execute(task(e,'openai'));
  assert.equal(result.receipt.provider_id,'anthropic');assert.deepEqual(f.loads,[packageName.anthropic]);
});
test('host authorization denial produces no SDK import and no execution result',async()=>{
  const f=fixture({authorize:async()=>false});await assert.rejects(f.team.execute(task(await evidence())),/NOT_AUTHORIZED/);
  assert.equal(f.authorized.length,1);assert.deepEqual(f.loads,[]);assert.deepEqual(f.calls,[]);
});
for(const provider of providers)test(`${provider} SDK failure is not silently retried on a different provider`,async()=>{
  const f=fixture({fail:provider});await assert.rejects(f.team.execute(task(await evidence(),provider)),/FIXTURE_SDK_FAILURE/);
  assert.deepEqual(f.calls.map(c=>c.provider),[provider]);assert.deepEqual(f.loads,[packageName[provider]]);
});
for(const provider of providers)test(`${provider} invalid native terminal output emits no successful result`,async()=>{
  const f=fixture({incomplete:true});await assert.rejects(f.team.execute(task(await evidence(),provider)));
  assert.deepEqual(f.calls.map(c=>c.provider),[provider]);
});
test('three concurrent callers keep actual agent contexts and receipt chains isolated',{timeout:3000},async()=>{
  let arrived=0,release;const barrier=new Promise(resolve=>{release=resolve;});
  const f=fixture({beforeReturn:async()=>{if(++arrived===3)release();await barrier;}});
  const e=await evidence();const inputs=providers.map((provider,i)=>task(e,provider,`task-${i}`));
  const results=await Promise.all(inputs.map(input=>f.team.execute(input)));
  assert.equal(arrived,3);assert.equal(f.calls.length,3);
  for(let i=0;i<3;i++) {
    assert.equal(results[i].output,`${providers[i]}:task-${i}`);
    await verifyReceipt(inputs[i],results[i],providers[i]);
  }
  assert.equal(new Set(results.map(r=>r.receipt.receipt_root)).size,3);
});
test('team captures task and registry before caller mutates them',async()=>{
  const f=fixture();const input=task(await evidence());const preserved=structuredClone(input);
  const pending=f.team.execute(input);input.task='changed';input.registry.agents[0].agent_id='forged-after-call';
  const result=await pending;assert.equal(result.output,'openai:inspect');await verifyReceipt(preserved,result,'openai');
});
