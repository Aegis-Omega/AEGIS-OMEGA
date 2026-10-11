import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
import {webcrypto} from 'node:crypto';

const src=stripTypeScriptTypes(fs.readFileSync(new URL('../index.ts',import.meta.url),'utf8').replace(/^import .*$/gm,''),{mode:'strip'});
function setup(permission='T12345:UOPERATOR'){
 const stats={db:0,requests:[]};
 const q={ select(){return q;}, eq(){return q;}, order(){return q;}, limit(){return Promise.resolve({data:[{customer_email:'example@mock.invalid',plan:'full'}],error:null})} };
 const createClient=()=>{stats.db++;return {from:()=>q}};
 const Deno={env:{get:n=>n==='AEGIS_PURCHASE_READERS'?permission:''},serve(){}};
 const obj=new Function('Deno','fetch','crypto','createClient','CORS','console','atob','btoa',src+'\nreturn {runTool};')(Deno,()=>{throw Error('PAID_NETWORK')},webcrypto,createClient,{},console,atob,btoa);
 return {...obj,stats};
}
test('no purchase reader credential => zero database calls',async()=>{
 const s=setup('');const r=await s.runTool('query_purchases',{limit:25},'UOPERATOR','T12345');
 assert.equal(r,'TOOL_NOT_AUTHORIZED');assert.equal(s.stats.db,0);
});
test('allowed colleague without reader scope => zero database calls',async()=>{
 const s=setup();const r=await s.runTool('query_purchases',{limit:25},'UCOLLEAGUE','T12345');
 assert.equal(r,'TOOL_NOT_AUTHORIZED');assert.equal(s.stats.db,0);
});
test('identical user ID in wrong workspace => zero database calls',async()=>{
 const s=setup();const r=await s.runTool('query_purchases',{limit:25},'UOPERATOR','T99999');
 assert.equal(r,'TOOL_NOT_AUTHORIZED');assert.equal(s.stats.db,0);
});
test('exact privileged actor+team can query bounded rows',async()=>{
 const s=setup();const r=await s.runTool('query_purchases',{limit:2},'UOPERATOR','T12345');
 assert.match(r,/example@mock.invalid/);assert.equal(s.stats.db,1);
});

test('unprivileged agent receives no purchase tools in provider request',async()=>{
 const requestBodies=[];
 const Deno={env:{get:n=>n==='ANTHROPIC_API_KEY'?'fake-key':n==='AEGIS_PURCHASE_READERS'?'T12345:UOPERATOR':''},serve(){}};
 const fakeFetch=async(url,options)=>{
   assert.equal(url,'https://api.anthropic.com/v1/messages');requestBodies.push(JSON.parse(options.body));
   return Response.json({stop_reason:'end_turn',content:[{type:'text',text:'ok'}]});
 };
 const obj=new Function('Deno','fetch','crypto','createClient','CORS','console','atob','btoa',src+'\nreturn {runAgent};')(Deno,fakeFetch,webcrypto,()=>{throw Error('DATABASE')},{},console,atob,btoa);
 await obj.runAgent('summarize','none','UCOLLEAGUE','T12345');
 assert.equal(requestBodies.length,1);assert.deepEqual(requestBodies[0].tools,[]);
});
test('exact reader scope exposes bounded query tool but no sending tools',async()=>{
 const requestBodies=[];
 const Deno={env:{get:n=>n==='ANTHROPIC_API_KEY'?'fake-key':n==='AEGIS_PURCHASE_READERS'?'T12345:UOPERATOR':''},serve(){}};
 const fakeFetch=async(url,options)=>{
   assert.equal(url,'https://api.anthropic.com/v1/messages');requestBodies.push(JSON.parse(options.body));
   return Response.json({stop_reason:'end_turn',content:[{type:'text',text:'ok'}]});
 };
 const obj=new Function('Deno','fetch','crypto','createClient','CORS','console','atob','btoa',src+'\nreturn {runAgent};')(Deno,fakeFetch,webcrypto,()=>{throw Error('DATABASE')},{},console,atob,btoa);
 await obj.runAgent('summarize','none','UOPERATOR','T12345');
 assert.equal(requestBodies.length,1);
 assert.deepEqual(requestBodies[0].tools.map(x=>x.name),['query_purchases']);
});

function runModelWithPurchaseToolOutcome(toolInput, databaseOutcome) {
  let modelCalls=0, dbCalls=0
  const Deno={env:{get:n=>n==='AEGIS_PURCHASE_READERS'?'T12345:UOPERATOR':
    n==='ANTHROPIC_API_KEY'?'dummy':''},serve(){}}
  const q={select(){return q},eq(){return q},order(){return q},
    limit(){dbCalls++;return Promise.resolve(databaseOutcome)}}
  const createClient=()=>({from(t){assert.equal(t,'purchases');return q}})
  const fetch=async()=>{
    modelCalls++
    return Response.json(modelCalls===1?
      {stop_reason:'tool_use',content:[{
        type:'tool_use',name:'query_purchases',id:'tool1',input:toolInput
      }]}:
      {stop_reason:'end_turn',content:[{type:'text',text:'Tool query completed; review the records'}]})
  }
  const runAgent=new Function('Deno','fetch','crypto','createClient','CORS','console','atob','btoa',
    src+'\nreturn runAgent')(Deno,fetch,webcrypto,createClient,{},console,atob,btoa)
  return {run:()=>runAgent('How many purchases?','','UOPERATOR','T12345'),
    stats:()=>({modelCalls,dbCalls})}
}

test('DB failure cannot be promoted to verified answer',async()=>{
  const a=runModelWithPurchaseToolOutcome({limit:10},
    {data:null,error:{message:'permission denied'}})
  await assert.rejects(a.run(),/TOOL_VERIFICATION_FAILED/)
  assert.equal(a.stats().modelCalls,1)
})
test('invalid model filter cannot be promoted to verified answer',async()=>{
  const a=runModelWithPurchaseToolOutcome({filter:'*@exfil.invalid'},
    {data:[],error:null})
  await assert.rejects(a.run(),/TOOL_VERIFICATION_FAILED/)
  assert.equal(a.stats().modelCalls,1)
  assert.equal(a.stats().dbCalls,0)
})
test('successful tool read permits a response without validating its factual claims',async()=>{
  const a=runModelWithPurchaseToolOutcome({filter:'full'},
    {data:[{customer_email:'mock@example.test',plan:'full'}],error:null})
  assert.equal((await a.run()).result,'Tool query completed; review the records')
  assert.equal(a.stats().modelCalls,2)
  assert.equal(a.stats().dbCalls,1)
})
