// Offline composition tests: actual team factory, explicit boundary doubles.
// These do not establish provider-mesh correctness or live SDK execution.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import vm from 'node:vm';
const ts=createRequire(import.meta.url)('typescript');
const url=new URL('../../src/sovereignty/provider-native-agent-team.ts',import.meta.url);
const source=readFileSync(url,'utf8');
const js=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
const root='a'.repeat(64);
function fixture({deny=false,wrongNative=false}={}) {
  const calls=[]; const wired=[]; const contexts=[]; const selections=[];
  const runners={openai:{kind:'openai'},anthropic:{kind:'anthropic'},google_cloud:{kind:'google-cloud'}};
  const native=id=>({runner})=>{
    wired.push([id,runner.kind]);
    return {async execute(input){calls.push(id);contexts.push(input);return {
      selection:{outcome:'SELECTED',provider_id:wrongNative?'wrong':id},
      output:{final_output:`${id}:${input.task}`},receipt:{receipt_root:root},
    };}};
  };
  const deps={
    './provider-adapters/provider-native-sdk-runtime.js':{createProviderNativeSdkRunnersV1:()=>runners},
    './provider-adapters/openai-native-agent.js':{createOpenAINativeAgentAdapterV1:native('openai')},
    './provider-adapters/anthropic-native-agent.js':{createAnthropicNativeAgentAdapterV1:native('anthropic')},
    './provider-adapters/google-adk-native-agent.js':{createGoogleAdkNativeAgentAdapterV1:native('google-cloud')},
    './provider-native-conductor.js':{createProviderNativeConductorV1:({adapters})=>({async execute(input){
      selections.push(input); await Promise.resolve();
      if(deny)return {output:null,receipt:{outcome:'DENIED'}};
      const id=input.preferred_provider_order?.[0]??'openai';
      const out=await adapters.find(a=>a.provider_id===id).execute(input.task);
      return {output:out.output,receipt:{outcome:'EXECUTED',native_receipt_root:out.native_receipt_root}};
    }})},
  };
  const exports={}; vm.runInNewContext(js,{exports,structuredClone,require:id=>{
    if(!deps[id])throw Error(`unexpected dependency ${id}`);return deps[id];
  }});
  const team=exports.createProviderNativeAgentTeamV1({});
  return {team,calls,wired,contexts,selections};
}
function task(name='inspect',provider='openai') {return {
  task:name,snapshot:{descriptors:[],observations:[{state:'OBSERVED_AVAILABLE'}]},registry:{agents:[]},
  current_generation:'10',max_observation_age_generations:'1',preferred_provider_order:[provider],
};}
test('team wires all three existing native adapters to matching runners',()=>{
  const f=fixture(); assert.deepEqual(f.wired,[['openai','openai'],['anthropic','anthropic'],['google-cloud','google-cloud']]);
  assert.deepEqual(Array.from(f.team.agent_ids),['provider-agent:openai','provider-agent:anthropic','provider-agent:google-cloud']);
  assert.deepEqual(f.calls,[]);
});
for(const id of ['openai','anthropic','google-cloud'])test(`team executes only selected native adapter ${id}`,async()=>{
  const f=fixture();const r=await f.team.execute(task('inspect',id));
  assert.equal(r.output,`${id}:inspect`);assert.equal(r.receipt.native_receipt_root,root);assert.deepEqual(f.calls,[id]);
});
test('denied conductor decision does not invoke native adapters',async()=>{
  const f=fixture({deny:true});const r=await f.team.execute(task());assert.equal(r.receipt.outcome,'DENIED');assert.deepEqual(f.calls,[]);
});
test('team requires both agent execution and model inference',async()=>{
  const f=fixture();await f.team.execute({...task(),required_capabilities:[]});
  assert.deepEqual(Array.from(f.selections[0].required_capabilities),['AGENT_EXECUTION','MODEL_INFERENCE']);
});
test('mismatched inner native selection fails without fallback',async()=>{
  const f=fixture({wrongNative:true});await assert.rejects(f.team.execute(task()),/native adapter/);assert.deepEqual(f.calls,['openai']);
});
test('team snapshots mutable task and evidence before async execution',async()=>{
  const f=fixture();const input=task();const promise=f.team.execute(input);
  input.task='changed';input.snapshot.observations[0].state='changed';input.current_generation='99';
  await promise;assert.equal(f.contexts[0].task,'inspect');assert.equal(f.contexts[0].current_generation,'10');
  assert.equal(f.contexts[0].snapshot.observations[0].state,'OBSERVED_AVAILABLE');
});
test('two callers never share captured task contexts',async()=>{
  const f=fixture();const [a,b]=await Promise.all([f.team.execute(task('one','openai')),f.team.execute(task('two','anthropic'))]);
  assert.equal(a.output,'openai:one');assert.equal(b.output,'anthropic:two');
});
