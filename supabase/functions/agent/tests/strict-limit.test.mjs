import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
import {webcrypto} from 'node:crypto';
const source=stripTypeScriptTypes(readFileSync(new URL('../index.ts',import.meta.url),'utf8').replace(/^import .*$/gm,''),{mode:'strip'});
function instance(){
 let db=0;const calls=[];
 const q={select(){return q},eq(){return q},order(){return q},limit(n){db++;calls.push(n);return Promise.resolve({data:[],error:null})}};
 const get=n=>n==='AEGIS_PURCHASE_READERS'?'T12345:UOPERATOR':'';
 const result=new Function('Deno','fetch','crypto','createClient','CORS','console','atob','btoa',source+'\nreturn {runTool}')( {env:{get},serve(){}},()=>{throw Error('PAID_NETWORK')},webcrypto,()=>({from:()=>q}),{},console,atob,btoa);
 return {runTool:(limit)=>result.runTool('query_purchases',{limit},'UOPERATOR','T12345'),getDb:()=>db,calls};
}
test('invalid limits fail closed before database read',async()=>{
 for(const limit of [-4,0,2.5,NaN,Infinity,'25',null,{},Number.MAX_SAFE_INTEGER+1]){
  const t=instance();const result=await t.runTool(limit);
  assert.equal(t.getDb(),0,`invalid limit=${String(limit)} launched ${t.getDb()} DB calls, returned ${result}`);
  assert.equal(result,'INVALID_LIMIT');
 }
});
test('valid bounds permit one bounded read',async()=>{
 for(const limit of [1,10,25,1000000]){const t=instance();await t.runTool(limit);assert.equal(t.getDb(),1);assert.deepEqual(t.calls,[Math.min(limit,25)])}
});

test('malformed model-proposed limit stops before the DB and second inference',async()=>{
 let paid=0,db=0;
 const q={select(){return q},eq(){return q},order(){return q},limit(){db++;return Promise.resolve({data:[],error:null})}};
 const get=n=>n==='AEGIS_PURCHASE_READERS'?'T12345:UOPERATOR':'';
 const runAgent=new Function('Deno','fetch','crypto','createClient','CORS','console','atob','btoa',source+'\nreturn runAgent')(
  {env:{get},serve(){}},async()=>{paid++;return Response.json({stop_reason:'tool_use',content:[{type:'tool_use',name:'query_purchases',id:'tool1',input:{limit:-9}}]})},
  webcrypto,()=>({from:()=>q}),{},console,atob,btoa);
 await assert.rejects(()=>runAgent('audit purchases','','UOPERATOR','T12345'),/TOOL_VERIFICATION_FAILED/);
 assert.equal(paid,1);assert.equal(db,0);
});
