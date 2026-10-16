import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('./public-observation.js',import.meta.url),'utf8');
const good={contract_version:'1.0.0',execution_id:'status-true',timestamp:'2026-10-11T04:00:00Z',data:{version:'2.0.0',contract_version:'1.0.0',total_agents:39,available:true,chain_valid:true,audit_chain_hash:'a'.repeat(64),usage:{customer_email:'private@example.com'}}};
function make(fetchMock){let handler=null;let urls=[];const env={Response,URL,AbortController,setTimeout,clearTimeout,Date,TextDecoder,Uint8Array,fetch:async (u,o)=>{urls.push([u,o]);return fetchMock(u,o)},addEventListener:(name,cb)=>{handler=cb}};vm.runInNewContext(source,env);const handle=async(path='/platform/status',method='GET')=>{let out;await handler({request:new Request('https://example.workers.dev'+path,{method}),respondWith:p=>{out=p}});return out};return {handle,urls}}
const jsonResponse=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'content-type':'application/json'}});
const remote=()=>jsonResponse(good);
test('live GET returns only public allowlisted fields and source labels',async()=>{let r=make(remote),v=await(await r.handle()).json();assert.equal(v.data.total_agents,39);assert.equal(v.gateway.authority,'UNSIGNED_REMOTE_REPORT_NOT_INDEPENDENTLY_VERIFIED');assert.equal(v.data.usage,undefined);assert.equal(r.urls[0][0],'https://aegis-vertex.aegisomega.com/platform/status')});
test('public read-only CORS; no key or credential proxy',async()=>{let r=make(remote),res=await r.handle(),h=res.headers;assert.equal(h.get('Access-Control-Allow-Origin'),'*');assert.equal(r.urls[0][1].method,'GET');assert.ok(!('credentials'in r.urls[0][1]));assert.equal(h.get('Cache-Control'),'no-store')});
test('POST rejected and never forwarded',async()=>{let r=make(remote),res=await r.handle('/platform/status','POST');assert.equal(res.status,405);assert.equal(r.urls.length,0)});
test('arbitrary path rejected and never forwarded',async()=>{let r=make(remote),res=await r.handle('/platform/tools');assert.equal(res.status,404);assert.equal(r.urls.length,0)});
test('contract mismatch or broken shape fails closed',async()=>{let r=make(()=>jsonResponse({...good,data:{...good.data,total_agents:'39'}}));let res=await r.handle();assert.equal(res.status,502);assert.equal((await res.json()).error,'UPSTREAM_INVALID_CONTRACT')});
test('upstream HTTP failure fails closed, no synthetic available',async()=>{let r=make(()=>jsonResponse({},500));let res=await r.handle();assert.equal(res.status,503);assert.equal((await res.json()).error,'UPSTREAM_UNAVAILABLE')});
test('upstream hidden content not passed through',async()=>{let r=make(()=>jsonResponse({...good,data:{...good.data, customer_email:'private@example.com',token:'private'}}));let res=await r.handle();let body=await res.text();assert.ok(!body.includes('private@example.com'));assert.ok(!body.includes('token'))});
test('oversize body rejected',async()=>{let r=make(()=>new Response('x'.repeat(9000)));let res=await r.handle();assert.equal(res.status,502)});
test('health requires no upstream',async()=>{let r=make(remote);let res=await r.handle('/api/health');assert.equal(res.status,200);assert.equal(r.urls.length,0)});

test('streamed body exceeding the byte cap is rejected before full consumption',async()=>{
  let chunks=0, cancelled=false;
  const upstream=()=>new Response(new ReadableStream({pull(controller){chunks++; controller.enqueue(new Uint8Array(4097)); if(chunks>4)controller.close()},cancel(){cancelled=true}}),{status:200});
  const r=make(upstream),res=await r.handle();
  assert.equal(res.status,502);
  assert.equal((await res.json()).error,'UPSTREAM_TOO_LARGE');
  assert.ok(chunks<=3,'body reader must not read an unbounded stream');
  assert.equal(cancelled,true);
});
test('byte cap applies to non-ASCII UTF-8, not JavaScript string length',async()=>{
  const data={...good, padding:'🚀'.repeat(2400)}; // 9600 bytes of emoji + envelope
  const r=make(()=>jsonResponse(data)),res=await r.handle();
  assert.equal(res.status,502);
  assert.equal((await res.json()).error,'UPSTREAM_TOO_LARGE');
});
test('missing body or invalid JSON fails closed',async()=>{
  const a=make(()=>new Response(null,{status:200}));
  assert.equal((await (await a.handle()).json()).error,'UPSTREAM_EMPTY_BODY');
  const b=make(()=>new Response('not-json',{status:200}));
  assert.equal((await (await b.handle()).json()).error,'UPSTREAM_INVALID_JSON');
});