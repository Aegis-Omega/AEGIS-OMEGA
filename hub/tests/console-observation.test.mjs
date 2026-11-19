import {test} from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
import vm from 'node:vm'
const require=createRequire(import.meta.url)
const ts=require('typescript')
const source=readFileSync(new URL('../src/lib/platformConsole.ts',import.meta.url),'utf8').replace('import.meta.env.VITE_PLATFORM_URL','({VITE_PLATFORM_URL:undefined}).VITE_PLATFORM_URL')
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
function load(fetch){const exports={};vm.runInNewContext(js,{exports,require:()=>({useCallback(){},useEffect(){},useRef(){},useState(){}}),fetch,AbortController,setTimeout,clearTimeout,Date});return exports}
const status={version:'2.0.0',contract_version:'1.0.0',total_agents:39,chain_valid:null,available:true}
function fake(responses,paths=[]){return async (url)=>{const key=new URL(url).pathname;paths.push(key);let d=responses[key];return d===undefined?{ok:false,status:401}:{ok:true,json:async()=>d}}}
const gateway=(data)=>({data,gateway:{schema:'AEGIS_PUBLIC_OBSERVATION_GATE_V1',upstream:'https://aegis-vertex.aegisomega.com',authority:'UNSIGNED_REMOTE_REPORT_NOT_INDEPENDENTLY_VERIFIED'},timestamp:'2026-10-11T04:33:12.970Z'})
const observed={ '/api/status':gateway(status) }
test('offline returns unknown not synthetic chain, calibration, or tools',async()=>{
 const s=await load(fake({})).fetchConsoleSnapshot();assert.equal(s.source,'unavailable');assert.equal(s.status.chain_valid,null);assert.equal(s.status.audit_chain_hash,null);assert.equal(s.status.available,false);assert.equal(s.calibration,null);assert.equal(s.tools.length,0);assert.ok(s.checks.every(c=>!c.ok))
})
test('status-only public observation is retained even when protected endpoints require credentials',async()=>{
 const paths=[],s=await load(fake(observed,paths)).fetchConsoleSnapshot();assert.equal(s.source,'live');assert.equal(s.status.total_agents,39);assert.deepEqual(paths,['/api/status']);assert.equal(s.calibration,null);assert.equal(s.tools_observed,false);assert.equal(s.tools.length,0)
})
test('edge chain_valid:null is accepted but NEVER marked independently verified',async()=>{
 const s=await load(fake(observed)).fetchConsoleSnapshot();const c=s.checks.find(x=>x.label==='Audit-chain evidence');assert.equal(c.ok,false);assert.match(c.reason,/UNKNOWN/)
})
test('claimed true chain verdict is reported, not independently certified',async()=>{
 const s=await load(fake({'/api/status':gateway({...status,chain_valid:true,audit_chain_hash:'a'.repeat(64)})})).fetchConsoleSnapshot();const c=s.checks.find(x=>x.label==='Audit-chain evidence');assert.equal(c.ok,false);assert.match(c.reason,/REPORTED VALID/)
})
test('reported invalid chain is not converted into successful evidence',async()=>{
 const s=await load(fake({'/api/status':gateway({...status,chain_valid:false})})).fetchConsoleSnapshot();const c=s.checks.find(x=>x.label==='Audit-chain evidence');assert.equal(c.ok,false);assert.match(c.reason,/INVALID/)
})
test('version mismatch retained as remote observation, flagged incompatible',async()=>{
 const s=await load(fake({'/api/status':gateway({...status,contract_version:'9.0.0'})})).fetchConsoleSnapshot();assert.equal(s.source,'live');const c=s.checks.find(x=>x.label==='Contract version');assert.equal(c.ok,false);assert.match(c.reason,/9.0.0/)
})
test('HTTP unavailable is fail closed with exact public endpoint status',async()=>{
 const paths=[],s=await load(fake({},paths)).fetchConsoleSnapshot();assert.equal(s.source,'unavailable');assert.match(s.reason,/HTTP 401/);assert.deepEqual(paths,['/api/status'])
})
test('malformed remote status does not become live',async()=>{
 for(const malformed of [{...status,total_agents:-1},{...status,total_agents:1.5},{...status,available:'true'},{...status,chain_valid:'true'},{...status,audit_chain_hash:'x'.repeat(400)},null]){
  const s=await load(fake({'/api/status':gateway(malformed)})).fetchConsoleSnapshot();assert.equal(s.source,'unavailable')
 }
})
test('public status reports available=false without making the service look healthy',async()=>{
 const s=await load(fake({'/api/status':gateway({...status,available:false})})).fetchConsoleSnapshot();assert.equal(s.source,'live');assert.equal(s.status.available,false);assert.equal(s.status.chain_valid,null)
})
test('no API keys or credentials are sent to public endpoint',async()=>{
 let opts=null;await load(async(_url,o)=>{opts=o;return {ok:true,json:async()=>gateway(status)}}).fetchConsoleSnapshot();assert.equal(opts.method,'GET');assert.equal(opts.credentials,'omit');assert.equal(opts.cache,'no-store');assert.equal(opts.headers,undefined)
})

test('malformed gateway claim cannot certify public observation',async()=>{const s=await load(fake({'/api/status':{data:status,gateway:{schema:'OTHER',upstream:'https://evil.invalid',authority:'SIGNED'}}})).fetchConsoleSnapshot();assert.equal(s.source,'unavailable');assert.equal(s.status.chain_valid,null)})
test('gateway supplies separately labeled source time without treating it as attestation',async()=>{const s=await load(fake(observed)).fetchConsoleSnapshot();assert.equal(s.upstream_at,'2026-10-11T04:33:12.970Z');assert.match(s.reason,/not signed attestation/)})