// Offline contract tests. SDK doubles never contact provider APIs.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const ts = require('typescript');
const sourceUrl = new URL('../../src/sovereignty/provider-adapters/provider-native-sdk-runtime.ts', import.meta.url);
const source = readFileSync(sourceUrl, 'utf8');
const js = ts.transpileModule(source, {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022}}).outputText;
const {createProviderNativeSdkRunnersV1: create} = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);

const models = {openai: 'fixture-openai', anthropic: 'fixture-anthropic', google_cloud: 'fixture-google'};
const input = {
  openai: {agent_name: 'AEGIS OpenAI Provider Agent', instructions: 'Evidence only.', task: 'inspect'},
  anthropic: {system_prompt: 'Evidence only.', allowed_tools: [], task: 'inspect'},
  google_cloud: {agent_name: 'aegis_google_provider_agent', instruction: 'Evidence only.', tools: [], task: 'inspect'},
};
function fixtures(overrides = {}) {
  const calls = []; const loads = []; const auth = []; const configs = {};
  const openai = {
    Agent: class { constructor(config) { configs.openaiAgent = config; } },
    Runner: class {
      constructor(config) { configs.openaiRunner = config; }
      async run(agent, task, options) { calls.push('openai'); configs.openaiRun = {task, options}; return overrides.openai ?? {finalOutput: 'openai evidence', lastResponseId: 'fixture-response'}; }
    },
  };
  const anthropic = {query(args) {
    calls.push('anthropic'); configs.anthropic = args;
    return (async function* () { for (const msg of overrides.anthropic ?? [{type: 'result', subtype: 'success', is_error: false, result: 'claude evidence', session_id: 'fixture-session'}]) yield msg; })();
  }};
  const google = {
    LlmAgent: class { constructor(config) { configs.googleAgent = config; } },
    InMemoryRunner: class {
      constructor(config) { configs.googleRunner = config; this.sessionService = {createSession: async args => {configs.googleSession = args; return {id: 'fixture-google-session'};}}; }
      async *runAsync(args) { calls.push('google-cloud'); configs.googleRun = args; for (const event of overrides.google ?? [{author:'aegis_google_provider_agent', final: true, content:{parts:[{text:'google evidence'}]}}]) yield event; }
    },
    isFinalResponse(event) { return event.final === true; },
  };
  const modules = {'@openai/agents': openai, '@anthropic-ai/claude-agent-sdk': anthropic, '@google/adk': google};
  const opts = {models: {...models}, authorize: async request => {auth.push(request); return true;}, loadSdk: async name => {loads.push(name); return modules[name];}};
  return {calls, loads, auth, configs, opts, modules};
}

test('constructing three runners performs zero SDK imports and zero API calls', () => {
  const f = fixtures(); const runners = create(f.opts);
  assert.deepEqual(Object.keys(runners).sort(), ['anthropic', 'google_cloud', 'openai']);
  assert.deepEqual(f.loads, []); assert.deepEqual(f.calls, []);
});
for (const provider of Object.keys(models)) {
  test(`${provider}: operator denial precedes SDK import`, async () => {
    const f = fixtures(); const r = create({...f.opts, authorize: async () => false});
    await assert.rejects(r[provider].run(input[provider]), /INVOCATION_NOT_AUTHORIZED/);
    assert.deepEqual(f.loads, []); assert.deepEqual(f.calls, []);
  });
  test(`${provider}: blank task is rejected before authorization`, async () => {
    const f = fixtures(); const r = create(f.opts);
    await assert.rejects(r[provider].run({...input[provider], task:'   '}), /task/);
    assert.deepEqual(f.auth, []); assert.deepEqual(f.loads, []);
  });
  test(`${provider}: oversized task is rejected before SDK import`, async () => {
    const f = fixtures(); const r = create({...f.opts, maxTaskChars: 5});
    await assert.rejects(r[provider].run(input[provider]), /task/);
    assert.deepEqual(f.loads, []);
  });
}

test('OpenAI constructs Agent and Runner with tools/handoffs/tracing disabled', async () => {
  const f = fixtures(); const out = await create({...f.opts, maxTurns:2, maxOutputTokens:256}).openai.run(input.openai);
  assert.equal(out.run_id, 'fixture-response'); assert.equal(out.final_output, 'openai evidence');
  assert.deepEqual(f.configs.openaiAgent.tools, []); assert.deepEqual(f.configs.openaiAgent.handoffs, []);
  assert.deepEqual(f.configs.openaiAgent.mcpServers, []);
  assert.equal(f.configs.openaiAgent.modelSettings.store, false);
  assert.equal(f.configs.openaiAgent.modelSettings.maxTokens, 256);
  assert.equal(f.configs.openaiRunner.tracingDisabled, true);
  assert.equal(f.configs.openaiRun.options.maxTurns, 2);
  assert.deepEqual(f.calls, ['openai']);
});
for (const result of [{finalOutput:'ok'}, {lastResponseId:'id'}, {lastResponseId:'id',finalOutput:{claim:'ok'}}, {lastResponseId:'',finalOutput:'ok'}]) {
  test(`OpenAI rejects incomplete/non-text native output ${JSON.stringify(result)}`, async () => {
    const f = fixtures({openai: result}); await assert.rejects(create(f.opts).openai.run(input.openai));
  });
}
test('Claude query disables tool availability, ambient MCP/settings and persistence', async () => {
  const f=fixtures(); const out=await create(f.opts).anthropic.run(input.anthropic);
  assert.equal(out.session_id, 'fixture-session'); assert.equal(out.final_output, 'claude evidence');
  const o=f.configs.anthropic.options;
  for(const k of ['tools','allowedTools','settingSources','plugins']) assert.deepEqual(o[k], []);
  assert.deepEqual(o.mcpServers, {}); assert.deepEqual(o.agents, {});
  assert.equal(o.strictMcpConfig,true); assert.equal(o.persistSession,false);
  assert.equal(o.permissionMode,'dontAsk'); assert.equal(o.allowDangerouslySkipPermissions,false);
  assert.equal((await o.canUseTool('Bash',{})).behavior,'deny');
  assert.deepEqual(f.calls,['anthropic']);
});
for(const messages of [[], [{type:'result',subtype:'error_max_turns',is_error:true,result:'not success',session_id:'s'}], [{type:'result',subtype:'success',is_error:false,result:'ok'}], [{type:'assistant',message:{content:[{text:'not terminal'}]}}]]) {
  test(`Claude rejects missing/error terminal result ${JSON.stringify(messages)}`, async () => {
    const f=fixtures({anthropic:messages}); await assert.rejects(create(f.opts).anthropic.run(input.anthropic));
  });
}
test('Claude rejects nonempty tools even when supplied by an untyped caller', async () => {
  const f=fixtures(); await assert.rejects(create(f.opts).anthropic.run({...input.anthropic,allowed_tools:['Bash']}), /tools/); assert.deepEqual(f.loads,[]);
});
test('Claude rejects a second terminal result',async()=>{
  const msg={type:'result',subtype:'success',is_error:false,result:'ok',session_id:'s'};
  const f=fixtures({anthropic:[msg,msg]}); await assert.rejects(create(f.opts).anthropic.run(input.anthropic),/terminal/);
});
test('Google creates a native LlmAgent and isolated in-memory session', async () => {
  const f=fixtures(); const out=await create({...f.opts,maxTurns:2}).google_cloud.run(input.google_cloud);
  assert.equal(out.session_id,'fixture-google-session'); assert.equal(out.final_output,'google evidence');
  assert.deepEqual(f.configs.googleAgent.tools,[]); assert.deepEqual(f.configs.googleAgent.subAgents,[]);
  assert.equal(f.configs.googleRun.runConfig.maxLlmCalls,2);
  assert.equal(f.configs.googleRun.runConfig.saveInputBlobsAsArtifacts,false);
  assert.deepEqual(f.configs.googleRun.newMessage,{role:'user',parts:[{text:'inspect'}]});
  assert.deepEqual(f.calls,['google-cloud']);
});
test('Google excludes thought parts from normalized final output', async () => {
  const f=fixtures({google:[{author:'aegis_google_provider_agent',final:true,content:{parts:[{text:'private',thought:true},{text:'public'}]}}]});
  assert.equal((await create(f.opts).google_cloud.run(input.google_cloud)).final_output,'public');
});
for(const events of [[], [{final:true,errorCode:'MODEL_FAILURE'}], [{final:true,author:'other',content:{parts:[{text:'x'}]}}], [{final:true,author:'aegis_google_provider_agent',content:{parts:[{functionCall:{name:'write'}}]}}], [{final:true,author:'aegis_google_provider_agent',content:{parts:[{text:'thought only',thought:true}]}}]]) {
  test(`Google rejects invalid/nonterminal event ${JSON.stringify(events)}`,async()=>{const f=fixtures({google:events}); await assert.rejects(create(f.opts).google_cloud.run(input.google_cloud));});
}
test('Google rejects nonempty tools before authorization',async()=>{
  const f=fixtures(); await assert.rejects(create(f.opts).google_cloud.run({...input.google_cloud,tools:['write']}),/tools/); assert.deepEqual(f.auth,[]);
});
test('stream event budget terminates an unbounded native stream',async()=>{
  const f=fixtures({anthropic:Array.from({length:4},()=>({type:'system'}))});
  await assert.rejects(create({...f.opts,maxEvents:3}).anthropic.run(input.anthropic),/event budget/);
});
test('models and limits are snapshotted against caller mutation',async()=>{
  const f=fixtures(); const r=create(f.opts); f.opts.models.openai='changed';
  await r.openai.run(input.openai); assert.equal(f.configs.openaiAgent.model,models.openai);
});
test('truthy non-boolean authority does not grant invocation',async()=>{
  const f=fixtures(); const r=create({...f.opts,authorize:async()=> 'yes'});
  await assert.rejects(r.openai.run(input.openai),/INVOCATION_NOT_AUTHORIZED/); assert.deepEqual(f.loads,[]);
});
for(const bad of [{maxTurns:0},{maxTurns:Infinity},{maxOutputTokens:0},{maxEvents:0},{maxTaskChars:-1},{models:{...models,openai:''}},{authorize:undefined}]) {
  test(`invalid runtime config fails before construction ${JSON.stringify(bad)}`,()=>{const f=fixtures(); assert.throws(()=>create({...f.opts,...bad})); assert.deepEqual(f.loads,[]);});
}
test('SDK load failure is not converted into an execution receipt',async()=>{
  const f=fixtures(); const r=create({...f.opts,loadSdk:async()=>{throw Error('SDK_UNAVAILABLE');}});
  await assert.rejects(r.openai.run(input.openai),/SDK_UNAVAILABLE/); assert.deepEqual(f.calls,[]);
});
