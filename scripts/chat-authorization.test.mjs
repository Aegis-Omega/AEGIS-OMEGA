import { readFileSync, existsSync } from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';
import { resolve } from 'node:path';

const root=resolve(import.meta.dirname,process.env.CHAT_FIX_TREE||'..');
const prefix='supabase/functions/';
const token='fixture.payload.signature';
const defaults={SUPABASE_URL:'https://auth.invalid',SUPABASE_SERVICE_ROLE_KEY:'SYNTHETIC',
  CHAT_ALLOWED_USER_IDS:'operator',CHAT_NEBIUS_ALLOWED_USER_IDS:'operator',
  CHAT_ENABLE_OPENAI:'true',CHAT_ENABLE_NEBIUS:'true',CHAT_ENABLE_AZURE:'true',
  OPENAI_API_KEY:'SYNTHETIC',OPENAI_MODEL:'fixture-model',
  NEBIUS_API_KEY:'SYNTHETIC',NEBIUS_MODEL:'fixture-model',DASHSCOPE_API_KEY:'SYNTHETIC',
  AZURE_OPENAI_ENDPOINT:'https://azure.invalid',AZURE_OPENAI_API_KEY:'SYNTHETIC',AZURE_OPENAI_DEPLOYMENT:'fixture',
  CHAT_UPSTREAM_TIMEOUT_MS:'10'};
async function invoke(provider,options={}){
  const events=[],upstream=[],logs=[];
  let handler;
  const env={...defaults,...options.env};
  const read=path=>readFileSync(resolve(root,prefix+path),'utf8');
  const helpers=['_shared/nebius-auth.ts','_shared/nebius-budget.ts','_shared/nebius-endpoint.ts','_shared/chat-provider-gate.ts','_shared/http.ts']
    .filter(path=>existsSync(resolve(root,prefix+path))).map(read).join('\n');
  const code=stripTypeScriptTypes((helpers+'\n'+read('chat/index.ts')).replace(/^import .*$/gm,'').replace(/^export /gm,''));
  const sandbox={Request,Response,URL,AbortController,setTimeout,clearTimeout,
    CORS:{},console:{error:(...args)=>logs.push(args)},
    Deno:{env:{get:key=>env[key]},serve:fn=>{handler=fn;}},
    createClient:()=>({
      auth:{getUser:async jwt=>{events.push('auth');assert.equal(jwt,token);
        if(options.authThrows)throw Error('AUTH UNAVAILABLE');
        return {data:{user:options.user===null?null:{id:options.user||'operator'}},error:options.authError?{message:'error'}:null};}},
      rpc:async(name,args)=>{events.push(name);
        if(name==='get_provider_runtime_candidate_v1')return {data:options.noCandidate?[]:[{provider_id:args.p_provider_id}],error:null};
        if(name==='reserve_nebius_inference_attempt_v1')return {data:options.noBudget?false:true,error:null};
        throw Error('Unexpected RPC '+name);
      },
    }),
    fetch:async(url,init)=>{events.push('upstream');upstream.push({url,init});
      if(options.waitForAbort)return new Promise((_,reject)=>init.signal?.addEventListener('abort',()=>reject(Error('ABORTED')),{once:true}));
      return new Response(options.upstreamError?'PRIVATE_UPSTREAM_TEXT':JSON.stringify({choices:[{message:{content:'fixture reply'}}]}),{status:options.upstreamError?500:200});},
  };
  new vm.Script(code).runInContext(vm.createContext(sandbox),{timeout:1000});
  const headers={'Content-Type':'application/json'};
  if(options.authorization!==null)headers.Authorization=options.authorization||'Bearer '+token;
  const req=new Request('https://handler.invalid/chat',{method:'POST',headers,body:JSON.stringify({message:'fixture message',provider,...options.body})});
  const response=await handler(req);
  return {status:response.status,body:await response.json(),events,upstream,logs};
}
for(const provider of ['dashscope','openai','azure','nebius']){
  for(const [label,opts] of [
    ['anonymous',{authorization:null}],['malformed token',{authorization:'Bearer invalid'}],
    ['missing global allowlist',{env:{CHAT_ALLOWED_USER_IDS:''}}],['wrong verified identity',{user:'other'}],
    ['auth service error',{authError:true}],['auth exception',{authThrows:true}],
  ])test(provider+': deny '+label+' before mesh and upstream',async()=>{
    const r=await invoke(provider,opts);assert.equal(r.status,401);assert.equal(r.upstream.length,0);
    assert.equal(r.events.includes('get_provider_runtime_candidate_v1'),false);
  });
  test(provider+': approved verified user retains exact provider',async()=>{
    const r=await invoke(provider);assert.equal(r.body.reply,'fixture reply');assert.equal(r.upstream.length,1);
    assert.equal(r.events[0],'auth');assert.equal(r.events.at(-1),'upstream');
    const host=new URL(r.upstream[0].url).hostname;
    assert.equal(host,{dashscope:'dashscope-intl.aliyuncs.com',openai:'api.openai.com',azure:'azure.invalid',nebius:'api.tokenfactory.nebius.com'}[provider]);
    assert.equal(r.upstream[0].init.redirect,'error');assert.ok(r.upstream[0].init.signal);
  });
  test(provider+': absent mesh candidate denies upstream',async()=>{
    const r=await invoke(provider,{noCandidate:true});assert.equal(r.body.provider_status,'not_observed_available');assert.equal(r.upstream.length,0);
  });
  test(provider+': malformed history rejected before external services',async()=>{
    const r=await invoke(provider,{body:{history:null}});assert.equal(r.status,413);assert.equal(r.events.length,0);
  });
  test(provider+': oversized message rejected before external services',async()=>{
    const r=await invoke(provider,{body:{message:'x'.repeat(4097)}});assert.equal(r.status,413);assert.equal(r.events.length,0);
  });
}
test('non-string message is rejected without invoking external services',async()=>{
  const r=await invoke('openai',{body:{message:17}});assert.equal(r.status,400);assert.equal(r.events.length,0);
});
test('Nebius additional allowlist remains mandatory',async()=>{
  const r=await invoke('nebius',{env:{CHAT_NEBIUS_ALLOWED_USER_IDS:'other'}});assert.equal(r.status,401);assert.equal(r.upstream.length,0);
});
test('Nebius exhausted reservation denies upstream',async()=>{
  const r=await invoke('nebius',{noBudget:true});assert.equal(r.body.provider_status,'budget_denied');assert.equal(r.upstream.length,0);
});
test('disabled OpenAI never falls back',async()=>{
  const r=await invoke('openai',{env:{CHAT_ENABLE_OPENAI:'false'}});assert.equal(r.body.provider_status,'disabled');assert.equal(r.events.length,0);
});
test('unknown provider never falls back',async()=>{
  const r=await invoke('unknown');assert.equal(r.status,400);assert.equal(r.events.length,0);
});
test('OpenAI missing credential denies upstream',async()=>{
  const r=await invoke('openai',{env:{OPENAI_API_KEY:''}});assert.equal(r.body.provider_status,'unconfigured');assert.equal(r.upstream.length,0);
});
test('upstream error text stays out of logs',async()=>{
  const r=await invoke('openai',{upstreamError:true});assert.equal(r.body.error,'AI unavailable');assert.equal(JSON.stringify(r.logs).includes('PRIVATE_UPSTREAM_TEXT'),false);
});
test('outbound request is aborted within configured timeout',{timeout:500},async()=>{
  const r=await invoke('openai',{waitForAbort:true});assert.equal(r.upstream.length,1);assert.equal(r.upstream[0].init.signal.aborted,true);
});
