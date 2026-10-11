import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
import {webcrypto} from 'node:crypto';

const src = stripTypeScriptTypes(fs.readFileSync(new URL('../index.ts', import.meta.url),'utf8').replace(/^import .*$/gm,''), {mode:'strip'});
function setup() {
  const calls={limits:[],eq:[],ilike:[],order:[]};
  const q={
    select(){return q}, eq(...args){calls.eq.push(args);return q},
    ilike(...args){calls.ilike.push(args);return q},
    order(...args){calls.order.push(args);return q},
    limit(v){calls.limits.push(v);return Promise.resolve({data:[],error:null})}
  };
  let handler;
  const Deno={env:{get:n=>n==='AEGIS_PURCHASE_READERS'?'T12345:UOPERATOR':''},serve:f=>handler=f};
  const client=()=>({from:()=>q});
  const factory = new Function('Deno','fetch','crypto','createClient','CORS','console','atob','btoa',src+'\n return {runTool};');
  const api=factory(Deno,()=>{throw Error('NETWORK')},webcrypto,client,{},console,atob,btoa);
  return {runTool:(name,input)=>api.runTool(name,input,'UOPERATOR','T12345'),calls};
}

test('huge purchase request is bounded to at most 25 rows',async()=>{
 const x=setup(); await x.runTool('query_purchases',{limit:1000000000});
 assert.ok(x.calls.limits[0] >= 1 && x.calls.limits[0] <= 25,JSON.stringify(x.calls.limits));
});
test('negative and nonnumeric limits cannot enter database',async()=>{
 for(const limit of [-100,Infinity,'NaN','10foobar',null]){
   const x=setup();await x.runTool('query_purchases',{limit});
   assert.ok(Number.isInteger(x.calls.limits[0])&&x.calls.limits[0]>=1&&x.calls.limits[0]<=25,`limit=${limit} used=${x.calls.limits[0]}`);
 }
});
test('email lookup uses exact equality, not contains/wildcard match',async()=>{
 const x=setup();await x.runTool('query_purchases',{filter:'a@example.com',limit:10});
 assert.deepEqual(x.calls.eq,[['customer_email','a@example.com']]);
 assert.deepEqual(x.calls.ilike,[]);
});
test('wildcard email filters are refused before hitting database',async()=>{
 const x=setup();await x.runTool('query_purchases',{filter:'%@example.com'});
 assert.equal(x.calls.limits.length,0);
});
test('unknown filter is refused rather than silently returning all purchases',async()=>{
 const x=setup();await x.runTool('query_purchases',{filter:'not-a-plan'});
 assert.equal(x.calls.limits.length,0);
});
